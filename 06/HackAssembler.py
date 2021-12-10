#!/usr/bin/python3


import sys
import re
from collections import defaultdict
from enum import Enum, auto

# anatomy HACK C assembly instr:
# dest=comp;JMP
#
# dest: D,M,A,DM,DA
# comp: D+1, D&M
# JGE/JMP/JEQ
#
# 00000000


class InstrType(Enum):
    A = auto()
    C = auto()
    L = auto()  # pseudo-instruction


class ParserError(Exception):
    pass


class Parser:
    def __init__(self, filename):
        self.fd = open(filename)  # the file we're assembling
        self.nextline = self.fd.readline()  # next line to be processed
        self.instr = None  # The current instruction
        self.desttok = self.comptok = self.jmptok = None  # tokens:
        # self.instrno = 0   # The current instruction #

    def has_next(self):
        """are there any more lines to process?"""

        return self.nextline != ""

    def _tokenize(self):
        # split instruction on '='. We have a lhs if len > 1
        eqsplit = self.instr.split('=')
        self.desttok = eqsplit[0] if len(eqsplit) > 1 else ''

        # split the rest on ';'
        # comp is always the leftmost.
        # we have a jmp if splitting on ';' yielded a left and right
        rest = eqsplit[-1]
        scsplit = rest.split(';')
        self.comptok = scsplit[0]
        self.jmptok = scsplit[-1] if len(scsplit) > 1 else ''

    def advance(self):
        """advance to the next instruction"""
        if not self.has_next():
            return self.instr

        curr = self.nextline
        self.nextline = self.fd.readline()

        curr = re.sub(r'//.*', '', curr.strip())  # strip newline and comments
        if curr != "":
            self.instr = curr
            if self.instr_type() is InstrType.C:
                self._tokenize()
            return self.instr
        else:
            return self.advance()

    def instr_type(self):
        """is this an A, C, or L instruction

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

    destmap = defaultdict(lambda: '000', {k: v for k, v in [
        ('M', '001'),
        ('D', '010'),
        ('DM', '011'),
        ('A', '100'),
        ('AM', '101'),
        ('AD', '110'),
        ('ADM', '111'),
    ]})

    def dest(self):
        if not self.instr_type() is InstrType.C:
            msg = f'cannot get dest for: {self.instr}: not C type'
            raise ParserError(msg)
        return self.destmap[self.desttok]

    compmap = {
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

    def comp(self):
        if not self.instr_type() is InstrType.C:
            msg = f'cannot get dest for: {self.instr}: not C type'
            raise ParserError(msg)
        return self.compmap[self.comptok]

    jmpmap = {
        '':    '000',
        'JGT': '001',
        'JEQ': '010',
        'JGE': '011',
        'JLT': '100',
        'JNE': '101',
        'JLE': '110',
        'JMP': '111',
    }

    def jump(self):
        if not self.instr_type() is InstrType.C:
            msg = f'cannot get dest for: {self.instr}: not C type'
            raise ParserError(msg)
        return self.jmpmap[self.jmptok]

    def close(self):
        self.fd.close()


if __name__ == '__main__':
    parser = Parser(sys.argv[1])

    while parser.has_next():
        instr = parser.advance()
        if parser.instr_type() is InstrType.C:
            parser.dest()
            parser.comp()
            parser.jump()
        print(instr)

    parser.close()
