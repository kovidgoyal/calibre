#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2015, Kovid Goyal <kovid at kovidgoyal.net>'

import posixpath, os
from collections import namedtuple

from calibre.ebooks.oeb.polish.container import OEB_DOCS, OEB_STYLES, OEB_FONTS

File = namedtuple('File', 'name dir basename size category')

def get_category(name, mt):
    category = 'misc'
    if mt.startswith('image/'):
        category = 'image'
    elif mt in OEB_FONTS:
        category = 'font'
    elif mt in OEB_STYLES:
        category = 'style'
    elif mt in OEB_DOCS:
        category = 'text'
    ext = name.rpartition('.')[-1].lower()
    if ext in {'ttf', 'otf', 'woff'}:
        # Probably wrong mimetype in the OPF
        category = 'font'
    elif ext == 'opf':
        category = 'opf'
    elif ext == 'ncx':
        category = 'toc'
    return category

def file_data(container):
    for name, path in container.name_path_map.iteritems():
        yield File(name, posixpath.dirname(name), os.path.getsize(name), posixpath.basename(name),
                   get_category(name, container.mime_map.get(name, '')))


def gather_data(container):
    data =  {'files':tuple(file_data(container))}
    return data
