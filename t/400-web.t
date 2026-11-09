#!/usr/bin/env perl
# t/400-web.pl: Test web.py
#
# Copyright (c) 2020 Christopher White, <cxwembedded@gmail.com>.
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
# # You should have received a copy of the GNU Affero General Public License
# along with Elixir.  If not, see <http://www.gnu.org/licenses/>.
#
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# This file uses core Perl modules only.

use FindBin '$Bin';
use lib $Bin;

use Test::More;

use TestEnvironment;
use TestHelpers;

# ===========================================================================
# Main

# Set up for the tests
my $tenv = TestEnvironment->new;
$tenv->build_repo(sibling_abs_path('tree'));	# dies on error
$tenv->build_db;
$tenv->update_env;

diag $tenv->report;

http_request_ok 'index query', $tenv, '/testproj/v5.4/source',
    [ qr{^Content-Type:\s*text/html}, qr{href="/testproj/v5.4/source/issue102.c"},
        qr{href="/testproj/v5.4/source/arch"},
        qr{href="/testproj/v5.4/source/python"},
        qr{href="/testproj/v5.4/source/typescript"},
        qr{<option value="P"}, qr{Python},
        qr{<option value="T"}, qr{TypeScript/JavaScript} ], 1;

http_request_ok 'identifier query', $tenv, '/testproj/v5.4/ident/gsb_buffer',
    [ qr{^Content-Type:\s*text/html}, qr{\bgsb_buffer\b},
        qr{source/drivers/i2c/i2c-core-acpi\.c#L23},
        qr{as a struct} ], 1;

# Doc comments: testcases pulled from t/300
http_request_ok 'doc-comment query (nonexistent)', $tenv,
    '/testproj/v5.4/ident/SOME_NONEXISTENT_IDENTIFIER_XYZZY_PLUGH',
    [ qr{^Content-Type:\s*text/html}, qr{Unknown identifier} ], 1;

http_request_ok 'doc-comment query (existent but not documented)', $tenv,
    '/testproj/v5.4/ident/gsb_buffer',   # in drivers/i2c/i2c-core-acpi.c
    [
        qr{^Content-Type:\s*text/html},
        { not => qr{\bDocumented in\b} },
    ], 1;

http_request_ok 'ident query (existent, function, documented in C file)', $tenv,
    '/testproj/v5.4/ident/i2c_acpi_get_i2c_resource',
    [
        qr{^Content-Type:\s*text/html},
        qr{\bDocumented in \d},
        qr{source/drivers/i2c/i2c-core-acpi\.c#L45},
    ], 1;

http_request_ok 'ident query (existent, function, documented in C file, #102)',
    $tenv, '/testproj/v5.4/ident/documented_function_XYZZY',
    [
        qr{^Content-Type:\s*text/html},
        qr{\bDocumented in \d},
        qr{source/issue102\.c#L6},
    ], 1;

http_request_ok 'python ident query', $tenv, '/testproj/v5.4/P/ident/py_make_widget',
    [
        qr{^Content-Type:\s*text/html},
        qr{python/py_widgets\.py},
        qr{line 16},
        qr{as a function},
        qr{python/py_consumer\.py},
        qr{<option value="P"},
        qr{\bPython\b},
    ], 1;

http_request_ok 'python ident is absent from the C family', $tenv,
    '/testproj/v5.4/C/ident/py_make_widget',
    [
        qr{^Content-Type:\s*text/html},
        qr{Unknown identifier 'py_make_widget'},
    ], 1;

http_request_ok 'python source links identifiers', $tenv,
    '/testproj/v5.4/source/python/py_widgets.py',
    [
        qr{^Content-Type:\s*text/html},
        qr{class="ident" href="/testproj/v5.4/P/ident/py_make_widget"},
        qr{class="ident" href="/testproj/v5.4/P/ident/PyWidget"},
        qr{py_make_widget in a comment should not count},
        { not => qr{source-image} },
        { not => qr{\bdownload=} },
    ], 1;

http_request_ok 'typescript ident query', $tenv, '/testproj/v5.4/T/ident/ts_make_widget',
    [
        qr{^Content-Type:\s*text/html},
        qr{typescript/ts_widgets\.ts},
        qr{line 22},
        qr{as a function},
        qr{typescript/js_consumer\.js},
        qr{<option value="T"},
        qr{TypeScript/JavaScript},
    ], 1;

http_request_ok 'typescript ident is absent from the C family', $tenv,
    '/testproj/v5.4/C/ident/ts_make_widget',
    [
        qr{^Content-Type:\s*text/html},
        qr{Unknown identifier 'ts_make_widget'},
    ], 1;

http_request_ok 'typescript source links identifiers', $tenv,
    '/testproj/v5.4/source/typescript/ts_widgets.ts',
    [
        qr{^Content-Type:\s*text/html},
        qr{class="ident" href="/testproj/v5.4/T/ident/ts_make_widget"},
        qr{class="ident" href="/testproj/v5.4/T/ident/TsWidget"},
        qr{ts_make_widget in a comment should not count},
    ], 1;

http_request_ok 'tsx source links tags but not JSX text', $tenv,
    '/testproj/v5.4/source/typescript/ts_widget_view.tsx',
    [
        qr{^Content-Type:\s*text/html},
        qr{class="ident" href="/testproj/v5.4/T/ident/TsWidget"},
        qr{class="ident" href="/testproj/v5.4/T/ident/render"},
        qr{>ts_make_widget<},
    ], 1;

# Image blobs are previewed, not highlighted. SVG markup must stay out of
# the HTML page (it is loaded only through <img src="?raw">).
my %image_types = (
    'images/pixel.png' => 'image/png',
    'images/pixel.jpg' => 'image/jpeg',
    'images/pixel.jpeg' => 'image/jpeg',
    'images/pixel.gif' => 'image/gif',
    'images/pixel.webp' => 'image/webp',
    'images/badge.svg' => 'image/svg+xml',
);

foreach my $path (sort keys %image_types) {
    my $ctype = $image_types{$path};
    my ($name) = $path =~ m{/([^/]+)$};

    http_request_ok "image preview $name", $tenv,
        "/testproj/v5.4/source/$path",
        [
            qr{^Content-Type:\s*text/html},
            qr{class="lxrcode source-image"},
            qr{<img src="\?raw" alt="\Q$name\E"},
            qr{download="\Q$name\E"},
            { not => qr{highlighttable} },
            { not => qr{alert\('xss'\)} },
        ];

    http_request_ok "image raw $name", $tenv,
        "/testproj/v5.4/source/$path?raw",
        [
            qr{^Content-Type:\s*\Q$ctype\E\s*$},
            qr{^content-disposition:\s*inline;}i,
            qr{^x-content-type-options:\s*nosniff}i,
            qr{^content-security-policy:.*\bsandbox\b}i,
        ];
}

http_request_ok 'png raw keeps the image bytes', $tenv,
    '/testproj/v5.4/source/images/pixel.png?raw',
    [ qr{\x89PNG\r\n} ];

http_request_ok 'svg raw still serves the file itself', $tenv,
    '/testproj/v5.4/source/images/badge.svg?raw',
    [ qr{<svg xmlns="http://www.w3.org/2000/svg"}, qr{alert\('xss'\)} ];

done_testing;
