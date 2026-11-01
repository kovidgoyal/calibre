import re
from typing import TYPE_CHECKING, cast

from lxml.html import tostring

from calibre.ebooks.chardet import xml_to_unicode
from calibre.ebooks.readability.cleaners import clean_attributes, normalize_spaces
from calibre.utils.xml_parse import document_fromstring

if TYPE_CHECKING:
    from lxml.html import HtmlElement


def build_doc(page: str | bytes) -> HtmlElement:
    page_unicode = xml_to_unicode(page, strip_encoding_pats=True)[0]
    doc = cast('HtmlElement', document_fromstring(page_unicode))  # parsed with the lxml.html parser
    return doc


def js_re(src: str, pattern: str, flags: int, repl: str) -> str:
    return re.compile(pattern, flags).sub(src, repl.replace('$', '\\'))


def normalize_entities(cur_title: str) -> str:
    entities = {
        '\u2014': '-',
        '\u2013': '-',
        '&mdash;': '-',
        '&ndash;': '-',
        '\u00a0': ' ',
        '\u00ab': '"',
        '\u00bb': '"',
        '&quot;': '"',
    }
    for c, r in entities.items():
        if c in cur_title:
            cur_title = cur_title.replace(c, r)

    return cur_title


def norm_title(title: str) -> str:
    return normalize_entities(normalize_spaces(title))


def get_title(doc: HtmlElement) -> str:
    try:
        title = doc.find('.//title').text  # ty: ignore[unresolved-attribute] a missing title is handled by the except clause
    except AttributeError:
        title = None
    if not title:
        return '[no-title]'

    return norm_title(title)


def add_match(collection: set[str], text: str, orig: str) -> None:
    text = norm_title(text)
    if len(text.split()) >= 2 and len(text) >= 15:
        if text.replace('"', '') in orig.replace('"', ''):
            collection.add(text)


def shorten_title(doc: HtmlElement) -> str:
    title = doc.find('.//title').text  # ty: ignore[unresolved-attribute] raises AttributeError if there is no <title>
    if not title:
        return ''

    title = orig = norm_title(title)

    candidates = set()

    for item in ['.//h1', './/h2', './/h3']:
        for e in list(doc.iterfind(item)):
            if e.text:
                add_match(candidates, e.text, orig)
            if e.text_content():
                add_match(candidates, e.text_content(), orig)

    for item in [
        "descendant-or-self::*[@id = 'title']",
        "descendant-or-self::*[@id = 'head']",
        "descendant-or-self::*[@id = 'heading']",
        "descendant-or-self::*[@class and contains(concat(' ', normalize-space(@class), ' '), ' pageTitle ')]",
        "descendant-or-self::*[@class and contains(concat(' ', normalize-space(@class), ' '), ' news_title ')]",
        "descendant-or-self::*[@class and contains(concat(' ', normalize-space(@class), ' '), ' title ')]",
        "descendant-or-self::*[@class and contains(concat(' ', normalize-space(@class), ' '), ' head ')]",
        "descendant-or-self::*[@class and contains(concat(' ', normalize-space(@class), ' '), ' heading ')]",
        "descendant-or-self::*[@class and contains(concat(' ', normalize-space(@class), ' '), ' contentheading ')]",
        "descendant-or-self::*[@class and contains(concat(' ', normalize-space(@class), ' '), ' small_header_red ')]",
    ]:
        for e in doc.xpath(item):
            if e.text:
                add_match(candidates, e.text, orig)
            if e.text_content():
                add_match(candidates, e.text_content(), orig)

    if candidates:
        title = max(candidates, key=len)
    else:
        for delimiter in [' | ', ' - ', ' :: ', ' / ']:
            if delimiter in title:
                parts = orig.split(delimiter)
                if len(parts[0].split()) >= 4:
                    title = parts[0]
                    break
                elif len(parts[-1].split()) >= 4:
                    title = parts[-1]
                    break
        else:
            if ': ' in title:
                parts = orig.split(': ')
                if len(parts[-1].split()) >= 4:
                    title = parts[-1]
                else:
                    title = orig.split(': ', 1)[1]

    if not 15 < len(title) < 150:
        return orig

    return title


def get_body(doc: HtmlElement) -> str:
    [elem.drop_tree() for elem in doc.xpath('.//script | .//link | .//style')]
    raw_html = str(tostring(doc.body or doc))
    return clean_attributes(raw_html)
