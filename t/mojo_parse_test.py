#!/usr/bin/env python3
# Parser checks for the Mojo family. Indexing coverage lives in 100-basic.t.
#
# SPDX-License-Identifier: AGPL-3.0-or-later

import importlib.util
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

spec = importlib.util.spec_from_file_location(
    'tokenize_mojo', os.path.join(ROOT, 'tokenize-mojo.py'))
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

from elixir.data import DefList


def restore(src):
    text = mod.tokenize_source(src)
    if not text.endswith('\n'):
        text += '\n'
    parts = text.split('\n')
    del parts[-1]
    out = []
    for index, part in enumerate(parts):
        if index % 2 == 0:
            out.append(part.replace('\001', '\n'))
        else:
            out.append(part)
    return ''.join(out)


SNIPPET = '''\
"""docstring struct Fake:
    var fake_field: Int
def fake_fn():
    pass
"""

@inline def same_line(x: Int) -> Int:
    return x

@fieldwise_init
struct Point:
    var x: Int
    var y: Int

    def norm(self) -> Int:
        var local_name = x
        return local_name

fn legacy(a: Int) -> Int:
    var hidden = a
    return hidden

alias OldName = Int
comptime NewName = Int
var module_var: Int = 1

trait Shape:
    def area(self) -> Int:
        ...

def after():
    comptime local_alias = 1
    var also_local = 2
    match also_local:
        case 1:
            var buried = 1

var alpha = 1; var beta = 2

comptime Scalar = SIMD[
    _, length=__mlir_attr[`#lit.struct<{_mlir_value = 1}> : `, SIMDLength]
]

def still_here():
    var made = still_here()
    var s = t"hi {still_here()}"
    var t = "still_here in a string"
    return made
'''

EXPECTED = [
    ('same_line', 'function', 7),
    ('Point', 'struct', 11),
    ('x', 'member', 12),
    ('y', 'member', 13),
    ('norm', 'method', 15),
    ('legacy', 'function', 19),
    ('OldName', 'alias', 23),
    ('NewName', 'comptime', 24),
    ('module_var', 'variable', 25),
    ('Shape', 'trait', 27),
    ('area', 'method', 28),
    ('after', 'function', 31),
    ('alpha', 'variable', 38),
    ('beta', 'variable', 38),
    ('Scalar', 'comptime', 40),
    ('still_here', 'function', 44),
]


def main():
    failed = 0

    def check(cond, message):
        nonlocal failed
        if not cond:
            print(message, file=sys.stderr)
            failed += 1

    defs = mod.parse_defs(SNIPPET)
    check(defs == EXPECTED, f'defs mismatch:\n got {defs}\n expected {EXPECTED}')

    if restore(SNIPPET) != SNIPPET:
        check(False, 'token stream does not round-trip')

    names = mod.reference_names(SNIPPET)
    still = [line for line, name in names if name == 'still_here']
    check(still == [44, 45, 46], f'still_here refs {still}')
    check(all(name != 'fake_fn' for _, name in names), 'docstring name leaked')
    check(all(name != 'fake_field' for _, name in names), 'docstring field leaked')
    keywords = {'def', 'fn', 'struct', 'trait', 'var', 'alias', 'comptime',
                'if', 'for', 'while', 'return', 'mut', 'out', 'owned'}
    leaked = sorted({name for _, name in names if name in keywords})
    check(not leaked, f'keywords indexed as refs: {leaked}')

    # Storage letters used by definitions.db must survive a pack/unpack.
    stored = DefList()
    for name, kind, line in defs:
        stored.append(1, kind, line, 'J')
    unpacked = [(kind, line) for _id, kind, line, family in stored.iter()]
    expect_stored = [(kind, line) for _name, kind, line in EXPECTED]
    check(unpacked == expect_stored and all(
        family == 'J' for _id, _kind, _line, family in stored.iter()
    ), f'DefList dropped a Mojo kind: {unpacked}')

    # Garbage must not raise, and a broken file stays viewable.
    for blob in ('\x00\xff', 'def foo(:', 'struct `unterminated', 't"open {x'):
        try:
            mod.parse_defs(blob)
            mod.tokenize_source(blob)
        except Exception as exc:
            check(False, f'raised on {blob!r}: {exc}')

    sys.exit(failed)


if __name__ == '__main__':
    main()
