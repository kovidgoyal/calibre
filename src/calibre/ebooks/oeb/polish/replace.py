#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from urlparse import urlparse

from cssutils import replaceUrls

from calibre.ebooks.oeb.polish.container import guess_type
from calibre.ebooks.oeb.base import (OEB_DOCS, OEB_STYLES, rewrite_links)

class LinkReplacer(object):

    def __init__(self, base, container, link_map, frag_map):
        self.base = base
        self.frag_map = frag_map
        self.link_map = link_map
        self.container = container
        self.replaced = False

    def __call__(self, url):
        name = self.container.href_to_name(url, self.base)
        if not name:
            return url
        nname = self.link_map.get(name, None)
        if not nname:
            return url
        purl = urlparse(url)
        href = self.container.name_to_href(nname, self.base)
        if purl.fragment:
            nfrag = self.frag_map(name, purl.fragment)
            if nfrag:
                href += '#%s'%nfrag
        if href != url:
            self.replaced = True
        return href

def replace_links(container, link_map, frag_map=lambda name, frag:frag):
    ncx_type = guess_type('toc.ncx')
    for name, media_type in container.mime_map.iteritems():
        repl = LinkReplacer(name, container, link_map, frag_map)
        if media_type.lower() in OEB_DOCS:
            rewrite_links(container.parsed(name), repl)
        elif media_type.lower() in OEB_STYLES:
            replaceUrls(container.parsed(name), repl)
        elif media_type.lower() == ncx_type:
            for elem in container.parsed(name).xpath('//*[@src]'):
                src = elem.get('src')
                nsrc = repl(src)
                if src != nsrc:
                    elem.set('src', nsrc)

        if repl.replaced:
            container.dirty(name)


