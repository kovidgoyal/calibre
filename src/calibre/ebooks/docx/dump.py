#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

import sys, os, shutil

from lxml import etree

from calibre import walk
from calibre.utils.zipfile import ZipFile

def dump(path):
    dest = os.path.splitext(os.path.basename(path))[0]
    dest += '_extracted'
    if os.path.exists(dest):
        shutil.rmtree(dest)
    with ZipFile(path) as zf:
        zf.extractall(dest)

    for f in walk(dest):
        if f.endswith('.xml'):
            with open(f, 'r+b') as stream:
                raw = stream.read()
                root = etree.fromstring(raw)
                stream.seek(0)
                stream.truncate()
                stream.write(etree.tostring(root, pretty_print=True, encoding='utf-8', xml_declaration=True))

    print (path, 'dumped to', dest)

if __name__ == '__main__':
    dump(sys.argv[-1])

