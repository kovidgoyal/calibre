#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os, shutil

from calibre.ebooks.oeb.base import OEB_DOCS

class Package(object):

    '''
    Move all the parts of an OEB into a folder structure rooted
    at the specified folder. All links in recognized content types
    are processed, the linked to resources are copied into the local
    folder tree and all references to those resources are updated.

    The created folder structure is

    Base directory(OPF, NCX) -- content (XHTML) -- resources (CSS, Images, etc)

    '''

    def __init__(self, base='.'):
        ':param base: The base folder at which the OEB will be rooted'
        self.new_base_path = os.path.abspath(base)

    def rewrite_links_in(self, item):
        new_items = []
        return new_items

    def move_manifest_item(self, item):
        item.data # Make sure the data has been loaded and cached
        old_abspath = os.path.join(self.old_base_path, *item.href.split('/'))
        bname = item.href.split('/')[-1]
        new_href = 'content/' + \
                ('resources/' if item.media_type in OEB_DOCS else '')+bname

    def __call__(self, oeb, context):
        self.map = {}
        self.old_base_path = os.path.abspath(oeb.container.rootdir)

        for item in self.oeb.manifest:
            self.move_manifest_item(item)

        for item in self.oeb.manifest:
            self.rewrite_links_in(item)


