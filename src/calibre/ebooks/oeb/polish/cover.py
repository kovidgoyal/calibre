# License: GPLv3 Copyright: 2013, Kovid Goyal <kovid at kovidgoyal.net>

import os
import re
import shutil
from collections.abc import Callable
from typing import IO, TYPE_CHECKING, Literal, TypedDict, cast

from lxml import etree

from calibre.ebooks.oeb.base import OEB_DOCS, OPF, XLINK, XML, XPath, xml2text
from calibre.ebooks.oeb.polish.replace import get_recommended_folders, replace_links
from calibre.utils.imghdr import identify
from calibre.utils.localization import _

if TYPE_CHECKING:
    from collections.abc import Collection, Iterator

    from lxml.etree import _Element

    from calibre.ebooks.oeb.polish.container import Container


class CoverOptions(TypedDict, total=False):
    """The options accepted by :func:`set_cover`"""

    existing_image: bool
    keep_aspect: bool
    no_svg: bool
    template: str


#: A callable used to report progress messages
type Reporter = Callable[[str], object]
#: Either the path to a cover image or a callable that is called with ('write_image', output_stream) to write the image
type CoverSource = str | Callable[[str, IO[bytes]], object]


def set_azw3_cover(container: Container, cover_path: str, report: Reporter, options: CoverOptions | None = None) -> None:
    existing_image = options is not None and options.get('existing_image', False)
    name: str | None = None
    found = True
    for gi in container.opf_xpath('//opf:guide/opf:reference[@href and contains(@type, "cover")]'):
        href = gi.get('href')
        name = container.href_to_name(href, container.opf_name)
        container.remove_from_xml(gi)
    if existing_image:
        name = cover_path
        found = False
    elif name is None or not container.has_name(name):
        item = container.generate_item(name='cover.jpeg', id_prefix='cover')
        # the href of a generated item always maps back to a name
        name = cast('str', container.href_to_name(item.get('href'), container.opf_name))
        found = False
    href = container.name_to_href(name, container.opf_name)
    guide = container.opf_xpath('//opf:guide')[0]
    container.insert_into_xml(guide, guide.makeelement(OPF('reference'), href=href, type='cover'))
    if not existing_image:
        with open(cover_path, 'rb') as src, container.open(name, 'wb') as dest:
            shutil.copyfileobj(src, dest)
    container.dirty(container.opf_name)
    report(_('Cover updated') if found else _('Cover inserted'))


def get_azw3_raster_cover_name(container: Container) -> str | None:
    items = container.opf_xpath('//opf:guide/opf:reference[@href and contains(@type, "cover")]')
    if items:
        return container.href_to_name(items[0].get('href'))


def mark_as_cover_azw3(container: Container, name: str) -> None:
    href = container.name_to_href(name, container.opf_name)
    found = False
    for item in container.opf_xpath('//opf:guide/opf:reference[@href and contains(@type, "cover")]'):
        item.set('href', href)
        found = True
    if not found:
        for guide in container.opf_xpath('//opf:guide'):
            container.insert_into_xml(guide, guide.makeelement(OPF('reference'), href=href, type='cover'))
    container.dirty(container.opf_name)


def get_raster_cover_name(container: Container) -> str | None:
    if container.book_type == 'azw3':
        return get_azw3_raster_cover_name(container)
    return find_cover_image(container, strict=True)


def get_cover_page_name(container: Container) -> str | None:
    if container.book_type == 'azw3':
        return
    return find_cover_page(container)


def set_cover(container: Container, cover_path: str, report: Reporter | None = None, options: CoverOptions | None = None) -> None:
    """
    Set the cover of the book to the image pointed to by cover_path.

    :param cover_path: Either the absolute path to an image file or the
        canonical name of an image in the book. When using an image in the book,
        you must also set options, see below.
    :param report: An optional callable that takes a single argument. It will
        be called with information about the tasks being processed.
    :param options: None or a dictionary that controls how the cover is set. The dictionary can have entries:
        **keep_aspect**: True or False  (Preserve aspect ratio of covers in EPUB)
        **no_svg**: True or False  (Use an SVG cover wrapper in the EPUB titlepage)
        **existing**: True or False  (``cover_path`` refers to an existing image in the book)
    """
    report = report or (lambda x: x)
    if container.book_type == 'azw3':
        set_azw3_cover(container, cover_path, report, options=options)
    else:
        set_epub_cover(container, cover_path, report, options=options)


def mark_as_cover(container: Container, name: str) -> None:
    """
    Mark the specified image as the cover image.
    """
    if name not in container.mime_map:
        raise ValueError(f'Cannot mark {name} as cover as it does not exist')
    mt = container.mime_map[name]
    if not is_raster_image(mt):
        raise ValueError(f'Cannot mark {name} as the cover image as it is not a raster image')
    if container.book_type == 'azw3':
        mark_as_cover_azw3(container, name)
    else:
        mark_as_cover_epub(container, name)


###############################################################################
# The delightful EPUB cover processing


def is_raster_image(media_type: str | None) -> bool | str | None:
    return media_type and media_type.lower() in {'image/png', 'image/jpeg', 'image/jpg', 'image/gif'}


COVER_TYPES = {
    'coverimagestandard',
    'other.ms-coverimage-standard',
    'other.ms-titleimage-standard',
    'other.ms-titleimage',
    'other.ms-coverimage',
    'other.ms-thumbimage-standard',
    'other.ms-thumbimage',
    'thumbimagestandard',
    'cover',
}


def find_cover_image2(container: Container, strict: bool = False) -> str | None:
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
    for ref_type, name in guide_type_map.items():
        if ref_type.lower() == 'cover' and is_raster_image(mm.get(name, None)):
            return name

    if strict:
        return

    # Find the largest image from all possible guide cover items
    largest_cover: tuple[str | None, int] = (None, 0)
    for ref_type, name in guide_type_map.items():
        if ref_type.lower() in COVER_TYPES and is_raster_image(mm.get(name, None)):
            path = container.name_path_map.get(name, None)
            if path:
                sz = os.path.getsize(path)
                if sz > largest_cover[1]:
                    largest_cover = (name, sz)

    if largest_cover[0]:
        return largest_cover[0]


def find_cover_image3(container: Container) -> str | None:
    for name in container.manifest_items_with_property('cover-image'):
        return name
    manifest_id_map = container.manifest_id_map
    mm = container.mime_map
    for meta in container.opf_xpath('//opf:meta[@name="cover" and @content]'):
        item_id = meta.get('content')
        name = manifest_id_map.get(item_id, None)
        media_type = mm.get(name, None)
        if is_raster_image(media_type):
            return name


def find_cover_image(container: Container, strict: bool = False) -> str | None:
    "Find a raster image marked as a cover in the OPF"
    ver = container.opf_version_parsed
    if ver.major < 3:
        return find_cover_image2(container, strict=strict)
    else:
        return find_cover_image3(container)


def get_guides(container: Container) -> list[_Element]:
    guides = container.opf_xpath('//opf:guide')
    if not guides:
        container.insert_into_xml(container.opf, container.opf.makeelement(OPF('guide')))
        guides = container.opf_xpath('//opf:guide')
    return guides


def mark_as_cover_epub(container: Container, name: str) -> None:
    mmap = {v: k for k, v in container.manifest_id_map.items()}
    if name not in mmap:
        raise ValueError(f'Cannot mark {name} as cover as it is not in manifest')
    mid = mmap[name]
    ver = container.opf_version_parsed

    # Remove all entries from the opf that identify a raster image as cover
    for meta in container.opf_xpath('//opf:meta[@name="cover" and @content]'):
        container.remove_from_xml(meta)
    for ref in container.opf_xpath('//opf:guide/opf:reference[@href and @type]'):
        rtype = ref.get('type')
        assert rtype is not None  # guaranteed by the XPath expression
        if rtype.lower() not in COVER_TYPES:
            continue
        rname = container.href_to_name(ref.get('href'), container.opf_name)
        mt = container.mime_map.get(rname, None)
        if is_raster_image(mt):
            container.remove_from_xml(ref)

    if ver.major < 3:
        # Add reference to image in <metadata>
        for metadata in container.opf_xpath('//opf:metadata'):
            m = metadata.makeelement(OPF('meta'), name='cover', content=mid)
            container.insert_into_xml(metadata, m)

        # If no entry for cover exists in guide, insert one that points to this
        # image
        if not container.opf_xpath('//opf:guide/opf:reference[@type="cover"]'):
            for guide in get_guides(container):
                container.insert_into_xml(
                    guide,
                    guide.makeelement(OPF('reference'), type='cover', href=container.name_to_href(name, container.opf_name)),
                )
    else:
        container.apply_unique_properties(name, 'cover-image')

    container.dirty(container.opf_name)


def mark_as_titlepage(container: Container, name: str, move_to_start: bool = True) -> None:
    """
    Mark the specified HTML file as the titlepage of the EPUB.

    :param move_to_start: If True the HTML file is moved to the start of the spine
    """
    ver = container.opf_version_parsed
    if move_to_start:
        for item, q, linear in container.spine_iter:
            if name == q:
                if not linear:
                    item.set('linear', 'yes')
                spine = cast('_Element', item.getparent())  # spine items always have a parent
                if spine.index(item) > 0:
                    container.insert_into_xml(spine, item, 0)
                break
    if ver.major < 3:
        for ref in container.opf_xpath('//opf:guide/opf:reference[@type="cover"]'):
            cast('_Element', ref.getparent()).remove(ref)  # guide references always have a parent

        for guide in get_guides(container):
            container.insert_into_xml(
                guide,
                guide.makeelement(OPF('reference'), type='cover', href=container.name_to_href(name, container.opf_name)),
            )
    else:
        container.apply_unique_properties(name, 'calibre:title-page')

    container.dirty(container.opf_name)


def find_cover_page(container: Container) -> str | None:
    "Find a document marked as a cover in the OPF"
    ver = container.opf_version_parsed
    mm = container.mime_map
    if ver.major < 3:
        guide_type_map = container.guide_type_map
        for ref_type, name in guide_type_map.items():
            if ref_type.lower() == 'cover' and mm.get(name, '').lower() in OEB_DOCS:
                return name
    else:
        for name in container.manifest_items_with_property('calibre:title-page'):
            return name
        from calibre.ebooks.oeb.polish.toc import get_landmarks

        for landmark in get_landmarks(container):
            if landmark['type'] == 'cover' and mm.get(landmark['dest'], '').lower() in OEB_DOCS:
                return landmark['dest']


def fix_conversion_titlepage_links_in_nav(container: Container) -> None:
    from calibre.ebooks.oeb.polish.toc import find_existing_nav_toc

    cover_page_name = find_cover_page(container)
    if not cover_page_name:
        return
    nav_page_name = find_existing_nav_toc(container)
    if not nav_page_name:
        return
    root = container.parsed(nav_page_name)
    assert isinstance(root, etree._Element)
    for elem in root.xpath('//*[@data-calibre-removed-titlepage]'):
        elem.attrib.pop('data-calibre-removed-titlepage')
        elem.set('href', container.name_to_href(cover_page_name, nav_page_name))
    container.dirty(nav_page_name)


def find_cover_image_in_page(container: Container, cover_page: str) -> str | None:
    root = container.parsed(cover_page)
    assert isinstance(root, etree._Element)
    body = XPath('//h:body')(root)
    if len(body) != 1:
        return
    body = body[0]
    images: list[str | None] = []
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


def clean_opf(container: Container) -> Iterator[str | None]:
    "Remove all references to covers from the OPF"
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
    ver = container.opf_version_parsed
    if ver.major > 2:
        removed_names = container.apply_unique_properties(None, 'cover-image', 'calibre:title-page')[0]
        for name in removed_names:
            yield name
    container.dirty(container.opf_name)


def create_epub_cover(
    container: Container, cover_path: CoverSource, existing_image: str | Literal[False], options: CoverOptions | None = None
) -> tuple[str, str]:
    from calibre.ebooks.conversion.config import load_defaults
    from calibre.ebooks.oeb.polish.opf import get_book_language_tag
    from calibre.ebooks.oeb.transforms.cover import CoverManager

    try:
        ext = cover_path.rpartition('.')[-1].lower()  # ty: ignore[unresolved-attribute] callables are handled by the except clause
    except Exception:
        ext = 'jpeg'
    cname, tname = 'cover.' + ext, 'titlepage.xhtml'
    recommended_folders = get_recommended_folders(container, (cname, tname))

    if existing_image:
        raster_cover = existing_image
        manifest_id = {v: k for k, v in container.manifest_id_map.items()}.get(existing_image)
        if manifest_id is None:
            # the image is in the book but not in the manifest
            manifest_id = container.add_name_to_manifest(existing_image, suggested_id='cover')
        raster_cover_item = container.opf_xpath(f'//opf:manifest/*[@id="{manifest_id}"]')[0]
    else:
        folder = recommended_folders[cname]
        if folder:
            cname = folder + '/' + cname
        raster_cover_item = container.generate_item(cname, id_prefix='cover')
        # the href of a generated item always maps back to a name
        raster_cover = cast('str', container.href_to_name(raster_cover_item.get('href'), container.opf_name))

        with container.open(raster_cover, 'wb') as dest:
            if callable(cover_path):
                cover_path('write_image', dest)
            else:
                with open(cover_path, 'rb') as src:
                    shutil.copyfileobj(src, dest)
    if options is None:
        opts = load_defaults('epub_output')
        keep_aspect = opts.get('preserve_cover_aspect_ratio', False)
        no_svg = opts.get('no_svg_cover', False)
    else:
        keep_aspect = options.get('keep_aspect', False)
        no_svg = options.get('no_svg', False)
    if no_svg:
        style = 'style="height: 100%%"'
        templ = CoverManager.NONSVG_TEMPLATE.replace('__style__', style)
        has_svg = False
    elif callable(cover_path):
        templ = (options or {}).get('template', CoverManager.SVG_TEMPLATE)
        has_svg = 'xlink:href' in templ
    else:
        width, height = 600, 800
        has_svg = True
        try:
            if existing_image:
                width, height = identify(container.raw_data(existing_image, decode=False))[1:]
            else:
                with open(cover_path, 'rb') as csrc:
                    width, height = identify(csrc)[1:]
        except Exception:
            container.log.exception('Failed to get width and height of cover')
        ar = 'xMidYMid meet' if keep_aspect else 'none'
        templ = CoverManager.SVG_TEMPLATE.replace('__ar__', ar)
        templ = templ.replace('__viewbox__', f'0 0 {width} {height}')
        templ = templ.replace('__width__', str(width))
        templ = templ.replace('__height__', str(height))
    templ = CoverManager.fill_metadata(templ, container.mi.title or '', get_book_language_tag(container))
    folder = recommended_folders[tname]
    if folder:
        tname = folder + '/' + tname
    titlepage_item = container.generate_item(tname, id_prefix='titlepage')
    # the href of a generated item always maps back to a name
    titlepage = cast('str', container.href_to_name(titlepage_item.get('href'), container.opf_name))
    raw = templ % container.name_to_href(raster_cover, titlepage)
    with container.open(titlepage, 'wb') as f:
        if not isinstance(raw, bytes):
            raw = raw.encode('utf-8')
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
    ref = spine.makeelement(OPF('itemref'), idref=cast('str', titlepage_item.get('id')))  # generated items always have an id
    container.insert_into_xml(spine, ref, index=0)
    ver = container.opf_version_parsed
    if ver.major < 3:
        guide = container.opf_get_or_create('guide')
        container.insert_into_xml(
            guide,
            guide.makeelement(
                OPF('reference'),
                type='cover',
                title=_('Cover'),
                href=container.name_to_href(titlepage, base=container.opf_name),
            ),
        )
        metadata = container.opf_get_or_create('metadata')
        meta = metadata.makeelement(OPF('meta'), name='cover')
        meta.set('content', cast('str', raster_cover_item.get('id')))  # the id was set to cover above
        container.insert_into_xml(metadata, meta)
    else:
        container.apply_unique_properties(raster_cover, 'cover-image')
        container.apply_unique_properties(titlepage, 'calibre:title-page')
        if has_svg:
            container.add_properties(titlepage, 'svg')
        # The template only has xml:lang as lang is not valid in EPUB 2
        root = container.parsed(titlepage)
        assert isinstance(root, etree._Element)
        if (lang := root.get(XML('lang'))) and not root.get('lang'):
            root.set('lang', lang)
            container.dirty(titlepage)

    return raster_cover, titlepage


def remove_cover_image_in_page(container: Container, page: str, cover_images: Collection[str | None]) -> None:
    root = container.parsed(page)
    assert isinstance(root, etree._Element)
    for img in root.xpath('//*[local-name()="img" and @src]'):
        href = img.get('src')
        name = container.href_to_name(href, page)
        if name in cover_images:
            img.getparent().remove(img)
        break


def has_epub_cover(container: Container) -> bool:
    if find_cover_image(container):
        return True
    if find_cover_page(container):
        return True
    spine_items = tuple(container.spine_items)
    if spine_items:
        candidate = container.abspath_to_name(spine_items[0])
        if find_cover_image_in_page(container, candidate) is not None:
            return True
    return False


def set_epub_cover(
    container: Container,
    cover_path: CoverSource,
    report: Reporter,
    options: CoverOptions | None = None,
    image_callback: Callable[[str | None, str | None], object] | None = None,
) -> tuple[str, str]:
    existing_image: str | Literal[False] = False
    if options is not None and options.get('existing_image', False):
        # cover_path is the name of an image in the book when existing_image is set
        existing_image = cast('str', cover_path)
    cover_image = find_cover_image(container)
    cover_page = find_cover_page(container)
    wrapped_image: str | None = None
    extra_cover_page: str | None = None
    updated = False
    log = container.log

    possible_removals = set(clean_opf(container))  # ruff: ignore[unused-variable]
    # TODO: Handle possible_removals and also iterate over links in the removed
    # pages and handle possibly removing stylesheets referred to by them.

    image_callback_called = False
    spine_items = tuple(container.spine_items)
    if cover_page is None and spine_items:
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
                    remove_cover_image_in_page(container, c, {wrapped_image, cover_image})

        if wrapped_image is not None:
            # The cover page is a simple wrapper around a single cover image,
            # we can remove it safely.
            log(f'Existing cover page {cover_page} is a simple wrapper, removing it')
            container.remove_item(cover_page)
            if wrapped_image != existing_image:
                if image_callback is not None and not image_callback_called:
                    image_callback(cover_image, wrapped_image)
                    image_callback_called = True
                container.remove_item(wrapped_image)
            updated = True

    if image_callback is not None and not image_callback_called:
        image_callback_called = True
        image_callback(cover_image, wrapped_image)
    if cover_image and cover_image != wrapped_image:
        # Remove the old cover image
        if cover_image != existing_image:
            container.remove_item(cover_image)

    # Insert the new cover
    raster_cover, titlepage = create_epub_cover(container, cover_path, existing_image, options=options)

    report(_('Cover updated') if updated else _('Cover inserted'))

    # Replace links to the old cover image/cover page
    link_sub = {
        s: d
        for s, d in {
            cover_page: titlepage,
            wrapped_image: raster_cover,
            cover_image: raster_cover,
            extra_cover_page: titlepage,
        }.items()
        if s is not None and s != d
    }
    if link_sub:
        replace_links(container, link_sub, frag_map=lambda x, y: None)
    return raster_cover, titlepage
