#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai


__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from datetime import datetime, timedelta


def align_block(raw, multiple=4, pad=b'\0'):
    '''
    Return raw with enough pad bytes append to ensure its length is a multiple
    of 4.
    '''
    extra = len(raw) % multiple
    if extra == 0:
        return raw
    return raw + pad*(multiple - extra)


class UnknownTable(object):

    def __init__(self, raw):
        self.raw = raw

    def __call__(self):
        return self.raw

    def __len__(self):
        return len(self.raw)


class DateTimeProperty(object):

    def __init__(self, name):
        self.name = name

    def __get__(self, obj, type=None):
        return datetime(1904, 1, 1) + timedelta(seconds=getattr(obj,
            self.name))

    def __set__(self, obj, val):
        td = val - datetime(1904, 1, 1)
        setattr(obj, self.name, int(td.total_seconds()))


class FixedProperty(object):

    def __init__(self, name):
        self.name = name

    def __get__(self, obj, type=None):
        val = getattr(obj, self.name)
        return val / 0x10000

    def __set__(self, obj, val):
        return int(round(val*(0x10000)))


def max_power_of_two(x):
    """
Return the highest exponent of two, so that
    (2 ** exponent) <= x
    """
    exponent = 0
    while x:
        x = x >> 1
        exponent += 1
    return max(exponent - 1, 0)


def load_font(stream_or_path):
    raw = stream_or_path
    if hasattr(raw, 'read'):
        raw = raw.read()
    from calibre.utils.fonts.sfnt.container import Sfnt
    return Sfnt(raw)

