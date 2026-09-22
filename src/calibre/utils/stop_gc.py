#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, Kovid Goyal <kovid at kovidgoyal.net>

import gc
from threading import Lock
from types import TracebackType


class StopGC:
    """Context manager to disable the cyclic garbage collector.

    The garbage collector is process global state, so nested and concurrent
    use from multiple threads is tracked with a counter. The collector is
    disabled when the first context is entered and its original state
    restored only when the last active context exits. Use the module level
    singleton :data:`stop_gc` rather than instantiating this class, so that
    all users share the counter.
    """

    def __init__(self) -> None:
        self._lock = Lock()
        self._depth: int = 0
        self._was_enabled: bool = False

    def __enter__(self) -> None:
        with self._lock:
            if self._depth == 0:
                self._was_enabled = gc.isenabled()
                gc.disable()
            self._depth += 1

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> bool | None:
        with self._lock:
            if self._depth < 1:  # unbalanced exit, nothing to restore
                return None
            self._depth -= 1
            if self._depth == 0 and self._was_enabled:
                self._was_enabled = False
                gc.enable()
        return None


stop_gc = StopGC()


def find_tests():
    import unittest
    from threading import Barrier, Thread

    class TestStopGC(unittest.TestCase):
        def setUp(self):
            self.gc_was_enabled = gc.isenabled()
            gc.enable()

        def tearDown(self):
            if self.gc_was_enabled:
                gc.enable()
            else:
                gc.disable()

        def test_stop_gc(self):
            sg = StopGC()
            with sg:
                self.assertFalse(gc.isenabled())
                with sg:  # nested use must not re-enable on inner exit
                    self.assertFalse(gc.isenabled())
                self.assertFalse(gc.isenabled())
            self.assertTrue(gc.isenabled())
            self.assertEqual(sg._depth, 0)

            # original state must be preserved
            gc.disable()
            with sg:
                self.assertFalse(gc.isenabled())
            self.assertFalse(gc.isenabled())
            gc.enable()

            # an unbalanced exit must be a no-op
            sg.__exit__(None, None, None)
            self.assertTrue(gc.isenabled())
            self.assertEqual(sg._depth, 0)

        def test_stop_gc_threaded(self):
            sg = StopGC()
            # Interleave two threads as: enter(1) enter(2) exit(1) exit(2)
            # with gc expected to be disabled throughout.
            steps = tuple(Barrier(2) for i in range(4))
            failures: list[str] = []
            completed: list[int] = []

            def check(thread_num: int, step: int) -> None:
                if gc.isenabled():
                    failures.append(f'gc enabled in thread {thread_num} at step {step}')

            def first() -> None:
                with sg:
                    check(1, 0)
                    steps[0].wait(30)  # allow thread 2 to enter
                    steps[1].wait(30)
                    check(1, 1)
                check(1, 2)  # thread 2 is still inside its context
                steps[2].wait(30)
                steps[3].wait(30)
                completed.append(1)

            def second() -> None:
                steps[0].wait(30)
                with sg:
                    check(2, 0)
                    steps[1].wait(30)  # allow thread 1 to exit
                    steps[2].wait(30)
                    check(2, 1)
                steps[3].wait(30)
                completed.append(2)

            threads = tuple(Thread(target=f, name=f'StopGCTest{i}') for i, f in enumerate((first, second)))
            for t in threads:
                t.start()
            for t in threads:
                t.join(60)
                self.assertFalse(t.is_alive(), 'timed out waiting for test threads')
            self.assertEqual(failures, [])
            self.assertEqual(sorted(completed), [1, 2], 'test threads did not run to completion')
            self.assertEqual(sg._depth, 0)
            self.assertTrue(gc.isenabled())

    return unittest.TestLoader().loadTestsFromTestCase(TestStopGC)


if __name__ == '__main__':
    from calibre.utils.run_tests import run_tests

    run_tests(find_tests)
