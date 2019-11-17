#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai


__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import re, codecs

from calibre.ebooks.BeautifulSoup import BeautifulSoup
from calibre.ebooks.chardet import xml_to_unicode
from calibre.ebooks.metadata import string_to_authors, MetaInformation
from calibre.utils.logging import default_log
from calibre.ptempfile import TemporaryFile
from calibre import force_unicode
from polyglot.builtins import iterkeys


def _clean(s):
    return s.replace('\u00a0', ' ')


def _detag(tag):
    ans = ""
    if tag is None:
        return ans
    for elem in tag:
        if hasattr(elem, "contents"):
            ans += _detag(elem)
        else:
            ans += _clean(elem)
    return ans


def _metadata_from_table(soup, searchfor):
    td = soup.find('td', text=re.compile(searchfor, flags=re.I))
    if td is None:
        return None
    td = td.parent
    # there appears to be multiple ways of structuring the metadata
    # on the home page. cue some nasty special-case hacks...
    if re.match(r'^\s*'+searchfor+r'\s*$', td.decode_contents(), flags=re.I):
        meta = _detag(td.findNextSibling('td'))
        return re.sub('^:', '', meta).strip()
    else:
        meta = _detag(td)
        return re.sub(r'^[^:]+:', '', meta).strip()


def _metadata_from_span(soup, searchfor):
    span = soup.find('span', {'class': re.compile(searchfor, flags=re.I)})
    if span is None:
        return None
    # this metadata might need some cleaning up still :/
    return _detag(span.decode_contents().strip())


def _get_authors(soup):
    aut = (_metadata_from_span(soup, r'author') or _metadata_from_table(soup, r'^\s*by\s*:?\s+'))
    ans = [_('Unknown')]
    if aut is not None:
        ans = string_to_authors(aut)
    return ans


def _get_publisher(soup):
    return (_metadata_from_span(soup, 'imprint') or _metadata_from_table(soup, 'publisher'))


def _get_isbn(soup):
    return (_metadata_from_span(soup, 'isbn') or _metadata_from_table(soup, 'isbn'))


def _get_comments(soup):
    date = (_metadata_from_span(soup, 'cwdate') or _metadata_from_table(soup, 'pub date'))
    pages = (_metadata_from_span(soup, 'pages') or _metadata_from_table(soup, 'pages'))
    try:
        # date span can have copyright symbols in it...
        date = date.replace('\u00a9', '').strip()
        # and pages often comes as '(\d+ pages)'
        pages = re.search(r'\d+', pages).group(0)
        return 'Published %s, %s pages.' % (date, pages)
    except:
        pass
    return None


def _get_cover(soup, rdr):
    ans = None
    try:
        ans = soup.find('img', alt=re.compile('cover', flags=re.I))['src']
    except TypeError:
        # meeehh, no handy alt-tag goodness, try some hackery
        # the basic idea behind this is that in general, the cover image
        # has a height:width ratio of ~1.25, whereas most of the nav
        # buttons are decidedly less than that.
        # what we do in this is work out that ratio, take 1.25 off it and
        # save the absolute value when we sort by this value, the smallest
        # one is most likely to be the cover image, hopefully.
        r = {}
        for img in soup('img'):
            try:
                r[abs(float(re.search(r'[0-9.]+',
                    img['height']).group())/float(re.search(r'[0-9.]+',
                        img['width']).group())-1.25)] = img['src']
            except KeyError:
                # interestingly, occasionally the only image without height
                # or width attrs is the cover...
                r[0] = img['src']
            except:
                # Probably invalid width, height aattributes, ignore
                continue
        if r:
            l = sorted(iterkeys(r))
            ans = r[l[0]]
    # this link comes from the internal html, which is in a subdir
    if ans is not None:
        try:
            ans = rdr.GetFile(ans)
        except:
            ans = rdr.root + "/" + ans
            try:
                ans = rdr.GetFile(ans)
            except:
                ans = None
        if ans is not None:
            from PIL import Image
            import io
            buf = io.BytesIO()
            try:
                Image.open(io.BytesIO(ans)).convert('RGB').save(buf, 'JPEG')
                ans = buf.getvalue()
            except:
                ans = None
    return ans


def get_metadata_from_reader(rdr):
    raw = rdr.GetFile(rdr.home)
    home = BeautifulSoup(xml_to_unicode(raw, strip_encoding_pats=True,
        resolve_entities=True)[0])

    title = rdr.title
    try:
        x = rdr.GetEncoding()
        codecs.lookup(x)
        enc = x
    except:
        enc = 'cp1252'
    title = force_unicode(title, enc)
    authors = _get_authors(home)
    mi = MetaInformation(title, authors)
    publisher = _get_publisher(home)
    if publisher:
        mi.publisher = publisher
    isbn = _get_isbn(home)
    if isbn:
        mi.isbn = isbn
    comments = _get_comments(home)
    if comments:
        mi.comments = comments

    cdata = _get_cover(home, rdr)
    if cdata is not None:
        mi.cover_data = ('jpg', cdata)

    return mi


def get_metadata(stream):
    with TemporaryFile('_chm_metadata.chm') as fname:
        with open(fname, 'wb') as f:
            f.write(stream.read())
        from calibre.ebooks.chm.reader import CHMReader
        rdr = CHMReader(fname, default_log)
        return get_metadata_from_reader(rdr)
