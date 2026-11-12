#!/usr/bin/env perl
# 131-rust-parse.t: Rust ctags kinds and the const/union supplement.
#
# SPDX-License-Identifier: AGPL-3.0-or-later

use FindBin '$Bin';
use lib $Bin;
use File::Spec;

use Test::More;

use TestHelpers;

my $script = File::Spec->catfile($Bin, 'rust_parse_test.py');
my ($status, $out, $err) = run_program('python3', $script);
ok($status == 0, 'rust parser and ctags kinds')
    or diag "@$out @$err";

done_testing;
