#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from calibre.constants import iswindows

if iswindows:
    from calibre.devices.mtp.windows.driver import MTP_DEVICE as BASE
    BASE
else:
    from calibre.devices.mtp.unix.driver import MTP_DEVICE as BASE

class MTP_DEVICE(BASE):
    pass

