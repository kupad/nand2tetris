#!/usr/bin/python3

import sys
from pathlib import Path
from tokenizer import Tokenizer, IDENTIFIER

types = set(['int', 'char', 'boolean'])
subroutine_start = set(['constructor', 'function', 'method'])
subroutine_types = set(['void', *types])
statement_start = set(['let', 'if', 'let', 'while', 'do', 'return'])


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
        return self.tokenizer.curr

    def processSkip(self):
        """process next token...by skipping it"""
        return next(self.it)

    def processAny(self):
        """process next token. Do not check for anything"""
        print(self.tokenizer.curr_to_xml(self.indent), file=self.outfile)
        return next(self.it)

    def processVoidType(self):
        """process a void or a type token"""
        return self.processAny()  # FIXME
        #if self.curr() not in types and self.curr() != 'void':
        #    raise JackError(
        #            f'syntax error: found {self.curr()} expected type or void',
        #            self.tokenizer.lineno)
        #print(self.tokenizer.curr_to_xml(self.indent))
        #return next(self.it)

    def processType(self):
        """process a type token"""
        return self.processAny()  # FIXME
        #if self.curr() not in types:
        #    raise JackError(
        #            f'syntax error: found {self.curr()} expected type',
        #            self.tokenizer.lineno)
        #print(self.tokenizer.curr_to_xml(self.indent))
        #return next(self.it)

    def processIdentifier(self):
        if self.tokenizer.token_type() != IDENTIFIER:
            msg = f"syntax error: found '{self.curr()}' expected an IDENTIFIER"
            raise JackError(msg, self.tokenizer.lineno)
        print(self.tokenizer.curr_to_xml(self.indent), file=self.outfile)
        return next(self.it)

    def processVarName(self):
        return self.processIdentifier()

    def process(self, s):
        """process next token. raise exception if the token is unexpected"""
        if self.curr() != s:
            raise JackError(
                    f'syntax error: found {self.curr()} expected: {s}',
                    self.tokenizer.lineno)
        print(self.tokenizer.curr_to_xml(self.indent), file=self.outfile)
        return next(self.it)

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
        self.processAny()  # className
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
        self.process(self.curr())  # static|field
        self.processType()
        self.processVarName()
        while self.curr() == ',':
            self.process(',')
            self.processVarName()
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
        self.processVoidType()  # ('void'|type)
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
        'if' '(' expression ')' '{' statements '}' ('else' '{' statements '}' )?
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
        # self.compileExpression()  # FIXME
        # subroutineCall
        while self.curr() != '(':
            self.processAny()
        self.process('(')
        self.compileExpressionList()
        self.process(')')
        # subroutineCall
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
        self.printEndNonTerm("expression")

    def compileTerm(self):
        """
        """
        self.printStartNonTerm("term")
        self.processAny()  # FIXME / TODO
        self.printEndNonTerm("term")

    def compileExpressionList(self):
        """
        """
        self.printStartNonTerm("expressionList")
        if self.curr() != ')':
            self.compileExpression()
        while self.curr() == ',':
            self.process(',')
            self.compileExpression()
        self.printEndNonTerm("expressionList")

    def start(self):
        try:
            next(self.it)
            self.compileClass()
        except StopIteration:
            pass


def main():
    if len(sys.argv) < 2:
        sys.exit("USAGE: tokenizer.py input")

    path = Path(sys.argv[1])   # input: source path
    if path.is_dir():
        jackfiles = [f for f in path.iterdir() if f.suffix == '.jack']
        outdir = path
    else:
        jackfiles = [path]
        outdir = path.parent

    for fpath in jackfiles:
        name = fpath.stem
        xmlpath = outdir.joinpath(name + 'T.test.xml')
        with open(fpath, 'r') as fp:
            tokenizer = Tokenizer(fp.read())
            compiler = CompilationEngine(tokenizer)
            compiler.start()
        # with open(xmlpath, 'w') as xmlfile:
        #    tokenizer.to_xml_tree(xmlfile)


if __name__ == '__main__':
    try:
        main()
    except JackError as e:
        sys.exit(e)

