#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai


__license__   = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from calibre.customize.ui import output_profiles
from calibre.ebooks.conversion.config import load_defaults
from calibre.ebooks.oeb.base import XPath, OPF
from calibre.ebooks.oeb.polish.cover import find_cover_page
from calibre.ebooks.oeb.transforms.jacket import render_jacket as render, referenced_images


def render_jacket(container, jacket):
    mi = container.mi
    ps = load_defaults('page_setup')
    op = ps.get('output_profile', 'default')
    opmap = {x.short_name:x for x in output_profiles()}
    output_profile = opmap.get(op, opmap['default'])
    root = render(mi, output_profile)
    for img, path in referenced_images(root):
        container.log('Embedding referenced image: %s into jacket' % path)
        ext = path.rpartition('.')[-1]
        jacket_item = container.generate_item('jacket_image.'+ext, id_prefix='jacket_img')
        name = container.href_to_name(jacket_item.get('href'), container.opf_name)
        with open(path, 'rb') as f:
            container.parsed_cache[name] = f.read()
            container.commit_item(name)
        href = container.name_to_href(name, jacket)
        img.set('src', href)
    return root


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
    root = render_jacket(container, name)
    container.parsed_cache[name] = root
    container.dirty(name)


def remove_jacket(container):
    ' Remove an existing jacket, if any. Returns False if no existing jacket was found. '
    name = find_existing_jacket(container)
    if name is not None:
        remove_jacket_images(container, name)
        container.remove_item(name)
        return True
    return False


def remove_jacket_images(container, name):
    root = container.parsed_cache[name]
    for img in root.xpath('//*[local-name() = "img" and @src]'):
        iname = container.href_to_name(img.get('src'), name)
        if container.has_name(iname):
            container.remove_item(iname)


def add_or_replace_jacket(container):
    ''' Either create a new jacket from the book's metadata or replace an
    existing jacket. Returns True if an existing jacket was replaced. '''
    name = find_existing_jacket(container)
    found = True
    if name is None:
        jacket_item = container.generate_item('jacket.xhtml', id_prefix='jacket')
        name = container.href_to_name(jacket_item.get('href'), container.opf_name)
        found = False
    if found:
        remove_jacket_images(container, name)

    replace_jacket(container, name)
    if not found:
        # Insert new jacket into spine
        index = 0
        sp = container.abspath_to_name(next(container.spine_items))
        if sp == find_cover_page(container):
            index = 1
        itemref = container.opf.makeelement(OPF('itemref'),
                                            idref=jacket_item.get('id'))
        container.insert_into_xml(container.opf_xpath('//opf:spine')[0], itemref,
                              index=index)
    return found

