#!/usr/bin/env python3


__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os, shutil, subprocess

base = os.path.dirname(os.path.abspath(__file__))

os.chdir('/tmp')
if os.path.exists('libmtp'):
    shutil.rmtree('libmtp')
subprocess.check_call(['git', 'clone', '--depth=1', 'git://git.code.sf.net/p/libmtp/code',
                       'libmtp'])
for x in ('src/music-players.h', 'src/device-flags.h'):
    shutil.copyfile('libmtp/'+x, os.path.join(base, os.path.basename(x)))
