#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os, shutil, subprocess

base = os.path.dirname(os.path.abspath(__file__))

os.chdir('/tmp')
if os.path.exists('libmtp'):
    shutil.rmtree('libmtp')
subprocess.check_call(['git', 'clone', 'git://git.code.sf.net/p/libmtp/code',
                       'libmtp'])
for x in ('src/music-players.h', 'src/device-flags.h'):
    with open(os.path.join(base, os.path.basename(x)), 'wb') as f:
        shutil.copyfileobj(open('libmtp/'+x), f)

