#!/usr/bin/env python3
# Parser checks for the TableGen family. Indexing coverage lives in 100-basic.t.
#
# SPDX-License-Identifier: AGPL-3.0-or-later

import importlib.util
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

spec = importlib.util.spec_from_file_location(
    'tokenize_tablegen', os.path.join(ROOT, 'tokenize-tablegen.py'))
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

from elixir.data import DefList

FIXTURE = os.path.join(ROOT, 't', 'tree', 'tablegen', 'ops.td')

EXPECTED = [
    ('TT_Op', 'class', 7),
    ('TT_IntToPtrOp', 'def', 11),
    ('TT_MultiInst', 'defm', 23),
    ('SomeMultiClass', 'multiclass', 25),
    ('_reg', 'def', 26),
    ('GenericSharedRead', 'variable', 29),
    ('WidgetAlias', 'variable', 30),
    ('WidgetSet', 'variable', 32),
    ('SetItem', 'def', 33),
    ('WidgetInt', 'typedef', 36),
    ('TT_ReturnOp', 'def', 39),
    ('TT_StringMention', 'def', 46),
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
    op_lines = [line for line, name in names if name == 'TT_IntToPtrOp']
    check(op_lines == [11, 30], f'TT_IntToPtrOp refs {op_lines}')
    for banned in ('not_in_code_block', 'NotAClass', 'TRITON_OPS', 'def', 'class'):
        check(all(name != banned for _, name in names), f'{banned} leaked as a ref')
    def_names = {name for name, _kind, _line in defs}
    check('PastedName' not in def_names, 'pasted def was indexed')

    stored = DefList()
    for name, kind, line in defs:
        stored.append(1, kind, line, 'G')
    unpacked = [(kind, line) for _id, kind, line, family in stored.iter()]
    expect_stored = [(kind, line) for _name, kind, line in EXPECTED]
    check(unpacked == expect_stored and all(
        family == 'G' for _id, _kind, _line, family in stored.iter()
    ), f'DefList dropped a TableGen kind: {unpacked}')

    for blob in ('\x00\xff', 'def :', 'class', '[{ def nope : X;'):
        try:
            mod.parse_defs(blob)
            mod.tokenize_source(blob)
        except Exception as exc:
            check(False, f'raised on {blob!r}: {exc}')

    empty = b''
    no_defs = '''\
// def NotAComment : Fake
/* class NotAClass {} */
#ifndef FOO
#define FOO
#endif
include "other.td"
def : Parent;
let x = 1;
[{
  def not_in_code_block : Fake;
  class NotAClass {}
}]
'''.encode('utf-8')
    check(mod.parse_defs(no_defs.decode('utf-8')) == [],
          'comment and code-block .td parsed as having definitions')
    check_defs_cli(check, empty, 'empty .td')
    check_tokenize_cli(check, empty, 'empty .td')
    check_defs_cli(check, no_defs, 'comment and code-block .td')
    check_tokenize_cli(check, no_defs, 'comment and code-block .td')

    kept = b'def KeptOp : Parent;\n'
    status, out, err = run_cli(kept, defs=True)
    check(status == 0 and err == b'' and out == b'KeptOp def 1\n',
          f'defs with a real record: {status} {out!r} {err!r}')
    fields = indexer_lines(out)
    check(len(fields) == 1 and fields[0].split(b' ') == [b'KeptOp', b'def', b'1'],
          f'defs line is three fields: {fields!r}')

    sys.exit(failed)


def run_cli(src, defs=False):
    cmd = [sys.executable, os.path.join(ROOT, 'tokenize-tablegen.py')]
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
