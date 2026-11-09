#  This file is part of Elixir, a source code cross-referencer.
#
#  Copyright (C) 2017--2026 Mikaël Bouillot <mikael.bouillot@bootlin.com>
#  and contributors
#
#  Elixir is free software: you can redistribute it and/or modify
#  it under the terms of the GNU Affero General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.

"""Last-commit dates for one directory listing.

Dates come from a single `git log` of the directory (see script.sh
`get-dir-log`), newest commit first. The walk stops as soon as every
immediate child — file or directory — has been seen, so a directory whose
entries were all touched recently does not replay the whole history.
Directory dates fall out of the same walk: a subdirectory's date is the
newest commit that changes anything under it.

Results are cached in the worker process. A finished walk is reused for a
few minutes (the commit it describes does not change). A walk that hits the
time budget is cached briefly and any entry still missing a date is omitted;
callers leave that cell blank instead of failing the page.
"""

import logging
import os
import re
import signal
import subprocess
import threading
import time
from collections import OrderedDict
from collections.abc import Iterable

from .lib import CURRENT_DIR, decode

logger = logging.getLogger(__name__)

# Commit headers in `get-dir-log` output are prefixed with this byte so a
# filename cannot be mistaken for a YYYY-MM-DD line.
COMMIT_MARK = '\x1f'

# Finished walks are immutable for a given tag, but tags can be moved, so the
# cache stays short. Partial walks (time budget) are kept even shorter so a
# later request can try again without repeating the walk on every hit.
DIR_DATE_CACHE_TTL_SECONDS = 300
DIR_DATE_PARTIAL_TTL_SECONDS = 30
DIR_DATE_WALK_BUDGET_SECONDS = 8
DIR_DATE_CACHE_MAX_ENTRIES = 128

_DATE_RE = re.compile(r'^\d{4}-\d{2}-\d{2}$')


def repo_prefix(path: str) -> str:
    """Elixir directory path ('', '/arch', '/drivers/i2c/') -> git path prefix."""
    if path.startswith('/'):
        path = path[1:]
    return path.strip('/')


def _unquote_git_path(path: str) -> str:
    """Undo git's C-style quoting. Unquoted paths are returned unchanged."""
    if len(path) < 2 or path[0] != '"' or path[-1] != '"':
        return path

    data = bytearray()
    inner = path[1:-1]
    i = 0
    simple = {
        'n': b'\n',
        't': b'\t',
        'b': b'\b',
        'a': b'\a',
        'f': b'\f',
        'v': b'\v',
        '"': b'"',
        '\\': b'\\',
    }
    while i < len(inner):
        ch = inner[i]
        if ch != '\\':
            data.extend(ch.encode('utf-8'))
            i += 1
            continue
        i += 1
        if i >= len(inner):
            break
        esc = inner[i]
        i += 1
        if esc in simple:
            data.extend(simple[esc])
        elif '0' <= esc <= '7':
            octal = esc
            for _ in range(2):
                if i < len(inner) and '0' <= inner[i] <= '7':
                    octal += inner[i]
                    i += 1
                else:
                    break
            data.append(int(octal, 8))
        else:
            data.extend(esc.encode('utf-8'))
    return data.decode('utf-8', 'surrogateescape')


def _child_name(path: str, prefix: str):
    """Map a repo-relative path onto an immediate child of prefix, or None."""
    path = _unquote_git_path(path)
    if prefix:
        prefix_slash = prefix + '/'
        if not path.startswith(prefix_slash):
            return None
        rel = path[len(prefix_slash):]
    else:
        rel = path
    if not rel:
        return None
    return rel.split('/', 1)[0]


def entry_dates_from_log_lines(lines, names, prefix: str) -> dict[str, str]:
    """Parse `get-dir-log` lines into {child name: YYYY-MM-DD}.

    `lines` is newest commit first. Iteration stops once every name has a
    date, so callers streaming a live `git log` can kill it early.
    `prefix` is an Elixir path or an already-relative git prefix.
    """
    wanted = set(names)
    found = {}
    if not wanted:
        return found

    prefix = repo_prefix(prefix)
    date = None
    for line in lines:
        if line.startswith(COMMIT_MARK):
            candidate = line[len(COMMIT_MARK):]
            date = candidate if _DATE_RE.fullmatch(candidate) else None
            continue
        if not line or date is None:
            continue
        child = _child_name(line, prefix)
        if child is None or child not in wanted or child in found:
            continue
        found[child] = date
        if len(found) == len(wanted):
            break
    return found


class DirDateCache:
    """Small TTL cache keyed by repository, version, and directory path."""

    def __init__(self, ttl=DIR_DATE_CACHE_TTL_SECONDS,
                 partial_ttl=DIR_DATE_PARTIAL_TTL_SECONDS,
                 max_entries=DIR_DATE_CACHE_MAX_ENTRIES,
                 clock=time.monotonic):
        self.ttl = ttl
        self.partial_ttl = partial_ttl
        self.max_entries = max_entries
        self.clock = clock
        self._lock = threading.Lock()
        # key -> (expires_at, dates, searched names, complete)
        self._data = OrderedDict()

    def clear(self):
        with self._lock:
            self._data.clear()

    def lookup(self, key, wanted: set):
        """Return cached dates when `wanted` was part of the stored search.

        None means the cache cannot answer. A returned dict may omit names
        that have no commit date; that is still a hit.
        """
        now = self.clock()
        with self._lock:
            item = self._data.get(key)
            if item is None:
                return None
            expires, dates, searched, _complete = item
            if expires <= now:
                del self._data[key]
                return None
            if not wanted <= searched:
                return None
            self._data.move_to_end(key)
            return dict(dates)

    def store(self, key, dates: dict, searched: set, complete: bool):
        now = self.clock()
        with self._lock:
            current = self._data.get(key)
            if current is not None:
                _expires, _dates, old_searched, old_complete = current
                # A finished walk is authoritative. Don't let a timed-out
                # walk of the same (or a smaller) name set replace it.
                if old_complete and not complete and searched <= old_searched:
                    self._data.move_to_end(key)
                    return
            expires = now + (self.ttl if complete else self.partial_ttl)
            self._data[key] = (expires, dict(dates), frozenset(searched), complete)
            self._data.move_to_end(key)
            while len(self._data) > self.max_entries:
                self._data.popitem(last=False)


CACHE = DirDateCache()


def _kill_process(proc: subprocess.Popen):
    if proc.poll() is not None:
        return
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except ProcessLookupError:
        return
    except PermissionError:
        try:
            proc.kill()
        except ProcessLookupError:
            return


def _walk_dir_dates(env: dict, version: str, path: str, wanted: set, budget_s: float):
    """Run one git log. Returns (dates, status) with status complete|partial|error."""
    script = os.path.join(CURRENT_DIR, 'script.sh')
    run_env = dict(env)
    run_env['GIT_TERMINAL_PROMPT'] = '0'
    run_env['GIT_OPTIONAL_LOCKS'] = '0'

    proc = subprocess.Popen(
        [script, 'get-dir-log', version, path],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
        env=run_env,
        start_new_session=True,
    )
    timer = threading.Timer(budget_s, _kill_process, args=(proc,))
    timer.daemon = True
    timer.start()
    rc = 1

    def lines():
        assert proc.stdout is not None
        for raw in proc.stdout:
            yield decode(raw.rstrip(b'\r\n'))

    try:
        dates = entry_dates_from_log_lines(lines(), wanted, path)
    finally:
        timer.cancel()
        _kill_process(proc)
        if proc.stdout is not None:
            proc.stdout.close()
        try:
            rc = proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            _kill_process(proc)
            rc = proc.wait(timeout=5)

    all_found = wanted <= dates.keys()
    if all_found or rc == 0:
        status = 'complete'
    elif rc > 0 and not dates:
        status = 'error'
        logger.warning('directory date walk failed for %s %s (git status %s)', version, path, rc)
    else:
        status = 'partial'
        logger.info(
            'directory date walk hit the time budget for %s %s (%d of %d entries)',
            version, path, len(dates), len(wanted),
        )
    return dates, status


def load_dir_dates(env: dict, version: str, path: str, names: Iterable[str],
                   budget_s: float = DIR_DATE_WALK_BUDGET_SECONDS) -> dict[str, str]:
    """Return {entry name: YYYY-MM-DD} for direct children of `path`.

    Never raises. Names with no available date are omitted.
    """
    try:
        wanted_list = []
        seen = set()
        for name in names:
            if name not in seen:
                seen.add(name)
                wanted_list.append(name)
        if not seen:
            return {}

        key = (env.get('LXR_REPO_DIR', ''), version, path)
        cached = CACHE.lookup(key, seen)
        if cached is not None:
            return {name: cached[name] for name in wanted_list if name in cached}

        dates, status = _walk_dir_dates(env, version, path, seen, budget_s)
        if status == 'error':
            return {}
        CACHE.store(key, dates, seen, complete=(status == 'complete'))
        return {name: dates[name] for name in wanted_list if name in dates}
    except Exception:
        logger.warning('directory date lookup failed for %s %s', version, path, exc_info=True)
        return {}
