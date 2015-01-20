#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2015, Kovid Goyal <kovid at kovidgoyal.net>'

import posixpath, os
from collections import namedtuple, defaultdict

from calibre.ebooks.oeb.polish.container import OEB_DOCS, OEB_STYLES, OEB_FONTS
from calibre.utils.icu import numeric_sort_key
from calibre.utils.magick.draw import identify

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

def safe_size(container, name):
    try:
        return os.path.getsize(container.name_to_abspath(name))
    except Exception:
        return 0

def safe_img_data(container, name, mt):
    if 'svg' in mt:
        return 0, 0
    try:
        width, height, fmt = identify(container.name_to_abspath(name))
    except Exception:
        width = height = 0
    return width, height

def file_data(container):
    for name, path in container.name_path_map.iteritems():
        yield File(name, posixpath.dirname(name), posixpath.basename(name), safe_size(container, name),
                   get_category(name, container.mime_map.get(name, '')))

Image = namedtuple('Image', 'name mime_type usage size width height')
L = namedtuple('Location', 'name line_number offset word')
def Location(name, line_number=None, offset=0, word=None):
    return L(name, line_number, offset, word)

def sort_locations(locations):
    def sort_key(l):
        return (numeric_sort_key(l.name), l.line_number, l.offset, l.word)
    return sorted(locations, key=sort_key)

def link_data(container):
    image_usage = defaultdict(set)
    link_sources = OEB_STYLES | OEB_DOCS
    for name, mt in container.mime_map.iteritems():
        if mt in link_sources:
            for href, line_number, offset in container.iterlinks(name):
                target = container.href_to_name(href, name)
                if target and container.exists(target):
                    mt = container.mime_map.get(target)
                    if mt and mt.startswith('image/'):
                        image_usage[target].add(Location(name, line_number, offset))

    image_data = []
    for name, mt in container.mime_map.iteritems():
        if mt.startswith('image/') and container.exists(name):
            image_data.append(Image(name, mt, sort_locations(image_usage.get(name, set())), safe_size(container, name),
                                    *safe_img_data(container, name, mt)))
    return tuple(image_data)

def gather_data(container):
    data =  {'files':tuple(file_data(container))}
    img_data = link_data(container)
    data['images'] = img_data
    return data
