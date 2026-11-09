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

"""Split TypeScript/JavaScript source into the token stream used by script.sh.

Reads source on stdin. An optional path argument selects JSX scanning for
.jsx/.tsx files. The output alternates separator and identifier lines.
Newlines inside separators are encoded as \\001 so the indexer can count
lines, and concatenating the pieces reproduces the original file.

Comments, string literals, template-literal text, and regex literals stay in
the separator stream. Names inside ${...} and JSX expressions are emitted.
JSX text is not code. .ts/.js files are not scanned as JSX, so '<' stays
available for generics and assertions.
"""

import sys


# Keywords that can be followed by an expression, a regex, or JSX.
# Other identifiers (including 'this' and 'function') are values, so a
# following '/' is division and a following '<' is a comparison or generic.
EXPR_KEYWORDS = frozenset({
    'await',
    'case',
    'delete',
    'do',
    'else',
    'extends',
    'in',
    'instanceof',
    'new',
    'of',
    'return',
    'throw',
    'typeof',
    'void',
    'yield',
})


def _jsx_path(path):
    name = path.lower()
    return name.endswith('.jsx') or name.endswith('.tsx')


class Scanner:
    def __init__(self, src, jsx):
        self.src = src
        self.n = len(src)
        self.i = 0
        self.jsx = jsx
        self.prev = 'other'
        self.idents = []

    def peek(self, k=0):
        j = self.i + k
        if j < self.n:
            return self.src[j]
        return ''

    def is_ident_start(self, char):
        return bool(char) and (char.isalpha() or char in '_$')

    def is_ident_cont(self, char):
        return bool(char) and (char.isalnum() or char in '_$')

    def scan(self):
        if self.src.startswith('#!'):
            self.scan_line_comment()
        self.scan_code(False)

    def render(self):
        out = []
        last = 0
        for start, end in self.idents:
            out.append(self.src[last:start].replace('\n', '\001'))
            out.append('\n')
            out.append(self.src[start:end])
            out.append('\n')
            last = end
        out.append(self.src[last:].replace('\n', '\001'))
        return ''.join(out)

    def scan_code(self, stop_brace):
        depth = 0
        while self.i < self.n:
            char = self.src[self.i]
            if char.isspace():
                self.i += 1
                continue
            if char == '/' and self.peek(1) == '/':
                self.scan_line_comment()
                continue
            if char == '/' and self.peek(1) == '*':
                self.scan_block_comment()
                continue
            if char == '/' and self.prev != 'value':
                self.scan_regex()
                continue
            if char in '"\'':
                self.scan_quoted()
                self.prev = 'value'
                continue
            if char == '`':
                self.scan_template()
                self.prev = 'value'
                continue
            if char == '<' and self.jsx and self.prev != 'value' and self.looks_like_jsx():
                self.scan_jsx_element()
                self.prev = 'value'
                continue
            if char == '{':
                depth += 1
                self.i += 1
                self.prev = 'other'
                continue
            if char == '}':
                if stop_brace and depth == 0:
                    return
                if depth > 0:
                    depth -= 1
                self.i += 1
                self.prev = 'value'
                continue
            if char in '+-' and self.peek(1) == char:
                postfix = self.prev == 'value'
                self.i += 2
                self.prev = 'value' if postfix else 'other'
                continue
            if self.is_ident_start(char):
                self.scan_ident()
                continue
            if char.isdigit() or (char == '.' and self.peek(1).isdigit()):
                self.scan_number()
                continue
            self.i += 1
            if char in ')]}':
                self.prev = 'value'
            else:
                self.prev = 'other'

    def scan_line_comment(self):
        while self.i < self.n and self.src[self.i] != '\n':
            self.i += 1

    def scan_block_comment(self):
        self.i += 2
        while self.i + 1 < self.n:
            if self.src[self.i] == '*' and self.src[self.i + 1] == '/':
                self.i += 2
                return
            self.i += 1
        self.i = self.n

    def scan_regex(self):
        start = self.i
        source = self.src
        i = start + 1
        in_class = False
        while i < self.n:
            char = source[i]
            if char == '\\':
                i += 2
                continue
            if char == '\n':
                self.i = start + 1
                self.prev = 'other'
                return
            if char == '[':
                in_class = True
                if i + 1 < self.n and source[i + 1] == '^':
                    i += 1
                if i + 1 < self.n and source[i + 1] == ']':
                    i += 1
            elif char == ']' and in_class:
                in_class = False
            elif char == '/' and not in_class:
                i += 1
                while i < self.n and source[i].isascii() and source[i].isalpha():
                    i += 1
                self.i = i
                self.prev = 'value'
                return
            i += 1
        self.i = self.n
        self.prev = 'value'

    def scan_quoted(self):
        quote = self.src[self.i]
        i = self.i + 1
        source = self.src
        while i < self.n:
            char = source[i]
            if char == '\\':
                i += 2
                continue
            if char == '\n':
                self.i = i
                return
            if char == quote:
                self.i = i + 1
                return
            i += 1
        self.i = self.n

    def scan_template(self):
        self.i += 1
        while self.i < self.n:
            char = self.src[self.i]
            if char == '\\':
                self.i += 2
                continue
            if char == '`':
                self.i += 1
                return
            if char == '$' and self.peek(1) == '{':
                self.i += 2
                self.scan_code(True)
                if self.peek() == '}':
                    self.i += 1
                continue
            self.i += 1

    def scan_ident(self):
        start = self.i
        self.i += 1
        while self.i < self.n and self.is_ident_cont(self.src[self.i]):
            self.i += 1
        text = self.src[start:self.i]
        self.idents.append((start, self.i))
        if text in EXPR_KEYWORDS:
            self.prev = 'other'
        else:
            self.prev = 'value'

    def scan_number(self):
        source = self.src
        i = self.i
        n = self.n
        if source[i] == '0' and i + 1 < n and source[i + 1] in 'xX':
            i += 2
            while i < n and source[i] in '0123456789abcdefABCDEF_':
                i += 1
        elif source[i] == '0' and i + 1 < n and source[i + 1] in 'bB':
            i += 2
            while i < n and source[i] in '01_':
                i += 1
        elif source[i] == '0' and i + 1 < n and source[i + 1] in 'oO':
            i += 2
            while i < n and source[i] in '01234567_':
                i += 1
        else:
            if source[i] == '.':
                i += 1
            while i < n and (source[i].isdigit() or source[i] == '_'):
                i += 1
            if source[self.i] != '.' and i < n and source[i] == '.':
                i += 1
                while i < n and (source[i].isdigit() or source[i] == '_'):
                    i += 1
            if i < n and source[i] in 'eE':
                j = i + 1
                if j < n and source[j] in '+-':
                    j += 1
                if j < n and source[j].isdigit():
                    i = j + 1
                    while i < n and (source[i].isdigit() or source[i] == '_'):
                        i += 1
            if i < n and source[i] == 'n':
                i += 1
        self.i = i
        self.prev = 'value'

    def looks_like_jsx(self):
        j = self.i + 1
        source = self.src
        n = self.n
        if j >= n:
            return False
        if source[j] == '>':
            return True
        if not self.is_ident_start(source[j]):
            return False
        k = j + 1
        while k < n and self.is_ident_cont(source[k]):
            k += 1
        while k < n and source[k].isspace():
            k += 1
        if k >= n:
            return True
        # <T,>, <T = U>, and <T extends U> are type parameters, including
        # generic arrows. TSX requires the trailing comma so <T> stays JSX.
        if source[k] in ',=':
            return False
        if source.startswith('extends', k) and (
                k + 7 >= n or not self.is_ident_cont(source[k + 7])):
            return False
        return True

    def scan_jsx_element(self):
        """Consume one element or closing tag. Return 'close' for </...>."""
        self.i += 1
        if self.peek() == '>':
            self.i += 1
            self.scan_jsx_children()
            return 'open'
        if self.peek() == '/':
            self.i += 1
            self.scan_jsx_name()
            self.skip_ws_and_comments()
            if self.peek() == '>':
                self.i += 1
            return 'close'
        self.scan_jsx_name()
        while self.i < self.n:
            self.skip_ws_and_comments()
            if self.i >= self.n:
                break
            char = self.src[self.i]
            if char == '>':
                self.i += 1
                self.scan_jsx_children()
                return 'open'
            if char == '/' and self.peek(1) == '>':
                self.i += 2
                return 'open'
            if char == '{':
                self.scan_brace_expr()
                continue
            if char == '<':
                self.scan_type_args()
                continue
            if self.is_ident_start(char):
                self.scan_jsx_name()
                self.skip_ws_and_comments()
                if self.peek() == '=':
                    self.i += 1
                    self.skip_ws_and_comments()
                    self.scan_jsx_attr_value()
                continue
            self.i += 1
        return 'open'

    def scan_jsx_children(self):
        while self.i < self.n:
            char = self.src[self.i]
            if char == '<':
                nxt = self.peek(1)
                if nxt == '/' or nxt == '>' or self.is_ident_start(nxt):
                    if self.scan_jsx_element() == 'close':
                        return
                    continue
            if char == '{':
                self.scan_brace_expr()
                continue
            self.i += 1

    def scan_jsx_name(self):
        while self.i < self.n and self.is_ident_start(self.src[self.i]):
            self.scan_ident()
            if self.peek() == '.':
                self.i += 1
                continue
            return

    def scan_jsx_attr_value(self):
        char = self.peek()
        if char in '"\'':
            self.scan_quoted()
        elif char == '{':
            self.scan_brace_expr()
        elif char == '<':
            self.scan_jsx_element()
        elif char == '`':
            self.scan_template()

    def scan_brace_expr(self):
        self.i += 1
        self.scan_code(True)
        if self.peek() == '}':
            self.i += 1

    def scan_type_args(self):
        self.i += 1
        depth = 1
        while self.i < self.n and depth > 0:
            char = self.src[self.i]
            if char in '"\'':
                self.scan_quoted()
                continue
            if char == '`':
                self.scan_template()
                continue
            if char == '/' and self.peek(1) == '/':
                self.scan_line_comment()
                continue
            if char == '/' and self.peek(1) == '*':
                self.scan_block_comment()
                continue
            if self.is_ident_start(char):
                self.scan_ident()
                continue
            if char == '<':
                depth += 1
                self.i += 1
                continue
            if char == '=' and self.peek(1) == '>':
                self.i += 2
                continue
            if char == '>':
                depth -= 1
                self.i += 1
                continue
            self.i += 1

    def skip_ws_and_comments(self):
        while self.i < self.n:
            char = self.src[self.i]
            if char.isspace():
                self.i += 1
                continue
            if char == '/' and self.peek(1) == '/':
                self.scan_line_comment()
                continue
            if char == '/' and self.peek(1) == '*':
                self.scan_block_comment()
                continue
            return


def tokenize_source(src, jsx=False):
    """Return the Elixir token stream for a TypeScript or JavaScript string."""
    scanner = Scanner(src, jsx)
    scanner.scan()
    return scanner.render()


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else ''
    raw = sys.stdin.buffer.read()
    try:
        src = raw.decode('utf-8')
    except UnicodeDecodeError:
        src = raw.decode('utf-8', errors='surrogateescape')
    text = tokenize_source(src, jsx=_jsx_path(path))
    out = text.encode('utf-8', errors='surrogateescape')
    if not out.endswith(b'\n'):
        out += b'\n'
    sys.stdout.buffer.write(out)


if __name__ == '__main__':
    main()
