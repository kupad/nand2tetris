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
from pathlib import Path
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


# global state:
state = {
    # file currently being processed
    'curr_filespace': 'unknown',

    # current function being translated
    'curr_function': "bootstrap",

    # return counter withing a function.
    # resets to 0 on every new function being defined
    'return_counter': 0,

    # global if/else label
    'if_else_labelno': 0,
}


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


def is_num(s):
    try:
        int(s)
        return True
    except ValueError:
        return False


def asm_mov(dest, source):
    # asm = [f'//asm_mov {dest}, {source}']
    asm = []
    if is_num(source):
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
        # f'//asm_mov_derefptr {ptr} {comp}',
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
        # f'//asm_lea {dest}, {baseptr}, {op}{offset}',
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


def genlabel():
    """
    Generates a generic label.  Uses a counter for uniquenes
    """
    label = f'(COND_LABEL_{state["if_else_labelno"]})'
    state['if_else_labelno'] += 1
    return label


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


def seglookup(segment, value):
    """segment+value -> source/dest"""
    if segment == 'constant':
        return value
    elif segment == 'temp':
        return '@' + str(5 + int(value))
    elif segment == 'pointer':
        return THIS if value == '0' else THAT
    elif segment == 'static':
        # ie: if file is Foo.vm->Foo.value
        return f"@{state['curr_filespace']}.{value}"


def translate_push(cmd):
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


def translate_pop(cmd):
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


def symb(label):
    return '@'+label[1:-1]


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


def translate_arith(cmd):
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


def translate_branch(cmd):
    label = state['curr_function'] + '.' + cmd.arg1

    if cmd.txt.startswith('label'):
        return ['('+label+')']

    elif cmd.txt.startswith('if-goto'):
        return [
            *asm_pop(D),
            '@'+label,
            'D;JNE'
        ]
    elif cmd.txt.startswith('goto'):
        return [
            '@'+label,
            '0;JMP'
        ]
    else:
        print("error in translate_branch", cmd)


def translate_funcdef(cmd):
    name = cmd.arg1
    nvars = int(cmd.arg2)

    state['curr_function'] = name
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


def translate_callfunc(cmd):
    name = cmd.arg1
    nargs = int(cmd.arg2)

    retlabel = f"{state['curr_function']}$ret.{state['return_counter']}"
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


def translate_return(cmd):
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


def translate_cmd(cmd):
    if cmd.is_push():
        asm = translate_push(cmd)
    elif cmd.is_pop():
        asm = translate_pop(cmd)
    elif cmd.is_branch():
        asm = translate_branch(cmd)
    elif cmd.is_function():
        asm = translate_funcdef(cmd)
    elif cmd.is_call():
        asm = translate_callfunc(cmd)
    elif cmd.is_return():
        asm = translate_return(cmd)
    else:
        asm = translate_arith(cmd)
    return '\n'.join(asm+[''])


def bootstrap():
    call_sysinit = parse_cmdtxt('call Sys.init 0')
    asm = [
        '(bootstrap)',
        *asm_mov(SP, '256'),
        *translate_callfunc(call_sysinit),
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


def is_vmfile(f):
    return f.suffix == '.vm'


def main():
    if len(sys.argv) < 2:
        sys.exit("USAGE: VMTranslator.py input.vm")

    path = Path(sys.argv[1])   # input: source path
    if path.is_dir():
        vmfiles = [f for f in path.iterdir() if is_vmfile(f)]
        outdir = path
    else:
        vmfiles = [path]
        outdir = path.parent

    name = path.stem
    asmpath = outdir.joinpath(name + '.asm')

    with open(asmpath, 'w') as asmfile:
        asmfile.write(bootstrap())
        for vmfile in vmfiles:
            state['curr_filespace'] = vmfile.stem
            for cmd in parse(vmfile):
                asmfile.write(translate_cmd(cmd))
        asmfile.write(infloop())


if __name__ == '__main__':
    main()

