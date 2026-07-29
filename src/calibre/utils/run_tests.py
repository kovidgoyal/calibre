#!/usr/bin/env python
# License: GPLv3 Copyright: 2016, Kovid Goyal <kovid at kovidgoyal.net>

import functools
import importlib
import importlib.resources
import json
import os
import queue
import sys
import tempfile
import threading
import unittest

from calibre.constants import debug, isbsd, islinux, ismacos, iswindows
from calibre.utils.monotonic import monotonic
from calibre.utils.serialize import msgpack_dumps
from polyglot.binary import as_hex_unicode

is_ci = os.environ.get('CI', '').lower() == 'true'

# Below this many tests, skip worker processes and run in-process instead.
_PARALLEL_MIN = 32

# ANSI colours – only when stdout is a real terminal.
_IS_TTY: bool = sys.stdout.isatty()
_USE_COLOR: bool = _IS_TTY
_R = '\033[0m'  # reset
_BD = '\033[1m'  # bold
_DM = '\033[2m'  # dim
_GR = '\033[32m'  # green
_RD = '\033[31m'  # red
_YL = '\033[33m'  # yellow
_CY = '\033[36m'  # cyan


def _c(code: str, text: str) -> str:
    """Wrap *text* in an ANSI escape sequence if colour output is enabled."""
    return f'{code}{text}{_R}' if _USE_COLOR else text


def no_endl(f):
    @functools.wraps(f)
    def func(*args, **kwargs):
        self = f.__self__
        orig = self.stream.writeln
        self.stream.writeln = self.stream.write
        try:
            return f(*args, **kwargs)
        finally:
            self.stream.writeln = orig

    return func


class TestResult(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.start_time = {}
        for x in ('Success', 'Error', 'Failure', 'Skip', 'ExpectedFailure', 'UnexpectedSuccess'):
            x = 'add' + x
            setattr(self, x, no_endl(getattr(self, x)))
        self.times = {}

    def startTest(self, test):
        self.start_time[test] = monotonic()
        return super().startTest(test)

    def stopTest(self, test):
        orig = self.stream.writeln
        try:
            self.stream.writeln = self.stream.write  # type: ignore
            super().stopTest(test)
            elapsed = monotonic()
            elapsed -= self.start_time.get(test, elapsed)
            self.times[test] = elapsed
        finally:
            self.stream.writeln = orig  # type: ignore
            self.stream.writeln(f' [{elapsed:.1f} s]')

    def stopTestRun(self):
        super().stopTestRun()
        if self.wasSuccessful():
            tests = sorted(self.times, key=self.times.__getitem__, reverse=True)
            slowest = [f'{t.id()} [{self.times[t]:.1f} s]' for t in tests[:3]]
            if len(slowest) > 1:
                self.stream.writeln('\nSlowest tests: {}'.format(' '.join(slowest)))


def find_tests_in_package(package, excludes=('main.py',)):
    items = [path.name for path in importlib.resources.files(package).iterdir()]
    suits = []
    excludes = set(excludes) | {x + 'c' for x in excludes}
    seen = set()
    for x in items:
        if (x.endswith(('.py', '.pyc'))) and x not in excludes:
            q = x.rpartition('.')[0]
            if q in seen:
                continue
            seen.add(q)
            m = importlib.import_module(package + '.' + x.partition('.')[0])
            suits.append(unittest.defaultTestLoader.loadTestsFromModule(m))
    return unittest.TestSuite(suits)


def itertests(suite):
    stack = [suite]
    while stack:
        suite = stack.pop()
        for test in suite:
            if isinstance(test, unittest.TestSuite):
                stack.append(test)
                continue
            if test.__class__.__name__ == 'ModuleImportFailure':
                raise Exception(f'Failed to import a test module: {test}')
            yield test


def init_env():
    from calibre.ebooks.metadata.book.base import reset_field_metadata
    from calibre.ebooks.oeb.polish.utils import setup_css_parser_serialization
    from calibre.utils.config_base import reset_tweaks_to_default

    reset_tweaks_to_default()
    reset_field_metadata()
    setup_css_parser_serialization()


def filter_tests(suite, test_ok):
    ans = unittest.TestSuite()
    added = set()
    for test in itertests(suite):
        if test_ok(test) and test not in added:
            ans.addTest(test)
            added.add(test)
    return ans


def filter_tests_by_name(suite, *names):
    names = {x if x.startswith('test_') else 'test_' + x for x in names}

    def q(test):
        return test._testMethodName in names

    return filter_tests(suite, q)


def remove_tests_by_name(suite, *names):
    names = {x if x.startswith('test_') else 'test_' + x for x in names}

    def q(test):
        return test._testMethodName not in names

    return filter_tests(suite, q)


def filter_tests_by_module(suite, *names):
    names = frozenset(names)

    def q(test):
        m = test.__class__.__module__.rpartition('.')[-1]
        return m in names

    return filter_tests(suite, q)


# ─── Parallel runner ──────────────────────────────────────────────────────────


class PipeTestResult(unittest.TestResult):
    """
    Writes test events as newline-delimited JSON to a text stream.
    Used inside worker processes; the master reads and aggregates the events.

    Event schema (field 'e'):
      's'    – test started (no elapsed)
      'ok'   – addSuccess
      'fail' – addFailure   (+ 'msg')
      'err'  – addError     (+ 'msg')
      'skip' – addSkip      (+ 'msg')
      'xf'   – addExpectedFailure (+ 'msg')
      'xp'   – addUnexpectedSuccess
    All events except 's' carry 't' (elapsed seconds as float).
    """

    def __init__(self, write_fd: int) -> None:
        super().__init__()
        self._out = open(write_fd, 'w', buffering=1, closefd=True)
        self._start: dict[str, float] = {}

    def _emit(self, record: dict) -> None:
        try:
            self._out.write(json.dumps(record, ensure_ascii=False) + '\n')
            self._out.flush()
        except OSError:
            pass

    def startTest(self, test: unittest.TestCase) -> None:
        super().startTest(test)
        self._start[test.id()] = monotonic()
        self._emit({'e': 's', 'id': test.id()})

    def _elapsed(self, test: unittest.TestCase) -> float:
        return monotonic() - self._start.pop(test.id(), monotonic())

    def addSuccess(self, test: unittest.TestCase) -> None:
        super().addSuccess(test)
        self._emit({'e': 'ok', 'id': test.id(), 't': self._elapsed(test)})

    def addFailure(self, test: unittest.TestCase, err) -> None:
        super().addFailure(test, err)
        self._emit({'e': 'fail', 'id': test.id(), 't': self._elapsed(test), 'msg': self._exc_info_to_string(err, test)})  # type: ignore

    def addError(self, test: unittest.TestCase, err) -> None:
        super().addError(test, err)
        self._emit({'e': 'err', 'id': test.id(), 't': self._elapsed(test), 'msg': self._exc_info_to_string(err, test)})  # type: ignore

    def addSkip(self, test: unittest.TestCase, reason: str) -> None:
        super().addSkip(test, reason)
        self._emit({'e': 'skip', 'id': test.id(), 't': self._elapsed(test), 'msg': reason})

    def addExpectedFailure(self, test: unittest.TestCase, err) -> None:
        super().addExpectedFailure(test, err)
        self._emit({'e': 'xf', 'id': test.id(), 't': self._elapsed(test), 'msg': self._exc_info_to_string(err, test)})  # type: ignore

    def addUnexpectedSuccess(self, test: unittest.TestCase) -> None:
        super().addUnexpectedSuccess(test)
        self._emit({'e': 'xp', 'id': test.id(), 't': self._elapsed(test)})

    def close(self) -> None:
        self._out.close()


def _worker_entry(write_fd_or_handle: int) -> None:
    """
    Entry point run inside subprocess workers.
    On POSIX, write_fd_or_handle is the write-end file descriptor number.
    On Windows, it is the underlying Windows HANDLE value (since POSIX fd
    numbers are per-process and are not inherited by number in child processes).
    """
    if iswindows:
        import msvcrt

        write_fd = msvcrt.open_osfhandle(write_fd_or_handle, os.O_WRONLY)
    else:
        write_fd = write_fd_or_handle
    os.set_inheritable(write_fd, False)
    debug(False)
    inp = sys.stdin.read()
    test_ids = frozenset(json.loads(inp))
    from calibre.utils.run_tests import PipeTestResult, filter_tests, find_tests, init_env

    init_env()
    suite = filter_tests(find_tests(), lambda t: t.id() in test_ids)
    result = PipeTestResult(write_fd)
    suite.run(result)
    result.close()


def _chunk_round_robin(tests: list, num_workers: int) -> list[list]:
    """Distribute tests evenly across workers using round-robin assignment."""
    chunks: list[list] = [[] for _ in range(num_workers)]
    for i, t in enumerate(tests):
        chunks[i % num_workers].append(t)
    return [c for c in chunks if c]


def _start_worker(idx: int, chunk: list, worker_cmd: list[str] | None = None) -> tuple:
    """
    Start a subprocess worker for the given test chunk.
    Returns (Popen, read_pipe_file).

    When *worker_cmd* is provided it must be a list whose last element is the
    placeholder to which the Python code string will be appended, e.g.
    ``[sys.executable, 'setup.py', 'test', '--worker']``.  The code string is
    appended as a new argument so the worker runs via setup.py instead of
    calibre-debug.  When *worker_cmd* is None (the default) the traditional
    ``calibre-debug -c <code>`` invocation is used.

    On POSIX, the write-end file descriptor number is passed directly to the
    worker (close_fds=False lets it be inherited).  On Windows, POSIX fd
    numbers are per-process and cannot be inherited by number; instead we pass
    the underlying Windows HANDLE value and the worker reconstructs a file
    descriptor from it via msvcrt.open_osfhandle.  Workers are always spawned
    one at a time in a loop and the parent closes its copy of the write-end
    before creating the next pipe, so no worker accidentally inherits another
    worker's write-end.
    """
    import subprocess

    r, w = os.pipe()
    os.set_inheritable(r, False)
    os.set_inheritable(w, True)

    test_ids_json = json.dumps([t.id() for t in chunk])

    if iswindows:
        import msvcrt

        w_arg = msvcrt.get_osfhandle(w)
        code = f'from calibre.utils.run_tests import _worker_entry; _worker_entry({w_arg})'
    else:
        code = f'from calibre.utils.run_tests import _worker_entry; _worker_entry({w})'

    if worker_cmd is not None:
        cmd = worker_cmd + [code]
    else:
        from calibre.startup import get_debug_executable

        cmd = get_debug_executable() + ['-c', code]

    with tempfile.NamedTemporaryFile(delete=False) as output_tf:
        env = os.environ.copy()
        from calibre.ptempfile import base_dir

        tdir = os.path.join(base_dir(), f'w{idx}')
        os.mkdir(tdir)
        env['CALIBRE_WORKER_TEMP_DIR'] = as_hex_unicode(msgpack_dumps(tdir))
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=output_tf,
            stderr=output_tf,
            close_fds=False,
            env=env,
        )
    assert proc.stdin is not None
    proc.stdin.write(test_ids_json.encode())
    proc.stdin.close()
    os.close(w)
    return proc, os.fdopen(r, 'r', errors='replace'), output_tf.name


_STATUS_INTERVAL = 1.0  # seconds between status lines when stdout is not a TTY
_last_status_print: list[float] = [0.0]


def _print_status(completed: int, total: int, start: float, n_bad: int = 0) -> None:
    elapsed = monotonic() - start
    if _IS_TTY:
        time_part = _c(_DM, f'[{elapsed:6.1f}s]')
        count_part = _c(_RD if n_bad else _BD, f'{completed}/{total}')
        sys.stdout.write(f'\r{time_part} {count_part} tests completed   ')
        sys.stdout.flush()
    else:
        now = monotonic()
        if now - _last_status_print[0] >= _STATUS_INTERVAL:
            _last_status_print[0] = now
            print(f'[{elapsed:6.1f}s] {completed}/{total} tests completed', flush=True)


def _print_summary(
    failures: list[tuple[str, str]],
    errors: list[tuple[str, str]],
    skips: list[tuple[str, str]],
    ok_count: int,
    xfail_count: int,
    times: dict[str, float],
    total: int,
    elapsed: float,
    lost_ids: list[str],
) -> None:
    """Print the failure details, one-line stats, and five slowest tests."""
    for label, colour, items in (
        ('FAIL', _RD, failures),
        ('ERROR', _BD + _RD, errors),
    ):
        for tid, msg in items:
            print(f'\n{_c(_BD, "=" * 70)}\n{_c(colour, label + ": " + tid)}\n{_c(_DM, "-" * 70)}')
            print(msg)

    def _stat(label: str, count: int, colour: str) -> str:
        s = f'{label}: {count}'
        return _c(colour, s) if count else s

    lost = len(lost_ids)
    print(f'\n{_c(_BD, f"Ran {total} tests")} in {elapsed:.1f}s')
    parts = [
        _c(_GR, f'OK: {ok_count}'),
        _stat('FAIL', len(failures), _RD),
        _stat('ERROR', len(errors), _RD),
        _stat('SKIP', len(skips), _YL),
    ]
    if xfail_count:
        parts.append(_c(_DM, f'XFAIL/XPASS: {xfail_count}'))
    if lost:
        parts.append(_c(_RD, f'LOST (worker crash?): {lost}'))
    print('  '.join(parts))
    if lost_ids:
        print(_c(_RD, '\nLost tests (never reported back):'))
        for tid in lost_ids:
            print(f'  {_c(_RD, tid)}')

    slowest = sorted(times.items(), key=lambda kv: kv[1], reverse=True)[:5]
    if slowest:
        print(_c(_DM, '\nSlowest tests:'))
        for tid, t in slowest:
            print(f'  {_c(_DM, f"{t:6.1f}s")}  {tid}')


class TooFewTests(Exception):
    pass


def run_parallel(suite: unittest.TestSuite, num_workers: int = 0, worker_cmd: list[str] | None = None) -> int:
    """
    Run *suite* spread across independent worker processes.
    Each process receives a round-robin slice of the tests and streams results
    back over a pipe as newline-delimited JSON.  The master prints a live status
    line and, once all workers finish, prints failures/errors and a summary.

    When the suite is smaller than *_PARALLEL_MIN* tests the overhead of
    spawning workers outweighs the benefit; in that case the suite is run
    in the current process instead.

    Returns the number of failures + errors (0 means all passed).
    """

    all_tests = sorted(itertests(suite), key=lambda t: t.id())
    total = len(all_tests)
    if not total:
        print('No tests found.', file=sys.stderr)
        return 0

    if num_workers <= 0:
        num_workers = max(1, min(total, os.cpu_count() or 4))
    num_workers = min(num_workers, total)

    if total < _PARALLEL_MIN or num_workers < 2:
        raise TooFewTests()
    chunks = _chunk_round_robin(all_tests, num_workers)

    pipes: list = []
    workers: list[tuple] = []  # (proc, output_file)
    for i, chunk in enumerate(chunks):
        proc, pipe, output_file = _start_worker(i, chunk, worker_cmd=worker_cmd)
        workers.append((proc, output_file))
        pipes.append(pipe)

    ev_queue: queue.Queue[dict | None] = queue.Queue()

    def _reader(pipe) -> None:
        try:
            for line in pipe:
                line = line.strip()
                if line:
                    try:
                        ev_queue.put(json.loads(line))
                    except json.JSONDecodeError:
                        pass
        finally:
            pipe.close()
        ev_queue.put(None)  # sentinel: this worker's pipe is exhausted

    for pipe in pipes:
        threading.Thread(target=_reader, args=(pipe,), daemon=True).start()

    failures: list[tuple[str, str]] = []
    errors: list[tuple[str, str]] = []
    skips: list[tuple[str, str]] = []
    times: dict[str, float] = {}
    ok_count = 0
    xfail_count = 0
    completed = 0
    done_workers = 0
    start_time = monotonic()

    while done_workers < len(pipes):
        try:
            event = ev_queue.get(timeout=0.25)
        except queue.Empty:
            _print_status(completed, total, start_time, len(failures) + len(errors))
            continue

        if event is None:
            done_workers += 1
        else:
            e = event.get('e')
            tid = event.get('id', '')
            t = float(event.get('t', 0.0))
            if e != 's':  # skip start events, they carry no result
                completed += 1
                times[tid] = t
                if e == 'ok':
                    ok_count += 1
                elif e == 'fail':
                    failures.append((tid, event.get('msg', '')))
                elif e == 'err':
                    errors.append((tid, event.get('msg', '')))
                elif e == 'skip':
                    skips.append((tid, event.get('msg', '')))
                elif e in ('xf', 'xp'):
                    xfail_count += 1

        _print_status(completed, total, start_time, len(failures) + len(errors))

    # Reap worker processes; report crashes.
    try:
        for proc, output_path in workers:
            rc = proc.wait()
            if rc != 0:
                with open(output_path, 'rb') as f:
                    output = f.read().decode(errors='replace')
                print(f'\n{_c(_RD, f"Worker process crashed (exit code {rc})")}', flush=True)
                if output.strip():
                    print(output, flush=True)
    finally:
        for _, output_path in workers:
            try:
                os.unlink(output_path)
            except OSError:
                pass

    if _IS_TTY:
        print()

    elapsed = monotonic() - start_time
    lost_ids = [t.id() for t in all_tests if t.id() not in times]
    _print_summary(failures, errors, skips, ok_count, xfail_count, times, total, elapsed, lost_ids)
    return 1 if len(failures) + len(errors) + len(lost_ids) else 0


# ─── Test discovery ───────────────────────────────────────────────────────────


class TestImports(unittest.TestCase):
    def base_check(self, base, exclude_packages, exclude_modules):
        import importlib

        import_base = os.path.dirname(base)
        count = 0
        for root, dirs, files in os.walk(base):
            for d in tuple(dirs):
                if not os.path.isfile(os.path.join(root, d, '__init__.py')):
                    dirs.remove(d)
            for fname in files:
                module_name, ext = os.path.splitext(fname)
                if ext != '.py':
                    continue
                path = os.path.join(root, module_name)
                relpath = os.path.relpath(path, import_base).replace(os.sep, '/')
                full_module_name = '.'.join(relpath.split('/'))
                if full_module_name.endswith('.__init__'):
                    full_module_name = full_module_name.rpartition('.')[0]
                if full_module_name in exclude_modules or ('.' in full_module_name and full_module_name.rpartition('.')[0] in exclude_packages):
                    continue
                importlib.import_module(full_module_name)
                count += 1
        return count

    def test_import_of_all_python_modules(self):

        exclude_packages = {'calibre.devices.mtp.unix.upstream'}
        exclude_modules = {'calibre.web.automate.browser'}
        if not iswindows:
            exclude_modules |= {'calibre.utils.iphlpapi', 'calibre.utils.open_with.windows', 'calibre.devices.winusb'}
            exclude_packages |= {'calibre.utils.winreg', 'calibre.utils.windows'}
        if not ismacos:
            exclude_modules.add('calibre.utils.open_with.osx')
        if not islinux:
            exclude_modules |= {
                'calibre.linux',
                'calibre.gui2.tts.speechd',
                'calibre.utils.linux_trash',
                'calibre.utils.open_with.linux',
                'calibre.gui2.linux_file_dialogs',
            }
        if 'SKIP_SPEECH_TESTS' in os.environ:
            exclude_packages.add('calibre.gui2.tts')
        if not isbsd:
            exclude_modules.add('calibre.devices.usbms.hal')
        d = os.path.dirname
        SRC = d(d(d(os.path.abspath(__file__))))
        self.assertGreater(self.base_check(os.path.join(SRC, 'odf'), exclude_packages, exclude_modules), 10)
        base = os.path.join(SRC, 'calibre')
        self.assertGreater(self.base_check(base, exclude_packages, exclude_modules), 1000)

        # Virtual imports for legacy compatibility
        import calibre.web.feeds.feedparser as f  # type: ignore

        del f
        from calibre.ebooks.markdown import Markdown  # type: ignore

        del Markdown


def find_tests(which_tests=None, exclude_tests=None):
    ans = []
    a = ans.append

    def ok(x):
        return (not which_tests or x in which_tests) and (not exclude_tests or x not in exclude_tests)

    if ok('fork'):
        from calibre.utils.forked_map import find_tests

        a(find_tests())
    if ok('build'):
        from calibre.test_build import find_tests

        a(find_tests(only_build=True))
    if ok('srv'):
        from calibre.srv.tests.main import find_tests

        a(find_tests())
    if ok('db'):
        from calibre.db.tests.main import find_tests

        a(find_tests())
    if ok('polish'):
        from calibre.ebooks.oeb.polish.tests.main import find_tests

        a(find_tests())
        from calibre.ebooks.oeb.polish.tests.structure import find_tests

        a(find_tests())
    if ok('opf'):
        from calibre.ebooks.metadata.opf2 import suite

        a(suite())
        from calibre.ebooks.metadata.opf3_test import suite

        a(suite())
    if ok('css'):
        from tinycss.tests.main import find_tests

        a(find_tests())
        from calibre.ebooks.oeb.normalize_css import test_normalization

        a(test_normalization(return_tests=True))
        from calibre.ebooks.css_transform_rules import test

        a(test(return_tests=True))
        from calibre.ebooks.html_transform_rules import test

        a(test(return_tests=True))
        from css_selectors.tests import find_tests

        a(find_tests())
    if ok('docx'):
        from calibre.ebooks.docx.fields import test_parse_fields

        a(test_parse_fields(return_tests=True))
        from calibre.ebooks.docx.writer.utils import test_convert_color

        a(test_convert_color(return_tests=True))
    if ok('cfi'):
        from calibre.ebooks.epub.cfi.tests import find_tests

        a(find_tests())
    if ok('matcher'):
        from calibre.utils.matcher import test

        a(test(return_tests=True))
    if ok('scraper'):
        from calibre.scraper.test_fetch_backend import find_tests

        a(find_tests())
        from calibre.web.automate.test_worker import find_tests

        a(find_tests())
    if ok('icu'):
        from calibre.utils.icu_test import find_tests

        a(find_tests())
    if ok('smartypants'):
        from calibre.utils.smartypants import run_tests

        a(run_tests(return_tests=True))
    if ok('ebooks'):
        from calibre.ebooks.conversion.plugins.archive_input import find_tests

        a(find_tests())
        from calibre.ebooks.conversion.plugins.txt_input import find_tests

        a(find_tests())
        from calibre.ebooks.metadata.rtf import find_tests

        a(find_tests())
        from calibre.ebooks.metadata.html import find_tests

        a(find_tests())
        from calibre.utils.xml_parse import find_tests

        a(find_tests())
        from calibre.gui2.viewer.annotations import find_tests

        a(find_tests())
        from calibre.gui2.library.test_annotations import find_tests

        a(find_tests())
        from calibre.ebooks.html_entities import find_tests

        a(find_tests())
        from calibre.spell.dictionary import find_tests

        a(find_tests())
    if ok('ai'):
        from calibre.ai.utils import find_tests

        a(find_tests())
    if ok('misc'):
        from calibre.ebooks.html.input import find_tests

        a(find_tests())
        from calibre.ebooks.metadata.test_author_sort import find_tests

        a(find_tests())
        from calibre.ebooks.metadata.tag_mapper import find_tests

        a(find_tests())
        from calibre.ebooks.metadata.author_mapper import find_tests

        a(find_tests())
        from calibre.utils.shared_file import find_tests

        a(find_tests())
        from calibre.utils.test_lock import find_tests

        a(find_tests())
        from calibre.utils.search_query_parser_test import find_tests

        a(find_tests())
        from calibre.utils.html2text import find_tests

        a(find_tests())
        from calibre.utils.shm import find_tests

        a(find_tests())
        from calibre.library.comments import find_tests

        a(find_tests())
        from calibre.ebooks.compression.palmdoc import find_tests

        a(find_tests())
        from calibre.gui2.viewer.convert_book import find_tests

        a(find_tests())
        from calibre.utils.hyphenation.test_hyphenation import find_tests

        a(find_tests())
        from calibre.live import find_tests

        a(find_tests())
        from calibre.utils.copy_files_test import find_tests

        a(find_tests())
        from calibre.utils.safe_atexit import find_tests

        a(find_tests())
        from calibre.gui2.listener import find_tests

        a(find_tests())
        if iswindows:
            from calibre.utils.windows.wintest import find_tests

            a(find_tests())
        a(unittest.defaultTestLoader.loadTestsFromTestCase(TestImports))
        from calibre.utils.translator.test_translator import find_tests

        a(find_tests())
        from calibre.utils.config_base import find_tests

        a(find_tests())
        from calibre.utils.zipfile import find_tests

        a(find_tests())
    if ok('dbcli'):
        from calibre.db.cli.tests import find_tests

        a(find_tests())

    tests = unittest.TestSuite(ans)
    return tests


# ─── Public entry points ──────────────────────────────────────────────────────


def run_tests(find_tests_fn, verbosity=4):
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument(
        'name',
        nargs='?',
        default=None,
        help='The name of the test to run, for example: writing.WritingTest.many_many_basic or .many_many_basic for a shortcut',
    )
    args = parser.parse_args()
    tests = find_tests_fn()
    if args.name:
        if args.name.startswith('.'):
            tests = filter_tests_by_name(tests, args.name[1:])
        else:
            tests = filter_tests_by_module(tests, args.name)
        if not tests._tests:
            raise SystemExit(f'No test named {args.name} found')
    run_cli(tests, verbosity, buffer=not args.name)


def run_test(test_name, verbosity=4):
    # calibre-debug -t test_name
    which_tests = None
    if test_name.startswith('@'):
        which_tests = (test_name[1:],)
    tests = find_tests(which_tests)
    buffer = True
    if test_name != 'all':
        buffer = False
        if test_name.startswith('.'):
            tests = filter_tests_by_module(tests, test_name[1:])
        elif test_name.startswith('@'):
            pass
        else:
            tests = filter_tests_by_name(tests, test_name)
    if not tests._tests:
        raise SystemExit(f'No test named {test_name} found')
    run_cli(tests, verbosity, buffer=buffer)


def run_cli(suite, verbosity=4, buffer=True, worker_cmd: list[str] | None = None):
    """
    Run *suite* and exit.
    When *buffer* is True (the default, used for full-suite runs) tests are
    distributed across worker processes via run_parallel().
    When *buffer* is False (used for single named-test runs) the suite runs
    single-threaded with verbose TextTestRunner output.
    *worker_cmd*, when provided, is forwarded to run_parallel() / _start_worker()
    as the command prefix used to spawn worker processes.
    """
    init_env()
    if buffer:
        try:
            raise SystemExit(run_parallel(suite, worker_cmd=worker_cmd))
        except TooFewTests:
            pass
    r = unittest.TextTestRunner
    r.resultclass = unittest.TextTestResult if verbosity < 2 else TestResult
    result = r(verbosity=verbosity, buffer=False).run(suite)
    rc = 0 if result.wasSuccessful() else 1
    raise SystemExit(rc)
