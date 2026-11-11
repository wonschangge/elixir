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
        qr{href="/testproj/v5\.4/source/\.gitignore"},
        qr{href="/testproj/v5\.4/source/\.agents"},
        qr{href="/testproj/v5\.4/source/\.github"},
        qr{<option value="P"}, qr{Python},
        qr{<option value="T"}, qr{TypeScript/JavaScript},
        qr{<option value="J"}, qr{Mojo},
        qr{href="/testproj/v5\.4/source/issue102\.c" data-commit-date="\d{4}-\d{2}-\d{2}"},
        qr{href="/testproj/v5\.4/source/arch" data-commit-date="\d{4}-\d{2}-\d{2}"},
        qr{href="/testproj/v5\.4/source/\.gitignore" data-commit-date="\d{4}-\d{2}-\d{2}"},
        qr{href="/testproj/v5\.4/source/\.agents" data-commit-date="\d{4}-\d{2}-\d{2}"},
        qr{<time datetime="\d{4}-\d{2}-\d{2}">\d{4}-\d{2}-\d{2}</time>},
        # '.' / '..' are not tree entries, and '.git' is not invented.
        { not => qr{^\s*\.\s*$}m },
        { not => qr{^\s*\.\.\s*$}m },
        { not => qr{/source/\.git(?:/|")} },
        { not => qr{Parent directory} },
        { not => qr{id="wrap-lines"} },
        { not => qr{id="markdown-original"} } ], 1;

# Hidden directories and files that exist in the tree use the same URLs
# as ordinary paths.
http_request_ok 'hidden directory listing', $tenv,
    '/testproj/v5.4/source/.agents',
    [ qr{^Content-Type:\s*text/html},
        qr{class="tree-icon icon-back"[^>]*>Parent directory},
        qr{href="/testproj/v5\.4/source/\.agents/notes\.txt"},
        qr{href="/testproj/v5\.4/source/\.agents/\.secret"},
        qr{href="/testproj/v5\.4/source/\.agents/notes\.txt" data-commit-date="\d{4}-\d{2}-\d{2}"},
        { not => qr{^\s*\.\s*$}m },
        { not => qr{^\s*\.\.\s*$}m },
        { not => qr{/source/\.git(?:/|")} } ], 1;

http_request_ok 'hidden directory of ordinary files', $tenv,
    '/testproj/v5.4/source/.github',
    [ qr{^Content-Type:\s*text/html},
        qr{href="/testproj/v5\.4/source/\.github/CODEOWNERS"} ], 1;

http_request_ok 'hidden file', $tenv,
    '/testproj/v5.4/source/.gitignore',
    [ qr{^Content-Type:\s*text/html},
        qr{Committed hidden file for directory listings},
        { not => qr{File not found} },
        { not => qr{Path contains characters that are not allowed} } ], 1;

http_request_ok 'file inside a hidden directory', $tenv,
    '/testproj/v5.4/source/.agents/notes.txt',
    [ qr{^Content-Type:\s*text/html},
        qr{agent notes},
        { not => qr{File not found} } ], 1;

http_request_ok 'hidden file inside a hidden directory', $tenv,
    '/testproj/v5.4/source/.agents/.secret',
    [ qr{^Content-Type:\s*text/html},
        qr{secret note},
        { not => qr{File not found} } ], 1;

http_request_ok 'subdirectory dates keep the parent row', $tenv,
    '/testproj/v5.4/source/drivers/i2c',
    [ qr{^Content-Type:\s*text/html},
        qr{class="tree-icon icon-back"[^>]*>Parent directory},
        qr{href="/testproj/v5\.4/source/drivers/i2c/i2c-core-acpi\.c" data-commit-date="\d{4}-\d{2}-\d{2}"},
        qr{href="/testproj/v5\.4/source/drivers/i2c/\.keep"},
        qr{bytes} ], 1;

http_request_ok 'hidden file in an ordinary directory', $tenv,
    '/testproj/v5.4/source/drivers/i2c/.keep',
    [ qr{^Content-Type:\s*text/html},
        qr{i2c keep},
        { not => qr{File not found} } ], 1;

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

http_request_ok 'mojo ident query', $tenv, '/testproj/v5.4/J/ident/mojo_make_widget',
    [
        qr{^Content-Type:\s*text/html},
        qr{mojo/mojo_widgets\.mojo},
        qr{line 40},
        qr{as a function},
        qr{Defined in},
        qr{mojo/mojo_consumer\.mojo},
        qr{<option value="J"},
        qr{\bMojo\b},
    ], 1;

http_request_ok 'mojo struct ident query', $tenv, '/testproj/v5.4/J/ident/MojoWidget',
    [
        qr{^Content-Type:\s*text/html},
        qr{as a struct},
        qr{line 19},
        qr{Referenced in},
    ], 1;

http_request_ok 'mojo trait ident query', $tenv, '/testproj/v5.4/J/ident/MojoWidgetLike',
    [
        qr{^Content-Type:\s*text/html},
        qr{as a trait},
        qr{line 31},
    ], 1;

http_request_ok 'mojo ident is absent from the C family', $tenv,
    '/testproj/v5.4/C/ident/mojo_make_widget',
    [
        qr{^Content-Type:\s*text/html},
        qr{Unknown identifier 'mojo_make_widget'},
    ], 1;

http_request_ok 'mojo source links identifiers', $tenv,
    '/testproj/v5.4/source/mojo/mojo_widgets.mojo',
    [
        qr{^Content-Type:\s*text/html},
        qr{class="ident" href="/testproj/v5.4/J/ident/mojo_make_widget"},
        qr{class="ident" href="/testproj/v5.4/J/ident/MojoWidget"},
        qr{mojo_make_widget in a comment should not count},
    ], 1;

http_request_ok 'mojo fire-suffix ident query', $tenv, '/testproj/v5.4/J/ident/MojoSpark',
    [
        qr{^Content-Type:\s*text/html},
        qr{as a struct},
        qr{line 3},
        qr{mojo/spark},
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
            { not => qr{id="wrap-lines"} },
            { not => qr{id="markdown-original"} },
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

http_request_ok 'source view offers line wrap and not markdown', $tenv,
    '/testproj/v5.4/source/issue102.c',
    [
        qr{^Content-Type:\s*text/html},
        qr{id="wrap-lines"},
        qr{Wrap lines},
        qr{class="ident"},
        { not => qr{id="markdown-original"} },
        { not => qr{markdown-preview\.js} },
        { not => qr{id="markdown-preview"} },
    ], 1;

http_request_ok 'markdown file previews by default', $tenv,
    '/testproj/v5.4/source/README.md',
    [
        qr{^Content-Type:\s*text/html},
        qr{id="wrap-lines"},
        qr{Wrap lines},
        qr{id="markdown-original"},
        qr{Original source},
        qr{id="markdown-view"},
        qr{data-source-base="/testproj/v5\.4/source"},
        qr{data-file-path="/README\.md"},
        qr{id="markdown-preview"},
        qr{id="markdown-source-data"},
        qr{/static/markdown-preview\.js\?v=2},
        qr{/static/style\.css\?v=20},
        qr{/static/script\.js\?v=19},
        qr{Elixir notes},
        qr{docs/note\.markdown},
        # Unchecked: rendered preview is the default. The box is not checked.
        # markdown-ready is added only after the client fills the preview.
        { not => qr{id="markdown-original"[^>]*\bchecked\b} },
        { not => qr{markdown-ready} },
        { not => qr{<script>alert\('xss-md'\)} },
        { not => qr{</script><script>} },
    ], 1;

# The highlighted source stays visible until JS adds markdown-ready.
# Hiding it on the js class alone is the blank-pane bug.
{
    open my $css_fh, '<', "$Bin/../static/style.css" or die $!;
    local $/;
    my $css = <$css_fh>;
    close $css_fh;
    like $css,
        qr/\.js \.source-markdown\.markdown-ready:not\(\.show-source\) \.markdown-source \{\s*display:\s*none;\s*\}/,
        'source hides only after markdown-ready';
    like $css,
        qr/\.js \.source-markdown\.markdown-ready:not\(\.show-source\) \.markdown-preview \{\s*display:\s*block;\s*\}/,
        'preview shows only after markdown-ready';
    like $css,
        qr/\.js main:has\(\.source-markdown\.markdown-ready:not\(\.show-source\)\) \{\s*width:\s*100%;\s*max-width:\s*100%;\s*\}/,
        'viewport fit waits for markdown-ready';
    unlike $css,
        qr/\.js \.source-markdown:not\(\.show-source\) \.markdown-source \{\s*display:\s*none;\s*\}/,
        'js class alone does not hide the source';
    unlike $css,
        qr/\.js main:has\(\.source-markdown:not\(\.show-source\)\) \{/,
        'js class alone does not force the preview viewport width';
}

http_request_ok 'markdown extension uses the same preview', $tenv,
    '/testproj/v5.4/source/docs/note.markdown',
    [
        qr{^Content-Type:\s*text/html},
        qr{id="markdown-original"},
        qr{Original source},
        qr{data-file-path="/docs/note\.markdown"},
        qr{/static/markdown-preview\.js\?v=2},
        qr{Back to},
        { not => qr{<script>alert} },
    ], 1;

done_testing;
