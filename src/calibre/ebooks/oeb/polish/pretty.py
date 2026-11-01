#!/usr/bin/env python
# License: GPLv3 Copyright: 2013, Kovid Goyal <kovid at kovidgoyal.net>

import textwrap
from typing import TYPE_CHECKING, cast

from lxml import etree

# from lxml.etree import Element
from calibre import force_unicode
from calibre.ebooks.oeb.base import OEB_DOCS, OEB_STYLES, SVG, XHTML, XPNSMAP, barename, serialize
from calibre.ebooks.oeb.polish.container import OPF_NAMESPACES
from calibre.ebooks.oeb.polish.utils import guess_type
from calibre.utils.icu import sort_key

if TYPE_CHECKING:
    from lxml.etree import _Element

    from calibre.ebooks.oeb.polish.container import Container


def isspace(x: str) -> bool:
    return not x.strip('\u0009\u000a\u000c\u000d\u0020')


def pretty_xml_tree(elem: _Element, level: int = 0, indent: str = '  ') -> None:
    """XML beautifier, assumes that elements that have children do not have
    textual content.  Also assumes that there is no text immediately after
    closing tags. These are true for opf/ncx and container.xml files. If either
    of the assumptions are violated, there should be no data loss, but pretty
    printing won't produce optimal results."""
    if (not elem.text and len(elem) > 0) or (elem.text and isspace(elem.text)):
        elem.text = '\n' + (indent * (level + 1))
    for i, child in enumerate(elem):
        pretty_xml_tree(child, level=level + 1, indent=indent)
        if not child.tail or isspace(child.tail):
            l = level + 1
            if i == len(elem) - 1:
                l -= 1
            child.tail = '\n' + (indent * l)


def pretty_opf(root: _Element) -> None:
    # Put all dc: tags first starting with title and author. Preserve order for
    # the rest.
    def dckey(x: _Element) -> int:
        tag = x.tag
        assert isinstance(tag, str)  # dc: elements always have str tags
        return {'title': 0, 'creator': 1}.get(barename(tag), 2)

    for metadata in root.xpath('//opf:metadata', namespaces=OPF_NAMESPACES):
        dc_tags = metadata.xpath('./*[namespace-uri()="{}"]'.format(OPF_NAMESPACES['dc']))
        dc_tags.sort(key=dckey)
        for x in reversed(dc_tags):
            metadata.insert(0, x)

    # Group items in the manifest
    spine_ids = root.xpath('//opf:spine/opf:itemref/@idref', namespaces=OPF_NAMESPACES)
    spine_ids = {x: i for i, x in enumerate(spine_ids)}

    def manifest_key(x: _Element) -> tuple[int, int | bytes]:
        mt = x.get('media-type', '')
        href = x.get('href', '')
        ext = href.rpartition('.')[-1].lower()
        cat = 1000
        if mt in OEB_DOCS:
            cat = 0
        elif mt == guess_type('a.ncx'):
            cat = 1
        elif mt in OEB_STYLES:
            cat = 2
        elif mt.startswith('image/'):
            cat = 3
        elif ext in {'otf', 'ttf', 'woff', 'woff2'}:
            cat = 4
        elif mt.startswith('audio/'):
            cat = 5
        elif mt.startswith('video/'):
            cat = 6

        if cat == 0:
            i = spine_ids.get(x.get('id', None), 1000000000)
        else:
            i = sort_key(href)
        return cat, i

    for manifest in root.xpath('//opf:manifest', namespaces=OPF_NAMESPACES):
        try:
            children = sorted(manifest, key=manifest_key)
        except AttributeError:
            continue  # There are comments so don't sort since that would mess up the comments
        for x in reversed(children):
            manifest.insert(0, x)


SVG_TAG = SVG('svg')
NON_NAMESPACED_BLOCK_TAGS = (
    'address',
    'article',
    'aside',
    'audio',
    'blockquote',
    'body',
    'canvas',
    'col',
    'colgroup',
    'dd',
    'div',
    'dl',
    'dt',
    'fieldset',
    'figcaption',
    'figure',
    'footer',
    'form',
    'h1',
    'h2',
    'h3',
    'h4',
    'h5',
    'h6',
    'header',
    'hgroup',
    'hr',
    'li',
    'svg',
    'noscript',
    'ol',
    'output',
    'p',
    'pre',
    'script',
    'section',
    'style',
    'table',
    'tbody',
    'td',
    'tfoot',
    'th',
    'thead',
    'tr',
    'ul',
    'video',
    'img',
)
BLOCK_TAGS = frozenset(map(XHTML, NON_NAMESPACED_BLOCK_TAGS))


def isblock(x: _Element) -> bool:
    if callable(x.tag) or not x.tag:
        return True
    return x.tag in BLOCK_TAGS


def has_only_blocks(x: _Element) -> bool:
    if hasattr(x.tag, 'split') and len(x) == 0:
        # Tag with no children,
        return False
    if x.text and not isspace(x.text):
        return False
    # ruff: ignore[reimplemented-builtin]
    for child in x:
        if not isblock(child) or (child.tail and not isspace(child.tail)):
            return False
    return True


def indent_for_tag(x: _Element) -> str:
    prev = x.getprevious()
    # x is a <script> or <style> tag inside an HTML document, so it has a parent
    text = cast('_Element', x.getparent()).text if prev is None else prev.tail
    if not text:
        return ''
    s = text.rpartition('\n')[-1]
    return s if isspace(s) else ''


def set_indent(elem: _Element, attr: str, indent: str) -> None:
    x = getattr(elem, attr)
    if not x:
        x = indent
    else:
        lines = x.splitlines()
        if isspace(lines[-1]):
            lines[-1] = indent
        else:
            lines.append(indent)
        x = '\n'.join(lines)
    setattr(elem, attr, x)


def pretty_block(parent: _Element, level: int = 1, indent: str = '  ') -> None:
    """Surround block tags with blank lines and recurse into child block tags
    that contain only other block tags"""
    if not parent.text or isspace(parent.text):
        parent.text = ''
    ptag = parent.tag
    nn = '\n' if isinstance(ptag, str) and barename(ptag) in {'tr', 'td', 'th'} else '\n\n'
    parent.text = (parent.text or '') + nn + (indent * level)
    for i, child in enumerate(parent):
        if isblock(child) and has_only_blocks(child):
            pretty_block(child, level=level + 1, indent=indent)
        elif child.tag == SVG_TAG:
            pretty_xml_tree(child, level=level, indent=indent)
        l = level
        if i == len(parent) - 1:
            l -= 1
        if not child.tail or isspace(child.tail):
            child.tail = ''
        child.tail = (child.tail or '') + nn + (indent * l)


def pretty_script_or_style(container: Container, child: _Element) -> None:
    if text := child.text:
        indent = indent_for_tag(child)
        tag = child.tag
        assert isinstance(tag, str)  # child is a <script> or <style> element
        if tag.endswith('style'):
            text = force_unicode(pretty_css(container, '', text), 'utf-8')
        text = textwrap.dedent(text)
        child.text = '\n' + '\n'.join([(indent + x) if x else '' for x in text.splitlines()])
        set_indent(child, 'text', indent)


def pretty_html_tree(container: Container | None, root: _Element) -> None:
    root.text = '\n\n'
    for child in root:
        child.tail = '\n\n'
        if isinstance(ctag := child.tag, str) and ctag.endswith('}head'):
            pretty_xml_tree(child)
    for body in root.findall('h:body', namespaces=XPNSMAP):
        pretty_block(body)
        # Special case the handling of a body that contains a single block tag
        # with all content. In this case we prettify the containing block tag
        # even if it has non block children.
        if (
            len(body) == 1
            and isinstance(first_tag := body[0].tag, str)
            and isblock(body[0])
            and not has_only_blocks(body[0])
            and barename(first_tag) not in ('pre', 'p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6')
            and len(body[0]) > 0
        ):
            pretty_block(body[0], level=2)

    if container is not None:
        # Handle <script> and <style> tags
        for child in root.xpath('//*[local-name()="script" or local-name()="style"]'):
            pretty_script_or_style(container, child)


def fix_html(container: Container, raw: str) -> bytes:
    "Fix any parsing errors in the HTML represented as a string in raw. Fixing is done using the HTML5 parsing algorithm."
    root = container.parse_xhtml(raw)
    return serialize(root, 'text/html')


def pretty_html(container: Container, name: str, raw: str) -> bytes:
    "Pretty print the HTML represented as a string in raw"
    root = container.parse_xhtml(raw)
    pretty_html_tree(container, root)
    return serialize(root, 'text/html')


def pretty_css(container: Container, name: str, raw: str) -> bytes:
    "Pretty print the CSS represented as a string in raw"
    sheet = container.parse_css(raw)
    return serialize(sheet, 'text/css')


def pretty_xml(container: Container, name: str, raw: str) -> bytes:
    "Pretty print the XML represented as a string in raw. If ``name`` is the name of the OPF, extra OPF-specific prettying is performed."
    root = container.parse_xml(raw)
    if name == container.opf_name:
        pretty_opf(root)
    pretty_xml_tree(root)
    return serialize(root, 'text/xml')


def fix_all_html(container: Container) -> None:
    "Fix any parsing errors in all HTML files in the container. Fixing is done using the HTML5 parsing algorithm."
    for name, mt in container.mime_map.items():
        if mt in OEB_DOCS:
            container.parsed(name)
            container.dirty(name)


def pretty_all(container: Container) -> None:
    "Pretty print all HTML/CSS/XML files in the container"
    xml_types = {guess_type('a.ncx'), guess_type('a.xml'), guess_type('a.svg')}
    for name, mt in container.mime_map.items():
        prettied = False
        if mt in OEB_DOCS:
            root = container.parsed(name)
            assert isinstance(root, etree._Element)  # HTML files are parsed into lxml trees
            pretty_html_tree(container, root)
            prettied = True
        elif mt in OEB_STYLES:
            container.parsed(name)
            prettied = True
        elif name == container.opf_name:
            root = container.parsed(name)
            assert isinstance(root, etree._Element)  # the OPF is parsed into an lxml tree
            pretty_opf(root)
            pretty_xml_tree(root)
            prettied = True
        elif mt in xml_types:
            root = container.parsed(name)
            assert isinstance(root, etree._Element)  # XML files are parsed into lxml trees
            pretty_xml_tree(root)
            prettied = True
        if prettied:
            container.dirty(name)
