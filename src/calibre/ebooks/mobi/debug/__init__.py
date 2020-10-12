#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai


__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'


def format_bytes(byts):
    byts = bytearray(byts)
    byts = [hex(b)[2:] for b in byts]
    return ' '.join(byts)


