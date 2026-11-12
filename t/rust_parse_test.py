#!/usr/bin/env python3
# Const/union supplement and ctags kinds for the Rust family.
# Indexing coverage lives in 100-basic.t.
#
# SPDX-License-Identifier: AGPL-3.0-or-later

import importlib.util
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

spec = importlib.util.spec_from_file_location(
    'rust_item_defs', os.path.join(ROOT, 'rust-item-defs.py'))
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

from elixir.data import DefList

FIXTURE = os.path.join(ROOT, 't', 'tree', 'rust', 'rust_widgets.rs')

# ctags 5.9 kind names after the script.sh remap (interface -> trait),
# plus the const/union supplement. Enum-variant fields are not tags.
CTAGS_AND_EXTRA = {
    ('Fancy', 'enumerator', 20),
    ('Plain', 'enumerator', 19),
    ('RUST_WIDGET_STATIC', 'variable', 4),
    ('RustInnerWidget', 'struct', 75),
    ('RustKind', 'enum', 18),
    ('RustLabel', 'typedef', 6),
    ('RustWidget', 'struct', 13),
    ('RustWidgetLike', 'trait', 8),
    ('new', 'method', 24),
    ('render', 'method', 33),
    ('render_like', 'method', 9),
    ('render_like', 'method', 42),
    ('rust_async_widget', 'function', 60),
    ('rust_const_fn', 'function', 64),
    ('rust_generic', 'method', 49),
    ('rust_inner', 'module', 74),
    ('rust_inner_fn', 'function', 77),
    ('rust_make_macro', 'macro', 68),
    ('rust_make_widget', 'function', 54),
    ('widget_count', 'field', 15),
    ('widget_label', 'field', 14),
    ('RUST_WIDGET_LIMIT', 'constant', 3),
    ('ASSOC_LIMIT', 'constant', 10),
    ('IMPL_LIMIT', 'constant', 38),
    ('ASSOC_LIMIT', 'constant', 45),
    ('INNER_LIMIT', 'constant', 76),
    ('RustUnion', 'union', 80),
    ('RAW_LIMIT', 'constant', 85),
}

SNIPPET = '''\
// const NOT_COMMENTED: i32 = 1;
/* union NotInComment { bits_a: u32 } */

pub(crate) const PUB_CRATE_LIMIT: i32 = 1;
const S: &str = "const FAKE_STRING: i32 = 1;";

pub fn outer() {
    const RUST_FN_CONST: i32 = 2;
}

impl<const WIDGET_N: usize, const WIDGET_M: u8> Outer {
    const ASSOC: usize = WIDGET_N;
    fn method(&self) {
        const LOCAL: i32 = 1;
    }
}

impl Widget for Other {
    const FOR_ASSOC: i32 = 1;
}

const fn ignored_const_fn() -> i32 { 1 }

pub union PubUnion { bits_a: u32, bits_b: f32 }

const RAW: i32 = r#"
const NOT_A_RAW_CONST: i32 = 1;
{ const ALSO_NOT: i32 = 2; }
"#.len() as i32;
'''

EXPECTED_SNIPPET = [
    ('PUB_CRATE_LIMIT', 'constant', 4),
    ('S', 'constant', 5),
    ('ASSOC', 'constant', 12),
    ('FOR_ASSOC', 'constant', 19),
    ('PubUnion', 'union', 24),
    ('RAW', 'constant', 26),
]


def ctags_defs(path):
    proc = subprocess.run(
        ['ctags', '-x', '--language-force=Rust', '--kinds-rust=MPefgimnstv', path],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.decode())
    found = []
    for line in proc.stdout.decode().splitlines():
        parts = line.split()
        if len(parts) < 3:
            continue
        name, kind, line_no = parts[0], parts[1], parts[2]
        if kind == 'interface':
            kind = 'trait'
        found.append((name, kind, int(line_no)))
    return found


def main():
    failed = 0

    def check(cond, message):
        nonlocal failed
        if not cond:
            print(message, file=sys.stderr)
            failed += 1

    defs = mod.parse_defs(SNIPPET)
    check(defs == EXPECTED_SNIPPET,
          f'snippet defs mismatch:\n got {defs}\n expected {EXPECTED_SNIPPET}')
    names = {name for name, _kind, _line in defs}
    for banned in ('NOT_COMMENTED', 'NotInComment', 'FAKE_STRING',
                   'RUST_FN_CONST', 'WIDGET_N', 'WIDGET_M', 'LOCAL',
                   'NOT_A_RAW_CONST', 'ALSO_NOT', 'ignored_const_fn'):
        check(banned not in names, f'{banned} was indexed')

    extra = mod.parse_defs(open(FIXTURE, encoding='utf-8').read())
    combined = set(ctags_defs(FIXTURE)) | set(extra)
    check(combined == CTAGS_AND_EXTRA,
          f'fixture defs mismatch:\n missing {CTAGS_AND_EXTRA - combined}\n'
          f' unexpected {combined - CTAGS_AND_EXTRA}')

    stored = DefList()
    for name, kind, line in (
            ('widget_label', 'field', 1),
            ('rust_inner', 'module', 2),
            ('RustWidgetLike', 'trait', 3),
            ('RUST_WIDGET_LIMIT', 'constant', 4),
            ('RustUnion', 'union', 5)):
        stored.append(1, kind, line, 'R')
    unpacked = [(kind, line) for _id, kind, line, family in stored.iter()]
    check(unpacked == [
        ('field', 1), ('module', 2), ('trait', 3), ('constant', 4), ('union', 5),
    ], f'DefList dropped a Rust kind: {unpacked}')

    check_cli(check, b'', 'empty .rs')
    check_cli(check, b'// const NOPE: i32 = 1;\n/* union NopeU { a: u32 } */\n',
              'comment-only .rs')
    kept = b'const KEPT: i32 = 1;\n'
    status, out, err = run_cli(kept)
    check(status == 0 and err == b'' and out == b'KEPT constant 1\n',
          f'const with a real item: {status} {out!r} {err!r}')

    sys.exit(failed)


def run_cli(src):
    fd, path = tempfile.mkstemp(suffix='.rs')
    try:
        os.write(fd, src)
        os.close(fd)
        proc = subprocess.run(
            [sys.executable, os.path.join(ROOT, 'rust-item-defs.py'), path],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return proc.returncode, proc.stdout, proc.stderr
    finally:
        if os.path.exists(path):
            os.remove(path)


def check_cli(check, src, label):
    status, out, err = run_cli(src)
    check(status == 0 and err == b'' and out == b'',
          f'{label} should print nothing, got status={status} '
          f'out={out!r} err={err!r}')


if __name__ == '__main__':
    main()
