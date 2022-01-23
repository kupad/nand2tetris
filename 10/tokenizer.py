#!/usr/bin/python3

import sys
from pathlib import Path
import re


KEYWORD = 'keyword'
SYMBOL = 'symbol'
STRING_CONST = 'stringConstant'
INT_CONST = 'integerConstant'
IDENTIFIER = 'identifier'


keywords = set([
    'class', 'constructor', 'function', 'method', 'field', 'static',
    'var', 'int', 'char', 'boolean', 'void', 'true', 'false', 'null', 'this',
    'let', 'do', 'if', 'else', 'while', 'return'
])


symbols = set([
    '{', '}', '(', ')', '[', ']', '.', ',', ';', '+', '-', '*',
    '/', '&', '|', '<', '>', '=', '~'
])


class Tokenizer:
    def __init__(self, content):
        content = re.sub(r'//.*', '', content)
        content = re.sub(r'/\*(.|\n)*?\*/', '', content)
        content = re.sub(r'/\*(.|\n)*?\*/', '', content, re.MULTILINE)
        # print(content)

        regex = r'".+"|\w+|[{}()\[\]\.,;\+\-\*/&\|<>=~]'
        self.words = re.findall(regex, content)
        self.curr = self.peek = None

    def token_type(self):
        if self.curr in keywords:
            return KEYWORD
        elif self.curr in symbols:
            return SYMBOL
        elif self.curr[0] == '"' and self.curr[-1] == '"':
            return STRING_CONST
        elif re.match(r'^\d+$', self.curr):
            if int(self.curr) > 32767:
                raise Exception(f'{self.curr} too large')
            return INT_CONST
        else:
            return IDENTIFIER

    def __iter__(self):
        if not self.words:
            return
        self.curr = self.words[0]
        for word in self.words[1:]:
            self.peek = word
            if self.curr.strip():
                yield self.curr.replace('"', '')
            self.curr = self.peek

        if self.curr.strip():
            yield self.curr.replace('"', '')

    def to_xml_tree(self, outfile):
        outfile.write('<tokens>\n')
        for token in self:
            toktype = self.token_type()
            token = re.sub(r'&', '&amp;', token)
            token = re.sub(r'<', '&lt;', token)
            token = re.sub(r'>', '&gt;', token)
            token = re.sub(r'"', '&quot;', token)
            outfile.write(f'<{toktype}>{token}</{toktype}>\n')
        outfile.write('</tokens>\n')


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
        with open(xmlpath, 'w') as xmlfile:
            tokenizer.to_xml_tree(xmlfile)


if __name__ == '__main__':
    main()

