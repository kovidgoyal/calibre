#!/usr/bin/env python2
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'


def control(func):
    func.function_type = 'control'
    return func


def data(func):
    func.function_type = 'data'
    return func


class DataError(Exception):

    def __init__(self, tb, msg=None):
        Exception.__init__(self, msg or _('Failed to get completion data'))
        self.tb = tb

    def traceback(self):
        return unicode(self) + '\n' + self.tb
