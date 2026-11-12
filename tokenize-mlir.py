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

"""Tokenize MLIR and extract named symbols.

Universal Ctags 5.9 has no MLIR parser. A line regex cannot tell a
defining ``tt.func @name`` from a use ``tt.call @name`` (or from
``llvm.mlir.addressof @name``) without listing op spellings, and it
would also treat comments and strings as code. SSA names (``%value``)
are not symbols.

Reference stream (default): ``@symbol`` names, bare attribute aliases
(``#Name``, not ``#dialect.attr``), and bare type aliases (``!Name``).
The sigil stays in the separator so a source page links the name.
``%`` SSA values and ``^`` block labels are not references.

Definitions (``--defs``):

* ``@symbol`` on an op whose name is ``func`` / ``module`` / ``global``,
  or ends in ``.func`` / ``.module`` / ``.global`` / ``.declare_reduction``,
  or is an IRDL ``irdl.dialect`` / ``irdl.operation`` / ``irdl.type`` /
  ``irdl.attribute``. Linkage and visibility words
  (``public``, ``external``, ``constant``, ...) may sit between the op
  and the symbol. ``*.call`` and ``*.addressof`` are uses.
* generic ``sym_name = "name"``
* top-level ``#Name =`` attribute aliases and ``!Name =`` type aliases

``--defs`` on a file with no symbols prints zero bytes.
"""

import sys

# Words that may appear between a defining op and its @symbol.
_VISIBILITY = frozenset({
    'public', 'private', 'nested', 'external', 'internal', 'constant',
    'weak', 'linkonce', 'linkonce_odr', 'common', 'appending',
    'extern_weak', 'available_externally', 'hidden', 'protected',
    'default', 'dso_local', 'dso_preemptable', 'local_unnamed_addr',
    'unnamed_addr', 'thread_local', 'externally_initialized',
    'linker_private', 'linker_private_weak', 'weak_odr', 'external_weak',
    'local',
})

_BASE_KINDS = {
    'func': 'function',
    'module': 'namespace',
    'global': 'variable',
    'declare_reduction': 'function',
}

_IRDL_KINDS = {
    'dialect': 'namespace',
    'operation': 'function',
    'type': 'typedef',
    'attribute': 'alias',
}


def kind_for_op(name):
    """Return a definition kind, or None when @symbol is a use."""
    if not name:
        return None
    parts = name.split('.')
    base = parts[-1]
    if parts[0] == 'irdl' and base in _IRDL_KINDS and len(parts) == 2:
        return _IRDL_KINDS[base]
    if base in _BASE_KINDS:
        return _BASE_KINDS[base]
    return None


def _acceptable(name):
    if not name or len(name) < 2:
        return False
    return not any(ch.isspace() for ch in name)


def _unescape(text):
    out = []
    i = 0
    while i < len(text):
        if text[i] == '\\' and i + 1 < len(text):
            nxt = text[i + 1]
            out.append({'n': '\n', 't': '\t', 'r': '\r'}.get(nxt, nxt))
            i += 2
            continue
        out.append(text[i])
        i += 1
    return ''.join(out)


def _is_ident_start(ch):
    return ch.isascii() and (ch.isalpha() or ch == '_')


def _is_bare_cont(ch):
    return ch.isascii() and (ch.isalnum() or ch in '_$.')


def _is_symbol_cont(ch):
    return ch.isascii() and (ch.isalnum() or ch in '_$.-')


class Scanner:
    def __init__(self, src):
        self.src = src
        self.n = len(src)
        self.i = 0
        self.line = 1
        self.depth = 0
        self.pending_op = None
        self.expect_sym = False
        self.expect_sym_string = False
        self.generic_op = None
        self.spans = []
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

    def peek_nonws(self):
        j = self.i
        while j < self.n and self.src[j] in ' \t\r\n':
            j += 1
        if j < self.n:
            return self.src[j]
        return ''

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
            if ch == '"':
                self._on_string(self._string())
                continue
            if ch == '@':
                self._symbol()
                continue
            if ch in '#!':
                self._sigil(ch)
                continue
            if ch == '%':
                self.bump()
                self._suffix()
                self._clear_pending()
                continue
            if ch == '^':
                self.bump()
                self._suffix()
                self._clear_pending()
                continue
            if _is_ident_start(ch):
                self._bare_ident()
                continue
            if ch.isdigit():
                self._number()
                self._clear_pending()
                continue
            self._punct(ch)
        return self.spans, self.defs

    def _clear_pending(self):
        self.pending_op = None
        self.expect_sym = False
        self.expect_sym_string = False

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

    def _string(self):
        """Consume a string. Return (content, inner_start, inner_end, line)."""
        line = self.line
        self.bump()
        start = self.i
        chars = []
        while self.i < self.n:
            ch = self.src[self.i]
            if ch == '\\':
                chars.append(self.bump())
                if self.i < self.n:
                    chars.append(self.bump())
                continue
            if ch == '"':
                end = self.i
                self.bump()
                return ''.join(chars), start, end, line
            if ch == '\n':
                end = self.i
                return ''.join(chars), start, end, line
            chars.append(self.bump())
        return ''.join(chars), start, self.i, line

    def _on_string(self, packed):
        raw, start, end, line = packed
        if self.expect_sym_string:
            name = _unescape(raw)
            if _acceptable(name) and '\\' not in raw:
                self.spans.append((start, end))
                kind = kind_for_op(self.generic_op) or 'function'
                self.defs.append((name, kind, line))
            elif _acceptable(name):
                self.defs.append((name, kind_for_op(self.generic_op) or 'function', line))
            self.expect_sym_string = False
            self.pending_op = None
            return
        if self.peek_nonws() == '(':
            self.generic_op = _unescape(raw)
        self.expect_sym = False

    def _suffix(self):
        if self.i >= self.n:
            return
        ch = self.src[self.i]
        if ch.isdigit():
            while self.i < self.n and self.src[self.i].isdigit():
                self.bump()
            return
        if _is_symbol_cont(ch):
            while self.i < self.n and _is_symbol_cont(self.src[self.i]):
                self.bump()

    def _symbol(self):
        line = self.line
        self.bump()  # @
        if self.i < self.n and self.src[self.i] == '"':
            raw, start, end, line = self._string()
            name = _unescape(raw)
            if _acceptable(name) and '\\' not in raw and end > start:
                self.spans.append((start, end))
            if self.pending_op and kind_for_op(self.pending_op) and _acceptable(name):
                self.defs.append((name, kind_for_op(self.pending_op), line))
        else:
            start = self.i
            self._suffix()
            end = self.i
            name = self.src[start:end]
            if name and end > start and not any(ch.isspace() for ch in name):
                self.spans.append((start, end))
            if self.pending_op and kind_for_op(self.pending_op) and _acceptable(name):
                self.defs.append((name, kind_for_op(self.pending_op), line))
        self._clear_pending()

    def _sigil(self, sigil):
        line = self.line
        self.bump()
        if self.i >= self.n or not _is_ident_start(self.src[self.i]):
            self._clear_pending()
            return
        start = self.i
        while self.i < self.n and _is_bare_cont(self.src[self.i]):
            self.bump()
        end = self.i
        name = self.src[start:end]
        self._clear_pending()
        if not name or '.' in name:
            return
        self.spans.append((start, end))
        if self.peek_nonws() == '=' and self.depth == 0 and _acceptable(name):
            kind = 'alias' if sigil == '#' else 'typedef'
            self.defs.append((name, kind, line))

    def _bare_ident(self):
        chars = []
        while self.i < self.n and _is_bare_cont(self.src[self.i]):
            # bare-id cannot start with '.' ; the caller checked the start.
            chars.append(self.bump())
        text = ''.join(chars)
        self.expect_sym_string = False
        if self.pending_op and text in _VISIBILITY:
            self.expect_sym = False
            return
        self.pending_op = text
        self.expect_sym = text == 'sym_name'

    def _number(self):
        while self.i < self.n and (self.src[self.i].isdigit() or self.src[self.i] == '_'):
            self.bump()
        if self.peek() == '.' and self.peek(1).isdigit():
            self.bump()
            while self.i < self.n and self.src[self.i].isdigit():
                self.bump()

    def _punct(self, ch):
        self.bump()
        if ch in '{[(':
            self.depth += 1
        elif ch in '}])':
            if self.depth:
                self.depth -= 1
        if ch == '=' and self.expect_sym:
            self.expect_sym_string = True
            self.expect_sym = False
            self.pending_op = None
            return
        self._clear_pending()


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


def _scan(src):
    return Scanner(src).run()


def tokenize_source(src):
    spans, _defs = _scan(src)
    return _stream(src, spans)


def reference_names(src):
    spans, _defs = _scan(src)
    names = []
    for start, end in spans:
        line = src.count('\n', 0, start) + 1
        names.append((line, src[start:end]))
    return names


def parse_defs(src):
    _spans, defs = _scan(src)
    return defs


def format_defs(defs):
    if not defs:
        return ''
    lines = []
    for name, kind, line in defs:
        if not _acceptable(name):
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
            f'tokenize-mlir.py: {exc.__class__.__name__}: {exc}\n')
        text = '' if defs_mode else src.replace('\n', '\001')
    out = text.encode('utf-8', errors='surrogateescape')
    # Same contract as tokenize-mojo.py: --defs with nothing to report
    # is zero bytes, and tokenize mode always ends with a newline.
    if (out or not defs_mode) and not out.endswith(b'\n'):
        out += b'\n'
    sys.stdout.buffer.write(out)


if __name__ == '__main__':
    main()
