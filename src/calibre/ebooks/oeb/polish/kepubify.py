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

import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor

from lxml import etree

from calibre.ebooks.metadata import authors_to_string
from calibre.ebooks.oeb.base import OEB_DOCS, XHTML, XPath, escape_cdata
from calibre.ebooks.oeb.parse_utils import barename, merge_multiple_html_heads_and_bodies
from calibre.ebooks.oeb.polish.container import get_container
from calibre.ebooks.oeb.polish.cover import find_cover_image, find_cover_image3, find_cover_page
from calibre.ebooks.oeb.polish.parsing import parse
from calibre.ebooks.oeb.polish.tts import lang_for_elem
from calibre.ebooks.oeb.polish.utils import extract, insert_self_closing
from calibre.spell.break_iterator import sentence_positions
from calibre.srv.render_book import Profiler, calculate_number_of_workers
from calibre.utils.localization import canonicalize_lang, get_lang

KOBO_CSS_CLASS = 'kobostylehacks'
OUTER_DIV_ID = 'book-columns'
INNER_DIV_ID = 'book-inner'
KOBO_SPAN_CLASS = 'koboSpan'
DUMMY_TITLE_PAGE_NAME = 'kobo-title-page-generated-by-calibre'
SKIPPED_TAGS = frozenset((
    '', 'script', 'style', 'atom', 'pre', 'audio', 'video', 'svg', 'math'
))
BLOCK_TAGS = frozenset((
    'p', 'ol', 'ul', 'table', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
))
KOBO_CSS = 'div#book-inner { margin-top: 0; margin-bottom: 0; }'


def outer_html(node):
    return etree.tostring(node, encoding='unicode', with_tail=False)


def add_style(root, css=KOBO_CSS, cls=KOBO_CSS_CLASS) -> bool:

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
    for x in XPath(f'//h:style[@type="text/css" and @class="{KOBO_CSS_CLASS}"]')(root):
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
        return parent.makeelement(span_tag_name, attrib={'class': KOBO_SPAN_CLASS, 'id': f'kobo.{paranum}.{segnum}'})

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


def unwrap(span: etree.Element) -> None:
    p = span.getparent()
    idx = p.index(span)
    del p[idx]
    if len(span):
        p.insert(idx, span[0])
    else:
        text = span.text + (span.tail or '')
        if idx > 0:
            prev = p[idx-1]
            prev.tail = (prev.tail or '') + text
        else:
            p.text = (p.text or '') + text


def remove_kobo_spans(body: etree.Element) -> bool:
    found = False
    for span in XPath(f'//h:span[@class="{KOBO_SPAN_CLASS}" and starts-with(@id, "kobo.")]')(body):
        unwrap(span)
        found = True
    return found


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
        remove_kobo_spans(body)


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


def kepubify_html_path(path: str, metadata_lang: str = 'en'):
    with open(path, 'r+b') as f:
        raw = f.read()
        root = kepubify_html_data(raw)
        raw = serialize_html(root)
        f.seek(0)
        f.truncate()
        f.write(raw)


def is_probably_a_title_page(root):
    for title in XPath('//h:title')(root):
        if title.text:
            words = title.text.lower().split()
            if 'cover' in words:
                return True
        title.text = None
    text = etree.tostring(root, method='text', encoding='unicode')
    textlen = len(re.sub(r'\s+', '', text))
    num_images = len(XPath('//h:img')(root))
    num_svgs = len(XPath('//h:svg')(root))
    return (num_images + num_svgs == 1 and textlen <= 10) or (textlen <= 50 and (num_images + num_svgs) < 1)


def add_dummy_title_page(container, cover_image_name):
    html = f'''\
<?xml version='1.0' encoding='utf-8'?>
<html xmlns="http://www.w3.org/1999/xhtml" lang="en" xml:lang="en">
    <head>
        <meta http-equiv="Content-Type" content="text/html; charset=utf-8"/>
        <title>Dummy title page created by calibre</title>
        <style type="text/css">
            @page {{ padding: 0pt; margin:0pt }}
            body {{ text-align: center; padding:0pt; margin: 0pt }}
            div {{ padding:0pt; margin: 0pt }}
            img {{ padding:0pt; margin: 0pt }}
        </style>
        <style type="text/css" class="{KOBO_CSS_CLASS}">
        {KOBO_CSS}
        </style>
    </head>
    <body><div id="{OUTER_DIV_ID}"><div id="{INNER_DIV_ID}">
    __CONTENT__
    </div></div></body></html>
'''
    titlepage_name = container.add_file(f'{DUMMY_TITLE_PAGE_NAME}.html', modify_name_if_needed=True)
    if cover_image_name:
        cover_href = container.name_to_href(cover_image_name, titlepage_name)
        html = html.replace('__CONTENT__', f'<img src="{cover_href}" alt="cover" style="height: 100%" />')
    else:
        mi = container.mi
        aus = authors_to_string(mi.authors)
        html = html.replace('__CONTENT__', f'''
        <h1 style="text-align: center">{mi.title}</h1>
        <h3 style="text-align: center">{aus}</h1>
        ''')
    with container.open(titlepage_name, 'w') as f:
        f.write(html)
    container.apply_unique_properties(titlepage_name, 'calibre:title-page')


def remove_dummy_title_page(container):
    for name, is_linear in container.spine_names():
        if is_linear:
            if DUMMY_TITLE_PAGE_NAME in name:
                container.remove_item(name)
            break


def first_spine_item_is_probably_cover(container) -> bool:
    for name, is_linear in container.spine_names:
        fname = name.split('/')[-1]
        if is_linear:
            if 'cover' in name or 'title' in fname:
                return True
            root = container.parsed(name)
            return is_probably_a_title_page(root)
    return False


def kepubify_container(container, max_workers=0):
    remove_dummy_title_page(container)
    metadata_lang = container.mi.language
    cover_image_name = find_cover_image(container) or find_cover_image3(container)
    if cover_image_name:
        container.apply_unique_properties(cover_image_name, 'cover-image')
    if not find_cover_page(container) and not first_spine_item_is_probably_cover(container):
        add_dummy_title_page(container, cover_image_name)
    names_that_need_work = tuple(name for name, mt in container.mime_map.items() if mt in OEB_DOCS)
    num_workers = calculate_number_of_workers(names_that_need_work, container, max_workers)
    paths = tuple(map(container.name_to_abspath, names_that_need_work))
    if num_workers < 2:
        for path in paths:
            kepubify_html_path(path, metadata_lang)
    else:
        with ThreadPoolExecutor(max_workers=num_workers) as executor:
            futures = tuple(executor.submit(kepubify_html_path, path, metadata_lang) for path in paths)
            for future in futures:
                future.result()


def profile():
    from calibre.ptempfile import TemporaryDirectory
    path = sys.argv[-1]
    with TemporaryDirectory() as tdir, Profiler():
        main(path, max_workers=1)


def develop():
    from zipfile import ZipFile

    from calibre.ptempfile import TemporaryDirectory
    path = sys.argv[-1]
    with TemporaryDirectory() as tdir:
        outpath = main(path, max_workers=1)
        with ZipFile(outpath) as zf:
            zf.extractall(tdir)
        print('Extracted to:', tdir)
        input('Press Enter to quit')


def main(path, max_workers=0):
    container = get_container(path, tweak_mode=True)
    kepubify_container(container, max_workers=max_workers)
    base, ext = os.path.splitext(path)
    outpath = base + '.kepub'
    container.commit(output=outpath)
    return outpath


if __name__ == '__main__':
    main(sys.argv[-1])
