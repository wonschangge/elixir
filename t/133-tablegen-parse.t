#!/usr/bin/env perl
# 133-tablegen-parse.t: TableGen definition parser and reference tokenizer.
#
# SPDX-License-Identifier: AGPL-3.0-or-later

use FindBin '$Bin';
use lib $Bin;
use File::Spec;

use Test::More;

use TestHelpers;

my $script = File::Spec->catfile($Bin, 'tablegen_parse_test.py');
my ($status, $out, $err) = run_program('python3', $script);
ok($status == 0, 'tablegen parser and tokenizer')
    or diag "@$out @$err";

done_testing;
