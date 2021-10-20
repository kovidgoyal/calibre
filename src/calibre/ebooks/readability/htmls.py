import re

from lxml.html import tostring
import lxml.html

from calibre.ebooks.readability.cleaners import normalize_spaces, clean_attributes
from calibre.ebooks.chardet import xml_to_unicode
from polyglot.builtins import iteritems


def build_doc(page):
    page_unicode = xml_to_unicode(page, strip_encoding_pats=True)[0]
    doc = lxml.html.document_fromstring(page_unicode)
    return doc


def js_re(src, pattern, flags, repl):
    return re.compile(pattern, flags).sub(src, repl.replace('$', '\\'))


def normalize_entities(cur_title):
    entities = {
        '\u2014':'-',
        '\u2013':'-',
        '&mdash;': '-',
        '&ndash;': '-',
        '\u00A0': ' ',
        '\u00AB': '"',
        '\u00BB': '"',
        '&quot;': '"',
    }
    for c, r in iteritems(entities):
        if c in cur_title:
            cur_title = cur_title.replace(c, r)

    return cur_title


def norm_title(title):
    return normalize_entities(normalize_spaces(title))


def get_title(doc):
    try:
        title = doc.find('.//title').text
    except AttributeError:
        title = None
    if not title:
        return '[no-title]'

    return norm_title(title)


def add_match(collection, text, orig):
    text = norm_title(text)
    if len(text.split()) >= 2 and len(text) >= 15:
        if text.replace('"', '') in orig.replace('"', ''):
            collection.add(text)


def shorten_title(doc):
    title = doc.find('.//title').text
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
            "descendant-or-self::*[@class and contains(concat(' ', normalize-space(@class), ' '), ' small_header_red ')]"
    ]:
        for e in doc.xpath(item):
            if e.text:
                add_match(candidates, e.text, orig)
            if e.text_content():
                add_match(candidates, e.text_content(), orig)

    if candidates:
        title = sorted(candidates, key=len)[-1]
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


def get_body(doc):
    [elem.drop_tree() for elem in doc.xpath('.//script | .//link | .//style')]
    raw_html = str(tostring(doc.body or doc))
    return clean_attributes(raw_html)
