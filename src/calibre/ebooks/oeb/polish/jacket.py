#!/usr/bin/env python
# License: GPLv3 Copyright: 2013, Kovid Goyal <kovid at kovidgoyal.net>

from typing import TYPE_CHECKING, cast

from calibre.customize.ui import output_profiles
from calibre.ebooks.conversion.config import load_defaults
from calibre.ebooks.oeb.base import OPF, XPath
from calibre.ebooks.oeb.polish.cover import find_cover_page
from calibre.ebooks.oeb.transforms.jacket import referenced_images
from calibre.ebooks.oeb.transforms.jacket import render_jacket as render

if TYPE_CHECKING:
    from lxml.etree import _Element

    from calibre.ebooks.oeb.polish.container import Container


def render_jacket(container: Container, jacket: str) -> _Element:
    mi = container.mi
    ps = load_defaults('page_setup')
    op = ps.get('output_profile', 'default')
    opmap = {x.short_name: x for x in output_profiles()}
    output_profile = opmap.get(op, opmap['default'])
    root = render(mi, output_profile)
    for img, path in referenced_images(root):
        container.log(f'Embedding referenced image: {path} into jacket')
        ext = path.rpartition('.')[-1]
        jacket_item = container.generate_item('jacket_image.' + ext, id_prefix='jacket_img')
        name = cast('str', container.href_to_name(jacket_item.get('href'), container.opf_name))  # generated items always have a href
        with open(path, 'rb') as f:
            container.parsed_cache[name] = f.read()
            container.commit_item(name)
        href = container.name_to_href(name, jacket)
        img.set('src', href)
    return root


def is_legacy_jacket(root: _Element) -> bool:
    return len(root.xpath('//*[starts-with(@class,"calibrerescale") and (local-name()="h1" or local-name()="h2")]')) > 0


def is_current_jacket(root: _Element) -> bool:
    return len(XPath('//h:meta[@name="calibre-content" and @content="jacket"]')(root)) > 0


def find_existing_jacket(container: Container) -> str | None:
    for item in container.spine_items:
        name = container.abspath_to_name(item)
        if container.book_type == 'azw3':
            root = cast('_Element', container.parsed(name))  # spine items are HTML, parsed into lxml trees
            if is_current_jacket(root):
                return name
        elif name.rpartition('/')[-1].startswith('jacket') and name.endswith('.xhtml'):
            root = cast('_Element', container.parsed(name))  # spine items are HTML, parsed into lxml trees
            if is_current_jacket(root) or is_legacy_jacket(root):
                return name


def replace_jacket(container: Container, name: str) -> None:
    root = render_jacket(container, name)
    container.parsed_cache[name] = root
    container.dirty(name)


def remove_jacket(container: Container) -> bool:
    "Remove an existing jacket, if any. Returns False if no existing jacket was found."
    name = find_existing_jacket(container)
    if name is not None:
        remove_jacket_images(container, name)
        container.remove_item(name)
        return True
    return False


def remove_jacket_images(container: Container, name: str) -> None:
    root = cast('_Element', container.parsed_cache[name])  # the jacket was parsed by find_existing_jacket()
    for img in root.xpath('//*[local-name() = "img" and @src]'):
        iname = container.href_to_name(img.get('src'), name)
        if container.has_name(iname):
            container.remove_item(iname)


def add_or_replace_jacket(container: Container) -> bool:
    """Either create a new jacket from the book's metadata or replace an
    existing jacket. Returns True if an existing jacket was replaced."""
    name = find_existing_jacket(container)
    found = True
    if name is None:
        jacket_item = container.generate_item('jacket.xhtml', id_prefix='jacket')
        name = cast('str', container.href_to_name(jacket_item.get('href'), container.opf_name))  # generated items always have a href
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
        itemref = container.opf.makeelement(OPF('itemref'), idref=cast('str', jacket_item.get('id')))  # generated items always have an id
        container.insert_into_xml(container.opf_xpath('//opf:spine')[0], itemref, index=index)
    return found
