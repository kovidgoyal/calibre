#!/usr/bin/env python

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
        return str(self) + '\n' + self.tb
