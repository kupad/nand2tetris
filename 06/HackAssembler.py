#!/usr/bin/python3


import sys
import re
from collections import UserDict
from enum import Enum, auto


class InstrType(Enum):
    A = auto()
    C = auto()
    L = auto()  # pseudo-instruction


# represent no token
# which is legal for dest and jmp
EMPTYTOK = ''


class ParserError(Exception):
    pass


class Instruction():
    def __init__(self, instrtxt, instrno):
        self.txt = instrtxt
        self.instrno = instrno

        # Is this an A, C, or L instruction?
        #
        # A: starts with @
        # L: labels, (label)
        # C: everything else: {dest}=comp{;jmp}
        if self.txt.startswith('@'):
            self.type = InstrType.A
        elif self.txt.startswith('('):
            self.type = InstrType.L
        else:
            self.type = InstrType.C

    def is_ainstr(self):
        return self.type is InstrType.A

    def is_cinstr(self):
        return self.type is InstrType.C

    def is_linstr(self):
        return self.type is InstrType.L

    def __repr__(self):
        return self.txt

    def symbol(self):
        """
        if A @xxx return xxx
        if L (xxx) return xxx
        """
        if self.is_ainstr():
            return self.txt[1:]
        elif self.is_linstr():
            return self.txt[1:-1]
        else:
            msg = f'cannot get symbol for: {self.instr}: not A or L type'
            raise ParserError(msg)

    def tokenize(self):
        """
        Takes the current C-instruction and breaks it down into
        the 3 tokens: dest, comp and jmp
        dest and jmp can be empty, only comp is mandatory

        Anatomy HACK C assembly instr:
            dest=comp;JMP

            dest: D,M,A,DM,DA...
            comp: D+1, D&M, ...
            jmp: JGE/JMP/JEQ/...

        returns: (desttok, comptok, jmptok)
        """
        # split instruction on '='. We have a lhs if len > 1
        eqsplit = self.txt.split('=')
        desttok = eqsplit[0] if len(eqsplit) > 1 else EMPTYTOK

        # split the rest on ';'
        # comp is always the leftmost.
        # we have a jmp if splitting on ';' yielded a left and right
        scsplit = eqsplit[-1].split(';')
        comptok = scsplit[0]
        jmptok = scsplit[-1] if len(scsplit) > 1 else EMPTYTOK
        return desttok, comptok, jmptok


class Parser:
    re_comment = re.compile(r'//.*')

    def __init__(self, asmfname):
        self.asmfname = asmfname  # the file we're assembling

    def __iter__(self):
        instrno = 0   # The current instruction num. starts at 0
        with open(self.asmfname) as asmfile:
            line = asmfile.readline()
            while line != "":
                # strip comments and whitespace
                instrtxt = self.re_comment.sub('', line).strip()
                if instrtxt != "":
                    instr = Instruction(instrtxt, instrno)
                    if not instr.is_linstr():
                        instrno += 1
                    yield instr
                line = asmfile.readline()


class SymbolTable(UserDict):
    """
    The symbol table is a dictionary.

    When encountering a symbol for the first time
    the symbol is entered in the table with nextmem as
    the value. Then nextmem is incremented.
    """
    def __init__(self):
        super().__init__({
            'R0': 0, 'R1': 1, 'R2': 2, 'R3': 3,
            'R4': 4, 'R5': 5, 'R6': 6, 'R7': 7,
            'R8': 8, 'R9': 9, 'R10': 10, 'R11': 11,
            'R12': 12, 'R13': 13, 'R14': 14, 'R15': 15,
            'SP': 0, 'LCL': 1, 'ARG': 2, 'THIS': 3, 'THAT': 4,
            'SCREEN': 16384, 'KBD': 24576,
        })
        # first available memory address is 16 (R0-R15 defined)
        self.nextmem = 16

    def __getitem__(self, key):
        if key not in self.data:
            self.data[key] = self.nextmem
            self.nextmem += 1
        return self.data[key]


class CodeError(Exception):
    pass


def dest2bits(desttok):
    """
    Translates a destination token to binary

    dest contains 3 bits. 0 or indicates the register
    is being written to.

    000
    ADM

    ie: DM -> 011
    """
    bits = ''
    bits += '1' if 'A' in desttok else '0'
    bits += '1' if 'D' in desttok else '0'
    bits += '1' if 'M' in desttok else '0'
    return bits


COMPMAP = {
    "0":   "0101010",
    "1":   "0111111",
    "-1":  "0111010",
    "D":   "0001100",
    "A":   "0110000", "M": "1110000",
    "!D":  "0001101",
    "!A":  "0110001", "!M": "1110001",
    "-D":  "0001111",
    "-A":  "0110011", "-M": "1110011",
    "D+1": "0011111",
    "A+1": "0110111", "M+1": "1110111",
    "D-1": "0001110",
    "A-1": "0110010", "M-1": "1110010",
    "D+A": "0000010", "D+M": "1000010",
    "D-A": "0010011", "D-M": "1010011",
    "A-D": "0000111", "M-D": "1000111",
    "D&A": "0000000", "D&M": "1000000",
    "D|A": "0010101", "D|M": "1010101",
}

JMPMAP = {
    EMPTYTOK: '000',
    'JGT': '001',
    'JEQ': '010',
    'JGE': '011',
    'JLT': '100',
    'JNE': '101',
    'JLE': '110',
    'JMP': '111',
}


# The global symbol table
symbols = SymbolTable()


def cinstr(desttok, comptok, jmptok):
    """
    Given the tokens of a C instr, translate to binary

    111|comp|dest|jmp
    """
    return '111' + COMPMAP[comptok] + dest2bits(desttok) + JMPMAP[jmptok]


def ainstr(symb):
    """
    Given the symbol of an A token, translate to binary

    given @xxx, op is xxx

    if xxx is a number: put into the A reg
    else find address in symbol table
    return: 0{01}*15
    """
    # try to get the symb as a number
    try:
        asnum = int(symb)
    except ValueError:
        asnum = None

    # if it's a number, that's what we load into A
    # else, we get the val from the symbol table
    val = asnum if asnum is not None else symbols[symb]

    return '0' + format(val, '015b')


if __name__ == '__main__':
    asmfname = sys.argv[1]   # input: asm filename
    hackfname = sys.argv[2]  # output: hack filename

    p = Parser(asmfname)

    # first pass: put labels in symbol table
    labels = filter(lambda instr: instr.is_linstr(), p)
    for instr in labels:
        symbols[instr.symbol()] = instr.instrno

    # second pass: translate to binary
    with open(hackfname, 'w') as hackfile:
        for instr in p:
            if instr.is_cinstr():
                desttok, comptok, jmptok = instr.tokenize()
                binout = cinstr(desttok, comptok, jmptok)
            elif instr.is_ainstr():
                binout = ainstr(instr.symbol())
            else:
                continue  # skip labels
            # print(instr.instrno, binout, '<->', instr)
            print(binout, file=hackfile)
