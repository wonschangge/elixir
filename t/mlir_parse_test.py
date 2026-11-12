#!/usr/bin/env python3
# Parser checks for the MLIR family. Indexing coverage lives in 100-basic.t.
#
# SPDX-License-Identifier: AGPL-3.0-or-later

import importlib.util
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

spec = importlib.util.spec_from_file_location(
    'tokenize_mlir', os.path.join(ROOT, 'tokenize-mlir.py'))
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

from elixir.data import DefList

FIXTURE = os.path.join(ROOT, 't', 'tree', 'mlir', 'add_kernel.mlir')

EXPECTED = [
    ('BlockedLayout', 'alias', 4),
    ('widget_tensor', 'typedef', 5),
    ('add_kernel', 'function', 8),
    ('llvm_helper', 'function', 18),
    ('global_smem', 'variable', 19),
    ('private_fn', 'function', 23),
    ('named_module', 'namespace', 28),
    ('gpu_kernel', 'function', 29),
    ('generic_fn', 'function', 35),
    ('demo_dialect', 'namespace', 39),
    ('demo_type', 'typedef', 40),
    ('demo_attr', 'alias', 41),
    ('demo_op', 'function', 42),
]


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


def main():
    failed = 0

    def check(cond, message):
        nonlocal failed
        if not cond:
            print(message, file=sys.stderr)
            failed += 1

    src = open(FIXTURE, encoding='utf-8').read()
    defs = mod.parse_defs(src)
    check(defs == EXPECTED, f'defs mismatch:\n got {defs}\n expected {EXPECTED}')
    check(restore(src) == src, 'token stream does not round-trip')

    names = mod.reference_names(src)
    add_lines = [line for line, name in names if name == 'add_kernel']
    check(add_lines == [8, 14], f'add_kernel refs {add_lines}')
    check(all(name != 'not_a_comment_def' for _, name in names),
          'comment symbol leaked')
    check(all(name != 'c256_i32' for _, name in names), 'SSA name leaked')
    check(all(name != 'arg0' for _, name in names), 'block arg leaked')
    check(all(not name.startswith('%') for _, name in names), 'percent sigil leaked')

    stored = DefList()
    for name, kind, line in defs:
        stored.append(1, kind, line, 'I')
    unpacked = [(kind, line) for _id, kind, line, family in stored.iter()]
    expect_stored = [(kind, line) for _name, kind, line in EXPECTED]
    check(unpacked == expect_stored and all(
        family == 'I' for _id, _kind, _line, family in stored.iter()
    ), f'DefList dropped an MLIR kind: {unpacked}')

    for blob in ('\x00\xff', 'tt.func @', '%', '"unterminated', 'func.func @'):
        try:
            mod.parse_defs(blob)
            mod.tokenize_source(blob)
        except Exception as exc:
            check(False, f'raised on {blob!r}: {exc}')

    empty = b''
    no_defs = '''\
// comment only
// tt.func @not_a_def
/* llvm.func @also_not */

%0 = arith.constant 1 : i32
%c256_i32 = arith.addi %0, %0 : i32
'''.encode('utf-8')
    check(mod.parse_defs(no_defs.decode('utf-8')) == [],
          'comment and SSA .mlir parsed as having definitions')
    check_defs_cli(check, empty, 'empty .mlir')
    check_tokenize_cli(check, empty, 'empty .mlir')
    check_defs_cli(check, no_defs, 'comment and SSA .mlir')
    check_tokenize_cli(check, no_defs, 'comment and SSA .mlir')

    calls = '''\
llvm.func @real(%arg0: i32)
llvm.call @real() : () -> ()
%0 = llvm.mlir.addressof @real : !llvm.ptr
'''.encode('utf-8')
    status, out, err = run_cli(calls, defs=True)
    check(status == 0 and err == b'' and out == b'real function 1\n',
          f'call and addressof must not be defs: {status} {out!r} {err!r}')

    sys.exit(failed)


def run_cli(src, defs=False):
    cmd = [sys.executable, os.path.join(ROOT, 'tokenize-mlir.py')]
    if defs:
        cmd.append('--defs')
    proc = subprocess.run(
        cmd, input=src, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return proc.returncode, proc.stdout, proc.stderr


def indexer_lines(blob):
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
