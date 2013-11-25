#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'


from calibre.ebooks.oeb.polish.parsing import parse
from calibre.ebooks.oeb.base import serialize, OEB_DOCS

def fix_html(raw):
    root = parse(raw)
    return serialize(root, 'text/html').decode('utf-8')

def fix_all_html(container):
    for name, mt in container.mime_map.iteritems():
        if mt in OEB_DOCS:
            container.parsed(name)
            container.dirty(name)

