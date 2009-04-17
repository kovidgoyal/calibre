#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os, re
from urllib import unquote as urlunquote
from functools import partial

from lxml import etree
import cssutils

from calibre import sanitize_file_name
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
        old_href = item.old_href.split('#')[0]
        new_href = item.href.split('#')[0]
        base = os.path.join(self.old_base_path, *old_href.split('/'))
        base = os.path.dirname(base)
        self.log.debug('\tRewriting links in', base+'/'+
                item.href.rpartition('/')[-1])
        new_base = os.path.join(self.new_base_path, *new_href.split('/'))
        new_base = os.path.dirname(new_base)

        if etree.iselement(item.data):
            self.rewrite_links_in_xml(item.data, base, new_base)
        elif hasattr(item.data, 'cssText'):
            self.rewrite_links_in_css(item.data, base, new_base)

    def link_replacer(self, link_, base='', new_base=''):
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
        nlink = os.path.relpath(self.map[link], new_base)
        if frag:
            nlink = '#'.join((nlink, frag))
        return nlink.replace(os.sep, '/')

    def rewrite_links_in_css(self, sheet, base, new_base):
        repl = partial(self.link_replacer, base=base, new_base=new_base)
        cssutils.replaceUrls(sheet, repl)

    def rewrite_links_in_xml(self, root, base, new_base):
        repl = partial(self.link_replacer, base=base, new_base=new_base)
        rewrite_links(root, repl)

    def uniqify_name(self, new_href, hrefs):
        c = 0
        while new_href in hrefs:
            c += 1
            parts = new_href.split('/')
            name, ext = os.path.splitext(parts[-1])
            name = re.sub(r'_\d+$', '', name)
            name += '_%d'%c
            parts[-1] = name + ext
            new_href = '/'.join(parts)
        return new_href


    def move_manifest_item(self, item, hrefs):
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
        new_href += sanitize_file_name(bname)

        if new_href in hrefs:
            new_href = self.uniqify_name(new_href, hrefs)
        hrefs.add(new_href)

        new_abspath = os.path.join(self.new_base_path, *new_href.split('/'))
        new_abspath = os.path.abspath(new_abspath)
        item.old_href = self.oeb.manifest.hrefs.pop(item.href).href
        item.href   = new_href
        self.oeb.manifest.hrefs[item.href] = item
        if not islinux:
            old_abspath, new_abspath = old_abspath.lower(), new_abspath.lower()
        if old_abspath != new_abspath:
            self.map[old_abspath] = new_abspath

    def rewrite_links_in_toc(self, toc):
        if toc.href:
            toc.href = self.link_replacer(toc.href, base=self.old_base_path,
                    new_base=self.new_base_path)

        for x in toc:
            self.rewrite_links_in_toc(x)

    def __call__(self, oeb, context):
        self.map = {}
        self.log = oeb.log
        self.oeb = oeb
        self.old_base_path = os.path.abspath(oeb.container.rootdir)
        self.log.info('Packaging HTML files...')

        hrefs = set([])
        for item in self.oeb.manifest:
            self.move_manifest_item(item, hrefs)

        self.log.debug('Rewriting links in OEB documents...')
        for item in self.oeb.manifest:
            self.rewrite_links_in(item)

        if getattr(oeb.toc, 'nodes', False):
            self.log.debug('Rewriting links in TOC...')
            self.rewrite_links_in_toc(oeb.toc)

        if hasattr(oeb, 'guide'):
            self.log.debug('Rewriting links in guide...')
            for ref in oeb.guide.values():
                ref.href = self.link_replacer(ref.href,
                        base=self.old_base_path,
                        new_base=self.new_base_path)
