#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'


from calibre.constants import plugins

libusb, libusb_err = plugins['libusb']

def scan():
    if libusb_err:
        raise RuntimeError('Failed to load libusb1: '+libusb_err)
    return set([x for x in libusb.scan() if x is not None])

def info(vendor, product, bcd):
    if libusb_err:
        raise RuntimeError('Failed to load libusb1: '+libusb_err)
    a = libusb.info(vendor, product, bcd)
    ans = {}
    for k, v in a.items():
        ans[k] = v.decode('ascii', 'replace')
    return ans

