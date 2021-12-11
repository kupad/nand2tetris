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


class Parser:
    commentpattern = re.compile(r'//.*')

    def __init__(self, filename):
        self.fd = open(filename)  # the file we're assembling
        self.nextline = self.fd.readline()  # next line to be processed
        self.instr = None  # The current instruction
        self.instrno = -1   # The current instruction num. starts at 0

    def reset(self):
        self.fd.seek(0)
        self.nextline = self.fd.readline()
        self.instr = None
        self.instrno = -1

    def has_next(self):
        """are there any more lines to process?"""
        return self.nextline != ""

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
        eqsplit = self.instr.split('=')
        desttok = eqsplit[0] if len(eqsplit) > 1 else EMPTYTOK

        # split the rest on ';'
        # comp is always the leftmost.
        # we have a jmp if splitting on ';' yielded a left and right
        scsplit = eqsplit[-1].split(';')
        comptok = scsplit[0]
        jmptok = scsplit[-1] if len(scsplit) > 1 else EMPTYTOK
        return desttok, comptok, jmptok

    def advance(self):
        """advance to the next instruction"""
        if not self.has_next():
            return self.instr

        curr = self.nextline
        self.nextline = self.fd.readline()

        # strip comments and whitespace
        curr = self.commentpattern.sub('', curr).strip()
        if curr != "":
            self.instr = curr
            if self.instr_type() is not InstrType.L:
                self.instrno += 1
            return self.instr
        else:
            return self.advance()

    def instr_type(self):
        """
        Is this an A, C, or L instruction?

        A: starts with @
        L: labels, (label)
        C: everything else: {dest}=comp{;jmp}
        """
        if self.instr.startswith('@'):
            return InstrType.A
        elif self.instr.startswith('('):
            return InstrType.L
        else:
            return InstrType.C

    def symbol(self):
        """
        if A @xxx return xxx
        if L (xxx) return xxx
        """
        itype = self.instr_type()
        if itype is InstrType.A:
            return self.instr[1:]
        elif itype is InstrType.L:
            return self.instr[1:-1]
        else:
            msg = f'cannot get symbol for: {self.instr}: not A or L type'
            raise ParserError(msg)

    def close(self):
        self.fd.close()


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
    infilename = sys.argv[1]
    outfilename = sys.argv[2]

    p = Parser(infilename)

    # first pass: put labels in symbol table
    while p.has_next():
        p.advance()
        if p.instr_type() is InstrType.L:
            symbols[p.symbol()] = p.instrno + 1

    p.reset()

    # second pass: translate to binary
    with open(outfilename, 'w') as outfile:
        while p.has_next():
            p.advance()
            itype = p.instr_type()
            if itype is InstrType.C:
                desttok, comptok, jmptok = p.tokenize()
                binout = cinstr(desttok, comptok, jmptok)
            elif itype is InstrType.A:
                binout = ainstr(p.symbol())
            else:
                continue  # skip labels
            # print(binout, '<->', p.instr)
            print(binout, file=outfile)

    p.close()
