#!/usr/bin/env python
# License: GPLv3 Copyright: 2019, Kovid Goyal <kovid at kovidgoyal.net>


import bs4
from bs4 import (  # noqa
    CData, Comment, Declaration, NavigableString, ProcessingInstruction,
    SoupStrainer, Tag, __version__
)


def parse_html(markup):
    from calibre.ebooks.chardet import strip_encoding_declarations, xml_to_unicode, substitute_entites
    from calibre.utils.cleantext import clean_xml_chars
    if isinstance(markup, str):
        markup = strip_encoding_declarations(markup)
        markup = substitute_entites(markup)
    else:
        markup = xml_to_unicode(markup, strip_encoding_pats=True, resolve_entities=True)[0]
    markup = clean_xml_chars(markup)
    from html5_parser.soup import parse
    return parse(markup, return_root=False)


def prettify(soup):
    ans = soup.prettify()
    if isinstance(ans, bytes):
        ans = ans.decode('utf-8')
    return ans


def BeautifulSoup(markup='', *a, **kw):
    return parse_html(markup)


def BeautifulStoneSoup(markup='', *a, **kw):
    return bs4.BeautifulSoup(markup, 'xml')
