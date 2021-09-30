#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2019, Kovid Goyal <kovid at kovidgoyal.net>

import sys
from functools import partial


class FilteredLog:

    ' Hide AUTH credentials from the log '

    def __init__(self, debug_to=None):
        self.debug_to = debug_to or partial(print, file=sys.stderr)

    def __call__(self, *a):
        if a and len(a) == 2 and a[0] == 'send:':
            a = list(a)
            raw = a[1]
            if len(raw) > 100:
                raw = raw[:100] + (b'...' if isinstance(raw, bytes) else '...')
            q = b'AUTH ' if isinstance(raw, bytes) else 'AUTH '
            if q in raw:
                raw = 'AUTH <censored>'
            a[1] = raw
        self.debug_to(*a)


import smtplib


class SMTP(smtplib.SMTP):

    def __init__(self, *a, **kw):
        self.debug_to = FilteredLog(kw.pop('debug_to', None))
        super().__init__(*a, **kw)

    def _print_debug(self, *a):
        if self.debug_to is not None:
            self.debug_to(*a)
        else:
            super()._print_debug(*a)


class SMTP_SSL(smtplib.SMTP_SSL):

    def __init__(self, *a, **kw):
        self.debug_to = FilteredLog(kw.pop('debug_to', None))
        super().__init__(*a, **kw)

    def _print_debug(self, *a):
        if self.debug_to is not None:
            self.debug_to(*a)
        else:
            super()._print_debug(*a)
