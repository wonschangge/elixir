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
                definitions-cache-T.db);

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
