#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2020, Kovid Goyal <kovid at kovidgoyal.net>

from calibre.constants import iswindows, ismacos

if iswindows:
    from .windows import Client
elif ismacos:
    pass
else:
    from .linux import Client
    Client
