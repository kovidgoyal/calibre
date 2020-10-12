#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2016, Kovid Goyal <kovid at kovidgoyal.net>


import os, subprocess, sys, shutil

j = os.path.join
base = os.path.dirname(os.path.abspath(__file__))
resources = j(os.path.dirname(base), 'resources')
icons = j(os.path.dirname(base), 'icons')
srv = j(os.path.dirname(os.path.dirname(base)), 'srv')


def render(outpath, sz, background=None):
    sz = str(sz)
    cmd = ['rsvg-convert', j(base, 'calibre.svg'), '-w', sz, '-h', sz, '-d', '96', '-p', '96', '-o', outpath]
    if background:
        cmd.insert(2, background), cmd.insert(2, '-b')
    subprocess.check_call(cmd)
    subprocess.check_call(['optipng', '-o7', '-strip', 'all', outpath])


render(j(resources, 'images', 'library.png'), 1024)
render(j(resources, 'images', 'lt.png'), 256)
render(j(resources, 'images', 'apple-touch-icon.png'), 256, 'white')
render(j(resources, 'content-server', 'calibre.png'), 128)
render(j(srv, 'main', 'calibre-paypal-logo.png'), 60)
shutil.copy2(j(resources, 'content-server', 'calibre.png'), j(resources, 'content_server', 'calibre.png'))
shutil.copy2(j(resources, 'images', 'lt.png'), j(srv, 'common', 'favicon.png'))
shutil.copy2(j(resources, 'images', 'lt.png'), j(srv, 'common', 'favicon.png'))

subprocess.check_call([sys.executable, j(icons, 'make_ico_files.py'), 'only-logo'])
shutil.copy2(j(icons, 'library.ico'), j(srv, 'common', 'favicon.ico'))
shutil.copy2(j(icons, 'library.ico'), j(srv, 'main/static/resources/img', 'favicon.ico'))
shutil.copy2(j(icons, 'library.ico'), j(srv, 'open-books/drmfree/static/img', 'favicon.ico'))
subprocess.check_call([sys.executable, j(icons, 'icns', 'make_iconsets.py'), 'only-logo'])

os.chdir(srv)
subprocess.check_call(['git', 'commit', '-am', 'Update calibre favicons'])
for s in 'main code open-books dl1'.split():
    subprocess.check_call(['./publish', s, 'update'])
