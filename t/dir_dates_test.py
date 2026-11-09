#!/usr/bin/env python3

#  This file is part of Elixir, a source code cross-referencer.
#
#  Elixir is free software: you can redistribute it and/or modify
#  it under the terms of the GNU Affero General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.

"""Unit tests for directory last-commit dates. Run directly or via prove."""

import os
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from elixir.dir_dates import (  # noqa: E402
    CACHE,
    COMMIT_MARK,
    DirDateCache,
    entry_dates_from_log_lines,
    load_dir_dates,
    repo_prefix,
)


def _mark(date):
    return COMMIT_MARK + date


class RepoPrefixTest(unittest.TestCase):
    def test_root_and_nested(self):
        self.assertEqual(repo_prefix(''), '')
        self.assertEqual(repo_prefix('/'), '')
        self.assertEqual(repo_prefix('/arch'), 'arch')
        self.assertEqual(repo_prefix('/drivers/i2c/'), 'drivers/i2c')


class LogParserTest(unittest.TestCase):
    def test_files_directories_and_first_date_wins(self):
        lines = [
            _mark('2021-06-02'),
            'README',
            'sub/new.txt',
            '',
            _mark('2020-01-15'),
            'README',
            'sub/nested.txt',
            'untouched',
        ]
        dates = entry_dates_from_log_lines(
            lines, ['README', 'sub', 'untouched'], '')
        self.assertEqual(dates, {
            'README': '2021-06-02',
            'sub': '2021-06-02',
            'untouched': '2020-01-15',
        })

        nested = entry_dates_from_log_lines(
            lines, ['nested.txt', 'new.txt', 'missing'], '/sub')
        self.assertEqual(nested, {
            'new.txt': '2021-06-02',
            'nested.txt': '2020-01-15',
        })

    def test_empty_commit_then_real_commit(self):
        # A merge with an empty name list is just a date line, then the next commit.
        lines = [
            _mark('2024-01-02'),
            _mark('2021-07-01'),
            'side.txt',
            '',
            _mark('2020-01-15'),
            'README',
        ]
        dates = entry_dates_from_log_lines(lines, ['side.txt', 'README'], '')
        self.assertEqual(dates, {
            'side.txt': '2021-07-01',
            'README': '2020-01-15',
        })

    def test_date_like_filename_is_not_a_commit_header(self):
        lines = [
            _mark('2024-02-02'),
            '2020-01-01',
        ]
        dates = entry_dates_from_log_lines(lines, ['2020-01-01'], '')
        self.assertEqual(dates, {'2020-01-01': '2024-02-02'})

    def test_invalid_mark_does_not_reuse_previous_date(self):
        lines = [
            _mark('2024-02-02'),
            'README',
            _mark('not-a-date'),
            'Makefile',
        ]
        dates = entry_dates_from_log_lines(lines, ['README', 'Makefile'], '')
        self.assertEqual(dates, {'README': '2024-02-02'})

    def test_quoted_git_path(self):
        lines = [
            _mark('2024-02-02'),
            '"quote\\"name.c"',
            '"caf\\303\\251.c"',
        ]
        dates = entry_dates_from_log_lines(
            lines, ['quote"name.c', 'café.c'], '')
        self.assertEqual(dates, {
            'quote"name.c': '2024-02-02',
            'café.c': '2024-02-02',
        })

    def test_stops_reading_once_every_name_is_known(self):
        def lines():
            yield _mark('2024-01-02')
            yield 'README'
            raise AssertionError('log walk should stop once README is dated')

        dates = entry_dates_from_log_lines(lines(), ['README'], '')
        self.assertEqual(dates, {'README': '2024-01-02'})

    def test_paths_outside_the_directory_are_ignored(self):
        lines = [
            _mark('2024-05-06'),
            'drivers/other/x.c',
            'README',
        ]
        dates = entry_dates_from_log_lines(lines, ['i2c-core.c'], 'drivers/i2c')
        self.assertEqual(dates, {})


class CacheTest(unittest.TestCase):
    def test_ttl_complete_wins_and_eviction(self):
        class Clock:
            def __init__(self):
                self.now = 0

            def __call__(self):
                return self.now

        clock = Clock()
        cache = DirDateCache(ttl=300, partial_ttl=30, max_entries=2, clock=clock)
        key = ('repo', 'v1', '/arch')

        cache.store(key, {'a': '2020-01-01'}, {'a', 'b'}, complete=False)
        self.assertEqual(cache.lookup(key, {'a'}), {'a': '2020-01-01'})
        self.assertIsNone(cache.lookup(key, {'a', 'b', 'c'}))

        clock.now = 31
        self.assertIsNone(cache.lookup(key, {'a'}))

        clock.now = 0
        cache.store(key, {'a': '2020-01-02', 'b': '2020-01-03'}, {'a', 'b'}, complete=True)
        cache.store(key, {'a': '1999-01-01'}, {'a'}, complete=False)
        self.assertEqual(cache.lookup(key, {'a', 'b'}), {
            'a': '2020-01-02',
            'b': '2020-01-03',
        })
        # Searched name with no commit still counts as a hit.
        self.assertEqual(cache.lookup(key, {'b'}), {
            'a': '2020-01-02',
            'b': '2020-01-03',
        })

        clock.now = 299
        self.assertIsNotNone(cache.lookup(key, {'a'}))
        clock.now = 301
        self.assertIsNone(cache.lookup(key, {'a'}))

        clock.now = 0
        cache.store(('r', 'v', '1'), {'a': '2020-01-01'}, {'a'}, complete=True)
        cache.store(('r', 'v', '2'), {'a': '2020-01-01'}, {'a'}, complete=True)
        cache.store(('r', 'v', '3'), {'a': '2020-01-01'}, {'a'}, complete=True)
        self.assertIsNone(cache.lookup(('r', 'v', '1'), {'a'}))
        self.assertIsNotNone(cache.lookup(('r', 'v', '3'), {'a'}))


class GitWalkTest(unittest.TestCase):
    def setUp(self):
        CACHE.clear()

    def tearDown(self):
        CACHE.clear()

    def _git(self, cwd, *args, author=None, committer=None):
        env = os.environ.copy()
        when = committer or author or '2020-01-15T00:00:00Z'
        env['GIT_AUTHOR_DATE'] = author or when
        env['GIT_COMMITTER_DATE'] = committer or when
        subprocess.check_call(
            ['git', '-C', cwd,
             '-c', 'user.email=test@example.com',
             '-c', 'user.name=test',
             '-c', 'init.defaultBranch=main',
             '-c', 'commit.gpgsign=false',
             *args],
            env=env,
            stdout=subprocess.DEVNULL,
        )

    def _repo(self):
        tmp = tempfile.TemporaryDirectory()
        cwd = tmp.name
        self._git(cwd, 'init')
        os.makedirs(os.path.join(cwd, 'sub'))
        with open(os.path.join(cwd, 'README'), 'w') as fh:
            fh.write('a\n')
        with open(os.path.join(cwd, 'untouched'), 'w') as fh:
            fh.write('u\n')
        with open(os.path.join(cwd, 'sub', 'nested.txt'), 'w') as fh:
            fh.write('n\n')
        os.symlink('README', os.path.join(cwd, 'link.txt'))
        self._git(cwd, 'add', '.')
        self._git(cwd, 'commit', '-m', 'initial',
                  author='2020-01-15T10:00:00Z', committer='2020-01-15T12:00:00Z')

        with open(os.path.join(cwd, 'README'), 'a') as fh:
            fh.write('b\n')
        with open(os.path.join(cwd, 'sub', 'new.txt'), 'w') as fh:
            fh.write('new\n')
        self._git(cwd, 'add', '.')
        self._git(cwd, 'commit', '-m', 'update',
                  author='2021-06-01T10:00:00Z', committer='2021-06-02T08:30:00Z')
        self._git(cwd, 'tag', 'v1')
        env = os.environ.copy()
        env['LXR_REPO_DIR'] = cwd
        env['LXR_DATA_DIR'] = cwd
        return tmp, env

    def test_dates_match_committer_date_and_cache(self):
        tmp, env = self._repo()
        with tmp:
            # README and sub are both touched by the newest commit, so the
            # walk can stop before older history. Killing git there must
            # still return those dates.
            early = load_dir_dates(env, 'v1', '', ['README', 'sub'])
            self.assertEqual(early, {
                'README': '2021-06-02',
                'sub': '2021-06-02',
            })
            CACHE.clear()

            root = load_dir_dates(env, 'v1', '', ['README', 'sub', 'untouched', 'link.txt'])
            self.assertEqual(root, {
                'README': '2021-06-02',
                'sub': '2021-06-02',
                'untouched': '2020-01-15',
                'link.txt': '2020-01-15',
            })
            nested = load_dir_dates(env, 'v1', '/sub', ['nested.txt', 'new.txt'])
            self.assertEqual(nested, {
                'nested.txt': '2020-01-15',
                'new.txt': '2021-06-02',
            })

            with patch('elixir.dir_dates.subprocess.Popen',
                       side_effect=AssertionError('cached directory should not run git')):
                again = load_dir_dates(env, 'v1', '', ['README', 'sub'])
            self.assertEqual(again, {
                'README': '2021-06-02',
                'sub': '2021-06-02',
            })

    def test_unknown_revision_is_empty(self):
        tmp, env = self._repo()
        with tmp:
            with self.assertLogs('elixir.dir_dates', level='WARNING'):
                dates = load_dir_dates(env, 'no-such-tag', '', ['README'])
            self.assertEqual(dates, {})


if __name__ == '__main__':
    unittest.main()
