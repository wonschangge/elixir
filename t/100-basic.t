#!/usr/bin/env perl
# 100-basic.t: Test basic elixir functions against the files in tree/ .
#
# Copyright (c) 2020 D3 Engineering, LLC.
# By Christopher White, <cwhite@d3engineering.com>.
#
# Elixir is free software; you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Elixir is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with Elixir.  If not, see <http://www.gnu.org/licenses/>.
#
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# This file uses core Perl modules only.

use autodie;    # note: still need to check system() calls manually

use FindBin '$Bin';
use lib $Bin;

use File::Spec;

use Test::More;

use TestEnvironment;
use TestHelpers;

# ===========================================================================
# Main

# Set up
my $tree_src_dir = sibling_abs_path('tree');

my $tenv = TestEnvironment->new;

# Check programs
my $script_sh = $tenv->script_sh;
my $update_py = $tenv->update_py;
my $query_py = $tenv->query_py;

ok_or_die( (-f $script_sh && -r _ && -x _), 'script.sh executable',
    "Could not find executable script.sh at $script_sh");
ok_or_die( (-f $update_py && -r _ && -x _), 'update.py executable',
    "Could not find executable update.py at $update_py");
ok_or_die( (-f $query_py && -r _ && -x _), 'query.py executable',
    "Could not find executable query.py at $query_py");

$tenv->build_repo($tree_src_dir);
$tenv->update_env;  # Set LXR_REPO_DIR

diag $tenv->report;

# Check for tags in `script.sh list-tags`, as a sanity check before
# building the test DB
my @tags = `$script_sh list-tags`;
die("Could not list tags: $! ($?)") if $?;
ok_or_die( @tags == 1, 'One tag present', "Not one tag (@{[scalar @tags]})");
ok_or_die( $tags[0] =~ /^v5.4$/, 'Found the correct tag', 'Not the tag we expected');

$tenv->build_db;
$tenv->update_env;  # Set LXR_DATA_DIR
my $db_dir = $tenv->lxr_data_dir;

ok_or_die( -d $db_dir, 'database dir exists',
    "Database dir $db_dir not present");

# Make sure the database has the files we expect
ok( (-r File::Spec->catfile($db_dir, $_)), "$_ exists" )
    foreach qw(blobs.db definitions.db filenames.db hashes.db references.db
                variables.db versions.db definitions-cache-P.db
                definitions-cache-T.db definitions-cache-R.db
                definitions-cache-I.db definitions-cache-G.db);

# Spot-check some identifiers

run_produces_ok('ident query (nonexistent)',
    [$query_py, qw(ident v5.4 SOME_NONEXISTENT_IDENTIFIER_XYZZY_PLUGH C)],
    [qr{^Symbol Definitions:}, qr{^Symbol References:}, qr{^\s*$}],
    MUST_SUCCEED);

run_produces_ok('ident query (existent)',
    [$query_py, qw(ident v5.4 i2c_acpi_notify C)],
    [qr{^Symbol Definitions:}, qr{^Symbol References:},
        { def => qr{drivers/i2c/i2c-core-acpi\.c.+\b402\b.+\bfunction\b} },
        { ref => qr{drivers/i2c/i2c-core-acpi\.c.+\b439} },
    ],
    MUST_SUCCEED);

run_produces_ok('ident query (existent, #131)',
    [$query_py, qw(ident v5.4 class C)],
    [qr{^Symbol Definitions:}, qr{^Symbol References:},
        { def => qr{issue131\.h.+\b9\b.+\bstruct\b} },
        { ref => qr{issue131\.h.+\b13}  },
    ],
    MUST_SUCCEED);

run_produces_ok('ident query (existent, #150)',
    [$query_py, qw(ident v5.4 memset C)],
    [qr{^Symbol Definitions:}, qr{^Symbol References:},
        { def => qr{issue150\.S.+\b7\b.+\bfunction\b} },
        { ref => qr{i2c-core-acpi\.c.+\b121\b} }
    ],
    MUST_SUCCEED);

run_produces_ok('ident query (ENTRY that should not be detected, #150)',
    [$query_py, qw(ident v5.4), 'HYPERVISOR_##hypercall', 'C'],
    [qr{^Symbol Definitions:}, qr{^Symbol References:},
        { def => { not => qr{hypercall\.S} } },
    ],
    MUST_SUCCEED);

run_produces_ok('ident query (ENTRY that should not be detected, #150)',
    [$query_py, qw(ident v5.4), '0xfffffffe', 'C'],
    [qr{^Symbol Definitions:}, qr{^Symbol References:},
        { def => { not => qr{bcm74xx_sprom\.c} } },
    ],
    MUST_SUCCEED);

run_produces_ok('ident query (existent, #228)',
    [$query_py, qw(ident v5.4 sys_init_module C)],
    [qr{^Symbol Definitions:}, qr{^Symbol References:},
        { def => qr{syscall_define\.c.+\b1\b.+\bfunction\b} }
    ],
    MUST_SUCCEED);

# Spot-check some files

run_produces_ok('file query (nonexistent)',
    [$query_py, qw(file v5.4 /SOME_NONEXISTENT_FILENAME_XYZZY_PLUGH)],
    [{not => qr{\S}}]);

run_produces_ok('file query (existent), .h',
    [$query_py, qw(file v5.4 /drivers/i2c/i2c-dev.c)],
    [qr{\S}],
    MUST_SUCCEED);

run_produces_ok('file query (existent), .c',
    [$query_py, qw(file v5.4 /drivers/i2c/i2c-dev.c)],
    [qr{i2c-dev\.c}, qr{\bVogl\b}],
    MUST_SUCCEED);

run_produces_ok('file query (existent), .h',
    [$query_py, qw(file v5.4 /drivers/i2c/i2c-core.h)],
    [qr{i2c-core\.h}, qr{\bWe\b}],
    MUST_SUCCEED);

# Python family: definitions, references, and tokens that must not be refs.

run_produces_ok('python ident query (function)',
    [$query_py, qw(ident v5.4 py_make_widget P)],
    [qr{^Symbol Definitions:}, qr{^Symbol References:},
        { def => qr{python/py_widgets\.py.+\b16\b.+\bfunction\b} },
        { ref => qr{python/py_widgets\.py.+\b22\b} },
        { ref => qr{python/py_widgets\.py.+\b26\b} },
        { ref => qr{python/py_consumer\.py.+\b4\b} },
        { ref => { not => qr{py_widgets\.py.+\b1\b} } },
        { ref => { not => qr{py_widgets\.py.+\b8\b} } },
        { ref => { not => qr{py_widgets\.py.+\b11\b} } },
        { ref => { not => qr{py_widgets\.py.+\b14\b} } },
        { ref => { not => qr{py_widgets\.py.+\b17\b} } },
        { ref => { not => qr{py_widgets\.py.+\b18\b} } },
    ],
    MUST_SUCCEED);

run_produces_ok('python ident query (class, variable, method)',
    [$query_py, qw(ident v5.4 PyWidget P)],
    [
        { def => qr{python/py_widgets\.py.+\b7\b.+\bclass\b} },
        { ref => qr{python/py_widgets\.py.+\b19\b} },
    ],
    MUST_SUCCEED);

run_produces_ok('python ident query (variable)',
    [$query_py, qw(ident v5.4 PY_WIDGET_LIMIT P)],
    [
        { def => qr{python/py_widgets\.py.+\b5\b.+\bvariable\b} },
    ],
    MUST_SUCCEED);

run_produces_ok('python ident query (method)',
    [$query_py, qw(ident v5.4 render P)],
    [
        { def => qr{python/py_widgets\.py.+\b13\b.+\bmember\b} },
        { ref => qr{python/py_widgets\.py.+\b23\b} },
    ],
    MUST_SUCCEED);

run_produces_ok('python ident is not a C symbol',
    [$query_py, qw(ident v5.4 py_make_widget C)],
    [
        { def => { not => qr{\S} } },
        { ref => { not => qr{\S} } },
    ],
    MUST_SUCCEED);

run_produces_ok('python ident is visible in all-symbols search',
    [$query_py, qw(ident v5.4 py_make_widget A)],
    [
        { def => qr{python/py_widgets\.py.+\bfunction\b} },
    ],
    MUST_SUCCEED);

run_produces_ok('C ident is not a Python symbol',
    [$query_py, qw(ident v5.4 i2c_acpi_notify P)],
    [
        { def => { not => qr{\S} } },
        { ref => { not => qr{\S} } },
    ],
    MUST_SUCCEED);

run_produces_ok('python file query keeps text and links real idents',
    [$query_py, qw(file v5.4 /python/py_widgets.py)],
    [
        qr{Module docstring mentions py_make_widget},
        qr{# py_make_widget in a comment should not count},
        qr{"py_make_widget inside a string"},
        qr{\x{1b}\[31mpy_make_widget\x{1b}\[0m\("demo"\)},
        qr{\x{1b}\[31mPyWidget\x{1b}\[0m},
        { not => qr{# \x{1b}\[31mpy_make_widget} },
        { not => qr{"\x{1b}\[31mpy_make_widget} },
    ],
    MUST_SUCCEED);

# TypeScript/JavaScript family: classes, functions, exports, imports,
# and cross-file calls. Comments, strings, template text, regexes, and
# JSX text are not references. Imports and function-scoped consts are
# not definitions.

run_produces_ok('typescript ident query (function)',
    [$query_py, qw(ident v5.4 ts_make_widget T)],
    [qr{^Symbol Definitions:}, qr{^Symbol References:},
        { def => qr{typescript/ts_widgets\.ts.+\b22\b.+\bfunction\b} },
        { ref => qr{typescript/ts_widgets\.ts.+\b29\b} },
        { ref => qr{typescript/ts_widgets\.ts.+\b30\b} },
        { ref => qr{typescript/ts_widgets\.ts.+\b36\b} },
        { ref => qr{typescript/ts_widget_view\.tsx.+\b4\b} },
        { ref => qr{typescript/js_consumer\.js.+\b4\b} },
        { ref => { not => qr{ts_widgets\.ts.+\b1\b} } },
        { ref => { not => qr{ts_widgets\.ts.+\b6\b} } },
        { ref => { not => qr{ts_widgets\.ts.+\b7\b} } },
        { ref => { not => qr{ts_widgets\.ts.+\b14\b} } },
        { ref => { not => qr{ts_widgets\.ts.+\b22\b} } },
        { ref => { not => qr{ts_widgets\.ts.+\b23\b} } },
        { ref => { not => qr{ts_widgets\.ts.+\b24\b} } },
        { ref => { not => qr{ts_widgets\.ts.+\b31\b} } },
        { ref => { not => qr{ts_widget_view\.tsx.+\b5\b} } },
    ],
    MUST_SUCCEED);

run_produces_ok('typescript ident query (class)',
    [$query_py, qw(ident v5.4 TsWidget T)],
    [
        { def => qr{typescript/ts_widgets\.ts.+\b5\b.+\bclass\b} },
        { ref => qr{typescript/ts_widgets\.ts.+\b25\b} },
        { ref => qr{typescript/ts_widget_view\.tsx.+\b5\b} },
    ],
    MUST_SUCCEED);

run_produces_ok('typescript ident query (constant)',
    [$query_py, qw(ident v5.4 TS_WIDGET_LIMIT T)],
    [
        { def => qr{typescript/ts_widgets\.ts.+\b3\b.+\bconstant\b} },
    ],
    MUST_SUCCEED);

run_produces_ok('typescript ident query (method)',
    [$query_py, qw(ident v5.4 render T)],
    [
        { def => qr{typescript/ts_widgets\.ts.+\b13\b.+\bmethod\b} },
        { ref => qr{typescript/ts_widgets\.ts.+\b32\b} },
        { ref => qr{typescript/ts_widget_view\.tsx.+\b5\b} },
    ],
    MUST_SUCCEED);

run_produces_ok('typescript ident query (interface)',
    [$query_py, qw(ident v5.4 TsWidgetOptions T)],
    [
        { def => qr{typescript/ts_widgets\.ts.+\b18\b.+\binterface\b} },
    ],
    MUST_SUCCEED);

run_produces_ok('typescript local const is not a definition',
    [$query_py, qw(ident v5.4 text T)],
    [
        { def => { not => qr{\S} } },
        { ref => { not => qr{\S} } },
    ],
    MUST_SUCCEED);

run_produces_ok('javascript ident query (export, import, cross-file call)',
    [$query_py, qw(ident v5.4 js_consume T)],
    [
        { def => qr{typescript/js_consumer\.js.+\b3\b.+\bfunction\b} },
        { def => { not => qr{js_view\.jsx} } },
        { ref => qr{typescript/js_view\.jsx.+\b4\b} },
    ],
    MUST_SUCCEED);

run_produces_ok('tsx export is a function',
    [$query_py, qw(ident v5.4 TsWidgetView T)],
    [
        { def => qr{typescript/ts_widget_view\.tsx.+\b3\b.+\bfunction\b} },
    ],
    MUST_SUCCEED);

run_produces_ok('typescript ident is not a C symbol',
    [$query_py, qw(ident v5.4 ts_make_widget C)],
    [
        { def => { not => qr{\S} } },
        { ref => { not => qr{\S} } },
    ],
    MUST_SUCCEED);

run_produces_ok('typescript ident is not a Python symbol',
    [$query_py, qw(ident v5.4 ts_make_widget P)],
    [
        { def => { not => qr{\S} } },
        { ref => { not => qr{\S} } },
    ],
    MUST_SUCCEED);

run_produces_ok('python ident is not a TypeScript symbol',
    [$query_py, qw(ident v5.4 py_make_widget T)],
    [
        { def => { not => qr{\S} } },
        { ref => { not => qr{\S} } },
    ],
    MUST_SUCCEED);

run_produces_ok('C ident is not a TypeScript symbol',
    [$query_py, qw(ident v5.4 i2c_acpi_notify T)],
    [
        { def => { not => qr{\S} } },
        { ref => { not => qr{\S} } },
    ],
    MUST_SUCCEED);

run_produces_ok('typescript ident is visible in all-symbols search',
    [$query_py, qw(ident v5.4 ts_make_widget A)],
    [
        { def => qr{typescript/ts_widgets\.ts.+\bfunction\b} },
    ],
    MUST_SUCCEED);

run_produces_ok('typescript file query keeps text and links real idents',
    [$query_py, qw(file v5.4 /typescript/ts_widgets.ts)],
    [
        qr{Module doc mentions ts_make_widget},
        qr{// ts_make_widget in a comment should not count},
        qr{"ts_make_widget inside a string"},
        qr{skip ts_make_widget},
        qr{/ts_make_widget/g},
        qr{\x{1b}\[31mts_make_widget\x{1b}\[0m\("demo"\)},
        qr{\$\{\x{1b}\[31mts_make_widget\x{1b}\[0m\("tmpl"\)\}},
        qr{\x{1b}\[31mTsWidget\x{1b}\[0m},
        { not => qr{mentions \x{1b}\[31mts_make_widget} },
        { not => qr{// \x{1b}\[31mts_make_widget} },
        { not => qr{"\x{1b}\[31mts_make_widget} },
        { not => qr{skip \x{1b}\[31mts_make_widget} },
        { not => qr{/\x{1b}\[31mts_make_widget} },
    ],
    MUST_SUCCEED);

run_produces_ok('tsx file query skips JSX text and links tags',
    [$query_py, qw(file v5.4 /typescript/ts_widget_view.tsx)],
    [
        qr{>ts_make_widget<},
        qr{\x{1b}\[31mts_make_widget\x{1b}\[0m\(props\.},
        qr{\x{1b}\[31mTsWidget\x{1b}\[0m},
        qr{\x{1b}\[31mrender\x{1b}\[0m\(\)},
        { not => qr{>\x{1b}\[31mts_make_widget\x{1b}\[0m<} },
    ],
    MUST_SUCCEED);

# Mojo family: fn/def, struct, trait, alias, comptime, struct fields.
# Comments, strings, docstrings, and keywords are not references.
# Function-local var/comptime and names inside backtick MLIR literals
# are not definitions.

run_produces_ok('mojo ident query (function)',
    [$query_py, qw(ident v5.4 mojo_make_widget J)],
    [qr{^Symbol Definitions:}, qr{^Symbol References:},
        { def => qr{mojo/mojo_widgets\.mojo.+\b40\b.+\bfunction\b} },
        { ref => qr{mojo/mojo_widgets\.mojo.+\b46\b} },
        { ref => qr{mojo/mojo_widgets\.mojo.+\b47\b} },
        { ref => qr{mojo/mojo_consumer\.mojo.+\b3\b} },
        { ref => qr{mojo/mojo_consumer\.mojo.+\b6\b} },
        { ref => { not => qr{mojo_widgets\.mojo.+\b1\b} } },
        { ref => { not => qr{mojo_widgets\.mojo.+\b7\b} } },
        { ref => { not => qr{mojo_widgets\.mojo.+\b36\b} } },
        { ref => { not => qr{mojo_widgets\.mojo.+\b40\b} } },
        { ref => { not => qr{mojo_widgets\.mojo.+\b41\b} } },
        { ref => { not => qr{mojo_widgets\.mojo.+\b42\b} } },
    ],
    MUST_SUCCEED);

run_produces_ok('mojo ident query (struct, trait, alias, comptime, fn)',
    [$query_py, qw(ident v5.4 MojoWidget J)],
    [
        { def => qr{mojo/mojo_widgets\.mojo.+\b19\b.+\bstruct\b} },
        { ref => qr{mojo/mojo_widgets\.mojo.+\b38\b} },
    ],
    MUST_SUCCEED);

run_produces_ok('mojo ident query (trait)',
    [$query_py, qw(ident v5.4 MojoWidgetLike J)],
    [
        { def => qr{mojo/mojo_widgets\.mojo.+\b31\b.+\btrait\b} },
    ],
    MUST_SUCCEED);

run_produces_ok('mojo ident query (alias)',
    [$query_py, qw(ident v5.4 MojoLabel J)],
    [
        { def => qr{mojo/mojo_widgets\.mojo.+\b14\b.+\balias\b} },
    ],
    MUST_SUCCEED);

run_produces_ok('mojo ident query (comptime)',
    [$query_py, qw(ident v5.4 MOJO_WIDGET_LIMIT J)],
    [
        { def => qr{mojo/mojo_widgets\.mojo.+\b12\b.+\bcomptime\b} },
    ],
    MUST_SUCCEED);

run_produces_ok('mojo ident query (comptime after backtick literal)',
    [$query_py, qw(ident v5.4 MojoNever J)],
    [
        { def => qr{mojo/mojo_widgets\.mojo.+\b16\b.+\bcomptime\b} },
    ],
    MUST_SUCCEED);

run_produces_ok('mojo ident query (method and field)',
    [$query_py, qw(ident v5.4 render J)],
    [
        { def => qr{mojo/mojo_widgets\.mojo.+\b27\b.+\bmethod\b} },
        { ref => qr{mojo/mojo_widgets\.mojo.+\b48\b} },
    ],
    MUST_SUCCEED);

run_produces_ok('mojo ident query (struct field)',
    [$query_py, qw(ident v5.4 label J)],
    [
        { def => qr{mojo/mojo_widgets\.mojo.+\b22\b.+\bmember\b} },
    ],
    MUST_SUCCEED);

run_produces_ok('mojo ident query (legacy fn)',
    [$query_py, qw(ident v5.4 mojo_legacy_widget J)],
    [
        { def => qr{mojo/mojo_widgets\.mojo.+\b35\b.+\bfunction\b} },
    ],
    MUST_SUCCEED);

run_produces_ok('mojo fire-suffix struct',
    [$query_py, qw(ident v5.4 MojoSpark J)],
    [
        { def => qr{mojo/spark.+\b3\b.+\bstruct\b} },
    ],
    MUST_SUCCEED);

run_produces_ok('mojo fire-suffix method',
    [$query_py, qw(ident v5.4 mojo_spark J)],
    [
        { def => qr{mojo/spark.+\b6\b.+\bmethod\b} },
    ],
    MUST_SUCCEED);

run_produces_ok('mojo local var is not a definition',
    [$query_py, qw(ident v5.4 mojo_local_only J)],
    [
        { def => { not => qr{\S} } },
        { ref => { not => qr{\S} } },
    ],
    MUST_SUCCEED);

run_produces_ok('mojo docstring code is not a definition',
    [$query_py, qw(ident v5.4 not_a_function J)],
    [
        { def => { not => qr{\S} } },
        { ref => { not => qr{\S} } },
    ],
    MUST_SUCCEED);

run_produces_ok('mojo keyword is not a reference',
    [$query_py, qw(ident v5.4 struct J)],
    [
        { def => { not => qr{\S} } },
        { ref => { not => qr{\S} } },
    ],
    MUST_SUCCEED);

run_produces_ok('mojo ident is not a C symbol',
    [$query_py, qw(ident v5.4 mojo_make_widget C)],
    [
        { def => { not => qr{\S} } },
        { ref => { not => qr{\S} } },
    ],
    MUST_SUCCEED);

run_produces_ok('mojo ident is not a Python symbol',
    [$query_py, qw(ident v5.4 mojo_make_widget P)],
    [
        { def => { not => qr{\S} } },
        { ref => { not => qr{\S} } },
    ],
    MUST_SUCCEED);

run_produces_ok('python ident is not a Mojo symbol',
    [$query_py, qw(ident v5.4 py_make_widget J)],
    [
        { def => { not => qr{\S} } },
        { ref => { not => qr{\S} } },
    ],
    MUST_SUCCEED);

run_produces_ok('C ident is not a Mojo symbol',
    [$query_py, qw(ident v5.4 i2c_acpi_notify J)],
    [
        { def => { not => qr{\S} } },
        { ref => { not => qr{\S} } },
    ],
    MUST_SUCCEED);

run_produces_ok('mojo ident is visible in all-symbols search',
    [$query_py, qw(ident v5.4 mojo_make_widget A)],
    [
        { def => qr{mojo/mojo_widgets\.mojo.+\bfunction\b} },
    ],
    MUST_SUCCEED);

# Rust family: ctags (functions, structs, enums, traits, methods, macros,
# modules, type aliases, statics, fields) plus const items and unions,
# which ctags 5.9 does not tag. Function-local const and const generic
# parameters are not definitions. The C tokenizer keeps comments and
# strings out of the reference stream.

run_produces_ok('rust ident query (function)',
    [$query_py, qw(ident v5.4 rust_make_widget R)],
    [qr{^Symbol Definitions:}, qr{^Symbol References:},
        { def => qr{rust/rust_widgets\.rs.+\b54\b.+\bfunction\b} },
        { ref => qr{rust/rust_widgets\.rs.+\b61\b} },
        { ref => qr{rust/rust_consumer\.rs.+\b2\b} },
        { ref => { not => qr{rust_widgets\.rs.+\b1\b} } },
        { ref => { not => qr{rust_widgets\.rs.+\b54\b} } },
        { ref => { not => qr{rust_widgets\.rs.+\b55\b} } },
        { ref => { not => qr{rust_widgets\.rs.+\b56\b} } },
    ],
    MUST_SUCCEED);

run_produces_ok('rust ident query (struct, trait, const, static)',
    [$query_py, qw(ident v5.4 RustWidget R)],
    [
        { def => qr{rust/rust_widgets\.rs.+\b13\b.+\bstruct\b} },
        { ref => qr{rust/rust_widgets\.rs.+\b57\b} },
    ],
    MUST_SUCCEED);

run_produces_ok('rust ident query (trait)',
    [$query_py, qw(ident v5.4 RustWidgetLike R)],
    [
        { def => qr{rust/rust_widgets\.rs.+\b8\b.+\btrait\b} },
    ],
    MUST_SUCCEED);

run_produces_ok('rust ident query (const)',
    [$query_py, qw(ident v5.4 RUST_WIDGET_LIMIT R)],
    [
        { def => qr{rust/rust_widgets\.rs.+\b3\b.+\bconstant\b} },
    ],
    MUST_SUCCEED);

run_produces_ok('rust ident query (associated const)',
    [$query_py, qw(ident v5.4 ASSOC_LIMIT R)],
    [
        { def => qr{rust/rust_widgets\.rs.+\b10\b.+\bconstant\b} },
        { def => qr{rust/rust_widgets\.rs.+\b45\b.+\bconstant\b} },
    ],
    MUST_SUCCEED);

run_produces_ok('rust ident query (static)',
    [$query_py, qw(ident v5.4 RUST_WIDGET_STATIC R)],
    [
        { def => qr{rust/rust_widgets\.rs.+\b4\b.+\bvariable\b} },
    ],
    MUST_SUCCEED);

run_produces_ok('rust ident query (method and field)',
    [$query_py, qw(ident v5.4 render R)],
    [
        { def => qr{rust/rust_widgets\.rs.+\b33\b.+\bmethod\b} },
        { def => { not => qr{py_widgets} } },
        { def => { not => qr{mojo_widgets} } },
        { def => { not => qr{ts_widgets} } },
    ],
    MUST_SUCCEED);

run_produces_ok('rust ident query (struct field)',
    [$query_py, qw(ident v5.4 widget_label R)],
    [
        { def => qr{rust/rust_widgets\.rs.+\b14\b.+\bfield\b} },
    ],
    MUST_SUCCEED);

run_produces_ok('rust ident query (enum and variant)',
    [$query_py, qw(ident v5.4 RustKind R)],
    [
        { def => qr{rust/rust_widgets\.rs.+\b18\b.+\benum\b} },
    ],
    MUST_SUCCEED);

run_produces_ok('rust ident query (enum variant)',
    [$query_py, qw(ident v5.4 Fancy R)],
    [
        { def => qr{rust/rust_widgets\.rs.+\b20\b.+\benumerator\b} },
    ],
    MUST_SUCCEED);

run_produces_ok('rust ident query (macro, module, typedef, union)',
    [$query_py, qw(ident v5.4 rust_make_macro R)],
    [
        { def => qr{rust/rust_widgets\.rs.+\b68\b.+\bmacro\b} },
    ],
    MUST_SUCCEED);

run_produces_ok('rust ident query (module)',
    [$query_py, qw(ident v5.4 rust_inner R)],
    [
        { def => qr{rust/rust_widgets\.rs.+\b74\b.+\bmodule\b} },
    ],
    MUST_SUCCEED);

run_produces_ok('rust ident query (type alias)',
    [$query_py, qw(ident v5.4 RustLabel R)],
    [
        { def => qr{rust/rust_widgets\.rs.+\b6\b.+\btypedef\b} },
    ],
    MUST_SUCCEED);

run_produces_ok('rust ident query (union)',
    [$query_py, qw(ident v5.4 RustUnion R)],
    [
        { def => qr{rust/rust_widgets\.rs.+\b80\b.+\bunion\b} },
    ],
    MUST_SUCCEED);

run_produces_ok('rust function-local const is not a definition',
    [$query_py, qw(ident v5.4 RUST_FN_CONST R)],
    [
        { def => { not => qr{\S} } },
        { ref => { not => qr{\S} } },
    ],
    MUST_SUCCEED);

run_produces_ok('rust const generic is not a definition',
    [$query_py, qw(ident v5.4 WIDGET_N R)],
    [
        { def => { not => qr{\S} } },
        { ref => { not => qr{\S} } },
    ],
    MUST_SUCCEED);

run_produces_ok('rust enum-variant field is not a definition',
    [$query_py, qw(ident v5.4 fancy_note R)],
    [
        { def => { not => qr{\S} } },
    ],
    MUST_SUCCEED);

run_produces_ok('rust ident is not a C symbol',
    [$query_py, qw(ident v5.4 rust_make_widget C)],
    [
        { def => { not => qr{\S} } },
        { ref => { not => qr{\S} } },
    ],
    MUST_SUCCEED);

run_produces_ok('rust ident is not a Python symbol',
    [$query_py, qw(ident v5.4 rust_make_widget P)],
    [
        { def => { not => qr{\S} } },
        { ref => { not => qr{\S} } },
    ],
    MUST_SUCCEED);

run_produces_ok('python ident is not a Rust symbol',
    [$query_py, qw(ident v5.4 py_make_widget R)],
    [
        { def => { not => qr{\S} } },
        { ref => { not => qr{\S} } },
    ],
    MUST_SUCCEED);

run_produces_ok('C ident is not a Rust symbol',
    [$query_py, qw(ident v5.4 i2c_acpi_notify R)],
    [
        { def => { not => qr{\S} } },
        { ref => { not => qr{\S} } },
    ],
    MUST_SUCCEED);

run_produces_ok('rust ident is visible in all-symbols search',
    [$query_py, qw(ident v5.4 rust_make_widget A)],
    [
        { def => qr{rust/rust_widgets\.rs.+\bfunction\b} },
    ],
    MUST_SUCCEED);

run_produces_ok('rust file query keeps text and links real idents',
    [$query_py, qw(file v5.4 /rust/rust_widgets.rs)],
    [
        qr{Module docs mention rust_make_widget},
        qr{// rust_make_widget in a comment should not count},
        qr{"rust_make_widget inside a string"},
        qr{\x{1b}\[31mrust_make_widget\x{1b}\[0m\("async"},
        qr{\x{1b}\[31mRustWidget\x{1b}\[0m},
        { not => qr{// \x{1b}\[31mrust_make_widget} },
        { not => qr{"\x{1b}\[31mrust_make_widget} },
        { not => qr{mention \x{1b}\[31mrust_make_widget} },
    ],
    MUST_SUCCEED);

# MLIR family: custom tokenizer. Defining ops are func/module/global
# (and IRDL dialect/op/type/attr). Calls and addressof are references.
# SSA names are not definitions or reference tokens.

run_produces_ok('mlir ident query (function)',
    [$query_py, qw(ident v5.4 add_kernel I)],
    [qr{^Symbol Definitions:}, qr{^Symbol References:},
        { def => qr{mlir/add_kernel\.mlir.+\b8\b.+\bfunction\b} },
        { ref => qr{mlir/add_kernel\.mlir.+\b14\b} },
        { ref => qr{mlir/mlir_consumer\.mlir.+\b3\b} },
        { ref => { not => qr{add_kernel\.mlir.+\b1\b} } },
        { ref => { not => qr{add_kernel\.mlir.+\b2\b} } },
        { ref => { not => qr{add_kernel\.mlir.+\b8\b} } },
        { ref => { not => qr{add_kernel\.mlir.+\b12\b} } },
        { ref => { not => qr{add_kernel\.mlir.+\b13\b} } },
    ],
    MUST_SUCCEED);

run_produces_ok('mlir ident query (llvm func, global, private, module)',
    [$query_py, qw(ident v5.4 llvm_helper I)],
    [
        { def => qr{mlir/add_kernel\.mlir.+\b18\b.+\bfunction\b} },
        { ref => qr{mlir/add_kernel\.mlir.+\b20\b} },
    ],
    MUST_SUCCEED);

run_produces_ok('mlir ident query (global)',
    [$query_py, qw(ident v5.4 global_smem I)],
    [
        { def => qr{mlir/add_kernel\.mlir.+\b19\b.+\bvariable\b} },
        { ref => qr{mlir/add_kernel\.mlir.+\b21\b} },
        { def => { not => qr{addressof} } },
    ],
    MUST_SUCCEED);

run_produces_ok('mlir ident query (attribute alias and type alias)',
    [$query_py, qw(ident v5.4 BlockedLayout I)],
    [
        { def => qr{mlir/add_kernel\.mlir.+\b4\b.+\balias\b} },
        { ref => qr{mlir/add_kernel\.mlir.+\b5\b} },
    ],
    MUST_SUCCEED);

run_produces_ok('mlir ident query (type alias)',
    [$query_py, qw(ident v5.4 widget_tensor I)],
    [
        { def => qr{mlir/add_kernel\.mlir.+\b5\b.+\btypedef\b} },
    ],
    MUST_SUCCEED);

run_produces_ok('mlir ident query (named module and gpu func)',
    [$query_py, qw(ident v5.4 named_module I)],
    [
        { def => qr{mlir/add_kernel\.mlir.+\b28\b.+\bnamespace\b} },
    ],
    MUST_SUCCEED);

run_produces_ok('mlir ident query (gpu func)',
    [$query_py, qw(ident v5.4 gpu_kernel I)],
    [
        { def => qr{mlir/add_kernel\.mlir.+\b29\b.+\bfunction\b} },
    ],
    MUST_SUCCEED);

run_produces_ok('mlir ident query (generic sym_name)',
    [$query_py, qw(ident v5.4 generic_fn I)],
    [
        { def => qr{mlir/add_kernel\.mlir.+\b35\b.+\bfunction\b} },
    ],
    MUST_SUCCEED);

run_produces_ok('mlir ident query (irdl dialect)',
    [$query_py, qw(ident v5.4 demo_dialect I)],
    [
        { def => qr{mlir/add_kernel\.mlir.+\b39\b.+\bnamespace\b} },
    ],
    MUST_SUCCEED);

run_produces_ok('mlir ident query (irdl type, attr, op)',
    [$query_py, qw(ident v5.4 demo_op I)],
    [
        { def => qr{mlir/add_kernel\.mlir.+\b42\b.+\bfunction\b} },
    ],
    MUST_SUCCEED);

run_produces_ok('mlir SSA name is not a definition',
    [$query_py, qw(ident v5.4 c256_i32 I)],
    [
        { def => { not => qr{\S} } },
        { ref => { not => qr{\S} } },
    ],
    MUST_SUCCEED);

run_produces_ok('mlir comment symbol is not a definition',
    [$query_py, qw(ident v5.4 not_a_comment_def I)],
    [
        { def => { not => qr{\S} } },
        { ref => { not => qr{\S} } },
    ],
    MUST_SUCCEED);

run_produces_ok('mlir ident is not a C symbol',
    [$query_py, qw(ident v5.4 add_kernel C)],
    [
        { def => { not => qr{\S} } },
        { ref => { not => qr{\S} } },
    ],
    MUST_SUCCEED);

run_produces_ok('mlir ident is not a Rust symbol',
    [$query_py, qw(ident v5.4 add_kernel R)],
    [
        { def => { not => qr{\S} } },
        { ref => { not => qr{\S} } },
    ],
    MUST_SUCCEED);

run_produces_ok('rust ident is not an MLIR symbol',
    [$query_py, qw(ident v5.4 rust_make_widget I)],
    [
        { def => { not => qr{\S} } },
        { ref => { not => qr{\S} } },
    ],
    MUST_SUCCEED);

run_produces_ok('C ident is not an MLIR symbol',
    [$query_py, qw(ident v5.4 i2c_acpi_notify I)],
    [
        { def => { not => qr{\S} } },
        { ref => { not => qr{\S} } },
    ],
    MUST_SUCCEED);

run_produces_ok('mlir ident is visible in all-symbols search',
    [$query_py, qw(ident v5.4 add_kernel A)],
    [
        { def => qr{mlir/add_kernel\.mlir.+\bfunction\b} },
    ],
    MUST_SUCCEED);

run_produces_ok('mlir file query links @symbols and not SSA or comments',
    [$query_py, qw(file v5.4 /mlir/add_kernel.mlir)],
    [
        qr{mentions add_kernel but is not a reference},
        qr{// tt\.func \@not_a_comment_def},
        qr{"add_kernel inside a string"},
        qr{\x{1b}\[31madd_kernel\x{1b}\[0m},
        qr{\x{1b}\[31mBlockedLayout\x{1b}\[0m},
        qr{\x{1b}\[31mglobal_smem\x{1b}\[0m},
        { not => qr{// \x{1b}\[31madd_kernel} },
        { not => qr{// tt\.func \@\x{1b}\[31mnot_a_comment_def} },
        { not => qr{"\x{1b}\[31madd_kernel} },
        { not => qr{\x{1b}\[31mc256_i32} },
        { not => qr{mentions \x{1b}\[31madd_kernel} },
    ],
    MUST_SUCCEED);

# TableGen family: def/defm/class/multiclass/defvar/defset/deftype.
# Code blocks, strings, comments, and anonymous or pasted defs are not
# definitions.

run_produces_ok('tablegen ident query (def)',
    [$query_py, qw(ident v5.4 TT_IntToPtrOp G)],
    [qr{^Symbol Definitions:}, qr{^Symbol References:},
        { def => qr{tablegen/ops\.td.+\b11\b.+\bdef\b} },
        { ref => qr{tablegen/ops\.td.+\b30\b} },
        { ref => { not => qr{ops\.td.+\b1\b} } },
        { ref => { not => qr{ops\.td.+\b11\b} } },
        { ref => { not => qr{ops\.td.+\b16\b} } },
        { ref => { not => qr{ops\.td.+\b47\b} } },
    ],
    MUST_SUCCEED);

run_produces_ok('tablegen ident query (class)',
    [$query_py, qw(ident v5.4 TT_Op G)],
    [
        { def => qr{tablegen/ops\.td.+\b7\b.+\bclass\b} },
        { ref => qr{tablegen/ops\.td.+\b11\b} },
        { ref => qr{tablegen/td_consumer\.td.+\b3\b} },
    ],
    MUST_SUCCEED);

run_produces_ok('tablegen ident query (defm and multiclass)',
    [$query_py, qw(ident v5.4 TT_MultiInst G)],
    [
        { def => qr{tablegen/ops\.td.+\b23\b.+\bdefm\b} },
    ],
    MUST_SUCCEED);

run_produces_ok('tablegen ident query (multiclass)',
    [$query_py, qw(ident v5.4 SomeMultiClass G)],
    [
        { def => qr{tablegen/ops\.td.+\b25\b.+\bmulticlass\b} },
    ],
    MUST_SUCCEED);

run_produces_ok('tablegen ident query (inner def, defvar, defset, deftype)',
    [$query_py, qw(ident v5.4 _reg G)],
    [
        { def => qr{tablegen/ops\.td.+\b26\b.+\bdef\b} },
    ],
    MUST_SUCCEED);

run_produces_ok('tablegen ident query (defvar)',
    [$query_py, qw(ident v5.4 GenericSharedRead G)],
    [
        { def => qr{tablegen/ops\.td.+\b29\b.+\bvariable\b} },
    ],
    MUST_SUCCEED);

run_produces_ok('tablegen ident query (defset)',
    [$query_py, qw(ident v5.4 WidgetSet G)],
    [
        { def => qr{tablegen/ops\.td.+\b32\b.+\bvariable\b} },
    ],
    MUST_SUCCEED);

run_produces_ok('tablegen ident query (deftype)',
    [$query_py, qw(ident v5.4 WidgetInt G)],
    [
        { def => qr{tablegen/ops\.td.+\b36\b.+\btypedef\b} },
    ],
    MUST_SUCCEED);

run_produces_ok('tablegen ident query (def inside let)',
    [$query_py, qw(ident v5.4 TT_ReturnOp G)],
    [
        { def => qr{tablegen/ops\.td.+\b39\b.+\bdef\b} },
    ],
    MUST_SUCCEED);

run_produces_ok('tablegen code block is not a definition',
    [$query_py, qw(ident v5.4 not_in_code_block G)],
    [
        { def => { not => qr{\S} } },
        { ref => { not => qr{\S} } },
    ],
    MUST_SUCCEED);

run_produces_ok('tablegen pasted def is not a definition',
    [$query_py, qw(ident v5.4 PastedName G)],
    [
        { def => { not => qr{\S} } },
    ],
    MUST_SUCCEED);

run_produces_ok('tablegen preprocessor macro is not a definition',
    [$query_py, qw(ident v5.4 TRITON_OPS G)],
    [
        { def => { not => qr{\S} } },
        { ref => { not => qr{\S} } },
    ],
    MUST_SUCCEED);

run_produces_ok('tablegen ident is not a C symbol',
    [$query_py, qw(ident v5.4 TT_IntToPtrOp C)],
    [
        { def => { not => qr{\S} } },
        { ref => { not => qr{\S} } },
    ],
    MUST_SUCCEED);

run_produces_ok('tablegen ident is not an MLIR symbol',
    [$query_py, qw(ident v5.4 TT_IntToPtrOp I)],
    [
        { def => { not => qr{\S} } },
        { ref => { not => qr{\S} } },
    ],
    MUST_SUCCEED);

run_produces_ok('mlir ident is not a TableGen symbol',
    [$query_py, qw(ident v5.4 add_kernel G)],
    [
        { def => { not => qr{\S} } },
        { ref => { not => qr{\S} } },
    ],
    MUST_SUCCEED);

run_produces_ok('C ident is not a TableGen symbol',
    [$query_py, qw(ident v5.4 i2c_acpi_notify G)],
    [
        { def => { not => qr{\S} } },
        { ref => { not => qr{\S} } },
    ],
    MUST_SUCCEED);

run_produces_ok('tablegen ident is visible in all-symbols search',
    [$query_py, qw(ident v5.4 TT_IntToPtrOp A)],
    [
        { def => qr{tablegen/ops\.td.+\bdef\b} },
    ],
    MUST_SUCCEED);

run_produces_ok('tablegen file query links records and skips code blocks',
    [$query_py, qw(file v5.4 /tablegen/ops.td)],
    [
        qr{Comment mentions TT_IntToPtrOp},
        qr{def not_in_code_block},
        qr{"TT_IntToPtrOp inside a string"},
        qr{\x{1b}\[31mTT_IntToPtrOp\x{1b}\[0m},
        qr{\x{1b}\[31mTT_Op\x{1b}\[0m},
        { not => qr{mentions \x{1b}\[31mTT_IntToPtrOp} },
        { not => qr{def \x{1b}\[31mnot_in_code_block} },
        { not => qr{"\x{1b}\[31mTT_IntToPtrOp} },
    ],
    MUST_SUCCEED);

run_produces_ok('mojo file query keeps text and links real idents',
    [$query_py, qw(file v5.4 /mojo/mojo_widgets.mojo)],
    [
        qr{Module docstring mentions mojo_make_widget},
        qr{# mojo_make_widget in a comment should not count},
        qr{"mojo_make_widget inside a string"},
        qr{\x{1b}\[31mmojo_make_widget\x{1b}\[0m\("demo"\)},
        qr{widget .\x{1b}\[31mmojo_make_widget\x{1b}\[0m\('tmpl'\)},
        qr{\x{1b}\[31mMojoWidget\x{1b}\[0m},
        { not => qr{# \x{1b}\[31mmojo_make_widget} },
        { not => qr{"\x{1b}\[31mmojo_make_widget} },
        { not => qr{mentions \x{1b}\[31mmojo_make_widget} },
    ],
    MUST_SUCCEED);

done_testing;
