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

"""Tokenize Mojo source and extract identifier definitions.

Universal Ctags (including 5.9, which this tree already targets) has no Mojo
parser. Its line regexes also cannot tell a struct field from a ``var`` inside
a function, because Mojo is indented rather than brace-delimited. This script
is the family-J equivalent of tokenize-python.py plus parse-defs:

* reference stream (default): the same separator/identifier alternation as
  tokenize-python.py. ``#`` comments, quoted strings, and docstrings stay in
  the separator text. Backtick spans are Mojo escaped identifiers or MLIR
  literals; only a single identifier inside the backticks is a reference.
  Keywords and argument conventions are not references.
* definitions (``--defs``): ``fn``/``def`` functions and methods, ``struct``,
  ``trait``, ``alias`` and ``comptime`` bindings, and ``var``/``let``/``ref``
  bindings at module scope (variable) or directly in a struct/trait (member).
  Locals, parameters, imports, and function-local comptime names are not
  definitions. ``fn`` and ``def`` are both recognized.

``t"..."`` and ``f"..."`` interpolations are scanned, so names inside ``{}``
are references. Other strings are opaque.
"""

import sys
from collections import namedtuple

# Words that are never reference identifiers. Declaration and control keywords
# are still produced as keyword tokens so the definition parser can see them.
# Argument conventions are included because they sit on almost every signature;
# `read` is not, because it is a plausible method name.
KEYWORDS = frozenset({
    'alias', 'and', 'as', 'assert', 'break', 'case', 'class', 'comptime',
    'continue', 'def', 'del', 'elif', 'else', 'except', 'finally', 'fn',
    'for', 'from', 'global', 'if', 'import', 'in', 'is', 'lambda', 'let',
    'match', 'nonlocal', 'not', 'or', 'pass', 'raise', 'raises', 'ref',
    'return', 'struct', 'trait', 'try', 'var', 'where', 'while', 'with',
    'yield',
    'borrowed', 'deinit', 'imm', 'inout', 'mut', 'out', 'owned',
})

_DECL_FUNCS = frozenset({'def', 'fn'})
_SUITE_START = frozenset({
    'if', 'elif', 'else', 'for', 'while', 'match', 'case',
    'try', 'except', 'finally', 'with',
})
_BINDING_SCOPES = frozenset({'module', 'struct', 'trait'})
_STRING_PREFIX = frozenset('rbtf')

Tok = namedtuple('Tok', 'kind text line')


def _is_ident_start(ch):
    return ch.isascii() and (ch.isalpha() or ch == '_')


def _is_ident_cont(ch):
    return ch.isascii() and (ch.isalnum() or ch == '_')


def _is_plain_ident(text):
    # Escaped identifiers may be keywords or non-ASCII. MLIR literals
    # (`!kgen.never`, `#lit.struct<...>`) are not identifiers.
    return bool(text) and text.isidentifier()


class Lexer:
    def __init__(self, src):
        self.src = src
        self.n = len(src)
        self.i = 0
        self.line = 1
        self.col = 0
        self.bracket = 0
        self.spans = []
        self.tokens = []
        self.indents = [0]

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
            self.col = 0
        elif ch == '\t':
            self.col = (self.col // 8 + 1) * 8
        elif ch != '\r':
            self.col += 1
        return ch

    def add(self, kind, text, line):
        self.tokens.append(Tok(kind, text, line))

    def run(self):
        at_bol = True
        continued = False
        while self.i < self.n:
            if at_bol and self.bracket == 0 and not continued:
                before = self.i
                blank = self._line_start()
                if blank:
                    if self.i == before and self.i < self.n:
                        self.bump()
                    at_bol = True
                    continue
                at_bol = False
                continue

            continued = False
            if self.i >= self.n:
                break
            ch = self.src[self.i]

            if ch == '\r':
                self.bump()
                continue

            if ch == '\n':
                if self.bracket == 0:
                    self.add('newline', '', self.line)
                self.bump()
                at_bol = self.bracket == 0
                continue

            if ch == '\\' and self.peek(1) == '\n':
                self.bump()
                self.bump()
                continued = True
                at_bol = False
                continue

            if ch == '#':
                while self.i < self.n and self.src[self.i] != '\n':
                    self.bump()
                continue

            if self._starts_string():
                self._string()
                continue

            if ch == '`':
                self._backtick()
                continue

            if _is_ident_start(ch):
                self._ident(as_token=True)
                continue

            if ch in '([{':
                self.bracket += 1
                self.add('op', ch, self.line)
                self.bump()
                continue
            if ch in ')]}':
                if self.bracket:
                    self.bracket -= 1
                self.add('op', ch, self.line)
                self.bump()
                continue
            if ch in ':@;':
                self.add('op', ch, self.line)
                self.bump()
                continue

            self.bump()

        while len(self.indents) > 1:
            self.indents.pop()
            self.add('dedent', '', self.line)

    def _line_start(self):
        """Consume a blank/comment line, or the indent of a code line.

        Returns True when the line had no code (caller stays at bol).
        """
        while self.i < self.n and self.src[self.i] in ' \t\r':
            self.bump()
        if self.i >= self.n or self.src[self.i] in '\n#':
            while self.i < self.n and self.src[self.i] != '\n':
                self.bump()
            if self.i < self.n and self.src[self.i] == '\n':
                self.bump()
            return True

        col = self.col
        if col > self.indents[-1]:
            self.indents.append(col)
            self.add('indent', '', self.line)
        elif col < self.indents[-1]:
            while len(self.indents) > 1 and col < self.indents[-1]:
                self.indents.pop()
                self.add('dedent', '', self.line)
            if self.indents[-1] != col:
                self.indents.append(col)
                self.add('indent', '', self.line)
        return False

    def _starts_string(self):
        j = self.i
        while j < self.n and self.src[j] in _STRING_PREFIX and (j - self.i) < 4:
            j += 1
        return j < self.n and self.src[j] in '"\''

    def _string(self):
        prefix = ''
        while (self.i < self.n and self.src[self.i] in _STRING_PREFIX
               and len(prefix) < 4 and self._starts_string()):
            if self.src[self.i] in '"\'':
                break
            prefix += self.bump()
        if self.i >= self.n or self.src[self.i] not in '"\'':
            return
        quote = self.bump()
        triple = False
        if (self.i + 1 < self.n and self.src[self.i] == quote
                and self.src[self.i + 1] == quote):
            self.bump()
            self.bump()
            triple = True
        interpolating = ('t' in prefix or 'f' in prefix)
        raw = 'r' in prefix
        end = quote * 3 if triple else quote
        while self.i < self.n:
            ch = self.src[self.i]
            if interpolating and ch == '{':
                if self.peek(1) == '{':
                    self.bump()
                    self.bump()
                    continue
                self._interpolation()
                continue
            if interpolating and ch == '}' and self.peek(1) == '}':
                self.bump()
                self.bump()
                continue
            if not raw and ch == '\\':
                self.bump()
                if self.i < self.n:
                    self.bump()
                continue
            if not triple and ch == '\n':
                return
            if self.src.startswith(end, self.i):
                for _ in end:
                    self.bump()
                return
            self.bump()

    def _interpolation(self):
        # Caller is on `{`. Names inside the expression are references, but
        # they are not definitions and must not affect the statement parser.
        self.bump()
        depth = 1
        while self.i < self.n and depth:
            ch = self.src[self.i]
            if self._starts_string():
                self._string()
                continue
            if ch == '`':
                self._backtick(as_token=False)
                continue
            if ch == '#':
                while self.i < self.n and self.src[self.i] != '\n':
                    self.bump()
                continue
            if _is_ident_start(ch):
                self._ident(as_token=False)
                continue
            if ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                self.bump()
                if depth == 0:
                    return
                continue
            self.bump()

    def _backtick(self, as_token=True):
        line = self.line
        self.bump()
        start = self.i
        while self.i < self.n and self.src[self.i] not in '`\n':
            self.bump()
        content = self.src[start:self.i]
        closed = self.i < self.n and self.src[self.i] == '`'
        if closed:
            self.bump()
        if closed and _is_plain_ident(content):
            self.spans.append((start, start + len(content)))
            if as_token:
                self.add('ident', content, line)

    def _ident(self, as_token):
        start = self.i
        line = self.line
        self.bump()
        while self.i < self.n and _is_ident_cont(self.src[self.i]):
            self.bump()
        text = self.src[start:self.i]
        if text in KEYWORDS:
            if as_token:
                self.add('kw', text, line)
            return
        self.spans.append((start, self.i))
        if as_token:
            self.add('ident', text, line)


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


def tokenize_source(src):
    """Return the Elixir token stream for a Mojo source string."""
    lexer = Lexer(src)
    lexer.run()
    return _stream(src, lexer.spans)


def reference_names(src):
    """Return (line, name) for every reference identifier, in order."""
    lexer = Lexer(src)
    lexer.run()
    names = []
    for start, end in lexer.spans:
        line = src.count('\n', 0, start) + 1
        names.append((line, src[start:end]))
    return names


class Parser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.i = 0
        self.scope = ['module']
        self.pending = None
        self.defs = []

    def eof(self):
        return self.i >= len(self.tokens)

    def peek(self, k=0):
        j = self.i + k
        if j < len(self.tokens):
            return self.tokens[j]
        return None

    def advance(self):
        tok = self.tokens[self.i]
        self.i += 1
        return tok

    def at_kw(self, names, k=0):
        tok = self.peek(k)
        if isinstance(names, str):
            names = (names,)
        return tok is not None and tok.kind == 'kw' and tok.text in names

    def at_op(self, text):
        tok = self.peek()
        return tok is not None and tok.kind == 'op' and tok.text == text

    def enclosing(self):
        for scope in reversed(self.scope):
            if scope != 'other':
                return scope
        return 'module'

    def parse(self):
        while not self.eof():
            tok = self.peek()
            if tok.kind == 'newline':
                self.advance()
                continue
            if tok.kind == 'dedent':
                self.pending = None
                if len(self.scope) > 1:
                    self.scope.pop()
                self.advance()
                continue
            if tok.kind == 'indent':
                self.scope.append(self.pending or 'other')
                self.pending = None
                self.advance()
                continue
            self.pending = None
            before = self.i
            self._statement()
            if self.i == before:
                self.advance()
        return self.defs

    def _statement(self):
        while self.at_op('@'):
            self._decorator()
        if self.peek() is None or self.peek().kind in ('indent', 'dedent', 'newline'):
            return
        if self.at_kw('async') and self.at_kw(_DECL_FUNCS, 1):
            self.advance()
        if self.at_kw(_DECL_FUNCS):
            self._function()
            return
        if self.at_kw('struct'):
            self._type_decl('struct', 'struct')
            return
        if self.at_kw('trait'):
            self._type_decl('trait', 'trait')
            return
        if self.at_kw('alias'):
            self._binding('alias')
            return
        if self.at_kw('comptime'):
            self._comptime()
            return
        if self.at_kw(('var', 'let', 'ref')):
            self._var()
            return
        if self.at_kw(_SUITE_START):
            self.advance()
            self._header_suite('other')
            return
        self._simple()

    def _function(self):
        self.advance()
        name, line = self._take_name()
        if name:
            kind = 'method' if self.enclosing() in ('struct', 'trait') else 'function'
            self.defs.append((name, kind, line))
        # The body is a function scope even for methods, so fields stay at
        # the struct indent and locals are not members.
        self._header_suite('function')

    def _type_decl(self, keyword, scope_kind):
        self.advance()
        name, line = self._take_name()
        if name:
            self.defs.append((name, keyword, line))
        self._header_suite(scope_kind)

    def _binding(self, kind):
        self.advance()
        name, line = self._take_name()
        if name and self.enclosing() in _BINDING_SCOPES:
            self.defs.append((name, kind, line))
        self._simple()

    def _comptime(self):
        self.advance()
        if self.at_kw(('if', 'for', 'else')):
            self.advance()
            self._header_suite('other')
            return
        if self.at_kw('assert'):
            self._simple()
            return
        name, line = self._take_name()
        if name and self.enclosing() in _BINDING_SCOPES:
            self.defs.append((name, 'comptime', line))
        self._simple()

    def _var(self):
        self.advance()
        name, line = self._take_name()
        scope = self.enclosing()
        if name and scope in _BINDING_SCOPES:
            kind = 'variable' if scope == 'module' else 'member'
            self.defs.append((name, kind, line))
        self._simple()

    def _take_name(self):
        tok = self.peek()
        if tok is not None and tok.kind == 'ident' and _is_plain_ident(tok.text):
            self.advance()
            return tok.text, tok.line
        return None, None

    def _decorator(self):
        # `@name`, `@name.attr(args)`, or `@name def ...` on one line.
        # Dots are not tokens, so a dotted name is just a run of idents.
        self.advance()  # @
        depth = 0
        while not self.eof():
            tok = self.peek()
            if depth == 0 and tok.kind in ('newline', 'indent', 'dedent'):
                if tok.kind == 'newline':
                    self.advance()
                return
            if depth == 0 and tok.kind == 'kw' and tok.text in (
                    'def', 'fn', 'struct', 'trait', 'alias', 'comptime',
                    'var', 'let', 'ref', 'async'):
                return
            if tok.kind == 'op' and tok.text in '([{':
                depth += 1
                self.advance()
                continue
            if tok.kind == 'op' and tok.text in ')]}':
                if depth:
                    depth -= 1
                self.advance()
                continue
            self.advance()

    def _header_suite(self, scope_kind):
        depth = 0
        while not self.eof():
            tok = self.peek()
            if tok.kind == 'newline' and depth == 0:
                self.advance()
                return
            if tok.kind in ('indent', 'dedent') and depth == 0:
                return
            if tok.kind == 'op' and tok.text in '([{':
                depth += 1
                self.advance()
            elif tok.kind == 'op' and tok.text in ')]}':
                if depth:
                    depth -= 1
                self.advance()
            elif tok.kind == 'op' and tok.text == ':' and depth == 0:
                self.advance()
                nxt = self.peek()
                if nxt is not None and nxt.kind not in ('newline', 'indent', 'dedent'):
                    self._simple()
                    return
                if nxt is not None and nxt.kind == 'newline':
                    self.advance()
                self.pending = scope_kind
                return
            else:
                self.advance()

    def _simple(self):
        depth = 0
        while not self.eof():
            tok = self.peek()
            if tok.kind == 'newline' and depth == 0:
                self.advance()
                return
            if tok.kind in ('indent', 'dedent') and depth == 0:
                return
            if tok.kind == 'op' and tok.text == ';' and depth == 0:
                self.advance()
                return
            if tok.kind == 'op' and tok.text in '([{':
                depth += 1
            elif tok.kind == 'op' and tok.text in ')]}':
                if depth:
                    depth -= 1
            self.advance()


def parse_defs(src):
    """Return (name, kind, line) definitions in source order.

    kind is one of function, method, struct, trait, alias, comptime,
    variable, member.
    """
    lexer = Lexer(src)
    lexer.run()
    return Parser(lexer.tokens).parse()


def format_defs(defs):
    if not defs:
        return ''
    lines = []
    for name, kind, line in defs:
        if not _is_plain_ident(name) or any(ch.isspace() for ch in name):
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
        # Keep indexing going: a bad blob must not abort the update thread.
        sys.stderr.write(
            f'tokenize-mojo.py: {exc.__class__.__name__}: {exc}\n')
        if defs_mode:
            text = ''
        else:
            text = src.replace('\n', '\001')
    out = text.encode('utf-8', errors='surrogateescape')
    if not out.endswith(b'\n'):
        out += b'\n'
    sys.stdout.buffer.write(out)


if __name__ == '__main__':
    main()
