#!/usr/bin/env python
# vim:fileencoding=utf-8


__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

import os, shutil, subprocess, sys

d, j, a = (getattr(os.path, x) for x in ('dirname', 'join', 'abspath'))
base = d(a(__file__))
os.chdir(base)

imgsrc = j(d(base), 'imgsrc')
sources = {'library':j(imgsrc, 'calibre.svg'), 'ebook-edit':j(imgsrc, 'tweak.svg'), 'viewer':j(imgsrc, 'viewer.svg'), 'favicon':j(imgsrc, 'calibre.svg')}
if sys.argv[-1] == 'only-logo':
    sources = {'library':sources['library']}

for name, src in sources.items():
    os.mkdir('ico_temp')
    try:
        names = []
        for sz in (16, 24, 32, 48, 64, 256):
            iname = os.path.join('ico_temp', '{0}x{0}.png'.format(sz))
            subprocess.check_call(['rsvg-convert', src, '-w', str(sz), '-h', str(sz), '-o', iname])
            subprocess.check_call(['optipng', '-o7', '-strip', 'all', iname])
            if sz >= 128:
                names.append('-r')  # store as raw PNG to reduce size
            else:
                names.extend(['-t', '0'])  # see https://bugzilla.gnome.org/show_bug.cgi?id=755200
            names.append(iname)
        subprocess.check_call(['icotool', '-c', '--output=' + name+'.ico'] + names)
    finally:
        shutil.rmtree('ico_temp')
