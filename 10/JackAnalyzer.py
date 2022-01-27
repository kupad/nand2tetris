#!/usr/bin/python3

import sys
from pathlib import Path
from tokenizer import Tokenizer
from compilation_engine import CompilationEngine, JackError


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

        with open(fpath, 'r') as jackfile:
            tokenizer = Tokenizer(jackfile.read())

        xmlpath = outdir.joinpath(name + '.mine.xml')
        with open(xmlpath, 'w') as xmlfile:
            compiler = CompilationEngine(tokenizer, xmlfile)
            compiler.start()


if __name__ == '__main__':
    try:
        main()
    except JackError as e:
        sys.exit(e)



