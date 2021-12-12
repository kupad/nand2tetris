#!/usr/bin/python3


import sys
import re
from collections import defaultdict
from enum import Enum, auto


class InstrType(Enum):
    A = auto()
    C = auto()
    L = auto()  # pseudo-instruction


# represent no token
# which is legal for dest and jmp
EMPTYTOK = ''


class AssemblyError(Exception):
    """
    Represents an error in the assembly
    """


class Instruction():
    def __init__(self, instrtxt, instrtype, instrno):
        self.txt = instrtxt
        self.type = instrtype
        self.instrno = instrno

    def is_ainstr(self):
        return self.type is InstrType.A

    def is_cinstr(self):
        return self.type is InstrType.C

    def is_linstr(self):
        return self.type is InstrType.L

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
            msg = f'cannot get symbol for: {self.txt}: not A or L type'
            raise AssemblyError(msg)

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

    def __repr__(self):
        return self.txt


class Parser:
    re_comment = re.compile(r'//.*')

    def __init__(self, asmfname):
        self.asmfname = asmfname  # the file we're assembling

    def parse(self):
        instrno = -1   # The current instruction num. starts at 0
        with open(self.asmfname) as asmfile:
            line = asmfile.readline()
            while line != "":
                # strip comments and whitespace
                instrtxt = self.re_comment.sub('', line).strip()
                if instrtxt != "":
                    instrtype = self._calc_type(instrtxt)
                    if instrtype is not InstrType.L:
                        instrno += 1
                    instr = Instruction(instrtxt, instrtype, instrno)
                    yield instr
                line = asmfile.readline()

    def _calc_type(self, instrtxt):
        """
        Is this an A, C, or L instruction?

        A: starts with @
        L: labels, (label)
        C: everything else: {dest}=comp{;jmp}
        """
        if instrtxt.startswith('@'):
            return InstrType.A
        elif instrtxt.startswith('('):
            return InstrType.L
        else:
            return InstrType.C


def create_symbtbl():
    """
    Create the symbol table.

    Symbol Table is a dictionary of symbol -> memory address.
    When looking up a unknown symbol, the next available memory
    address will be the value
    """
    # next available memory address for symbol table
    # starts at 16 (R0-R15 defined)
    nextaddr = 16

    def getnextaddr():
        """
        Returns next avail memory address and increments it.
        """
        nonlocal nextaddr
        addr = nextaddr
        nextaddr += 1
        return addr

    return defaultdict(getnextaddr, {
        'R0': 0, 'R1': 1, 'R2': 2, 'R3': 3,
        'R4': 4, 'R5': 5, 'R6': 6, 'R7': 7,
        'R8': 8, 'R9': 9, 'R10': 10, 'R11': 11,
        'R12': 12, 'R13': 13, 'R14': 14, 'R15': 15,
        'SP': 0, 'LCL': 1, 'ARG': 2, 'THIS': 3, 'THAT': 4,
        'SCREEN': 16384, 'KBD': 24576,
    })


# Symbol Table
symbtbl = create_symbtbl()


# maps a computation (ie D+1,D&M) -> binary
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

# maps a jmp (ie JEQ, JMP) -> binary
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


def cinstr2bin(instr):
    """
    Translate a C instr to binary.

    111|comp|dest|jmp
    """
    desttok, comptok, jmptok = instr.tokenize()
    return ('111' +
            COMPMAP[comptok] +
            dest2bits(desttok) +
            JMPMAP[jmptok])


def ainstr2bin(instr):
    """
    Translate an A instr translate to binary

    given @xxx, op is xxx

    if xxx is a number: put into the A reg
    else find address in symbol table
    return: 0{01}*15
    """
    symbol = instr.symbol()
    # try to get the symb as a number
    try:
        num = int(symbol)
        isnum = True
    except ValueError:
        num = None
        isnum = False

    # if it's a number, that's what we load into A
    # else, we get the val from the symbol table
    val = num if isnum else symbtbl[symbol]

    return '0' + format(val, '015b')


def instr2bin(instr):
    """
    Translates an instruction into binary.
    """
    if instr.is_ainstr():
        return ainstr2bin(instr)
    elif instr.is_cinstr():
        return cinstr2bin(instr)
    else:
        raise Exception(
                f"pseudo-instr cannot be translated to bin {instr}")


if __name__ == '__main__':
    asmfname = sys.argv[1]   # input: asm filename
    hackfname = sys.argv[2]  # output: hack filename

    p = Parser(asmfname)

    # first pass: put labels in symbol table
    labels = (instr for instr in p.parse() if instr.is_linstr())
    for label in labels:
        symbtbl[label.symbol()] = label.instrno + 1

    # second pass: translate to binary
    binary = ((instr, instr2bin(instr)) for instr in p.parse()
              if not instr.is_linstr())

    with open(hackfname, 'w') as hackfile:
        for instr, binout in binary:
            # print(instr.instrno, binout, '<->', instr)
            print(binout, file=hackfile)
