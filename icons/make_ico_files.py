#!/usr/bin/env python2
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

import os, shutil, subprocess

d, j, a = (getattr(os.path, x) for x in ('dirname', 'join', 'abspath'))
base = d(a(__file__))
os.chdir(base)

imgsrc = j(d(base), 'imgsrc')
sources = {'library':j(imgsrc, 'calibre.svg'), 'ebook-edit':j(imgsrc, 'tweak.svg'), 'viewer':j(imgsrc, 'viewer.svg'), 'favicon':j(imgsrc, 'calibre.svg')}

for name, src in sources.iteritems():
    os.mkdir('ico_temp')
    try:
        names = []
        for sz in (16, 32, 48, 256):
            iname = os.path.join('ico_temp', '{0}x{0}.png'.format(sz))
            subprocess.check_call(['rsvg-convert', src, '-w', str(sz), '-h', str(sz), '-o', iname])
            subprocess.check_call(['optipng', '-o7', '-strip', 'all', iname])
            names.append(iname)
        names[-1:-1] = ['-r']
        subprocess.check_call(['icotool', '-c', '--output=' + name+'.ico'] + names)
    finally:
        shutil.rmtree('ico_temp')
