#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from calibre.customize.ui import output_profiles
from calibre.ebooks.conversion.config import load_defaults
from calibre.ebooks.oeb.base import XPath, OPF
from calibre.ebooks.oeb.polish.cover import find_cover_page
from calibre.ebooks.oeb.transforms.jacket import render_jacket as render

def render_jacket(mi):
    ps = load_defaults('page_setup')
    op = ps.get('output_profile', 'default')
    opmap = {x.short_name:x for x in output_profiles()}
    output_profile = opmap.get(op, opmap['default'])
    return render(mi, output_profile)

def is_legacy_jacket(root):
    return len(root.xpath(
        '//*[starts-with(@class,"calibrerescale") and (local-name()="h1" or local-name()="h2")]')) > 0

def is_current_jacket(root):
    return len(XPath(
        '//h:meta[@name="calibre-content" and @content="jacket"]')(root)) > 0

def find_existing_jacket(container):
    for item in container.spine_items:
        name = container.abspath_to_name(item)
        if container.book_type == 'azw3':
            root = container.parsed(name)
            if is_current_jacket(root):
                return name
        else:
            if name.rpartition('/')[-1].startswith('jacket') and name.endswith('.xhtml'):
                root = container.parsed(name)
                if is_current_jacket(root) or is_legacy_jacket(root):
                    return name

def replace_jacket(container, name):
    root = render_jacket(container.mi)
    container.parsed_cache[name] = root
    container.dirty(name)

def remove_jacket(container):
    name = find_existing_jacket(container)
    if name is not None:
        container.remove_item(name)
        return True
    return False

def add_or_replace_jacket(container):
    name = find_existing_jacket(container)
    found = True
    if name is None:
        jacket_item = container.generate_item('jacket.xhtml', id_prefix='jacket')
        name = container.href_to_name(jacket_item.get('href'), container.opf_name)
        found = False
    replace_jacket(container, name)
    if not found:
        # Insert new jacket into spine
        index = 0
        sp = container.abspath_to_name(container.spine_items.next())
        if sp == find_cover_page(container):
            index = 1
        itemref = container.opf.makeelement(OPF('itemref'),
                                            idref=jacket_item.get('id'))
        container.insert_into_xml(container.opf_xpath('//opf:spine')[0], itemref,
                              index=index)
    return found

