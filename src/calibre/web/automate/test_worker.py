#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, Kovid Goyal <kovid at kovidgoyal.net>

import asyncio
import builtins
import os
import sys
import tempfile
import threading
import time
import traceback
import unittest
from collections.abc import Sequence
from typing import Any

from calibre.constants import ismacos
from calibre.web.automate.worker import make_request, start_server, start_worker


def print(*a: object, **kw: Any) -> None:  # noqa: ANN401
    kw['file'] = sys.stderr
    builtins.print(*a, **kw)


# Long enough that the client has certainly finished writing its request, and
# so half closed its end of the socket, before the answer is ready. That takes
# a fraction of a millisecond on a unix socket, so this is already a margin of
# three orders of magnitude, and every second of it is a second the test suite
# spends asleep.
SLOW_HANDLER_TIME = 0.5  # seconds


class TestAutomateWorker(unittest.TestCase):
    def test_automate_worker(self) -> None:
        asyncio.run(name_collision(self))
        worker(self)

    def test_automate_worker_slow_handler(self) -> None:
        "A handler that takes its time still gets its answer back to the client"
        path, close = start_worker('calibre.web.automate.test_worker:slow_handler_for_test')
        try:
            start = time.monotonic()
            r = make_request(path, SLOW_HANDLER_TIME)
            self.assertFalse(r.exception, r.traceback)
            self.assertEqual(r.response, f'slept {SLOW_HANDLER_TIME}')
            self.assertGreaterEqual(time.monotonic() - start, SLOW_HANDLER_TIME)
        finally:
            close()

    def test_automate_worker_parallel_requests(self) -> None:
        "Slow requests from several threads are served at the same time, not one after another"
        num = 4
        path, close = start_worker('calibre.web.automate.test_worker:slow_handler_for_test')
        try:
            responses: dict[int, Any] = {}
            errors: dict[int, str] = {}

            def make(i: int) -> None:
                # Exceptions in a thread are merely printed by the default
                # threading excepthook, so record them or the test fails with
                # a mystifying count mismatch and no sign of the actual error
                try:
                    responses[i] = make_request(path, SLOW_HANDLER_TIME)
                except Exception:
                    errors[i] = traceback.format_exc()

            start = time.monotonic()
            threads = [threading.Thread(target=make, args=(i,), name=f'WorkerRequest{i}') for i in range(num)]
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=60)
                self.assertFalse(t.is_alive(), 'a request thread never finished')
            elapsed = time.monotonic() - start
        finally:
            close()
        self.assertFalse(errors, 'some requests raised: ' + '\n'.join(errors.values()))
        self.assertEqual(len(responses), num)
        for i, r in sorted(responses.items()):
            self.assertFalse(r.exception, f'request {i} failed: {r.traceback}')
            self.assertEqual(r.response, f'slept {SLOW_HANDLER_TIME}')
        self.assertLess(elapsed, SLOW_HANDLER_TIME * num, 'the requests were served one after another')


async def name_collision(self: TestAutomateWorker) -> None:
    path1, srv1 = await start_server(random_suffix='test')
    q = '-test.sock' if ismacos else '-test'
    self.assertEndsWith(path1, q)
    path2, srv2 = await start_server(random_suffix='test')
    self.assertNotEqual(path1, path2)
    srv1.close()
    await srv1.wait_closed()
    path3, srv3 = await start_server(random_suffix='test')
    self.assertEndsWith(path3, q)
    srv2.close()
    await srv2.wait_closed()
    srv3.close()
    await srv3.wait_closed()


delayed_setup_items: list[Any] = []
handler_items: list[tuple[Any, Any]] = []


async def delayed_setup_for_test(x: Any = None) -> None:  # noqa: ANN401
    delayed_setup_items.append(x)


async def handler_for_test(*args: Any) -> dict[str, Any]:  # noqa: ANN401
    if len(args) == 1:
        x, input_data = args[0], None
    else:
        input_data, x = args
    if x == 'raise-exception':
        raise Exception(x)
    handler_items.append((input_data, x))
    return {'arg': x, 'delayed_setup_items': delayed_setup_items}


async def slow_handler_for_test(x: Any) -> Any:  # noqa: ANN401
    await asyncio.sleep(float(x))
    return f'slept {x}'


def finalize(x: Sequence[str] | None = None) -> None:
    if x:
        os.remove(x[0])


def worker(self: TestAutomateWorker) -> None:
    tf = tempfile.NamedTemporaryFile(delete=False)
    tf.close()
    for input_data in (None, [tf.name]):
        path, close = start_worker(
            'calibre.web.automate.test_worker:handler_for_test',
            'calibre.web.automate.test_worker:delayed_setup_for_test',
            'calibre.web.automate.test_worker:finalize',
            input_data=input_data,
        )
        try:
            self.assertTrue(path)
            r = make_request(path, 'some-test-input')
            self.assertFalse(r.exception)
            self.assertEqual({'arg': 'some-test-input', 'delayed_setup_items': [input_data]}, r.response)
            r = make_request(path, 'some-test-input2')
            self.assertEqual({'arg': 'some-test-input2', 'delayed_setup_items': [input_data]}, r.response)
            r = make_request(path, 'raise-exception')
            self.assertIn('raise-exception', r.exception)
        finally:
            close()
        if input_data:
            self.assertFalse(os.path.exists(tf.name))
        else:
            self.assertTrue(os.path.exists(tf.name))


def find_tests() -> unittest.TestSuite:
    return unittest.defaultTestLoader.loadTestsFromTestCase(TestAutomateWorker)
