#!/usr/bin/env python2
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'
'''
Try to read metadata from an HTML file.
'''

import re

from calibre.ebooks.metadata import string_to_authors
from calibre.ebooks.metadata.book.base import Metadata
from calibre.ebooks.chardet import xml_to_unicode
from calibre import replace_entities, isbytestring
from calibre.utils.date import parse_date, is_date_undefined


def get_metadata(stream):
    src = stream.read()
    return get_metadata_(src)


COMMENT_NAMES = {
    'title': 'TITLE',
    'authors': 'AUTHOR',
    'publisher': 'PUBLISHER',
    'isbn': 'ISBN',
    'language': 'LANGUAGE',
    'pubdate': 'PUBDATE',
    'timestamp': 'TIMESTAMP',
    'series': 'SERIES',
    'series_index': 'SERIESNUMBER',
    'rating': 'RATING',
    'comments': 'COMMENTS',
    'tags': 'TAGS',
}

META_NAMES = {
    'title' : ('dc.title', 'dcterms.title', 'title'),
    'authors': ('author', 'dc.creator.aut', 'dcterms.creator.aut', 'dc.creator'),
    'publisher': ('publisher', 'dc.publisher', 'dcterms.publisher'),
    'isbn': ('isbn', 'dc.identifier.isbn', 'dcterms.identifier.isbn'),
    'language': ('dc.language', 'dcterms.language'),
    'pubdate': ('pubdate', 'date of publication', 'dc.date.published', 'dc.date.publication', 'dc.date.issued', 'dcterms.issued'),
    'timestamp': ('timestamp', 'date of creation', 'dc.date.created', 'dc.date.creation', 'dcterms.created'),
    'series': ('series',),
    'series_index': ('seriesnumber', 'series_index', 'series.index'),
    'rating': ('rating',),
    'comments': ('comments', 'dc.description'),
    'tags': ('tags',),
}

# Extract an HTML attribute value, supports both single and double quotes and
# single quotes inside double quotes and vice versa.
attr_pat = r'''(?:(?P<sq>')|(?P<dq>"))(?P<content>(?(sq)[^']+|[^"]+))(?(sq)'|")'''


def parse_meta_tags(src):
    rmap = {}
    for field, names in META_NAMES.iteritems():
        for name in names:
            rmap[name.lower()] = field
    all_names = '|'.join(rmap)
    ans = {}
    npat = r'''name\s*=\s*['"]{0,1}(?P<name>%s)['"]{0,1}''' % all_names
    cpat = 'content\s*=\s*%s' % attr_pat
    for pat in (
        '<meta\s+%s\s+%s' % (npat, cpat),
        '<meta\s+%s\s+%s' % (cpat, npat),
    ):
        for match in re.finditer(pat, src, flags=re.IGNORECASE):
            x = match.group('name').lower()
            try:
                field = rmap[x]
            except KeyError:
                try:
                    field = rmap[x.replace(':', '.')]
                except KeyError:
                    continue

            if field not in ans:
                ans[field] = replace_entities(match.group('content'))
            if len(ans) == len(META_NAMES):
                return ans
    return ans


def parse_comment_tags(src):
    all_names = '|'.join(COMMENT_NAMES.itervalues())
    rmap = {v:k for k, v in COMMENT_NAMES.iteritems()}
    ans = {}
    for match in re.finditer(r'''<!--\s*(?P<name>%s)\s*=\s*%s''' % (all_names, attr_pat), src):
        field = rmap[match.group('name')]
        if field not in ans:
            ans[field] = replace_entities(match.group('content'))
        if len(ans) == len(COMMENT_NAMES):
            break
    return ans


def get_metadata_(src, encoding=None):
    # Meta data definitions as in
    # https://www.mobileread.com/forums/showpost.php?p=712544&postcount=9

    if isbytestring(src):
        if not encoding:
            src = xml_to_unicode(src)[0]
        else:
            src = src.decode(encoding, 'replace')
    src = src[:150000]  # Searching shouldn't take too long
    comment_tags = parse_comment_tags(src)
    meta_tags = parse_meta_tags(src)

    def get(field):
        ans = comment_tags.get(field, meta_tags.get(field, None))
        if ans:
            ans = ans.strip()
        if not ans:
            ans = None
        return ans

    # Title
    title = get('title')
    if not title:
        pat = re.compile('<title>([^<>]+?)</title>', re.IGNORECASE)
        match = pat.search(src)
        if match:
            title = replace_entities(match.group(1))

    # Author
    authors = get('authors') or _('Unknown')

    # Create MetaInformation with Title and Author
    mi = Metadata(title or _('Unknown'), string_to_authors(authors))

    for field in ('publisher', 'isbn', 'language', 'comments'):
        val = get(field)
        if val:
            setattr(mi, field, val)

    for field in ('pubdate', 'timestamp'):
        try:
            val = parse_date(get(field))
        except:
            pass
        else:
            if not is_date_undefined(val):
                setattr(mi, field, val)

    # SERIES
    series = get('series')
    if series:
        pat = re.compile(r'\[([.0-9]+)\]$')
        match = pat.search(series)
        series_index = None
        if match is not None:
            try:
                series_index = float(match.group(1))
            except:
                pass
            series = series.replace(match.group(), '').strip()
        mi.series = series
        if series_index is None:
            series_index = get('series_index')
            try:
                series_index = float(series_index)
            except:
                pass
        if series_index is not None:
            mi.series_index = series_index

    # RATING
    rating = get('rating')
    if rating:
        try:
            mi.rating = float(rating)
            if mi.rating < 0:
                mi.rating = 0
            if mi.rating > 5:
                mi.rating /= 2.
            if mi.rating > 5:
                mi.rating = 0
        except:
            pass

    # TAGS
    tags = get('tags')
    if tags:
        tags = [x.strip() for x in tags.split(',') if x.strip()]
        if tags:
            mi.tags = tags

    return mi
