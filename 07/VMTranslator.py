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
from collections import defaultdict
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
TMP1 = R13 = '@R13'
TRUE = -1
FALSE = 0
SP = '@SP'
LCL = '@LCL'
ARG = '@ARG'
THIS = '@THIS'
THAT = '@THAT'
TEMP = '@R5'


staticlookup = None


def create_static_lookup(prognamespace):
    # next available memory address for symbol table
    # starts at 16 (R0-R15 defined)
    nextaddr = 16

    def getnextreg():
        """
        Returns next avail memory address and increments it.
        """
        nonlocal nextaddr
        addr = nextaddr
        nextaddr += 1
        return '@'+str(addr)

    statictbl = defaultdict(getnextreg)

    def lookup(num):
        nonlocal prognamespace
        symb = prognamespace+'.'+num
        return statictbl[symb]

    return lookup


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

move comp value into whatever @SP is currently pointing to.
NOTE: SP is pointing one higher than the logical stack
"""
asm_mov_derefsp = partial(asm_mov_derefptr, SP)


seg2symb = {
    'local': LCL,
    'this': THIS,
    'that': THAT,
    'temp': TEMP,
    'argument': ARG,
}


def asm_load_val(dest, val):
    """load val into dest"""
    return [
        '@'+val,
        f'{dest}=A'
    ]


def asm_lea(dest, segment, offset):
    asm = [
        '@'+offset,
        'D=A',
        seg2symb[segment],
        'A=M',
        'A=A+D',
    ]
    if dest and dest != M:
        asm.append(f'{dest}=M')
    return asm


def asm_sav_tmp1(source=D):
    return [
        TMP1,
        f'M={source}',
    ]


def asm_push(comp=D):
    """push the comp onto the stack"""
    return [
        *asm_mov_derefsp(comp),
        *asm_inc_sp(),
    ]


def asm_pop(dest=D):
    """pop the value off stack into dest reg"""
    asm = [
        SP,
        'M=M-1',
        'A=M',
    ]
    if dest:
        asm.append(dest+'=M')
    return asm


def stackpushtoasm(cmd):
    segment = cmd.arg1
    value = cmd.arg2

    asm = ['//push '+segment+' '+value]

    if segment == 'constant':
        asm += [
            *asm_load_val(D, value),
            *asm_push(D),
        ]
    elif segment == 'temp':
        reg = str(5 + int(value))
        asm += [
            '@'+reg,
            'D=M',
            *asm_push(D),
        ]
    elif segment == 'pointer':
        reg = THIS if value == '0' else THAT
        asm += [
            reg,
            'D=M',
            *asm_push(D),
        ]
    elif segment == 'static':
        reg = staticlookup(value)
        asm += [
            reg,
            'D=M',
            *asm_push(D),
        ]
    else:
        asm += [
            *asm_lea(D, segment, value),
            *asm_push(D),
        ]
    return asm


def stackpoptoasm(cmd):
    segment = cmd.arg1
    value = cmd.arg2

    asm = ['//pop '+segment+' '+value]
    if segment == 'temp':
        reg = str(5 + int(value))
        asm += [
            *asm_pop(D),
            '@'+reg,
            'M=D',
        ]
    elif segment == 'pointer':
        reg = THIS if value == '0' else THAT
        asm += [
            *asm_pop(D),
            reg,
            'M=D',
        ]
    elif segment == 'static':
        reg = staticlookup(value)
        asm += [
            *asm_pop(D),
            reg,
            'M=D',
        ]
    else:
        asm += [
            *asm_lea('', segment, value),
            'D=A',
            *asm_sav_tmp1(D),
            *asm_pop(D),
            *asm_mov_derefptr(TMP1, D)
        ]
    return asm


def stacktoasm(cmd):
    return stackpushtoasm(cmd) if cmd.is_push() else stackpoptoasm(cmd)


def arith2op(op, precmt=''):
    """
    Pop top 2 values from stack. Perform operation on it.
    Then push result on stack.

    precmt: cmt for the following instructions
    op: a valid 2 op computation {+,-,|,&}

    Note: This optimizes things a bit. Taking advantage of the location
    of the SP, we avoid some instrunctions
    """
    asm = [
        precmt,
        '//D <- pop op2',
        *asm_pop(D),

        '//pop op1. M == op1',
        *asm_pop(dest=None),

        f'//M <- op1(M) {op} op2(D)',
        f'M=M{op}D',

        '//inc stack',
        *asm_inc_sp(),
    ]
    return asm


def arith1op(op, precmt=''):
    """
    Pop top value from stack. Perform operation on it.
    Then push result back on stack.

    precmt: cmt for the following instructions
    op: a valid 1 op computation {!,-}

    Note: This optimizes things a bit. Taking advantage of the location
    of the SP, we avoid some instrunctions
    """
    asm = [
        precmt,

        '//pop op',
        *asm_pop(None),

        f'//M <- {op}M',
        f'M={op}M',

        '//inc stack',
        *asm_inc_sp(),
    ]
    return asm


labelno = 0


def genlabel():
    """
    Generates a generic label.  Uses a counter for uniqueness
    """
    global labelno
    label = f'(LABEL_{labelno})'
    labelno += 1
    return label


def symb(label):
    return '@'+label[1:-1]


def asm_ifelse(cmpinstr, iftrue, iffalse):
    """
    Generates the instructions for a if-then-else control.

    cmpinstr: {comp};{jmp} (ie: D;JEQ)
    iftrue: instructions to generate if jmp would be true
    iffalse: instructions to generate if jmp would be false
    """
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


def arithcmp(jmp, precmt=''):
    """
    Pop top 2 values from the stack and do a compare.
    Push result of comparisaon on stack

    jmp: {JEQ,JLT,JGT}
        JEQ: if op1 > op2, push TRUE, else FALSE
        JLT: if op1 < op2, push TRUE, else FALSE
        JGT: if op1 > op2, push TRUE, else FALSE
    """
    asm = [
        precmt,
        '//D <- pop op2',
        *asm_pop(D),

        '//pop op1. M == op1',
        *asm_pop(None),

        'MD=M-D',
        *asm_ifelse(
            f'D;{jmp}',
            asm_mov_derefsp(TRUE),
            asm_mov_derefsp(FALSE)),

        '//inc stack',
        *asm_inc_sp(),
    ]
    return asm


def arithtoasm(cmd):
    op = cmd.txt
    if op == 'add':
        return arith2op('+', '//add')
    elif op == 'sub':
        return arith2op('-', '//sub')
    elif op == 'and':
        return arith2op('&', '//and')
    elif op == 'or':
        return arith2op('|', '//or')
    elif op == 'neg':
        return arith1op('-', '//arith neg (-)')
    elif op == 'not':
        return arith1op('!', '//logic bitwise not (!)')
    elif op == 'eq':
        return arithcmp('JEQ', '//eq')
    elif op == 'lt':
        return arithcmp('JLT', '//lt')
    elif op == 'gt':
        return arithcmp('JGT', '//gt')
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


def main():
    global staticlookup
    if len(sys.argv) < 2:
        sys.exit("USAGE: VMTranslator.py input.vm")

    vmfpath = sys.argv[1]   # input: vm file full path
    dirname, vmfname = os.path.split(vmfpath)
    basename, ext = os.path.splitext(vmfname)
    prognamespace = basename
    staticlookup = create_static_lookup(prognamespace)

    asmfname = basename+'.asm'
    asmpath = os.path.join(dirname, asmfname)

    with open(asmpath, 'w') as asmfile:
        for cmd in parse(vmfpath):
            asmfile.write(cmdtoasm(cmd))
        asmfile.write(infloop())


if __name__ == '__main__':
    main()

