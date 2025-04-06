#!/usr/bin/env python
# License: GPLv3 Copyright: 2025, Kovid Goyal <kovid at kovidgoyal.net>

import os
import pickle
import select
import signal
import ssl
import traceback
from collections.abc import Callable, Iterator
from contextlib import ExitStack
from itertools import batched, chain
from typing import Any, BinaryIO, NamedTuple, TypeVar

T = TypeVar('T')
R = TypeVar('R')


class _RemoteTraceback(Exception):
    def __init__(self, tb):
        self.tb = tb
    def __str__(self):
        return self.tb


class _ExceptionWithTraceback:
    def __init__(self, exc):
        tb = ''.join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        self.exc = exc
        # Traceback object needs to be garbage-collected as its frames
        # contain references to all the objects in the exception scope
        self.exc.__traceback__ = None
        self.tb = f'\n"""\n{tb}"""'
    def __reduce__(self):
        return _rebuild_exc, (self.exc, self.tb)


def _rebuild_exc(exc, tb):
    exc.__cause__ = _RemoteTraceback(tb)
    return exc


class Job(NamedTuple):
    id: int
    arg: Any
    fn: Callable[[Any], Any]


class Worker:
    pid: int
    pipe: BinaryIO
    unpickler: pickle.Unpickler

    def __init__(self, pid: int, pipe_fd: int):
        self.pid = pid
        self.pipe = open(pipe_fd, 'rb')
        self.unpickler = pickle.Unpickler(self.pipe)

    def __enter__(self) -> 'Worker':
        return self

    def __exit__(self, exc_type, exc_value, tb) -> None:
        self.pipe.close()
        pid, status = os.waitpid(self.pid, os.WNOHANG)
        if not pid:
            os.kill(self.pid, signal.SIGKILL)
            os.waitpid(self.pid, 0)


class Result(NamedTuple):
    ok: bool
    id: int
    value: Any


def run_jobs(*jobs: Job) -> Worker:
    r, w = os.pipe()
    os.set_inheritable(w, True)
    os.set_inheritable(r, False)
    if pid := os.fork():  # parent
        os.close(w)
        ssl.RAND_bytes(1)  # change state of OpenSSL RNG so that it is not shared with child process
        return Worker(pid, r)
    else:
        try:
            with open(w, 'wb') as pipe:
                pickler = pickle.Pickler(pipe, protocol=pickle.HIGHEST_PROTOCOL)
                for job in jobs:
                    try:
                        result = Result(True, job.id, job.fn(job.arg))
                    except BaseException as e:
                        result = Result(False, job.id, _ExceptionWithTraceback(e))
                    pickler.dump(result)
                    pipe.flush()
        except (BrokenPipeError, KeyboardInterrupt):
            pass
        except BaseException:
            traceback.print_exc()
            os._exit(os.EX_OSERR)
        # do not call atexit and finally handlers
        os._exit(os.EX_OK)


def forked_map(fn: Callable[[T], R], iterable: T, *iterables: T, timeout: int | float | None = None, num_workers: int = 0) -> Iterator[R]:
    '''
    Should be used only in worker processes that have no threads and that do not use/import any non fork safe libraries such as macOS
    system libraries.
    '''
    if num_workers <= 0:
        num_workers = max(1, os.cpu_count())
    chunk_size = max(1, len(iterables) / num_workers)
    groups = batched((Job(i, arg, fn) for i, arg in enumerate(chain(iterable, *iterables))), chunk_size)
    cache: dict[int, Result] = {}
    pos = 0
    workers = tuple(run_jobs(*g) for g in groups)
    with ExitStack() as stack:
        for w in workers:
            stack.push(w)
        wmap = {w.pipe.fileno(): w for w in workers}
        while wmap:
            ready, _, _ = select.select(tuple(wmap), (), (), timeout)
            if not ready:
                raise TimeoutError(f'Forked workers did not produce a result in {timeout} seconds')
            for r in ready:
                w = wmap[r]
                try:
                    result: Result = w.unpickler.load()
                except EOFError:
                    del wmap[r]
                    continue
                if pos == result.id:
                    if not result.ok:
                        raise result.value
                    yield result.value
                    pos += 1
                    while res := cache.pop(pos, None):
                        yield res.value
                        pos += 1
                else:
                    cache[result.id] = result
    while r := cache.pop(pos, None):
        yield r.value
        pos += 1
    if pos < len(iterables):
        raise OSError(f'Forked workers exited producing only {pos} out of {len(iterables)} results')


forked_map_is_supported = hasattr(os, 'fork')


def find_tests():
    import random
    import time
    import unittest
    class TestForkedMap(unittest.TestCase):
        @unittest.skipUnless(forked_map_is_supported, 'forking not supported on this platform')
        def test_forked_map(self):
            def sleep(x: int) -> int:
                time.sleep(10 * x)
                return x
            with self.assertRaises(TimeoutError):
                tuple(forked_map(sleep, range(os.cpu_count() * 3), timeout=0.001))
            def raise_error(x: int) -> None:
                raise ReferenceError('testing')
            with self.assertRaises(ReferenceError):
                tuple(forked_map(raise_error, range(os.cpu_count() * 3)))
            timings = 0, 1, 2, 3
            def echo(x: int) -> int:
                time.sleep(0.0001 * random.choice(timings))
                return x
            for num_workers in range(1, os.cpu_count() + 1):
                items = tuple(range(num_workers * 3))
                self.assertEqual(tuple(map(echo, items)), tuple(forked_map(echo, items)))
    return unittest.defaultTestLoader.loadTestsFromTestCase(TestForkedMap)
