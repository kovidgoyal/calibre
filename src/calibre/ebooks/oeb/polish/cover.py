#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import shutil, re, os

from calibre.ebooks.oeb.base import OPF, OEB_DOCS, XPath, XLINK, xml2text
from calibre.ebooks.oeb.polish.replace import replace_links

def set_azw3_cover(container, cover_path, report):
    name = None
    found = True
    for gi in container.opf_xpath('//opf:guide/opf:reference[@href and contains(@type, "cover")]'):
        href = gi.get('href')
        name = container.href_to_name(href, container.opf_name)
        container.remove_from_xml(gi)
    if name is None or not container.has_name(name):
        item = container.generate_item(name='cover.jpeg', id_prefix='cover')
        name = container.href_to_name(item.get('href'), container.opf_name)
        found = False
    href = container.name_to_href(name, container.opf_name)
    guide = container.opf_xpath('//opf:guide')[0]
    container.insert_into_xml(guide, guide.makeelement(
        OPF('reference'), href=href, type='cover'))
    with open(cover_path, 'rb') as src, container.open(name, 'wb') as dest:
        shutil.copyfileobj(src, dest)
    container.dirty(container.opf_name)
    report('Cover updated' if found else 'Cover inserted')

def set_cover(container, cover_path, report):
    if container.book_type == 'azw3':
        set_azw3_cover(container, cover_path, report)
    else:
        set_epub_cover(container, cover_path, report)

###############################################################################
# The delightful EPUB cover processing

def is_raster_image(media_type):
    return media_type and media_type.lower() in {
        'image/png', 'image/jpeg', 'image/jpg', 'image/gif'}

COVER_TYPES = {            'coverimagestandard', 'other.ms-coverimage-standard',
            'other.ms-titleimage-standard', 'other.ms-titleimage',
            'other.ms-coverimage', 'other.ms-thumbimage-standard',
            'other.ms-thumbimage', 'thumbimagestandard', 'cover'}

def find_cover_image(container):
    'Find a raster image marked as a cover in the OPF'
    manifest_id_map = container.manifest_id_map
    mm = container.mime_map
    for meta in container.opf_xpath('//opf:meta[@name="cover" and @content]'):
        item_id = meta.get('content')
        name = manifest_id_map.get(item_id, None)
        media_type = mm.get(name, None)
        if is_raster_image(media_type):
            return name

    # First look for a guide item with type == 'cover'
    guide_type_map = container.guide_type_map
    for ref_type, name in guide_type_map.iteritems():
        if ref_type.lower() == 'cover' and is_raster_image(mm.get(name, None)):
            return name

    # Find the largest image from all possible guide cover items
    largest_cover = (None, 0)
    for ref_type, name in guide_type_map.iteritems():
        if ref_type.lower() in COVER_TYPES and is_raster_image(mm.get(name, None)):
            path = container.name_path_map.get(name, None)
            if path:
                sz = os.path.getsize(path)
                if sz > largest_cover[1]:
                    largest_cover = (name, sz)

    if largest_cover[0]:
        return largest_cover[0]

def find_cover_page(container):
    'Find a document marked as a cover in the OPF'
    mm = container.mime_map
    guide_type_map = container.guide_type_map
    for ref_type, name in guide_type_map.iteritems():
        if ref_type.lower() == 'cover' and mm.get(name, '').lower() in OEB_DOCS:
            return name

def find_cover_image_in_page(container, cover_page):
    root = container.parsed(cover_page)
    body = XPath('//h:body')(root)
    if len(body) != 1: return
    body = body[0]
    images = []
    for img in XPath('descendant::h:img[@src]|descendant::svg:svg/descendant::svg:image')(body):
        href = img.get('src') or img.get(XLINK('href'))
        if href:
            name = container.href_to_name(href, base=cover_page)
            images.append(name)
    text = re.sub(r'\s+', '', xml2text(body))
    if text or len(images) > 1:
        # Document has more content than a single image
        return
    if images:
        return images[0]

def clean_opf(container):
    'Remove all references to covers from the OPF'
    manifest_id_map = container.manifest_id_map
    for meta in container.opf_xpath('//opf:meta[@name="cover" and @content]'):
        name = manifest_id_map.get(meta.get('content', None), None)
        container.remove_from_xml(meta)
        if name and name in container.name_path_map:
            yield name

    gtm = container.guide_type_map
    for ref in container.opf_xpath('//opf:guide/opf:reference[@type]'):
        typ = ref.get('type', '')
        if typ.lower() in COVER_TYPES:
            container.remove_from_xml(ref)
            name = gtm.get(typ, None)
            if name and name in container.name_path_map:
                yield name

    container.dirty(container.opf_name)

def create_epub_cover(container, cover_path):
    from calibre.ebooks.conversion.config import load_defaults
    from calibre.ebooks.oeb.transforms.cover import CoverManager

    ext = cover_path.rpartition('.')[-1].lower()
    raster_cover_item = container.generate_item('cover.'+ext, id_prefix='cover')
    raster_cover = container.href_to_name(raster_cover_item.get('href'),
                                          container.opf_name)
    with open(cover_path, 'rb') as src, container.open(raster_cover, 'wb') as dest:
        shutil.copyfileobj(src, dest)
    opts = load_defaults('epub_output')
    keep_aspect = opts.get('preserve_cover_aspect_ratio', False)
    no_svg = opts.get('no_svg_cover', False)
    if no_svg:
        style = 'style="height: 100%%"'
        templ = CoverManager.NONSVG_TEMPLATE.replace('__style__', style)
    else:
        width, height = 600, 800
        ar = 'xMidYMid meet' if keep_aspect else 'none'
        templ = CoverManager.SVG_TEMPLATE.replace('__ar__', ar)
        templ = templ.replace('__viewbox__', '0 0 %d %d'%(width, height))
        templ = templ.replace('__width__',  str(width))
        templ = templ.replace('__height__', str(height))
    titlepage_item = container.generate_item('titlepage.xhtml',
                                             id_prefix='titlepage')
    titlepage = container.href_to_name(titlepage_item.get('href'),
                                          container.opf_name)
    raw = templ%container.name_to_href(raster_cover).encode('utf-8')
    with container.open(titlepage, 'wb') as f:
        f.write(raw)

    # We have to make sure the raster cover item has id="cover" for the moron
    # that wrote the Nook firmware
    if raster_cover_item.get('id') != 'cover':
        from calibre.ebooks.oeb.base import uuid_id
        newid = uuid_id()
        for item in container.opf_xpath('//*[@id="cover"]'):
            item.set('id', newid)
        for item in container.opf_xpath('//*[@idref="cover"]'):
            item.set('idref', newid)
        raster_cover_item.set('id', 'cover')

    spine = container.opf_xpath('//opf:spine')[0]
    ref = spine.makeelement(OPF('itemref'), idref=titlepage_item.get('id'))
    container.insert_into_xml(spine, ref, index=0)
    guide = container.opf_get_or_create('guide')
    container.insert_into_xml(guide, guide.makeelement(
        OPF('reference'), type='cover', title=_('Cover'),
        href=container.name_to_href(titlepage)))
    metadata = container.opf_get_or_create('metadata')
    meta = metadata.makeelement(OPF('meta'), name='cover')
    meta.set('content', raster_cover_item.get('id'))
    container.insert_into_xml(metadata, meta)

    return raster_cover, titlepage

def remove_cover_image_in_page(container, page, cover_images):
    for img in container.parsed(page).xpath('//*[local-name()="img" and @src]'):
        href = img.get('src')
        name = container.href_to_name(href, page)
        if name in cover_images:
            img.getparent.remove(img)
        break

def set_epub_cover(container, cover_path, report):
    cover_image = find_cover_image(container)
    cover_page = find_cover_page(container)
    wrapped_image = extra_cover_page = None
    updated = False
    log = container.log

    possible_removals = set(clean_opf(container))
    possible_removals
    # TODO: Handle possible_removals and also iterate over links in the removed
    # pages and handle possibly removing stylesheets referred to by them.

    spine_items = tuple(container.spine_items)
    if cover_page is None:
        # Check if the first item in the spine is a simple cover wrapper
        candidate = container.abspath_to_name(spine_items[0])
        if find_cover_image_in_page(container, candidate) is not None:
            cover_page = candidate

    if cover_page is not None:
        log('Found existing cover page')
        wrapped_image = find_cover_image_in_page(container, cover_page)

        if len(spine_items) > 1:
            # Look for an extra cover page
            c = container.abspath_to_name(spine_items[1])
            if c != cover_page:
                candidate = find_cover_image_in_page(container, c)
                if candidate and candidate in {wrapped_image, cover_image}:
                    log('Found an extra cover page that is a simple wrapper, removing it')
                    # This page has only a single image and that image is the
                    # cover image, remove it.
                    container.remove_item(c)
                    extra_cover_page = c
                    spine_items = spine_items[:1] + spine_items[2:]
                elif candidate is None:
                    # Remove the cover image if it is the first image in this
                    # page
                    remove_cover_image_in_page(container, c, {wrapped_image,
                                                          cover_image})

        if wrapped_image is not None:
            # The cover page is a simple wrapper around a single cover image,
            # we can remove it safely.
            log('Existing cover page is a simple wrapper, removing it')
            container.remove_item(cover_page)
            container.remove_item(wrapped_image)
            updated = True

    if cover_image and cover_image != wrapped_image:
        # Remove the old cover image
        container.remove_item(cover_image)

    # Insert the new cover
    raster_cover, titlepage = create_epub_cover(container, cover_path)

    report('Cover updated' if updated else 'Cover inserted')

    # Replace links to the old cover image/cover page
    link_sub = {s:d for s, d in {
        cover_page:titlepage, wrapped_image:raster_cover,
        cover_image:raster_cover, extra_cover_page:titlepage}.iteritems()
        if s is not None}
    if link_sub:
        replace_links(container, link_sub, frag_map=lambda x, y:None)


