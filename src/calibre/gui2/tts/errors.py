#!/usr/bin/env python
# License: GPL v3 Copyright: 2020, Kovid Goyal <kovid at kovidgoyal.net>


class TTSSystemUnavailable(Exception):
    def __init__(self, message, details):
        Exception.__init__(self, message)
        self.short_msg = message
        self.details = details
