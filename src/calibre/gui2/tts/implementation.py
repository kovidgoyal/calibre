#!/usr/bin/env python
# License: GPL v3 Copyright: 2020, Kovid Goyal <kovid at kovidgoyal.net>

from calibre.constants import ismacos, iswindows

if iswindows:
    from calibre.utils.config_base import tweaks
    if tweaks.get('prefer_winsapi'):
        from .windows_sapi import Client
    else:
        from .windows import Client
elif ismacos:
    from .macos import Client
else:
    from .linux import Client
Client
