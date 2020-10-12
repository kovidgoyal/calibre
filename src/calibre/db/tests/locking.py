#!/usr/bin/env python
# vim:fileencoding=utf-8


__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

import time, random
from threading import Thread
from calibre.db.tests.base import BaseTest
from calibre.db.locking import SHLock, RWLockWrapper, LockingError
from polyglot.builtins import range


def wait_for(period):
    # time.sleep() is not useful for very small values on windows because the
    # default timer has a resolutions of about 16ms see
    # https://stackoverflow.com/questions/40594587/why-time-sleep-is-so-slow-in-windows
    deadline = time.perf_counter() + period
    while time.perf_counter() < deadline:
        pass


class TestLock(BaseTest):
    """Tests for db locking """

    def test_owns_locks(self):
        lock = SHLock()
        self.assertFalse(lock.owns_lock())
        lock.acquire(shared=True)
        self.assertTrue(lock.owns_lock())
        lock.release()
        self.assertFalse(lock.owns_lock())
        lock.acquire(shared=False)
        self.assertTrue(lock.owns_lock())
        lock.release()
        self.assertFalse(lock.owns_lock())

        done = []

        def test():
            if not lock.owns_lock():
                done.append(True)
        lock.acquire()
        t = Thread(target=test)
        t.daemon = True
        t.start()
        t.join(1)
        self.assertEqual(len(done), 1)
        lock.release()

    def test_multithread_deadlock(self):
        lock = SHLock()

        def two_shared():
            r = RWLockWrapper(lock)
            with r:
                time.sleep(0.2)
                with r:
                    pass

        def one_exclusive():
            time.sleep(0.1)
            w = RWLockWrapper(lock, is_shared=False)
            with w:
                pass
        threads = [Thread(target=two_shared), Thread(target=one_exclusive)]
        for t in threads:
            t.daemon = True
            t.start()
        for t in threads:
            t.join(5)
        live = [t for t in threads if t.is_alive()]
        self.assertListEqual(live, [], 'ShLock hung')

    def test_upgrade(self):
        lock = SHLock()
        lock.acquire(shared=True)
        self.assertRaises(LockingError, lock.acquire, shared=False)
        lock.release()

    def test_downgrade(self):
        lock = SHLock()
        lock.acquire(shared=False)
        self.assertRaises(LockingError, lock.acquire, shared=True)
        lock.release()

    def test_recursive(self):
        lock = SHLock()
        lock.acquire(shared=True)
        lock.acquire(shared=True)
        self.assertEqual(lock.is_shared, 2)
        lock.release()
        lock.release()
        self.assertFalse(lock.is_shared)
        lock.acquire(shared=False)
        lock.acquire(shared=False)
        self.assertEqual(lock.is_exclusive, 2)
        lock.release()
        lock.release()
        self.assertFalse(lock.is_exclusive)

    def test_release(self):
        lock = SHLock()
        self.assertRaises(LockingError, lock.release)

        def get_lock(shared):
            lock.acquire(shared=shared)
            time.sleep(1)
            lock.release()

        threads = [Thread(target=get_lock, args=(x,)) for x in (True,
            False)]
        for t in threads:
            t.daemon = True
            t.start()
            self.assertRaises(LockingError, lock.release)
            t.join(15)
            self.assertFalse(t.is_alive())
        self.assertFalse(lock.is_shared)
        self.assertFalse(lock.is_exclusive)

    def test_acquire(self):
        lock = SHLock()

        def get_lock(shared):
            lock.acquire(shared=shared)
            time.sleep(1)
            lock.release()

        shared = Thread(target=get_lock, args=(True,))
        shared.daemon = True
        shared.start()
        time.sleep(0.1)
        self.assertTrue(lock.acquire(shared=True, blocking=False))
        lock.release()
        self.assertFalse(lock.acquire(shared=False, blocking=False))
        lock.acquire(shared=False)
        shared.join(1)
        self.assertFalse(shared.is_alive())
        lock.release()
        self.assertTrue(lock.acquire(shared=False, blocking=False))
        lock.release()

        exclusive = Thread(target=get_lock, args=(False,))
        exclusive.daemon = True
        exclusive.start()
        time.sleep(0.1)
        self.assertFalse(lock.acquire(shared=False, blocking=False))
        self.assertFalse(lock.acquire(shared=True, blocking=False))
        lock.acquire(shared=True)
        exclusive.join(1)
        self.assertFalse(exclusive.is_alive())
        lock.release()
        lock.acquire(shared=False)
        lock.release()
        lock.acquire(shared=True)
        lock.release()
        self.assertFalse(lock.is_shared)
        self.assertFalse(lock.is_exclusive)

    def test_contention(self):
        lock = SHLock()
        done = []

        def lots_of_acquires():
            for _ in range(1000):
                shared = random.choice([True,False])
                lock.acquire(shared=shared)
                lock.acquire(shared=shared)
                wait_for(random.random() * 0.0001)
                lock.release()
                wait_for(random.random() * 0.0001)
                lock.acquire(shared=shared)
                wait_for(random.random() * 0.0001)
                lock.release()
                lock.release()
            done.append(True)
        threads = [Thread(target=lots_of_acquires) for _ in range(2)]
        for t in threads:
            t.daemon = True
            t.start()
        end_at = time.monotonic() + 20
        for t in threads:
            left = end_at - time.monotonic()
            if left <= 0:
                break
            t.join(left)
        live = [t for t in threads if t.is_alive()]
        self.assertEqual(len(live), 0, 'ShLock hung or very slow, {} threads alive'.format(len(live)))
        self.assertEqual(len(done), len(threads), 'SHLock locking failed')
        self.assertFalse(lock.is_shared)
        self.assertFalse(lock.is_exclusive)


def find_tests():
    import unittest
    return unittest.defaultTestLoader.loadTestsFromTestCase(TestLock)


def run_tests():
    from calibre.utils.run_tests import run_tests
    run_tests(find_tests)
