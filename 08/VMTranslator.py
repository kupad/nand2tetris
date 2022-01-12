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
    BRANCH = auto()
    FUNCTION = auto()
    CALL = auto()
    RETURN = auto()


# prefined registers and symbols and values
A = 'A'
D = 'D'
M = 'M'
TMP1 = R13 = '@R13'
TMP2 = R14 = '@R14'
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
    def __init__(self, instrtxt, cmdtype, cmdtok, arg1, arg2, cmdno, lineno):
        self.txt = instrtxt
        self.type = cmdtype
        self.cmdtok = cmdtok
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

    def is_branch(self):
        return self.type is CmdType.BRANCH

    def is_function(self):
        return self.type is CmdType.FUNCTION

    def is_call(self):
        return self.type is CmdType.CALL

    def is_return(self):
        return self.type is CmdType.RETURN

    def __repr__(self):
        return f'{self.txt}|{self.type}'


RE_COMMENT = re.compile(r'//.*')


def parse_cmdtxt(cmdtxt, cmdno=-1, lineno=-1):
    tokens = cmdtxt.split(" ")
    cmdtok = tokens[0]
    arg1 = None
    arg2 = None

    # Determine what kind of instruction this is
    if cmdtok == 'push':
        cmdtype = CmdType.PUSH
        arg1 = tokens[1]
        arg2 = tokens[2]
    elif cmdtok == 'pop':
        cmdtype = CmdType.POP
        arg1 = tokens[1]
        arg2 = tokens[2]
    elif cmdtok == 'function':
        cmdtype = CmdType.FUNCTION
        arg1 = tokens[1]
        arg2 = tokens[2]
    elif cmdtok == 'call':
        cmdtype = CmdType.CALL
        arg1 = tokens[1]
        arg2 = tokens[2]
    elif cmdtok == 'return':
        cmdtype = CmdType.RETURN
    elif cmdtok in ('label', 'goto', 'if-goto'):
        cmdtype = CmdType.BRANCH
        arg1 = tokens[1]
    else:
        cmdtype = CmdType.ARITHMETIC

    # create cmd and return
    cmd = Command(cmdtxt, cmdtype, cmdtok, arg1, arg2, cmdno, lineno)
    return cmd


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
            cmdno += 1
            cmd = parse_cmdtxt(cmdtxt, cmdno, lineno)
            yield cmd


def isnum(s):
    try:
        int(s)
        return True
    except ValueError:
        return False


def asm_goto(addr):
    return [
        addr,
        '0;JMP'
    ]


def asm_mov(dest, source):
    asm = [f'//asm_mov {dest}, {source}']
    if isnum(source):
        asm += ['@'+source]
        if dest.startswith('@'):
            asm += ['D=A']
            sourcereg = D
        else:
            sourcereg = A
    elif source.startswith('@'):
        asm += [source]
        if dest.startswith('@'):
            asm += ['D=M']
            sourcereg = D
        else:
            sourcereg = M
    else:
        sourcereg = source

    if dest.startswith('@'):
        asm += [dest]
        destreg = M
    else:
        destreg = dest

    asm += [f'{destreg}={sourcereg}']
    return asm


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


def asm_lea(dest, baseptr, offset, op='+'):
    """
    load effective address

    baseptr: an ainstr (ie: @LCL). It's value is a ptr
    offset: offset from baseptr
    dest: dest for value in [(baseptr+offset)]
    """
    asm = [
        f'//asm_lea {dest}, {baseptr}, {op}{offset}',
        *asm_mov(D, offset),
        baseptr,
        'A=M',
        'A=A+D' if op == '+' else 'A=A-D',
    ]
    if dest:
        if dest.startswith('@'):
            asm += [
                'D=M',
                dest,
                'M=D'
            ]
        elif dest != M:
            asm.append(f'{dest}=M')
    return asm


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


def seglookup(segment, value):
    """segment+value -> source/dest"""
    if segment == 'constant':
        return value
    elif segment == 'temp':
        return '@' + str(5 + int(value))
    elif segment == 'pointer':
        return THIS if value == '0' else THAT
    elif segment == 'static':
        return staticlookup(value)


def stackpushtoasm(cmd):
    segment = cmd.arg1
    value = cmd.arg2

    asm = ['//push '+segment+' '+value]

    if segment in ('constant', 'temp', 'pointer', 'static'):
        source = seglookup(segment, value)
        asm += [*asm_mov(D, source)]
    else:
        basemem = seg2symb[segment]
        asm += [*asm_lea(D, basemem, value)]
    asm += [*asm_push(D)]
    return asm


def stackpoptoasm(cmd):
    segment = cmd.arg1
    value = cmd.arg2

    asm = ['//pop '+segment+' '+value]
    if segment in ('constant', 'temp', 'pointer', 'static'):
        dest = seglookup(segment, value)
        asm += [
            *asm_pop(D),
            *asm_mov(dest, D)
        ]
    else:
        basemem = seg2symb[segment]
        asm += [
            *asm_lea(None, basemem, value),
            'D=A',
            *asm_mov(TMP1, D),
            *asm_pop(D),
            *asm_mov_derefptr(TMP1, D)
        ]
    return asm


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
        *asm_pop(None),

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

    Internal labels
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


def branchtoasm(cmd):
    label = cmd.arg1
    funcname = "Foo"  # tmp

    def asm_label():
        return funcname+'.'+label

    if cmd.txt.startswith('label'):
        return ['('+asm_label()+')']

    elif cmd.txt.startswith('if-goto'):
        return [
            *asm_pop(D),
            '@'+asm_label(),
            'D;JNE'
        ]
    elif cmd.txt.startswith('goto'):
        return [
            '@'+asm_label(),
            '0;JMP'
        ]
    else:
        print("error in branchtoasm", cmd)


state = {
    'current_function': "bootstrap",
    'return_counter': 0
}


def functiontoasm(cmd):
    name = cmd.arg1
    nvars = int(cmd.arg2)

    state['current_function'] = name
    state['return_counter'] = 0

    asm = [
        f'//function def: {name}',
        '('+name+')',
    ]
    for _ in range(nvars):
        asm += [
            'D=0',
            *asm_push(D)
        ]
    return asm


def calltoasm(cmd):
    name = cmd.arg1
    nargs = int(cmd.arg2)

    retlabel = f"{state['current_function']}$ret.{state['return_counter']}"
    state['return_counter'] += 1

    asm = [
        f'//call {name} {nargs}',

        # save ret address
        '@'+retlabel, 'D=A', *asm_push(D),

        # save pointers:
        '@LCL',  'D=M', *asm_push(D),
        '@ARG',  'D=M', *asm_push(D),
        '@THIS', 'D=M', *asm_push(D),
        '@THAT', 'D=M', *asm_push(D),

        # ARG = SP - 5 - nargs
        # notes:
        #   1) before call, args have been pushed by callee
        #   2) call just pushed 5 more values on the stack
        *asm_mov(D, '5'),
        '@' + str(nargs),
        'D=A+D',
        SP,
        'D=M-D',
        *asm_mov(ARG, D),

        # LCL = SP
        *asm_mov(LCL, SP),

        # goto f
        '@'+name,
        '0;JMP',

        # return label:
        '('+retlabel+')'
    ]

    return asm


def returntoasm(cmd):
    frame = TMP1
    retaddr = TMP2
    asm = [
        '//return',

        # frame = @LCL
        *asm_mov(frame, LCL),
        # retaddr = *(frame-5)
        *asm_lea(retaddr, frame, '5', '-'),
        # *ARG = pop()
        *asm_pop(D),
        *asm_mov_derefptr(ARG, D),

        # SP = ARG + 1
        *asm_mov(SP, ARG),
        *asm_inc_sp(),

        # THAT = *(frame-1)
        # THIS = *(frame-2)
        # ARG = *(frame-3)
        # LCL = *(frame-4)
        *asm_lea(THAT, frame, '1', '-'),
        *asm_lea(THIS, frame, '2', '-'),
        *asm_lea(ARG, frame, '3', '-'),
        *asm_lea(LCL, frame, '4', '-'),

        # goto retaddr
        retaddr,
        'A=M',
        '0;JMP',
    ]
    return asm


def cmdtoasm(cmd):
    if cmd.is_push():
        asm = stackpushtoasm(cmd)
    elif cmd.is_pop():
        asm = stackpoptoasm(cmd)
    elif cmd.is_branch():
        asm = branchtoasm(cmd)
    elif cmd.is_function():
        asm = functiontoasm(cmd)
    elif cmd.is_call():
        asm = calltoasm(cmd)
    elif cmd.is_return():
        asm = returntoasm(cmd)
    else:
        asm = arithtoasm(cmd)
    return '\n'.join(asm+[''])


def bootstrap():
    call_sysinit = parse_cmdtxt('call Sys.init 0')
    asm = [
        '(bootstrap)',
        *asm_mov(SP, '256'),
        *calltoasm(call_sysinit),
        '',
    ]
    return '\n'.join(asm)


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
    staticlookup = create_static_lookup(basename)

    asmfname = basename+'.asm'
    asmpath = os.path.join(dirname, asmfname)

    with open(asmpath, 'w') as asmfile:
        asmfile.write(bootstrap())
        for cmd in parse(vmfpath):
            asmfile.write(cmdtoasm(cmd))
        asmfile.write(infloop())


if __name__ == '__main__':
    main()

