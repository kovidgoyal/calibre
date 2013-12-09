#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

from collections import defaultdict
from urlparse import urlparse

from calibre.ebooks.oeb.base import OEB_DOCS, OEB_STYLES
from calibre.ebooks.oeb.polish.container import guess_type
from calibre.ebooks.oeb.polish.check.base import BaseError, WARN

class BadLink(BaseError):

    HELP = _('The resource pointed to by this link does not exist. You should'
             ' either fix, or remove the link.')
    level = WARN

class FileLink(BadLink):

    HELP = _('This link uses the file:// URL scheme. This does not work with many ebook readers.'
             ' Remove the file:// prefix and make sure the link points to a file inside the book.')

class LocalLink(BadLink):

    HELP = _('This link points to a file outside the book. It will not work if the'
             ' book is read on any computer other than the one it was created on.'
             ' Either fix or remove the link.')

def check_links(container):
    links_map = defaultdict(set)
    xml_types = {guess_type('a.opf'), guess_type('a.ncx')}
    errors = []
    a = errors.append

    def fl(x):
        x = repr(x)
        if x.startswith('u'):
            x = x[1:]
        return x

    for name, mt in container.mime_map.iteritems():
        if mt in OEB_DOCS or mt in OEB_STYLES or mt in xml_types:
            for href, lnum, col in container.iterlinks(name):
                tname = container.href_to_name(href, name)
                if tname is not None:
                    if container.exists(tname):
                        links_map[tname].add(name)
                    else:
                        a(BadLink(_('The linked resource %s does not exist') % fl(href), name, lnum, col))
                else:
                    purl = urlparse(href)
                    if purl.scheme == 'file':
                        a(FileLink(_('The link %s is a file:// URL') % fl(href), name, lnum, col))
                    elif purl.path and purl.path.startswith('/') and purl.scheme in {'', 'file'}:
                        a(LocalLink(_('The link %s points to a file outside the book') % fl(href), name, lnum, col))

    return errors
