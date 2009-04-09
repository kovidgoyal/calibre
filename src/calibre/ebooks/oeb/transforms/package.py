#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os
from urllib import unquote as urlunquote
from functools import partial

from lxml import etree
import cssutils

from calibre.constants import islinux
from calibre.ebooks.oeb.base import OEB_DOCS, urlnormalize, urldefrag, \
                                    rewrite_links

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
        base = os.path.join(self.new_base_path, *item.href.split('/'))
        base = os.path.dirname(base)

        if etree.iselement(item.data):
            self.rewrite_links_in_xml(item.data, base)
        elif hasattr(item.data, 'cssText'):
            self.rewrite_links_in_css(item.data, base)

    def link_replacer(self, link_, base=''):
        link = urlnormalize(link_)
        link, frag = urldefrag(link)
        link = urlunquote(link).replace('/', os.sep)
        if base and not os.path.isabs(link):
            link = os.path.join(base, link)
        link = os.path.abspath(link)
        if not islinux:
            link = link.lower()
        if link not in self.map:
            return link_
        nlink = os.path.relpath(self.map[link], base)
        if frag:
            nlink = '#'.join(nlink, frag)
        return nlink.replace(os.sep, '/')

    def rewrite_links_in_css(self, sheet, base):
        repl = partial(self.link_replacer, base=base)
        cssutils.replaceUrls(sheet, repl)

    def rewrite_links_in_xml(self, root, base):
        repl = partial(self.link_replacer, base=base)
        rewrite_links(root, repl)

    def move_manifest_item(self, item):
        item.data # Make sure the data has been loaded and cached
        old_abspath = os.path.join(self.old_base_path,
                *(urldefrag(item.href)[0].split('/')))
        old_abspath = os.path.abspath(old_abspath)
        bname = item.href.split('/')[-1].partition('#')[0]
        new_href = 'content/resources/'
        if item.media_type in OEB_DOCS:
            new_href = 'content/'
        elif item.href.lower().endswith('.ncx'):
            new_href = ''
        new_href += bname

        new_abspath = os.path.join(self.new_base_path, *new_href.split('/'))
        new_abspath = os.path.abspath(new_abspath)
        item.href   = new_href
        if not islinux:
            old_abspath, new_abspath = old_abspath.lower(), new_abspath.lower()
        if old_abspath != new_abspath:
            self.map[old_abspath] = new_abspath

    def rewrite_links_in_toc(self, toc):
        if toc.href:
            toc.href = self.link_replacer(toc.href, base=self.new_base_path)

        for x in toc:
            self.rewrite_links_in_toc(x)

    def __call__(self, oeb, context):
        self.map = {}
        self.log = self.oeb.log
        self.old_base_path = os.path.abspath(oeb.container.rootdir)

        for item in self.oeb.manifest:
            self.move_manifest_item(item)

        for item in self.oeb.manifest:
            self.rewrite_links_in(item)

        if getattr(oeb.toc, 'nodes', False):
            self.rewrite_links_in_toc(oeb.toc)

        if hasattr(oeb, 'guide'):
            for ref in oeb.guide.values():
                ref.href = self.link_replacer(ref.href, base=self.new_base_path)
