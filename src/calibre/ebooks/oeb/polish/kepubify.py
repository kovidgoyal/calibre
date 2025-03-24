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
from functools import lru_cache
from typing import NamedTuple

from css_parser import CSSParser
from css_parser.css import CSSComment, CSSPageRule, CSSRule
from lxml import etree

from calibre.ebooks.metadata import authors_to_string
from calibre.ebooks.oeb.base import OEB_DOCS, OEB_STYLES, XHTML, XPath, escape_cdata
from calibre.ebooks.oeb.parse_utils import barename, merge_multiple_html_heads_and_bodies
from calibre.ebooks.oeb.polish.container import Container, EpubContainer, get_container
from calibre.ebooks.oeb.polish.cover import find_cover_image, find_cover_image3, find_cover_page
from calibre.ebooks.oeb.polish.errors import DRMError
from calibre.ebooks.oeb.polish.parsing import parse
from calibre.ebooks.oeb.polish.tts import lang_for_elem
from calibre.ebooks.oeb.polish.utils import extract, insert_self_closing
from calibre.spell.break_iterator import sentence_positions
from calibre.srv.render_book import Profiler, calculate_number_of_workers
from calibre.utils.localization import canonicalize_lang, get_lang
from calibre.utils.short_uuid import uuid4

KOBO_CSS_ID = 'kobostylehacks'  # kepubify uses class, actual books from Kobo use id
EXTRA_KOBO_CSS_IDS = ('koboSpanStyle',)  # these are present in some kepub files from kobo such as dark forest by cixin liu
KOBO_JS_NAME = 'kobo.js'
KOBO_CSS_NAME = 'kobo.css'
OUTER_DIV_ID = 'book-columns'
INNER_DIV_ID = 'book-inner'
KOBO_SPAN_CLASS = 'koboSpan'
DUMMY_TITLE_PAGE_NAME = 'kobo-title-page-generated-by-calibre'
DUMMY_COVER_IMAGE_NAME = 'kobo-cover-image-generated-by-calibre'
CSS_COMMENT_COOKIE = 'calibre-removed-css-for-kobo'
SKIPPED_TAGS = frozenset((
    '', 'script', 'style', 'atom', 'pre', 'audio', 'video', 'svg', 'math'
))
BLOCK_TAGS = frozenset((
    'p', 'ol', 'ul', 'table', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
))
KOBO_CSS = 'div#book-inner { margin-top: 0; margin-bottom: 0; }'


@lru_cache(2)
def css_parser() -> CSSParser:
    return CSSParser(validate=False)


class Options(NamedTuple):
    extra_css: str = KOBO_CSS
    remove_widows_and_orphans: bool = False
    remove_at_page_rules: bool = False

    for_removal: bool = False

    @property
    def needs_stylesheet_processing(self) -> bool:
        return self.remove_at_page_rules or self.remove_widows_and_orphans or self.for_removal


def outer_html(node):
    return etree.tostring(node, encoding='unicode', with_tail=False)


@lru_cache(2)
def kobo_js() -> bytes:
    return P('templates/kobo.js', data=True)


def add_style_and_script(root, kobo_js_href: str, opts: Options) -> bool:

    def add(parent):
        e = parent.makeelement(XHTML('style'), type='text/css', id=KOBO_CSS_ID)
        e.text = opts.extra_css
        insert_self_closing(parent, e)
        e = parent.makeelement(XHTML('script'), type='text/javascript', src=kobo_js_href)
        insert_self_closing(parent, e)

    if heads := XPath('./h:head')(root):
        add(heads[-1])
        return True
    if bodies := XPath('./h:body')(root):
        add(bodies[-1])
        return True
    return False


def is_href_to_fname(href: str | None, fname: str) -> bool:
    return href and href.rpartition('/')[-1] == fname


def remove_kobo_styles_and_scripts(root):
    ids_to_remove = EXTRA_KOBO_CSS_IDS + (KOBO_CSS_ID,)
    for style in XPath('//h:style')(root):
        if style.get('id') in ids_to_remove:
            extract(style)
    for link in XPath('//h:link')(root):
        if link.get('rel') == 'stylesheet' and link.get('type') == 'text/css' and is_href_to_fname(link.get('href'), KOBO_CSS_NAME):
            extract(link)
    for script in XPath('//h:script')(root):
        if script.get('type') == 'text/javascript' and is_href_to_fname(script.get('src'), KOBO_JS_NAME):
            extract(script)
    for comment in root.iter(tag=etree.Comment):
        if comment.text == ' kobo-style ':  # these are present in KEPUB from Kobo
            extract(comment)


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
        try:
            at = 0 if after_child is None else parent.index(after_child) + 1
        except ValueError:  # wrapped child
            at = parent.index(after_child.getparent()) + 1
        stripped = leading_whitespace_pat.sub('', text)
        if not at and not stripped and not len(parent):
            stripped = text
        ws = None
        if num := len(text) - len(stripped):
            ws = text[:num]
        before = None if stripped else ws
        if at:
            parent[at-1].tail = before
        else:
            parent.text = before
        if stripped:
            text = (ws + stripped) if ws else stripped
            for pos, sz in sentence_positions(text, lang):
                s = kobo_span(parent)
                s.text = text[pos:pos+sz]
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


def add_kobo_markup_to_html(root: etree.Element, kobo_js_href: str, opts: Options, metadata_lang: str) -> None:
    root_lang = canonicalize_lang(lang_for_elem(root, canonicalize_lang(metadata_lang or get_lang())) or 'en')
    add_style_and_script(root, kobo_js_href, opts)
    for body in XPath('./h:body')(root):
        inner = wrap_body_contents(body)
        add_kobo_spans(inner, lang_for_elem(body, root_lang))


def remove_kobo_markup_from_html(root):
    remove_kobo_styles_and_scripts(root)
    for body in XPath('./h:body')(root):
        unwrap_body_contents(body)
        remove_kobo_spans(body)


def serialize_html(root) -> bytes:
    escape_cdata(root)
    ans = etree.tostring(root, encoding='unicode', xml_declaration=False, pretty_print=False, with_tail=False)
    ans = ans.replace('\xa0', '&#160;')
    return b"<?xml version='1.0' encoding='utf-8'?>\n" + ans.encode('utf-8')


def nest_css_comments(text: str) -> str:
    return text.replace('*/', '*\u200c/')


def process_stylesheet(css: str, opts: Options) -> str:
    has_comment_cookie = CSS_COMMENT_COOKIE in css
    if opts.for_removal and not has_comment_cookie:
        return css  # avoid expensive parse
    sheet = css_parser().parseString(css)
    changed = False
    page_rules = []
    if has_comment_cookie:
        for i, rule in enumerate(sheet.cssRules):
            if rule.type == CSSRule.STYLE_RULE:
                s = rule.style
                for q in ('widows', 'orphans'):
                    if (prop := s.getProperty(f'-{CSS_COMMENT_COOKIE}-{q}')) is not None:
                        prop.name = q
                        changed = True
            elif rule.type == CSSRule.COMMENT:
                if rule.cssText.startswith(f'/* {CSS_COMMENT_COOKIE}: '):
                    page_rules.append((i, rule))
                    changed = True
    for i, cr in page_rules:
        pr = CSSPageRule()
        pr.cssText = cr.cssText[len(f'/* {CSS_COMMENT_COOKIE}: '):-3]
        sheet.deleteRule(i)
        sheet.insertRule(pr, i)

    if opts.for_removal:
        return sheet.cssText if changed else css

    for i, rule in enumerate(sheet.cssRules):
        if rule.type == CSSRule.STYLE_RULE:
            if opts.remove_widows_and_orphans:
                s = rule.style
                for q in ('widows', 'orphans'):
                    if (prop := s.getProperty(q)) is not None:
                        changed = True
                        prop.name = f'-{CSS_COMMENT_COOKIE}-{q}'
        elif rule.type == CSSRule.PAGE_RULE:
            if opts.remove_at_page_rules:
                changed = True
                page_rules.append((i, rule))

    for i, pr in page_rules:
        comment = CSSComment(f'/* {CSS_COMMENT_COOKIE}: {nest_css_comments(pr.cssText)} */')
        sheet.deleteRule(i)
        sheet.insertRule(comment, i)
    return sheet.cssText if changed else css


def kepubify_parsed_html(root: etree.Element, kobo_js_href: str, opts: Options, metadata_lang: str = 'en'):
    remove_kobo_markup_from_html(root)
    if not opts.for_removal:
        merge_multiple_html_heads_and_bodies(root)
    if opts.needs_stylesheet_processing:
        for style in XPath('//h:style')(root):
            if (style.get('type') or 'text/css') == 'text/css' and style.text:
                style.text = process_stylesheet(style.text, opts)
    if not opts.for_removal:
        add_kobo_markup_to_html(root, kobo_js_href, opts, metadata_lang)


def kepubify_html_data(raw: str | bytes, kobo_js_href: str = KOBO_JS_NAME, opts: Options = Options(), metadata_lang: str = 'en'):
    root = parse(raw)
    kepubify_parsed_html(root, kobo_js_href, opts, metadata_lang)
    return root


def kepubify_html_path(path: str, kobo_js_href: str = KOBO_JS_NAME, metadata_lang: str = 'en', opts: Options = Options()):
    with open(path, 'r+b') as f:
        raw = f.read()
        root = kepubify_html_data(raw, kobo_js_href, opts, metadata_lang)
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


def add_dummy_title_page(container: Container, cover_image_name: str, mi, kobo_js_name: str) -> None:
    titlepage_name = container.add_file(f'{DUMMY_TITLE_PAGE_NAME}.xhtml', modify_name_if_needed=True, spine_index=0)
    kobo_js_href = container.name_to_href(kobo_js_name, titlepage_name)
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
        <style type="text/css" id="{KOBO_CSS_ID}">
        {KOBO_CSS}
        </style>
        <script type="text/javascript" src="{kobo_js_href}"/>
    </head>
    <body><div id="{OUTER_DIV_ID}"><div id="{INNER_DIV_ID}">
    __CONTENT__
    </div></div></body>
</html>
'''
    if cover_image_name:
        cover_href = container.name_to_href(cover_image_name, titlepage_name)
        html = html.replace('__CONTENT__', f'<img src="{cover_href}" alt="cover" style="height: 100%" />')
    else:
        aus = authors_to_string(mi.authors)
        html = html.replace('__CONTENT__', f'''
        <h1 style="text-align: center">{mi.title}</h1>
        <h3 style="text-align: center">{aus}</h1>
        ''')
    with container.open(titlepage_name, 'w') as f:
        f.write(html)
    container.apply_unique_properties(titlepage_name, 'calibre:title-page')
    return titlepage_name


def remove_dummy_title_page(container: Container) -> None:
    for name, is_linear in container.spine_names:
        if is_linear:
            if DUMMY_TITLE_PAGE_NAME in name:
                container.remove_item(name)
            break


def remove_dummy_cover_image(container: Container) -> None:
    for name in tuple(container.mime_map):
        if DUMMY_COVER_IMAGE_NAME in name:
            container.remove_item(name)


def first_spine_item_is_probably_title_page(container: Container) -> bool:
    for name, is_linear in container.spine_names:
        fname = name.split('/')[-1]
        if is_linear:
            if 'cover' in name or 'title' in fname:
                return True
            root = container.parsed(name)
            return is_probably_a_title_page(root)
    return False


def process_stylesheet_path(path: str, opts: Options) -> None:
    if opts.needs_stylesheet_processing:
        with open(path, 'r+b') as f:
            css = f.read().decode()
            ncss = process_stylesheet(css, opts)
            if ncss is not css:
                f.seek(0)
                f.truncate()
                f.write(ncss)


def process_path(path: str, kobo_js_href: str, metadata_lang: str, opts: Options, media_type: str) -> None:
    if media_type in OEB_DOCS:
        kepubify_html_path(path, kobo_js_href, metadata_lang, opts)
    elif media_type in OEB_STYLES:
        process_stylesheet_path(path, opts)


def do_work_in_parallel(container: Container, kobo_js_name: str, opts: Options, metadata_lang: str, max_workers: int) -> None:
    names_that_need_work = tuple(name for name, mt in container.mime_map.items() if mt in OEB_DOCS or mt in OEB_STYLES)
    num_workers = calculate_number_of_workers(names_that_need_work, container, max_workers)
    def name_to_abspath(name: str) -> str:
        return container.get_file_path_for_processing(name, allow_modification=True)

    if num_workers < 2:
        for name in names_that_need_work:
            process_path(name_to_abspath(name), container.name_to_href(kobo_js_name, name), metadata_lang, opts, container.mime_map[name])
    else:
        with ThreadPoolExecutor(max_workers=num_workers) as executor:
            futures = tuple(executor.submit(
                process_path, name_to_abspath(name), container.name_to_href(kobo_js_name, name),
                metadata_lang, opts, container.mime_map[name]) for name in names_that_need_work)
            for future in futures:
                future.result()


def remove_kobo_files(container):
    for name, mt in tuple(container.mime_map.items()):
        fname = name.rpartition('/')[-1]
        if mt == 'application/javascript' and fname == KOBO_JS_NAME:
            container.remove_item(name)
        elif mt == 'text/css' and fname == KOBO_CSS_NAME:
            container.remove_item(name)


def unkepubify_container(container: Container, max_workers: int = 0) -> None:
    check_for_kobo_drm(container)
    remove_dummy_cover_image(container)
    remove_dummy_title_page(container)
    remove_kobo_files(container)
    opts = Options(for_removal=True)
    metadata_lang = container.mi.language
    do_work_in_parallel(container, KOBO_JS_NAME, opts, metadata_lang, max_workers)


def uniqify_name(container: Container, fname: str) -> str:
    q = fname
    while container.has_name_case_insensitive(q) or container.manifest_has_name(q):
        q = f'{uuid4()}/fname'
    return q


def kepubify_container(container: Container, opts: Options, max_workers: int = 0) -> None:
    remove_dummy_title_page(container)
    remove_dummy_cover_image(container)
    remove_kobo_files(container)
    metadata_lang = container.mi.language
    cover_image_name = find_cover_image(container) or find_cover_image3(container)
    mi = container.mi
    if not cover_image_name:
        from calibre.ebooks.covers import generate_cover
        cdata = generate_cover(mi)
        cover_image_name = container.add_file(f'{DUMMY_COVER_IMAGE_NAME}.jpeg', cdata, modify_name_if_needed=True)
    container.apply_unique_properties(cover_image_name, 'cover-image')
    kobo_js_name = container.add_file(
            uniqify_name(container, KOBO_JS_NAME), kobo_js(), media_type='application/javascript', suggested_id='js-kobo.js')
    if not find_cover_page(container) and not first_spine_item_is_probably_title_page(container):
        add_dummy_title_page(container, cover_image_name, mi, kobo_js_name)
    do_work_in_parallel(container, kobo_js_name, opts, metadata_lang, max_workers)


def kepubify_path(path, outpath='', max_workers=0, allow_overwrite=False, opts: Options = Options()):
    container = get_container(path, tweak_mode=True)
    kepubify_container(container, opts, max_workers=max_workers)
    base, ext = os.path.splitext(path)
    outpath = outpath or base + '.kepub'
    c = 0
    while not allow_overwrite and outpath == path:
        c += 1
        outpath = f'{base}-{c}.kepub'
    container.commit(outpath=outpath)
    return outpath


def check_for_kobo_drm(container: Container) -> None:
    # sadly rights.xml is not definitive as various dedrm tools leave it behind
    has_rights_xml = container.has_name_and_is_not_empty('rights.xml')
    if not has_rights_xml:
        return
    for name, is_linear in container.spine_names:
        mt = container.mime_map[name]
        if mt in OEB_DOCS:
            with container.open(name, 'rb') as f:
                raw = f.read(8192)
                if b'<?xml' not in raw and b'<html' not in raw and KOBO_SPAN_CLASS.encode() not in raw:
                    raise DRMError()
            break


def unkepubify_path(path, outpath='', max_workers=0, allow_overwrite=False):
    container = get_container(path, tweak_mode=True, ebook_cls=EpubContainer)
    unkepubify_container(container, max_workers)
    base, ext = os.path.splitext(path)
    outpath = outpath or base + '.epub'
    c = 0
    while not allow_overwrite and outpath == path:
        c += 1
        outpath = f'{base}-{c}.epub'
    container.commit(outpath=outpath)
    return outpath


def check_if_css_needs_modification(extra_css: str) -> tuple[bool, bool]:
    remove_widows_and_orphans = remove_at_page_rules = False
    sheet = None
    if extra_css:
        try:
            sheet = css_parser().parseString(extra_css)
        except Exception:
            pass
        else:
            for rule in sheet.cssRules:
                if rule.type == CSSRule.PAGE_RULE:
                    remove_at_page_rules = True
                elif rule.type == CSSRule.STYLE_RULE:
                    if rule.style['widows'] or rule.style['orphans']:
                        remove_widows_and_orphans = True
                if remove_widows_and_orphans and remove_at_page_rules:
                    break
    return sheet, remove_widows_and_orphans, remove_at_page_rules


def make_options(
    extra_css: str = '',
    affect_hyphenation: bool = False,
    disable_hyphenation: bool = False,
    hyphenation_min_chars: int = 6,
    hyphenation_min_chars_before: int = 3,
    hyphenation_min_chars_after: int = 3,
    hyphenation_limit_lines: int = 2,

    remove_widows_and_orphans: bool | None = None,
    remove_at_page_rules: bool | None = None,
) -> Options:
    if remove_widows_and_orphans is None or remove_at_page_rules is None:
        _, remove_widows_and_orphans, remove_at_page_rules = check_if_css_needs_modification(extra_css)
    hyphen_css = ''
    if affect_hyphenation:
        if disable_hyphenation:
            hyphen_css = '''
* {
  -webkit-hyphens: none !important;
  hyphens: none !important;
}
'''
        elif hyphenation_min_chars > 0:
            hyphen_css = f'''
* {{
    /* Vendor-prefixed CSS properties for hyphenation. Keep -webkit first since
     * some user agents also recognize -webkit properties and will apply them.
     */
    -webkit-hyphens: auto;
    -webkit-hyphenate-limit-after: {hyphenation_min_chars_after};
    -webkit-hyphenate-limit-before: {hyphenation_min_chars_before};
    -webkit-hyphenate-limit-chars: {hyphenation_min_chars} {hyphenation_min_chars_before} {hyphenation_min_chars_after};
    -webkit-hyphenate-limit-lines: {hyphenation_limit_lines};

    /* CSS4 standard properties for hyphenation. If a property isn't represented
     * in the standard, don't put a vendor-prefixed property for it above.
     */
    hyphens: auto;
    hyphenate-limit-chars: {hyphenation_min_chars} {hyphenation_min_chars_before} {hyphenation_min_chars_after};
    hyphenate-limit-lines: {hyphenation_limit_lines};
    hyphenate-limit-last: page;
}}

h1, h2, h3, h4, h5, h6, td {{
    -webkit-hyphens: none !important;
    hyphens: none !important;
}}
'''
    if extra_css:
        extra_css = KOBO_CSS + '\n\n' + extra_css
    else:
        extra_css = KOBO_CSS
    if hyphen_css:
        extra_css += '\n\n' + hyphen_css
    return Options(extra_css=extra_css, remove_widows_and_orphans=remove_widows_and_orphans, remove_at_page_rules=remove_at_page_rules)


def profile():
    path = sys.argv[-1]
    with Profiler():
        kepubify_path(path, max_workers=1)


def develop():
    from zipfile import ZipFile

    from calibre.ptempfile import TemporaryDirectory
    path = sys.argv[-1]
    with TemporaryDirectory() as tdir:
        outpath = kepubify_path(path, max_workers=1)
        with ZipFile(outpath) as zf:
            zf.extractall(tdir)
        print('Extracted to:', tdir)
        input('Press Enter to quit')


def kepubify_main(args=sys.argv):
    for path in args[1:]:
        outpath = ''
        if path.endswith('.epub'):
            outpath = path[:-4] + 'kepub.epub'
        kepub_path = kepubify_path(path, outpath, allow_overwrite=True)
        print(f'{path} converted to: {kepub_path}')


def unkepubify_main(args=sys.argv):
    for path in args[1:]:
        outpath = ''
        if path.endswith('.kepub.epub'):
            outpath = path[:-len('kepub.epub')] + 'epub'
        kepub_path = unkepubify_path(path, outpath, allow_overwrite=True)
        print(f'{path} converted to: {kepub_path}')


if __name__ == '__main__':
    kepubify_main()
