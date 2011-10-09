#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

_count = 0

import time, cStringIO
from Queue import Queue, Empty

from calibre import prints
from calibre.constants import DEBUG

class BaseJob(object):

    WAITING  = 0
    RUNNING  = 1
    FINISHED = 2

    def __init__(self, description, done=lambda x: x):
        global _count
        _count += 1

        self.id            = _count
        self.description   = description
        self.done          = done
        self.done2         = None
        self.killed        = False
        self.failed        = False
        self.kill_on_start = False
        self.start_time    = None
        self.result        = None
        self.duration      = None
        self.log_path      = None
        self.notifications = Queue()

        self._run_state    = self.WAITING
        self.percent       = 0
        self._message      = None
        self._status_text  = _('Waiting...')
        self._done_called  = False
        self.core_usage    = 1
        self.timed_out     = False

    def update(self, consume_notifications=True):
        if self.duration is not None:
            self._run_state   = self.FINISHED
            self.percent = 100
            if self.killed:
                if self.timed_out:
                    self._status_text = _('Aborted, taking too long')
                else:
                    self._status_text = _('Stopped')
            else:
                self._status_text = _('Error') if self.failed else _('Finished')
            if DEBUG:
                try:
                    prints('Job:', self.id, self.description, 'finished',
                        safe_encode=True)
                    prints('\t'.join(self.details.splitlines(True)),
                        safe_encode=True)
                except:
                    pass
            if not self._done_called:
                self._done_called = True
                try:
                    self.done(self)
                except:
                    pass
                try:
                    if callable(self.done2):
                        self.done2(self)
                except:
                    pass
        elif self.start_time is not None:
            self._run_state = self.RUNNING
            self._status_text = _('Working...')

        if consume_notifications:
            return self.consume_notifications()
        return False

    def consume_notifications(self):
        got_notification = False
        while self.notifications is not None:
            try:
                self.percent, self._message = self.notifications.get_nowait()
                self.percent *= 100.
                got_notification = True
            except Empty:
                break
        return got_notification

    @property
    def status_text(self):
        if self._run_state == self.FINISHED or not self._message:
            return self._status_text
        return self._message

    @property
    def run_state(self):
        return self._run_state

    @property
    def running_time(self):
        if self.duration is not None:
            return self.duration
        if self.start_time is not None:
            return time.time() - self.start_time
        return None

    @property
    def is_finished(self):
        return self._run_state == self.FINISHED

    @property
    def is_started(self):
        return self._run_state != self.WAITING

    @property
    def is_running(self):
        return self.is_started and not self.is_finished

    def __cmp__(self, other):
        if self.is_finished == other.is_finished:
            if self.start_time is None:
                if other.start_time is None: # Both waiting
                    return cmp(other.id, self.id)
                else:
                    return 1
            else:
                if other.start_time is None:
                    return -1
                else: # Both running
                    return cmp(other.start_time, self.start_time)

        else:
            return 1 if self.is_finished else -1
        return 0

    @property
    def log_file(self):
        if self.log_path:
            return open(self.log_path, 'rb')
        return cStringIO.StringIO(_('No details available.').encode('utf-8',
            'replace'))

    @property
    def details(self):
        return self.log_file.read().decode('utf-8', 'replace')


class ParallelJob(BaseJob):

    def __init__(self, name, description, done, args=[], kwargs={}):
        self.name, self.args, self.kwargs = name, args, kwargs
        BaseJob.__init__(self, description, done)



