#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import codecs
from urlparse import urlparse

from calibre.ebooks.chardet import strip_encoding_declarations

class LinkReplacer(object):

    def __init__(self, base, container, link_map, frag_map):
        self.base = base
        self.frag_map = frag_map
        self.link_map = link_map
        self.container = container
        self.replaced = False

    def __call__(self, url):
        if url and url.startswith('#'):
            repl = self.frag_map(self.base, url[1:])
            if not repl or repl == url[1:]:
                return url
            self.replaced = True
            return '#' + repl
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

class LinkRebaser(object):

    def __init__(self, container, old_name, new_name):
        self.old_name, self.new_name = old_name, new_name
        self.container = container
        self.replaced = False

    def __call__(self, url):
        if url and url.startswith('#'):
            return url
        purl = urlparse(url)
        frag = purl.fragment
        name = self.container.href_to_name(url, self.old_name)
        if not name:
            return url
        if name == self.old_name:
            name = self.new_name
        href = self.container.name_to_href(name, self.new_name)
        if frag:
            href += '#' + frag
        if href != url:
            self.replaced = True
        return href


def replace_links(container, link_map, frag_map=lambda name, frag:frag, replace_in_opf=False):
    for name, media_type in container.mime_map.iteritems():
        if name == container.opf_name and not replace_in_opf:
            continue
        repl = LinkReplacer(name, container, link_map, frag_map)
        container.replace_links(name, repl)

def smarten_punctuation(container, report):
    from calibre.ebooks.conversion.preprocess import smarten_punctuation
    for path in container.spine_items:
        name = container.abspath_to_name(path)
        changed = False
        with container.open(name, 'r+b') as f:
            html = container.decode(f.read())
            newhtml = smarten_punctuation(html, container.log)
            if newhtml != html:
                changed = True
                report(_('Smartened punctuation in: %s')%name)
                newhtml = strip_encoding_declarations(newhtml)
                f.seek(0)
                f.truncate()
                f.write(codecs.BOM_UTF8 + newhtml.encode('utf-8'))
        if changed:
            # Add an encoding declaration (it will be added automatically when
            # serialized)
            root = container.parsed(name)
            for m in root.xpath('descendant::*[local-name()="meta" and @http-equiv]'):
                m.getparent().remove(m)
            container.dirty(name)

def rename_files(container, file_map):
    overlap = set(file_map).intersection(set(file_map.itervalues()))
    if overlap:
        raise ValueError('Circular rename detected. The files %s are both rename targets and destinations' % ', '.join(overlap))
    for name, dest in file_map.iteritems():
        if container.exists(dest):
            raise ValueError('Cannot rename {0} to {1} as {1} already exists'.format(name, dest))
    if len(tuple(file_map.itervalues())) != len(set(file_map.itervalues())):
        raise ValueError('Cannot rename, the set of destination files contains duplicates')
    link_map = {}
    for current_name, new_name in file_map.iteritems():
        container.rename(current_name, new_name)
        if new_name != container.opf_name:  # OPF is handled by the container
            link_map[current_name] = new_name
    replace_links(container, link_map, replace_in_opf=True)

