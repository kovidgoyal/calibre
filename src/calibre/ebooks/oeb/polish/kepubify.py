#!/usr/bin/env python
# License: GPLv3 Copyright: 2025, Kovid Goyal <kovid at kovidgoyal.net>

# Add/remove the markup needed for Kobo's custom EPUB renderer. It's
# mostly completely unnecessary junk added to the HTML because Kobo
# doesn't know how to render EPUB without needing such hacks. The list of
# changes:
#     * Add Kobo style tweaks
#     * Add body div wrappers (used to apply pagination styles)
#     * Add spans around sentences. Apparently Kobo cannot implement
#       highlighting and bookmarking without this, they should be using CFI for this, sigh.
#     * Cover marking in the OPF
#     * Markup cleanup (remove various things that trip up the Kobo renderer)

import re

from lxml import etree

from calibre.ebooks.oeb.base import XHTML, XPath, escape_cdata
from calibre.ebooks.oeb.parse_utils import barename, merge_multiple_html_heads_and_bodies
from calibre.ebooks.oeb.polish.parsing import parse
from calibre.ebooks.oeb.polish.tts import lang_for_elem
from calibre.ebooks.oeb.polish.utils import extract, insert_self_closing
from calibre.spell.break_iterator import sentence_positions
from calibre.utils.localization import canonicalize_lang, get_lang

KOBO_STYLE_HACKS = 'kobostylehacks'
OUTER_DIV_ID = 'book-columns'
INNER_DIV_ID = 'book-inner'
SKIPPED_TAGS = frozenset((
    '', 'script', 'style', 'atom', 'pre', 'audio', 'video', 'svg', 'math'
))
BLOCK_TAGS = frozenset((
    'p', 'ol', 'ul', 'table', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
))


def outer_html(node):
    return etree.tostring(node, encoding='unicode', with_tail=False)


def add_style(root, css='div#book-inner { margin-top: 0; margin-bottom: 0; }', cls=KOBO_STYLE_HACKS) -> bool:

    def add(parent):
        e = parent.makeelement(XHTML('style'), type='text/css')
        e.text = css
        e.set('class', cls)
        insert_self_closing(parent, e)

    if heads := XPath('./h:head')(root):
        add(heads[-1])
        return True
    if bodies := XPath('./h:body')(root):
        add(bodies[-1])
        return True
    return False


def remove_kobo_styles(root):
    for x in XPath(f'//h:style[@type="text/css" and @class="{KOBO_STYLE_HACKS}"]')(root):
        extract(x)


def wrap_body_contents(body):
    # Kobo wraps the body with two div tags,
    # div#book-columns > div#book-inner to provide a target for applying
    # pagination styles.
    for elem in XPath(f'//*[@id="{OUTER_DIV_ID}" or @id={INNER_DIV_ID}]')(body):
        elem.attrib.pop('id')
    outer = body.makeelement(XHTML('div'), id=OUTER_DIV_ID)
    inner = body.makeelement(XHTML('div'), id=INNER_DIV_ID)
    outer.append(inner)
    inner.text = body.text
    body.text = None
    for child in body:
        inner.append(child)
    del body[:]
    body.append(outer)
    return inner


def unwrap_body_contents(body):
    children = []
    text = ''
    for inner in XPath(f'./h:div[@id="{OUTER_DIV_ID}"]/h:div[@id="{INNER_DIV_ID}"]')(body):
        children.extend(inner)
        if inner.text:
            text += inner.text
        extract(inner.getparent())
    body.extend(children)
    body.text = text


def add_kobo_spans(inner, root_lang):
    stack = []
    a, p = stack.append, stack.pop
    a((inner, None, barename(inner.tag).lower(), lang_for_elem(inner, root_lang)))
    paranum, segnum = 0, 0
    increment_next_para = True
    span_tag_name = XHTML('span')
    leading_whitespace_pat = re.compile(r'^\s+')

    def kobo_span(parent):
        nonlocal paranum, segnum
        segnum += 1
        return parent.makeelement(span_tag_name, attrib={'class': 'koboSpan', 'id': f'kobo.{paranum}.{segnum}'})

    def wrap_text_in_spans(text: str, parent: etree.Element, after_child: etree.ElementBase, lang: str) -> str | None:
        nonlocal increment_next_para, paranum, segnum
        if increment_next_para:
            paranum += 1
            segnum = 0
            increment_next_para = False
        stripped = leading_whitespace_pat.sub('', text)
        ws = None
        if num := len(text) - len(stripped):
            ws = text[:num]
        try:
            at = 0 if after_child is None else parent.index(after_child) + 1
        except ValueError:  # wrapped child
            at = parent.index(after_child.getparent()) + 1
        if at:
            parent[at-1].tail = ws
        else:
            parent.text = ws
        for pos, sz in sentence_positions(stripped, lang):
            s = kobo_span(parent)
            s.text = stripped[pos:pos+sz]
            parent.insert(at, s)
            at += 1

    def wrap_child(child: etree.Element) -> etree.Element:
        nonlocal increment_next_para, paranum, segnum
        increment_next_para = False
        paranum += 1
        segnum = 0
        node = child.getparent()
        idx = node.index(child)
        w = kobo_span(node)
        node[idx] = w
        w.append(child)
        w.tail = child.tail
        child.tail = child.text = None
        return w

    while stack:
        node, parent, tagname, node_lang = p()
        if parent is not None:  # tail text
            wrap_text_in_spans(node, parent, tagname, node_lang)
            continue
        if tagname == 'img':
            wrap_child(node)
            continue
        if not increment_next_para and tagname in BLOCK_TAGS:
            increment_next_para = True
        for child in reversed(node):
            child_name = barename(child.tag).lower() if isinstance(child.tag, str) else ''
            if child.tail:
                a((child.tail, node, child, node_lang))
            if child_name not in SKIPPED_TAGS:
                a((child, None, child_name, lang_for_elem(child, node_lang)))
        if node.text:
            wrap_text_in_spans(node.text, node, None, node_lang)


def add_kobo_markup_to_html(root, metadata_lang):
    root_lang = canonicalize_lang(lang_for_elem(root, canonicalize_lang(metadata_lang or get_lang())) or 'en')
    add_style(root)
    for body in XPath('./h:body')(root):
        inner = wrap_body_contents(body)
        add_kobo_spans(inner, lang_for_elem(body, root_lang))


def remove_kobo_markup_from_html(root):
    remove_kobo_styles(root)
    for body in XPath('./h:body')(root):
        unwrap_body_contents(body)


def serialize_html(root) -> bytes:
    escape_cdata(root)
    ans = etree.tostring(root, encoding='unicode', xml_declaration=False, pretty_print=False, with_tail=False)
    ans = ans.replace('\xa0', '&#160;')
    return b"<?xml version='1.0' encoding='utf-8'?>\n" + ans.encode('utf-8')


def kepubify_parsed_html(root, metadata_lang: str = 'en'):
    remove_kobo_markup_from_html(root)
    merge_multiple_html_heads_and_bodies(root)
    add_kobo_markup_to_html(root, metadata_lang)


def kepubify_html_data(raw: str | bytes, metadata_lang: str = 'en'):
    root = parse(raw)
    kepubify_parsed_html(root, metadata_lang)
    return root


def kepubify_container(container):
    lang = container.mi.language
