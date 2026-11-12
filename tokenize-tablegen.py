#!/usr/bin/env python3

#  This file is part of Elixir, a source code cross-referencer.
#
#  Copyright (C) 2026 The Elixir contributors
#
#  Elixir is free software: you can redistribute it and/or modify
#  it under the terms of the GNU Affero General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  Elixir is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU Affero General Public License for more details.
#
#  You should have received a copy of the GNU Affero General Public License
#  along with Elixir.  If not, see <http://www.gnu.org/licenses/>.

"""Tokenize LLVM TableGen and extract top-level named records.

Universal Ctags 5.9 has no TableGen parser. A line regex cannot skip
``[{ ... }]`` code blocks (ODS descriptions often contain the letters
``def`` and ``class``) or tell ``def Name`` from ``def : Parent`` and
from ``def Name#paste``.

Reference stream (default): identifiers outside comments, strings, code
blocks, and preprocessor lines. Keywords (``def``, ``class``, ``let``,
...) stay in the separator.

Definitions (``--defs``):

* ``def``, ``defm``, ``class``, ``multiclass`` with a plain identifier
  name (not ``def : Parent``, not ``def Name#paste``)
* ``defvar`` and ``defset`` (the name before ``=``)
* ``deftype``

``--defs`` on a file with no records prints zero bytes.
"""

import sys
from collections import namedtuple

KEYWORDS = frozenset({
    'assert', 'bit', 'bits', 'class', 'code', 'dag', 'def', 'defm',
    'defset', 'deftype', 'defvar', 'dump', 'else', 'false', 'field',
    'foreach', 'if', 'in', 'include', 'int', 'let', 'list', 'multiclass',
    'string', 'then', 'true',
})

_DEF_KINDS = {
    'def': 'def',
    'defm': 'defm',
    'class': 'class',
    'multiclass': 'multiclass',
    'defvar': 'variable',
    'deftype': 'typedef',
}

Tok = namedtuple('Tok', 'kind text line')


def _is_ident_start(ch):
    return ch.isascii() and (ch.isalpha() or ch == '_')


def _is_ident_cont(ch):
    return ch.isascii() and (ch.isalnum() or ch == '_')


class Lexer:
    def __init__(self, src):
        self.src = src
        self.n = len(src)
        self.i = 0
        self.line = 1
        self.at_bol = True
        self.tokens = []
        self.spans = []

    def peek(self, k=0):
        j = self.i + k
        if j < self.n:
            return self.src[j]
        return ''

    def bump(self):
        ch = self.src[self.i]
        self.i += 1
        if ch == '\n':
            self.line += 1
            self.at_bol = True
        elif ch not in ' \t\r':
            self.at_bol = False
        return ch

    def run(self):
        while self.i < self.n:
            ch = self.src[self.i]
            if ch in ' \t\r':
                self.bump()
                continue
            if ch == '\n':
                self.bump()
                continue
            if self.at_bol and ch == '#':
                self._preprocessor()
                continue
            if ch == '/' and self.peek(1) == '/':
                self._line_comment()
                continue
            if ch == '/' and self.peek(1) == '*':
                self._block_comment()
                continue
            if ch == '[' and self.peek(1) == '{':
                self._code_block()
                continue
            if ch == '"':
                self._string()
                continue
            if _is_ident_start(ch):
                self._ident()
                continue
            if ch.isdigit():
                self._number()
                continue
            self._add('punct', ch, self.line)
            self.bump()
        return self.tokens, self.spans

    def _add(self, kind, text, line):
        self.tokens.append(Tok(kind, text, line))

    def _preprocessor(self):
        while self.i < self.n and self.src[self.i] != '\n':
            self.bump()

    def _line_comment(self):
        while self.i < self.n and self.src[self.i] != '\n':
            self.bump()

    def _block_comment(self):
        self.bump()
        self.bump()
        while self.i < self.n:
            if self.src[self.i] == '*' and self.peek(1) == '/':
                self.bump()
                self.bump()
                return
            self.bump()

    def _code_block(self):
        # Caller is on `[{`. Code blocks nest and may contain strings.
        self.bump()
        self.bump()
        depth = 1
        while self.i < self.n and depth:
            if self.src.startswith('[{', self.i):
                depth += 1
                self.bump()
                self.bump()
                continue
            if self.src.startswith('}]', self.i):
                depth -= 1
                self.bump()
                self.bump()
                continue
            if self.src[self.i] == '"':
                self._string()
                continue
            if self.src[self.i] == '/' and self.peek(1) == '/':
                self._line_comment()
                continue
            self.bump()

    def _string(self):
        self.bump()
        while self.i < self.n:
            ch = self.src[self.i]
            if ch == '\\':
                self.bump()
                if self.i < self.n:
                    self.bump()
                continue
            if ch == '"':
                self.bump()
                return
            if ch == '\n':
                return
            self.bump()

    def _ident(self):
        line = self.line
        start = self.i
        self.bump()
        while self.i < self.n and _is_ident_cont(self.src[self.i]):
            self.bump()
        text = self.src[start:self.i]
        self._add('ident', text, line)
        if text not in KEYWORDS:
            self.spans.append((start, self.i))

    def _number(self):
        while self.i < self.n and (self.src[self.i].isdigit()
                                    or self.src[self.i] == '_'):
            self.bump()


def _stream(src, spans):
    out = []
    last = 0
    for start, end in spans:
        if start < last or end > len(src):
            continue
        out.append(src[last:start].replace('\n', '\001'))
        out.append('\n')
        out.append(src[start:end])
        out.append('\n')
        last = end
    out.append(src[last:].replace('\n', '\001'))
    return ''.join(out)


class Parser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.defs = []

    def parse(self):
        i = 0
        tokens = self.tokens
        n = len(tokens)
        while i < n:
            tok = tokens[i]
            if tok.kind == 'ident' and tok.text == 'defset':
                i = self._defset(i)
                continue
            if tok.kind == 'ident' and tok.text in _DEF_KINDS:
                name = self._plain_name(i)
                if name is not None:
                    self.defs.append((name.text, _DEF_KINDS[tok.text], name.line))
            i += 1
        return self.defs

    def _plain_name(self, kw_index):
        j = kw_index + 1
        tokens = self.tokens
        if j >= len(tokens) or tokens[j].kind != 'ident':
            return None
        if (j + 1 < len(tokens) and tokens[j + 1].kind == 'punct'
                and tokens[j + 1].text == '#'):
            return None
        return tokens[j]

    def _defset(self, kw_index):
        tokens = self.tokens
        angle = 0
        prev = None
        j = kw_index + 1
        while j < len(tokens):
            tok = tokens[j]
            if tok.kind == 'punct' and tok.text == '<':
                angle += 1
            elif tok.kind == 'punct' and tok.text == '>':
                if angle:
                    angle -= 1
            elif tok.kind == 'ident':
                prev = tok
            elif tok.kind == 'punct' and tok.text == '=' and angle == 0:
                if prev is not None and prev.text not in KEYWORDS:
                    self.defs.append((prev.text, 'variable', prev.line))
                return j + 1
            elif tok.kind == 'punct' and tok.text == ';' and angle == 0:
                return j + 1
            j += 1
        return j


def _lex(src):
    return Lexer(src).run()


def tokenize_source(src):
    _tokens, spans = _lex(src)
    return _stream(src, spans)


def reference_names(src):
    _tokens, spans = _lex(src)
    names = []
    for start, end in spans:
        line = src.count('\n', 0, start) + 1
        names.append((line, src[start:end]))
    return names


def parse_defs(src):
    tokens, _spans = _lex(src)
    return Parser(tokens).parse()


def format_defs(defs):
    if not defs:
        return ''
    lines = []
    for name, kind, line in defs:
        if not name or any(ch.isspace() for ch in name):
            continue
        if not (name[0].isascii() and (name[0].isalpha() or name[0] == '_')):
            continue
        lines.append(f'{name} {kind} {line}')
    if not lines:
        return ''
    return '\n'.join(lines) + '\n'


def main():
    raw = sys.stdin.buffer.read()
    try:
        src = raw.decode('utf-8')
    except UnicodeDecodeError:
        src = raw.decode('utf-8', errors='surrogateescape')
    defs_mode = '--defs' in sys.argv[1:]
    try:
        text = format_defs(parse_defs(src)) if defs_mode else tokenize_source(src)
    except Exception as exc:
        sys.stderr.write(
            f'tokenize-tablegen.py: {exc.__class__.__name__}: {exc}\n')
        text = '' if defs_mode else src.replace('\n', '\001')
    out = text.encode('utf-8', errors='surrogateescape')
    # Same contract as tokenize-mojo.py: --defs with nothing to report
    # is zero bytes, and tokenize mode always ends with a newline.
    if (out or not defs_mode) and not out.endswith(b'\n'):
        out += b'\n'
    sys.stdout.buffer.write(out)


if __name__ == '__main__':
    main()
