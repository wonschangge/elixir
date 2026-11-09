#!/usr/bin/env perl
# t/410-dir-dates.t: Last-commit dates for directory listings.
#
# SPDX-License-Identifier: AGPL-3.0-or-later

use FindBin '$Bin';
use Test::More tests => 1;

my $status = system('python3', "$Bin/dir_dates_test.py");
ok($status == 0, 'directory date unit tests');
