#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

MP = 'http://libmtp.git.sourceforge.net/git/gitweb.cgi?p=libmtp/libmtp;a=blob_plain;f=src/music-players.h;hb=HEAD'
DF = 'http://libmtp.git.sourceforge.net/git/gitweb.cgi?p=libmtp/libmtp;a=blob_plain;f=src/device-flags.h;hb=HEAD'

import urllib, os, shutil

base = os.path.dirname(os.path.abspath(__file__))

for url, fname in [(MP, 'music-players.h'), (DF, 'device-flags.h')]:
    with open(os.path.join(base, fname), 'wb') as f:
        shutil.copyfileobj(urllib.urlopen(url), f)

