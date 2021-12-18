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
import os
import re
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
    def __init__(self, cmdtxt, cmdtype, arg1, arg2, cmdno, lineno):
        self.txt = cmdtxt
        self.type = cmdtype
        self.arg1 = arg1
        self.arg2 = arg2
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

            tokens = cmdtxt.split(" ")
            cmdtypetxt = tokens[0]
            arg1 = None
            arg2 = None

            # Determine what kind of instruction this is
            if cmdtypetxt == 'push':
                cmdtype = CmdType.PUSH
                arg1 = tokens[1]
                arg2 = tokens[2]
            elif cmdtypetxt == 'pop':
                cmdtype = CmdType.POP
                arg1 = tokens[1]
                arg2 = tokens[2]
            else:
                cmdtype = CmdType.ARITHMETIC

            # create cmd and return
            cmd = Command(cmdtxt, cmdtype, arg1, arg2, cmdno, lineno)
            yield cmd


TMP1 = 'R5'


def write_asm_push():
    """push the value in the source reg onto the stack"""
    asm = ''
    asm += '@SP\n'
    asm += 'A=M\n'
    asm += 'M=D\n'
    asm += '@SP\n'
    asm += 'M=M+1\n'
    return asm


def write_asm_pop(dest='D'):
    """pop the value off stack into dest reg"""
    asm = ''
    asm += '@SP\n'
    asm += 'M=M-1\n'
    asm += 'A=M\n'
    asm += dest+'=M\n'
    return asm


def write_stack(cmd):
    segment = cmd.arg1
    value = cmd.arg2
    asm = ''

    # gen comment
    asm += '//'
    asm += 'push ' if cmd.is_push() else 'pop '
    asm += segment+' '+value+'\n'

    # assuming segment is constant...
    asm += '@'+value+'\n'
    asm += 'D=A\n'

    if cmd.is_push():
        asm += write_asm_push()
    else:
        asm += write_asm_pop()

    return asm


def write_arithmetic(cmd):
    op = cmd.txt
    asm = ''
    if op == 'add':
        asm += '//add\n'
        # pop op2
        asm += '//D <- pop op2\n'
        asm += '@SP\n'
        asm += 'M=M-1\n'
        asm += 'A=M\n'
        asm += 'D=M\n'  # op2

        # load op2 into TMP space
        asm += '//TMP1 <- op2 \n'
        asm += '@'+TMP1+'\n'
        asm += 'M=D\n'

        # pop op1
        asm += '//D <- pop op1 \n'
        asm += '@SP\n'
        asm += 'M=M-1\n'
        asm += 'A=M\n'
        asm += 'D=M\n'  # op1

        # add op1 and TMP1
        asm += '//D <- op1 + TMP1\n'
        asm += '@'+TMP1+'\n'
        asm += 'D=D+M\n'

        # push D onto stack
        asm += '//push D onto stack\n'
        asm += ''
        asm += '@SP\n'
        asm += 'A=M\n'
        asm += 'M=D\n'
        asm += '@SP\n'
        asm += 'M=M+1\n'
        return asm
    else:
        return ''


def write_asm(cmd):
    if cmd.is_push() or cmd.is_pop():
        return write_stack(cmd)
    else:
        return write_arithmetic(cmd)


def infloop():
    asm = '(INFINITE_LOOP)\n'
    asm += '@INFINITE_LOOP\n'
    asm += '0;JMP\n'
    return asm


if __name__ == '__main__':
    if len(sys.argv) < 2:
        sys.exit("USAGE: VMTranslator.py input.vm")

    vmfpath = sys.argv[1]   # input: vm file full path
    dirname, vmfname = os.path.split(vmfpath)
    asmfname = os.path.splitext(vmfname)[0]+'.asm'
    asmpath = os.path.join(dirname, asmfname)

    with open(asmpath, 'w') as asmfile:
        for cmd in parse(vmfpath):
            asmfile.write(write_asm(cmd))
        asmfile.write(infloop())

