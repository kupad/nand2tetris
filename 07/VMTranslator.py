#!/usr/bin/python3
"""
Nand2Tetris VM Translator. Week 7 project.

input: Jack VM code
output: hack assembly

USAGE:
./

Author: Phil Dreizen
"""
import sys
import re
from collections import defaultdict
from enum import Enum, auto


class CmdType(Enum):
    ARITHMETIC = auto()
    PUSH = auto()
    POP = auto()


class VMError(Exception):
    """
    Represents an error in the VM code.
    """
    def __init__(self, msg, lineno):
        super().__init__(msg)
        self.lineno = lineno

    def __str__(self):
        return f'Error: line {self.lineno}: {super().__str__()}'


class Command():
    def __init__(self, cmdtxt, cmdtype, cmdno, lineno):
        self.txt = cmdtxt
        self.type = cmdtype
        self.cmdno = cmdno
        self.lineno = lineno

    def is_arithmetic(self):
        return self.type is CmdType.ARITHMETIC

    def is_push(self):
        return self.type is CmdType.PUSH

    def is_pop(self):
        return self.type is CmdType.POP

    def __repr__(self):
        return f'{self.txt}|{self.type}'


RE_COMMENT = re.compile(r'//.*')


def parse(vmfname):
    """
    Parse the vm file. Generates a single command at a time.

    Advance through the file one line at a time ignoring comments.
    Uses a generator to yield a Command object when a command
    is found
    """
    cmdno = -1   # The current cmd num. starts at 0
    with open(vmfname) as vmfile:
        for lineno, line in enumerate(vmfile, 1):
            # strip comments and whitespace
            cmdtxt = RE_COMMENT.sub('', line).strip()
            if cmdtxt == "":
                continue

            # Determine what kind of instruction this is
            if cmdtxt.startswith('push'):
                cmdtype = CmdType.PUSH
            elif cmdtxt.startswith('pop'):
                cmdtype = CmdType.POP
            else:
                cmdtype = CmdType.ARITHMETIC

            # create cmd and return
            cmd = Command(cmdtxt, cmdtype, cmdno, lineno)
            yield cmd


if __name__ == '__main__':
    if len(sys.argv) < 2:
        sys.exit("USAGE: VMTranslator.py input.vm")

    vmfname = sys.argv[1]   # input: vmfilename

    for cmd in parse(vmfname):
        print(cmd)

