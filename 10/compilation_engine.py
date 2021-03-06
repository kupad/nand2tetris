#!/usr/bin/python3

from tokenizer import (
    IDENTIFIER, INT_CONST, STRING_CONST, KEYWORD
)

types = set(['int', 'char', 'boolean'])
subroutine_start = set(['constructor', 'function', 'method'])
subroutine_types = set(['void', *types])
statement_start = set(['let', 'if', 'let', 'while', 'do', 'return'])
ops = set(['+',  '-', '*', '/', '&', '|', '<', '>', '='])
unary_op = set(['-', '~'])


class JackError(Exception):
    """
    Represents an error in the JACK code.
    """
    def __init__(self, msg, lineno):
        super().__init__(msg)
        self.lineno = lineno

    def __str__(self):
        return f'Error: line {self.lineno}: {super().__str__()}'


class CompilationEngine:
    def __init__(self, tokenizer, outfile):
        self.tokenizer = tokenizer
        self.outfile = outfile
        self.it = iter(self.tokenizer)
        self.indent = 0

    def curr(self):
        """returns the current token being processed"""
        return self.tokenizer.curr

    def is_type(self):
        """returns true if the current token represents a type"""
        return (
            self.curr() in types or
            self.tokenizer.token_type() == IDENTIFIER)

    def processNext(self):
        """process next token. Do not check for anything"""
        print(self.tokenizer.curr_to_xml(self.indent), file=self.outfile)
        return next(self.it)

    def processVoidType(self):
        """process a void or a type token"""
        if self.curr() != 'void' and not self.is_type():
            raise JackError(
                f"syntax error: found '{self.curr()}' expected type or void",
                self.tokenizer.lineno)
        return self.processNext()

    def processType(self):
        """process a type token"""
        if not self.is_type():
            raise JackError(
                f'syntax error: found {self.curr()} expected type',
                self.tokenizer.lineno)
        return self.processNext()

    def processIdentifier(self):
        """process an identifier """
        if self.tokenizer.token_type() != IDENTIFIER:
            msg = f"syntax error: found '{self.curr()}' expected an IDENTIFIER"
            raise JackError(msg, self.tokenizer.lineno)
        return self.processNext()

    def processVarName(self):
        """process a varName"""
        return self.processIdentifier()

    def process(self, s):
        """process next token. raise exception if the token is unexpected"""
        if self.curr() != s:
            raise JackError(
                    f'syntax error: found {self.curr()} expected: {s}',
                    self.tokenizer.lineno)
        return self.processNext()

    def printStartNonTerm(self, s):
        """start of non-terminal"""
        print(f"{'  '*self.indent}<{s}>", file=self.outfile)
        self.indent += 1

    def printEndNonTerm(self, s):
        """start of non-terminal"""
        self.indent -= 1
        print(f"{'  '*self.indent}</{s}>", file=self.outfile)

    def compileClass(self):
        """
        'class' classname '{' classVarDec* subroutineDec* '}'
        """
        self.printStartNonTerm("class")
        self.process("class")
        self.processIdentifier()  # className
        self.process("{")
        while self.curr() in ('static', 'field'):
            self.compileClassVarDec()
        while self.curr() in subroutine_start:
            self.compileSubRoutineDec()
        try:
            self.process("}")
        except StopIteration:
            self.printEndNonTerm("class")

    def compileClassVarDec(self):
        """
        ('static'|'field') type varName (',' varName)* ';'
        """
        self.printStartNonTerm("classVarDec")
        self.processNext()  # static | field
        self.processType()
        self.processIdentifier()  # varName
        while self.curr() == ',':
            self.process(',')
            self.processIdentifier()  # varName
        self.process(';')
        self.printEndNonTerm("classVarDec")

    def compileSubRoutineDec(self):
        """
        ('constructor'|'function'|'method') ('void'|type) subroutineName
        '(' parameterList ')' subroutineBody
        """
        self.printStartNonTerm("subroutineDec")
        if self.curr() in subroutine_start:
            self.process(self.curr())
        self.processVoidType()
        self.processIdentifier()  # subroutineName
        self.process('(')
        self.compileParamList()
        self.process(')')
        self.compileSubroutineBody()
        self.printEndNonTerm("subroutineDec")

    def compileParamList(self):
        """
        ((type varName) ("," type varName)*)?
        """
        self.printStartNonTerm("parameterList")
        if self.curr() != ')':
            self.processType()
            self.processIdentifier()
            while self.curr() == ',':
                self.process(',')
                self.processType()
                self.processIdentifier()  # varName
        self.printEndNonTerm("parameterList")

    def compileSubroutineBody(self):
        """
        '{' varDec* statements '}'
        """
        self.printStartNonTerm("subroutineBody")
        self.process('{')
        while self.curr() == 'var':
            self.compileVarDec()
        self.compileStatements()
        self.process('}')
        self.printEndNonTerm("subroutineBody")

    def compileVarDec(self):
        """
        'var' type varName (','varName)*) ';'
        """
        self.printStartNonTerm("varDec")
        self.process('var')
        self.processType()
        self.processIdentifier()  # varName
        while self.curr() == ',':
            self.process(",")
            self.processIdentifier()  # varName
        self.process(';')
        self.printEndNonTerm("varDec")

    def compileStatements(self):
        """
        statement*
        """
        self.printStartNonTerm("statements")
        while self.curr() in statement_start:
            if self.curr() == 'let':
                self.compileLet()
            elif self.curr() == 'if':
                self.compileIf()
            elif self.curr() == 'while':
                self.compileWhile()
            elif self.curr() == 'do':
                self.compileDo()
            elif self.curr() == 'return':
                self.compileReturn()
        self.printEndNonTerm("statements")

    def compileLet(self):
        """
        'let' varName ('[' expression ']')? '=' expression ';'
        """
        self.printStartNonTerm("letStatement")
        self.process('let')
        self.processVarName()
        if self.curr() == '[':
            self.process('[')
            self.compileExpression()
            self.process(']')
        self.process('=')
        self.compileExpression()
        self.process(';')
        self.printEndNonTerm("letStatement")

    def compileIf(self):
        """
        'if' '(' expression ')' '{' statements '}'
        ('else' '{' statements '}' )?
        """
        self.printStartNonTerm("ifStatement")
        self.process('if')
        self.process('(')
        self.compileExpression()
        self.process(')')
        self.process('{')
        self.compileStatements()
        self.process('}')
        if self.curr() == 'else':
            self.process('else')
            self.process('{')
            self.compileStatements()
            self.process('}')
        self.printEndNonTerm("ifStatement")

    def compileWhile(self):
        """
        'while' '(' expression ')' '{' statements '}'
        """
        self.printStartNonTerm("whileStatement")
        self.process("while")
        self.process("(")
        self.compileExpression()
        self.process(")")
        self.process("{")
        self.compileStatements()
        self.process("}")
        self.printEndNonTerm("whileStatement")

    def compileDo(self):
        """
        'do' subroutineCall ';'
        """
        self.printStartNonTerm("doStatement")
        self.process('do')
        self.compileSubroutineCall()
        self.process(';')
        self.printEndNonTerm("doStatement")

    def compileReturn(self):
        """
        'return' (expression)? ';'
        """
        self.printStartNonTerm("returnStatement")
        self.process('return')
        if self.curr() != ';':
            self.compileExpression()
        self.process(';')
        self.printEndNonTerm("returnStatement")

    def compileExpression(self):
        """
        term (op term)*
        """
        self.printStartNonTerm("expression")
        self.compileTerm()
        while self.curr() in ops:
            self.processNext()  # op
            self.compileTerm()
        self.printEndNonTerm("expression")

    def compileTerm(self):
        """
        integerConst | stringConst | keywordConst | varName |
        varName '[' expression ']' | '(' expression ')' | unaryOp term |
        subroutineCall
        """
        curr = self.curr()
        curr_toktype = self.tokenizer.token_type()
        peek = self.tokenizer.peek

        self.printStartNonTerm("term")
        if curr_toktype in (INT_CONST, STRING_CONST, KEYWORD):
            self.processNext()
        elif curr == '(':
            self.process('(')
            self.compileExpression()
            self.process(')')
        elif curr in unary_op:
            self.processNext()
            self.compileTerm()

        # arr[expression]
        elif curr_toktype == IDENTIFIER and peek == '[':
            self.processIdentifier()
            self.process('[')
            self.compileExpression()
            self.process(']')

        # subroutine call:
        elif curr_toktype == IDENTIFIER and peek in ('(', '.'):
            self.compileSubroutineCall()

        # varName
        else:
            self.processIdentifier()

        self.printEndNonTerm("term")

    def compileSubroutineCall(self):
        """
        subroutineName '(' expressionList ')' |
        (className|varName)'.'subroutineName '(' expressionList ')'

        Note: subroutineCall is special: we don't print it out as a non-term
        """
        self.processIdentifier()  # subroutineName|className|varName
        if self.curr() == '(':
            self.process('(')
            self.compileExpressionList()
            self.process(')')
        elif self.curr() == '.':
            self.process('.')
            self.processIdentifier()  # subroutineName
            self.process('(')
            self.compileExpressionList()
            self.process(')')

    def compileExpressionList(self):
        """
        """
        count = 0
        self.printStartNonTerm("expressionList")
        if self.curr() != ')':
            self.compileExpression()
            count += 1
        while self.curr() == ',':
            self.process(',')
            self.compileExpression()
            count += 1
        self.printEndNonTerm("expressionList")
        return count

    def start(self):
        try:
            next(self.it)
            self.compileClass()
        except StopIteration:
            pass
