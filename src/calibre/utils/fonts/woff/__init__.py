#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from calibre.constants import plugins

def get_woff():
    woff, woff_err = plugins['woff']
    if woff_err:
        raise RuntimeError('Failed to load the WOFF plugin: %s'%woff_err)
    return woff

def to_woff(raw):
    woff = get_woff()
    return woff.to_woff(raw)

def from_woff(raw):
    woff = get_woff()
    return woff.from_woff(raw)

def test():
    sfnt = P('fonts/calibreSymbols.otf', data=True)
    woff = to_woff(sfnt)
    recon = from_woff(woff)
    if recon != sfnt:
        raise ValueError('WOFF roundtrip resulted in different sfnt')

if __name__ == '__main__':
    test()


