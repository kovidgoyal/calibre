#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai


__license__   = 'GPL v3'
__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import traceback, sys
from threading import Lock, Condition, current_thread
from calibre.utils.config_base import tweaks


class LockingError(RuntimeError):

    is_locking_error = True

    def __init__(self, msg, extra=None):
        RuntimeError.__init__(self, msg)
        self.locking_debug_msg = extra


class DowngradeLockError(LockingError):
    pass


def create_locks():
    '''
    Return a pair of locks: (read_lock, write_lock)

    The read_lock can be acquired by multiple threads simultaneously, it can
    also be acquired multiple times by the same thread.

    Only one thread can hold write_lock at a time, and only if there are no
    current read_locks. While the write_lock is held no
    other threads can acquire read locks. The write_lock can also be acquired
    multiple times by the same thread.

    Both read_lock and write_lock are meant to be used in with statements (they
    operate on a single underlying lock.

    WARNING: Be very careful to not try to acquire a read lock while the same
    thread holds a write lock and vice versa. That is, a given thread should
    always release *all* locks of type A before trying to acquire a lock of type
    B. Bad things will happen if you violate this rule, the most benign of
    which is the raising of a LockingError (I haven't been able to eliminate
    the possibility of deadlocking in this scenario).
    '''
    l = SHLock()
    wrapper = DebugRWLockWrapper if tweaks.get('newdb_debug_locking', False) else RWLockWrapper
    return wrapper(l), wrapper(l, is_shared=False)


class SHLock(object):  # {{{
    '''
    Shareable lock class. Used to implement the Multiple readers-single writer
    paradigm. As best as I can tell, neither writer nor reader starvation
    should be possible.

    Based on code from: https://github.com/rfk/threading2
    '''

    def __init__(self):
        self._lock = Lock()
        #  When a shared lock is held, is_shared will give the cumulative
        #  number of locks and _shared_owners maps each owning thread to
        #  the number of locks is holds.
        self.is_shared = 0
        self._shared_owners = {}
        #  When an exclusive lock is held, is_exclusive will give the number
        #  of locks held and _exclusive_owner will give the owning thread
        self.is_exclusive = 0
        self._exclusive_owner = None
        #  When someone is forced to wait for a lock, they add themselves
        #  to one of these queues along with a "waiter" condition that
        #  is used to wake them up.
        self._shared_queue = []
        self._exclusive_queue = []
        #  This is for recycling waiter objects.
        self._free_waiters = []

    def acquire(self, blocking=True, shared=False):
        '''
        Acquire the lock in shared or exclusive mode.

        If blocking is False this method will return False if acquiring the
        lock failed.
        '''
        with self._lock:
            if shared:
                return self._acquire_shared(blocking)
            else:
                return self._acquire_exclusive(blocking)
            assert not (self.is_shared and self.is_exclusive)

    def owns_lock(self):
        me = current_thread()
        with self._lock:
            return self._exclusive_owner is me or me in self._shared_owners

    def release(self):
        ''' Release the lock. '''
        #  This decrements the appropriate lock counters, and if the lock
        #  becomes free, it looks for a queued thread to hand it off to.
        #  By doing the handoff here we ensure fairness.
        me = current_thread()
        with self._lock:
            if self.is_exclusive:
                if self._exclusive_owner is not me:
                    raise LockingError("release() called on unheld lock")
                self.is_exclusive -= 1
                if not self.is_exclusive:
                    self._exclusive_owner = None
                    #  If there are waiting shared locks, issue them
                    #  all and them wake everyone up.
                    if self._shared_queue:
                        for (thread, waiter) in self._shared_queue:
                            self.is_shared += 1
                            self._shared_owners[thread] = 1
                            waiter.notify()
                        del self._shared_queue[:]
                    #  Otherwise, if there are waiting exclusive locks,
                    #  they get first dibbs on the lock.
                    elif self._exclusive_queue:
                        (thread, waiter) = self._exclusive_queue.pop(0)
                        self._exclusive_owner = thread
                        self.is_exclusive += 1
                        waiter.notify()
            elif self.is_shared:
                try:
                    self._shared_owners[me] -= 1
                    if self._shared_owners[me] == 0:
                        del self._shared_owners[me]
                except KeyError:
                    raise LockingError("release() called on unheld lock")
                self.is_shared -= 1
                if not self.is_shared:
                    #  If there are waiting exclusive locks,
                    #  they get first dibbs on the lock.
                    if self._exclusive_queue:
                        (thread, waiter) = self._exclusive_queue.pop(0)
                        self._exclusive_owner = thread
                        self.is_exclusive += 1
                        waiter.notify()
                    else:
                        assert not self._shared_queue
            else:
                raise LockingError("release() called on unheld lock")

    def _acquire_shared(self, blocking=True):
        me = current_thread()
        #  Each case: acquiring a lock we already hold.
        if self.is_shared and me in self._shared_owners:
            self.is_shared += 1
            self._shared_owners[me] += 1
            return True
        #  If the lock is already spoken for by an exclusive, add us
        #  to the shared queue and it will give us the lock eventually.
        if self.is_exclusive or self._exclusive_queue:
            if self._exclusive_owner is me:
                raise DowngradeLockError("can't downgrade SHLock object")
            if not blocking:
                return False
            waiter = self._take_waiter()
            try:
                self._shared_queue.append((me, waiter))
                waiter.wait()
                assert not self.is_exclusive
            finally:
                self._return_waiter(waiter)
        else:
            self.is_shared += 1
            self._shared_owners[me] = 1
        return True

    def _acquire_exclusive(self, blocking=True):
        me = current_thread()
        #  Each case: acquiring a lock we already hold.
        if self._exclusive_owner is me:
            assert self.is_exclusive
            self.is_exclusive += 1
            return True
        # Do not allow upgrade of lock
        if self.is_shared and me in self._shared_owners:
            raise LockingError("can't upgrade SHLock object")
        #  If the lock is already spoken for, add us to the exclusive queue.
        #  This will eventually give us the lock when it's our turn.
        if self.is_shared or self.is_exclusive:
            if not blocking:
                return False
            waiter = self._take_waiter()
            try:
                self._exclusive_queue.append((me, waiter))
                waiter.wait()
            finally:
                self._return_waiter(waiter)
        else:
            self._exclusive_owner = me
            self.is_exclusive += 1
        return True

    def _take_waiter(self):
        try:
            return self._free_waiters.pop()
        except IndexError:
            return Condition(self._lock)

    def _return_waiter(self, waiter):
        self._free_waiters.append(waiter)

# }}}


class RWLockWrapper(object):

    def __init__(self, shlock, is_shared=True):
        self._shlock = shlock
        self._is_shared = is_shared

    def acquire(self):
        self._shlock.acquire(shared=self._is_shared)

    def release(self, *args):
        self._shlock.release()

    __enter__ = acquire
    __exit__ = release

    def owns_lock(self):
        return self._shlock.owns_lock()


class DebugRWLockWrapper(RWLockWrapper):

    def __init__(self, *args, **kwargs):
        RWLockWrapper.__init__(self, *args, **kwargs)

    def acquire(self):
        print('#' * 120, file=sys.stderr)
        print('acquire called: thread id:', current_thread(), 'shared:', self._is_shared, file=sys.stderr)
        traceback.print_stack()
        RWLockWrapper.acquire(self)
        print('acquire done: thread id:', current_thread(), file=sys.stderr)
        print('_' * 120, file=sys.stderr)

    def release(self, *args):
        print('*' * 120, file=sys.stderr)
        print('release called: thread id:', current_thread(), 'shared:', self._is_shared, file=sys.stderr)
        traceback.print_stack()
        RWLockWrapper.release(self)
        print('release done: thread id:', current_thread(), 'is_shared:', self._shlock.is_shared, 'is_exclusive:', self._shlock.is_exclusive, file=sys.stderr)
        print('_' * 120, file=sys.stderr)

    __enter__ = acquire
    __exit__ = release


class SafeReadLock(object):

    def __init__(self, read_lock):
        self.read_lock = read_lock
        self.acquired = False

    def acquire(self):
        try:
            self.read_lock.acquire()
        except DowngradeLockError:
            pass
        else:
            self.acquired = True
        return self

    def release(self, *args):
        if self.acquired:
            self.read_lock.release()
        self.acquired = False

    __enter__ = acquire
    __exit__  = release
