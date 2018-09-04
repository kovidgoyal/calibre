#!/usr/bin/env python2
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import json, time

from PyQt5.Qt import QApplication, QEventLoop

from calibre.constants import DEBUG


class PagePosition(object):

    def __init__(self, document):
        self.document = document
        document.jump_to_cfi_listeners.add(self)
        self.cfi_job_id = 0
        self.pending_scrolls = set()

    @property
    def viewport_cfi(self):
        ans = self.document.mainFrame().evaluateJavaScript('''
            ans = 'undefined';
            if (window.paged_display) {
                ans = window.paged_display.current_cfi();
                if (!ans) ans = 'undefined';
            }
            ans;
        ''')
        if ans in {'', 'undefined'}:
            ans = None
        return ans

    def scroll_to_cfi(self, cfi):
        if cfi:
            jid = self.cfi_job_id
            self.cfi_job_id += 1
            cfi = json.dumps(cfi)
            self.pending_scrolls.add(jid)
            self.document.mainFrame().evaluateJavaScript(
                    'paged_display.jump_to_cfi(%s, %d)' % (cfi, jid))
            # jump_to_cfi is async, so we wait for it to complete
            st = time.time()
            WAIT = 1  # seconds
            while jid in self.pending_scrolls and time.time() - st < WAIT:
                QApplication.processEvents(QEventLoop.ExcludeUserInputEvents | QEventLoop.ExcludeSocketNotifiers)
                time.sleep(0.01)
            if jid in self.pending_scrolls:
                self.pending_scrolls.discard(jid)
                if DEBUG:
                    print ('jump_to_cfi() failed to complete after %s seconds' % WAIT)

    @property
    def current_pos(self):
        ans = self.viewport_cfi
        if not ans:
            ans = self.document.scroll_fraction
        return ans

    def __enter__(self):
        self.save()

    def __exit__(self, *args):
        self.restore()

    def __call__(self, cfi_job_id):
        self.pending_scrolls.discard(cfi_job_id)

    def save(self, overwrite=True):
        if not overwrite and self._cpos is not None:
            return
        self._cpos = self.current_pos

    def restore(self):
        if self._cpos is None:
            return
        self.to_pos(self._cpos)
        self._cpos = None

    def to_pos(self, pos):
        if isinstance(pos, (int, float)):
            self.document.scroll_fraction = pos
        else:
            self.scroll_to_cfi(pos)

    def set_pos(self, pos):
        self._cpos = pos
