#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

from collections import defaultdict
from urlparse import urlparse

from calibre.ebooks.oeb.base import OEB_DOCS, OEB_STYLES
from calibre.ebooks.oeb.polish.container import guess_type, OEB_FONTS
from calibre.ebooks.oeb.polish.check.base import BaseError, WARN, INFO

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

class UnreferencedResource(BadLink):

    HELP = _('This file is included in the book but not referred to by any document in the spine.'
             ' This means that the file will not be viewable on most ebook readers. You should '
             ' probably remove this file from the book or add a link to it somewhere.')

    def __init__(self, name):
        BadLink.__init__(self, _(
            'The file %s is not referenced') % name, name)

class UnreferencedDoc(UnreferencedResource):

    HELP = _('This file is not in the book spine. All content documents must be in the spine.'
             ' You should probably add it to the spine.')

class Unmanifested(BadLink):

    HELP = _('This file is not listed in the book manifest. While not strictly necessary'
             ' it is good practice to list all files in the manifest. Either list this'
             ' file in the manifest or remove it from the book if it is an unnecessary file.')

    def __init__(self, name):
        BadLink.__init__(self, _(
            'The file %s is not listed in the manifest') % name, name)
        if name == 'META-INF/calibre_bookmarks.txt':
            self.HELP = _(
                'This file stores the bookmarks and last opened information from'
                ' the calibre ebook viewer. You can remove it if you do not'
                ' need that information, or dont want to share it with'
                ' other people you send this book to.')
            self.INDIVIDUAL_FIX = _('Remove this file')
            self.level = INFO
            self.msg = _('The bookmarks file used by the calibre ebook viewer is present')

    def __call__(self, container):
        container.remove_item(self.name)
        return True


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
                        links_map[name].add(tname)
                    else:
                        a(BadLink(_('The linked resource %s does not exist') % fl(href), name, lnum, col))
                else:
                    purl = urlparse(href)
                    if purl.scheme == 'file':
                        a(FileLink(_('The link %s is a file:// URL') % fl(href), name, lnum, col))
                    elif purl.path and purl.path.startswith('/') and purl.scheme in {'', 'file'}:
                        a(LocalLink(_('The link %s points to a file outside the book') % fl(href), name, lnum, col))

    spine_docs = {name for name, linear in container.spine_names}
    spine_styles = {tname for name in spine_docs for tname in links_map[name] if container.mime_map[tname] in OEB_STYLES}
    num = -1
    while len(spine_styles) > num:
        # Handle import rules in stylesheets
        num = len(spine_styles)
        spine_styles |= {tname for name in spine_styles for tname in links_map[name] if container.mime_map[tname] in OEB_STYLES}
    seen = set(OEB_DOCS) | set(OEB_STYLES)
    spine_resources = {tname for name in spine_docs | spine_styles for tname in links_map[name] if container.mime_map[tname] not in seen}
    unreferenced = set()

    cover_name = container.guide_type_map.get('cover', None)

    for name, mt in container.mime_map.iteritems():
        if mt in OEB_STYLES and name not in spine_styles:
            a(UnreferencedResource(name))
        elif mt in OEB_DOCS and name not in spine_docs:
            a(UnreferencedDoc(name))
        elif (mt in OEB_FONTS or mt.partition('/')[0] in {'image', 'audio', 'video'}) and name not in spine_resources and name != cover_name:
            a(UnreferencedResource(name))
        else:
            continue
        unreferenced.add(name)

    manifest_names = set(container.manifest_id_map.itervalues())
    for name in container.mime_map:
        if name not in container.names_that_need_not_be_manifested and name not in manifest_names:
            a(Unmanifested(name))

    return errors
