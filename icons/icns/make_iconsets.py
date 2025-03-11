#!/usr/bin/env python


__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

import os
import shutil
import subprocess
import sys
import tempfile

d, j, a = (getattr(os.path, x) for x in ('dirname', 'join', 'abspath'))
base = d(a(__file__))
os.chdir(base)

imgsrc = j(d(d(base)), 'imgsrc')
sources = {'calibre':j(imgsrc, 'calibre.svg'), 'ebook-edit':j(imgsrc, 'tweak.svg'), 'ebook-viewer':j(imgsrc, 'viewer.svg'), 'book':j(imgsrc, 'book.svg')}
if sys.argv[-1] == 'only-logo':
    sources = {'calibre':sources['calibre']}


def render_svg(src, sz, dest):
    subprocess.check_call(['rsvg-convert', src, '-w', str(sz), '-h', str(sz), '-o', dest])


with tempfile.TemporaryDirectory() as tdir:

    def render_frame(sz: int):
        f = os.path.join(tdir, f'frame-{sz}.png')
        if not os.path.exists(f):
            render_svg(j(imgsrc, 'frame.svg'), sz, f)
        return f

    def render_framed(sz: int, iname: str, shrink_factor: float = 0.75):
        frame = render_frame(sz)
        icon = os.path.join(tdir, f'icon-{sz}.png')
        render_svg(src, int(shrink_factor * sz), icon)
        subprocess.check_call(f'convert {frame} {icon} -gravity center -compose over -composite {iname}'.split())

    for name, src in sources.items():
        iconset = name + '.iconset'
        if os.path.exists(iconset):
            shutil.rmtree(iconset)
        os.mkdir(iconset)
        os.chdir(iconset)
        try:
            for sz in (16, 32, 128, 256, 512, 1024):
                iname = f'icon_{sz}x{sz}.png'
                iname2x = f'icon_{sz // 2}x{sz // 2}@2x.png'
                if sz < 128:
                    render_svg(src, sz, iname)
                else:
                    render_framed(sz, iname)
                if sz > 16:
                    shutil.copy2(iname, iname2x)
                if sz > 512:
                    os.remove(iname)
                for name in (iname, iname2x):
                    if os.path.exists(name):
                        subprocess.check_call(['optipng', '-o7', '-strip', 'all', name])
        finally:
            os.chdir('..')
