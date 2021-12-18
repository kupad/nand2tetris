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


# prefined registers and symbols
A = 'A'
D = 'D'
M = 'M'
SP = '@SP'
TMP0 = R13 = '@R13'


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


def asm_inc_sp():
    asm = [
        '@SP',
        'M=M+1',
    ]
    return asm


def asm_push(source='D'):
    """push the value in the source reg onto the stack"""
    asm = [
        '@SP',
        'A=M',
        'M='+source,
    ]
    asm += asm_inc_sp()
    return asm


def asm_pop(dest='D'):
    """pop the value off stack into dest reg"""
    asm = [
        '@SP',
        'M=M-1',
        'A=M',
    ]
    if dest:
        asm.append(dest+'=M')
    return asm


def asm_load(destmem, source='D'):
    """
    destmem: a memory location
    source: a register
    """
    asm = [
        destmem,
        'M='+source,
    ]
    return asm


def stacktoasm(cmd):
    segment = cmd.arg1
    value = cmd.arg2

    asm = [
        # gen comment
        '//'+'push ' if cmd.is_push() else 'pop '+segment+' '+value,

        # assuming segment is constant...
        '@'+value,
        'D=A',
    ]

    if cmd.is_push():
        asm += asm_push()
    else:
        asm += asm_pop()

    return asm


def arithtoasm(cmd):
    op = cmd.txt
    if op == 'add':
        asm = [
            '//add',

            '//D <- pop op2i',
            *asm_pop(),

            '//dec sp (M becomes op1)',
            *asm_pop(dest=None),

            '//M <- op1(M) + op2(D)',
            'M=D+M',

            '//inc stack',
            *asm_inc_sp(),
        ]
        return asm
    else:
        return []


def cmdtoasm(cmd):
    if cmd.is_push() or cmd.is_pop():
        asm = stacktoasm(cmd)
    else:
        asm = arithtoasm(cmd)
    return '\n'.join(asm+[''])


def infloop():
    asm = [
        '(INFINITE_LOOP)',
        '@INFINITE_LOOP',
        '0;JMP',
        '',
    ]
    return '\n'.join(asm)


if __name__ == '__main__':
    if len(sys.argv) < 2:
        sys.exit("USAGE: VMTranslator.py input.vm")

    vmfpath = sys.argv[1]   # input: vm file full path
    dirname, vmfname = os.path.split(vmfpath)
    asmfname = os.path.splitext(vmfname)[0]+'.asm'
    asmpath = os.path.join(dirname, asmfname)

    with open(asmpath, 'w') as asmfile:
        for cmd in parse(vmfpath):
            asmfile.write(cmdtoasm(cmd))
        asmfile.write(infloop())

