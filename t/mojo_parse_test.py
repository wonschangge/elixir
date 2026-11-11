#!/usr/bin/env python3
# Parser checks for the Mojo family. Indexing coverage lives in 100-basic.t.
#
# SPDX-License-Identifier: AGPL-3.0-or-later

import importlib.util
import os
import subprocess
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

    # Empty files, and files that only have comments or top-level
    # statements, have no definitions. --defs must print nothing: a
    # lone newline is one empty field after scriptLines splits, and
    # update.py cannot unpack that into three columns. Normal tokenize
    # mode keeps the historical trailing newline.
    empty_mojo = b''
    no_defs_mojo = '''\
# comment only, not a definition
"""docstring
def not_a_def():
    var fake_field: Int
"""

from helpers import imported_name

print(imported_name)
bare = 1 + 2
if bare:
    also = bare
'''.encode('utf-8')

    check(mod.parse_defs(no_defs_mojo.decode('utf-8')) == [],
          'comment and statement .mojo parsed as having definitions')
    check_defs_cli(check, empty_mojo, 'empty .mojo')
    check_tokenize_cli(check, empty_mojo, 'empty .mojo')
    check_defs_cli(check, no_defs_mojo, 'comment and statement .mojo')
    check_tokenize_cli(check, no_defs_mojo, 'comment and statement .mojo')

    kept = 'def kept():\n    pass\n'.encode('utf-8')
    status, out, err = run_cli(kept, defs=True)
    check(status == 0 and err == b'' and out == b'kept function 1\n',
          f'defs with a real function: {status} {out!r} {err!r}')
    fields = indexer_lines(out)
    check(len(fields) == 1 and fields[0].split(b' ') == [b'kept', b'function', b'1'],
          f'defs line is three fields: {fields!r}')

    sys.exit(failed)


def run_cli(src, defs=False):
    cmd = [sys.executable, os.path.join(ROOT, 'tokenize-mojo.py')]
    if defs:
        cmd.append('--defs')
    proc = subprocess.run(
        cmd, input=src, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return proc.returncode, proc.stdout, proc.stderr


def indexer_lines(blob):
    """Split the way elixir.lib.scriptLines does."""
    parts = blob.split(b'\n')
    del parts[-1]
    return parts


def check_defs_cli(check, src, label):
    status, out, err = run_cli(src, defs=True)
    lines = indexer_lines(out) if status == 0 else None
    check(status == 0 and err == b'' and out == b'' and lines == [],
          f'{label} --defs should be empty, got status={status} '
          f'out={out!r} err={err!r} lines={lines!r}')


def check_tokenize_cli(check, src, label):
    status, out, err = run_cli(src, defs=False)
    text = mod.tokenize_source(src.decode('utf-8'))
    expect = text.encode('utf-8')
    if not expect.endswith(b'\n'):
        expect += b'\n'
    same = status == 0 and err == b'' and out == expect
    check(same,
          f'{label} tokenize bytes differ: status={status} '
          f'out={out!r} expect={expect!r} err={err!r}')
    if not same:
        return
    # The stream the indexer keeps must rebuild the original file.
    parts = out.decode('utf-8').split('\n')
    del parts[-1]
    rebuilt = []
    for index, part in enumerate(parts):
        if index % 2 == 0:
            rebuilt.append(part.replace('\001', '\n'))
        else:
            rebuilt.append(part)
    check(''.join(rebuilt) == src.decode('utf-8'),
          f'{label} tokenize did not round-trip')


if __name__ == '__main__':
    main()
