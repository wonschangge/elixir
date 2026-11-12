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

"""Const items and unions that Universal Ctags 5.9 does not tag.

ctags 5.9's Rust parser tags functions, structs, enums, traits (as
interface), impl methods, macros, modules, type aliases, and statics.
It has no const kind and no union kind. Function-local ``let`` bindings
are already ignored by ctags.

This supplement emits ``name constant line`` and ``name union line`` for:

* ``const NAME`` at module scope, or directly in a ``mod``, ``trait``, or
  ``impl`` (associated consts)
* ``union NAME`` in those same positions

It does not emit function-local consts, const generic parameters
(``impl<const N: usize>``), ``const fn``, or names that appear only in
comments, strings, or attributes. A file with nothing to report prints
zero bytes.
"""

import sys

_ITEM_BLOCKS = frozenset({'trait', 'impl', 'mod'})
# A pending item (`impl`, `fn`, ...) must survive the `for` in
# `impl Foo for Bar` and the `for` in `fn f(x: for<'a> ...)`.
_KEEP_PENDING = frozenset({
    'fn', 'trait', 'impl', 'mod', 'struct', 'enum', 'union', 'const',
})
_BLOCK_KEYWORDS = frozenset({
    'fn', 'trait', 'impl', 'mod', 'struct', 'enum', 'union',
    'match', 'if', 'while', 'loop', 'for', 'unsafe',
})


def _is_ident_char(ch):
    return ch.isascii() and (ch.isalnum() or ch == '_')


class Scanner:
    def __init__(self, src):
        self.src = src
        self.n = len(src)
        self.i = 0
        self.line = 1
        self.stack = []
        self.pending = None
        self.prev = None
        self.paren = 0
        self.bracket = 0
        self.expect_const_name = False
        self.pending_const = None
        self.expect_union_name = False
        self.defs = []

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
            if ch == '/' and self.peek(1) == '/':
                self._line_comment()
                continue
            if ch == '/' and self.peek(1) == '*':
                self._block_comment()
                continue
            if ch in 'bcr"' and self._starts_string():
                self._string()
                continue
            if ch == "'":
                self._char_or_lifetime()
                continue
            if _is_ident_char(ch) and not ch.isdigit():
                self._ident()
                continue
            if ch.isdigit():
                self._number()
                continue
            self._punct(ch)
        return self.defs

    def _item_context(self):
        if self.paren or self.bracket:
            return False
        if self.prev in (('punct', '<'), ('punct', ',')):
            return False
        if not self.stack:
            return True
        return self.stack[-1] in _ITEM_BLOCKS

    def _line_comment(self):
        while self.i < self.n and self.src[self.i] != '\n':
            self.bump()

    def _block_comment(self):
        self.bump()
        self.bump()
        depth = 1
        while self.i < self.n and depth:
            if self.src[self.i] == '/' and self.peek(1) == '*':
                depth += 1
                self.bump()
                self.bump()
                continue
            if self.src[self.i] == '*' and self.peek(1) == '/':
                depth -= 1
                self.bump()
                self.bump()
                continue
            self.bump()

    def _starts_string(self):
        j = self.i
        src = self.src
        if j < self.n and src[j] in 'bc':
            j += 1
        if j < self.n and src[j] == 'r':
            j += 1
        while j < self.n and src[j] == '#':
            j += 1
        if j < self.n and src[j] == '"':
            return True
        return (self.i < self.n and src[self.i] == 'b'
                and self.peek(1) == "'")

    def _string(self):
        if self.src[self.i] == 'b' and self.peek(1) == "'":
            self.bump()
            self._char_or_lifetime()
            return
        if self.src[self.i] in 'bc':
            nxt = self.peek(1)
            if nxt == 'r' or nxt == '"' or nxt == '#':
                self.bump()
        if self.i < self.n and self.src[self.i] == 'r':
            self.bump()
        hashes = 0
        while self.i < self.n and self.src[self.i] == '#':
            hashes += 1
            self.bump()
        if self.i >= self.n or self.src[self.i] != '"':
            return
        self.bump()
        end = '"' + ('#' * hashes)
        while self.i < self.n:
            if self.src.startswith(end, self.i):
                for _ in end:
                    self.bump()
                return
            if hashes == 0 and self.src[self.i] == '\\':
                self.bump()
                if self.i < self.n:
                    self.bump()
                continue
            self.bump()

    def _char_or_lifetime(self):
        self.bump()
        if self.i >= self.n:
            return
        if self.src[self.i] == '\\':
            self.bump()
            while self.i < self.n and self.src[self.i] != "'":
                self.bump()
            if self.i < self.n:
                self.bump()
            return
        if self.i + 1 < self.n and self.src[self.i + 1] == "'":
            self.bump()
            self.bump()
            return
        while self.i < self.n and _is_ident_char(self.src[self.i]):
            self.bump()

    def _ident(self):
        start_line = self.line
        chars = []
        while self.i < self.n and _is_ident_char(self.src[self.i]):
            chars.append(self.bump())
        self._on_ident(''.join(chars), start_line)

    def _on_ident(self, text, line):
        if self.expect_const_name:
            self.expect_const_name = False
            if text == 'fn':
                self.pending = 'fn'
            else:
                self.pending_const = (text, line)
            self.prev = ('ident', text)
            return
        if self.expect_union_name:
            self.expect_union_name = False
            self.defs.append((text, 'union', line))
            self.pending = 'union'
            self.prev = ('ident', text)
            return
        if text == 'const' and self._item_context():
            self.expect_const_name = True
            self.prev = ('ident', text)
            return
        if text == 'union' and self._item_context():
            self.expect_union_name = True
            self.prev = ('ident', text)
            return
        if text == 'fn':
            self.pending = 'fn'
        elif text in ('trait', 'impl', 'mod', 'struct', 'enum'):
            self.pending = text
        elif text in _BLOCK_KEYWORDS and self.pending not in _KEEP_PENDING:
            # unsafe fn / unsafe trait still reach the fn/trait arm above
            # on the next identifier and overwrite this.
            self.pending = 'block'
        self.prev = ('ident', text)

    def _number(self):
        while self.i < self.n and (self.src[self.i].isdigit()
                                    or self.src[self.i] == '_'):
            self.bump()
        if (self.peek() == '.' and self.peek(1).isdigit()):
            self.bump()
            while self.i < self.n and (self.src[self.i].isdigit()
                                        or self.src[self.i] == '_'):
                self.bump()
        self.prev = ('punct', '0')

    def _punct(self, ch):
        self.bump()
        if self.expect_const_name or self.expect_union_name:
            self.expect_const_name = False
            self.expect_union_name = False
        if self.pending_const:
            if ch == ':':
                name, line = self.pending_const
                self.defs.append((name, 'constant', line))
                self.pending = 'const'
            self.pending_const = None
        if ch == '{':
            self.stack.append(self.pending or 'block')
            self.pending = None
        elif ch == '}':
            if self.stack:
                self.stack.pop()
            self.pending = None
        elif ch == ';':
            self.pending = None
        elif ch == '(':
            self.paren += 1
        elif ch == ')':
            if self.paren:
                self.paren -= 1
        elif ch == '[':
            self.bracket += 1
        elif ch == ']':
            if self.bracket:
                self.bracket -= 1
        self.prev = ('punct', ch)


def parse_defs(src):
    """Return (name, kind, line) for const items and unions."""
    return Scanner(src).run()


def format_defs(defs):
    if not defs:
        return ''
    lines = []
    for name, kind, line in defs:
        if not name or any(ch.isspace() for ch in name):
            continue
        lines.append(f'{name} {kind} {line}')
    if not lines:
        return ''
    return '\n'.join(lines) + '\n'


def main():
    if len(sys.argv) != 2:
        sys.stderr.write('usage: rust-item-defs.py FILE\n')
        sys.exit(2)
    try:
        raw = open(sys.argv[1], 'rb').read()
    except OSError as exc:
        sys.stderr.write(f'rust-item-defs.py: {exc}\n')
        sys.exit(0)
    try:
        src = raw.decode('utf-8')
    except UnicodeDecodeError:
        src = raw.decode('utf-8', errors='surrogateescape')
    try:
        text = format_defs(parse_defs(src))
    except Exception as exc:
        sys.stderr.write(
            f'rust-item-defs.py: {exc.__class__.__name__}: {exc}\n')
        text = ''
    sys.stdout.buffer.write(text.encode('utf-8', errors='surrogateescape'))


if __name__ == '__main__':
    main()
