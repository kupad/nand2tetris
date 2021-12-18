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
from functools import partial
from enum import Enum, auto


class CmdType(Enum):
    ARITHMETIC = auto()
    PUSH = auto()
    POP = auto()


# prefined registers and symbols and values
A = 'A'
D = 'D'
M = 'M'
SP = '@SP'
TMP0 = R13 = '@R13'
TRUE = -1
FALSE = 0


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


def asm_inc_ptr(ptr):
    """
    Increment ptr
    """
    return [
        ptr,
        'M=M+1',
    ]


"""
Increment Stack Pointer
"""
asm_inc_sp = partial(asm_inc_ptr, SP)


def asm_mov_derefptr(ptr, comp):
    """
    [ptr] <- comp

    ptr: a memory address, ie: '@SP'
    comp: A valid computation ie (D,0,-1,D+1)

    Find the memory address in ptr, load it into A, then
    load value into A
    """
    return [
        ptr,
        'A=M',
        f'M={comp}',
    ]


"""
[@SP] <- comp

move comp value into whatever @SP is currently pointing to
"""
asm_mov_derefsp = partial(asm_mov_derefptr, SP)


def asm_push(comp='D'):
    """push the comp in the source reg onto the stack"""
    return [
        *asm_mov_derefsp(comp),
        *asm_inc_sp(),
    ]


def asm_pop(dest='D'):
    """pop the value off stack into dest reg"""
    asm = [
        '@SP',
        'M=M-1',
        'A=M',
    ]
    # TODO: can combine following instr 'A=M'
    if dest:
        asm.append(dest+'=M')
    return asm


def stacktoasm(cmd):
    segment = cmd.arg1
    value = cmd.arg2
    asm = [
        # gen comment
        '//'+('push ' if cmd.is_push() else 'pop ')+segment+' '+value,

        # assuming segment is constant...
        '@'+value,
        'D=A',
    ]

    if cmd.is_push():
        asm += asm_push(D)
    else:
        asm += asm_pop(D)

    return asm


def asm_2op(preamble, opcmt, opinstr):
    """2 op with no comparison"""
    asm = [
        preamble,
        '//D <- pop op2',
        *asm_pop(D),

        '//pop op1',
        *asm_pop(dest=None),

        opcmt,
        opinstr,

        '//inc stack',
        *asm_inc_sp(),
    ]
    return asm


def addtoasm(cmd):
    return asm_2op(
        '//add',
        '//M <- op1(M) + op2(D)',
        'M=D+M')


def subtoasm(cmd):
    return asm_2op(
        '//sub',
        '//M <- op1(M) - op2(D)',
        'M=M-D')


def andtoasm(cmd):
    return asm_2op(
        '//and',
        '//M <- op1(M) & op2(D)',
        'M=D&M')


def ortoasm(cmd):
    return asm_2op(
        '//or',
        '//M <- op1(M) | op2(D)',
        'M=D|M')


def negtoasm(cmd):
    """arithmetic negation"""
    asm = [
        '//neg',

        '//pop op1',
        *asm_pop(dest=None),

        'M=-M',

        '//inc stack',
        *asm_inc_sp(),
    ]
    return asm


def nottoasm(cmd):
    """bitwise logical not"""
    asm = [
        '//not',

        '//pop op1',
        *asm_pop(dest=None),

        'M=!M',

        '//inc stack',
        *asm_inc_sp(),
    ]
    return asm


labelno = 1


def genlabel():
    global labelno
    label = f'(LABEL_{labelno})'
    labelno += 1
    return label


def symb(label):
    return '@'+label[1:-1]


def asm_ifelse(cmpinstr, iftrue, iffalse):
    islbl = genlabel()
    isnotlbl = genlabel()

    asm = [
        symb(islbl),
        cmpinstr,
        *iffalse,
        symb(isnotlbl),
        '0;JMP',
        islbl,
        *iftrue,
        isnotlbl,
    ]
    return asm


def eqtoasm(cmd):
    asm = [
        '//eq',
        '//D <- pop op2',
        *asm_pop(D),

        '//dec sp (M becomes op1)',
        *asm_pop(None),

        'MD=M-D',
        *asm_ifelse(
            'D;JEQ',
            asm_mov_derefsp(TRUE),
            asm_mov_derefsp(FALSE)),

        '//inc stack',
        *asm_inc_sp(),
    ]
    return asm


def lttoasm(cmd):
    asm = [
        '//lt',
        '//D <- pop op2',
        *asm_pop(D),

        '//dec sp (M becomes op1)',
        # leaves D with previous val
        *asm_pop(None),

        'MD=M-D',
        *asm_ifelse(
            'D;JLT',
            asm_mov_derefsp(TRUE),
            asm_mov_derefsp(FALSE)),

        '//inc stack',
        *asm_inc_sp(),
    ]
    return asm


def gttoasm(cmd):
    asm = [
        '//gt',
        '//D <- pop op2',
        *asm_pop(D),

        '//dec sp (M becomes op1)',
        # leaves D with previous val
        *asm_pop(None),

        'MD=M-D',
        *asm_ifelse(
            'D;JGT',
            asm_mov_derefsp(TRUE),
            asm_mov_derefsp(FALSE)),

        '//inc stack',
        *asm_inc_sp(),
    ]
    return asm


def arithtoasm(cmd):
    op = cmd.txt
    if op == 'add':
        return addtoasm(cmd)
    elif op == 'sub':
        return subtoasm(cmd)
    elif op == 'and':
        return andtoasm(cmd)
    elif op == 'or':
        return ortoasm(cmd)
    elif op == 'neg':
        return negtoasm(cmd)
    elif op == 'not':
        return nottoasm(cmd)
    elif op == 'eq':
        return eqtoasm(cmd)
    elif op == 'lt':
        return lttoasm(cmd)
    elif op == 'gt':
        return gttoasm(cmd)
    else:
        print('UNKNOWN', cmd)
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

