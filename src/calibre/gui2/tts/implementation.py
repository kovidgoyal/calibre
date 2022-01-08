#!/usr/bin/env python
# License: GPL v3 Copyright: 2020, Kovid Goyal <kovid at kovidgoyal.net>

from calibre.constants import iswindows, ismacos

if iswindows:
    from .windows import Client
elif ismacos:
    from .macos import Client
else:
    from .linux import Client
Client
