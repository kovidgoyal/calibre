#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai


__license__   = 'GPL v3'
__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import re, socket

from mechanize import URLError

from calibre.ebooks.metadata.book.base import Metadata
from calibre import browser
from calibre.ebooks.BeautifulSoup import BeautifulSoup
from calibre.ebooks.chardet import xml_to_unicode
from polyglot.builtins import codepoint_to_chr, unicode_type, range
from polyglot.urllib import parse_qs, quote_plus

URL = \
"http://ww2.kdl.org/libcat/WhatsNext.asp?AuthorLastName={0}&AuthorFirstName=&SeriesName=&BookTitle={1}&CategoryID=0&cmdSearch=Search&Search=1&grouping="

_ignore_starts = '\'"'+''.join(codepoint_to_chr(x) for x in list(range(0x2018, 0x201e))+[0x2032, 0x2033])


def get_series(title, authors, timeout=60):
    mi = Metadata(title, authors)
    if title and title[0] in _ignore_starts:
        title = title[1:]
    title = re.sub(r'^(A|The|An)\s+', '', title).strip()
    if not title:
        return mi
    if isinstance(title, unicode_type):
        title = title.encode('utf-8')

    title = quote_plus(title)

    author = authors[0].strip()
    if not author:
        return mi
    if ',' in author:
        author = author.split(',')[0]
    else:
        author = author.split()[-1]

    url = URL.format(author, title)
    br = browser()
    try:
        raw = br.open_novisit(url, timeout=timeout).read()
    except URLError as e:
        if isinstance(e.reason, socket.timeout):
            raise Exception('KDL Server busy, try again later')
        raise
    if 'see the full results' not in raw:
        return mi
    raw = xml_to_unicode(raw)[0]
    soup = BeautifulSoup(raw)
    searcharea = soup.find('div', attrs={'class':'searcharea'})
    if searcharea is None:
        return mi
    ss = searcharea.find('div', attrs={'class':'seriessearch'})
    if ss is None:
        return mi
    a = ss.find('a', href=True)
    if a is None:
        return mi
    href = a['href'].partition('?')[-1]
    data = parse_qs(href)
    series = data.get('SeriesName', [])
    if not series:
        return mi
    series = series[0]
    series = re.sub(r' series$', '', series).strip()
    if series:
        mi.series = series
    ns = ss.nextSibling
    if ns.contents:
        raw = unicode_type(ns.contents[0])
        raw = raw.partition('.')[0].strip()
        try:
            mi.series_index = int(raw)
        except Exception:
            pass
    return mi


if __name__ == '__main__':
    import sys
    print(get_series(sys.argv[-2], [sys.argv[-1]]))
