#!/usr/bin/env python2
# vim:fileencoding=utf-8
from __future__ import absolute_import, division, print_function, unicode_literals

__license__   = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'
'''
Try to read metadata from an HTML file.
'''

import re

from collections import defaultdict
from HTMLParser import HTMLParser

from calibre.ebooks.metadata import string_to_authors, authors_to_string
from calibre.ebooks.metadata.book.base import Metadata
from calibre.ebooks.chardet import xml_to_unicode
from calibre import replace_entities, isbytestring
from calibre.utils.date import parse_date, is_date_undefined
from polyglot.builtins import iteritems, itervalues


def get_metadata(stream):
    src = stream.read()
    return get_metadata_(src)


COMMENT_NAMES = {
    'title': 'TITLE',
    'authors': 'AUTHOR',
    'publisher': 'PUBLISHER',
    'isbn': 'ISBN',
    'languages': 'LANGUAGE',
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
    'isbn': ('isbn',),
    'languages': ('dc.language', 'dcterms.language'),
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

def parse_metadata(src):
    class MetadataParser(HTMLParser):
        def __init__(self):
            self.comment_tags = defaultdict(list)
            self.meta_tag_ids = defaultdict(list)
            self.meta_tags = defaultdict(list)
            self.title_tag = ''

            self.recording = False
            self.recorded = []
            
            self.rmap_comment = {v:k for k, v in iteritems(COMMENT_NAMES)}
            self.rmap_meta = {v:k for k, l in iteritems(META_NAMES) for v in l}

            HTMLParser.__init__(self)

        def handle_starttag(self, tag, attrs):
            attr_dict = dict(attrs)

            if tag == 'title':
                self.recording = True
                self.recorded = []

            elif tag == 'meta' and re.match(r'(?:dc|dcterms)[.:]identifier(?:\.|$)', attr_dict.get('name', ''), flags=re.IGNORECASE):
                scheme = None
                if re.match(r'(?:dc|dcterms)[.:]identifier$', attr_dict.get('name', ''), flags=re.IGNORECASE):
                    scheme = attr_dict.get('scheme', '').strip()
                elif 'scheme' not in attr_dict:
                    elements = re.split(r'[.:]', attr_dict['name'])
                    if len(elements) == 3:
                        scheme = elements[2].strip()
                if scheme:
                    self.meta_tag_ids[scheme.lower()].append(attr_dict.get('content', ''))

            elif tag == 'meta':
                x = attr_dict.get('name', '').lower()
                field = None
                try:
                    field = self.rmap_meta[x]
                except KeyError:
                    try:
                        field = self.rmap_meta[x.replace(':', '.')]
                    except KeyError:
                        pass
                if field:
                    self.meta_tags[field].append(attr_dict.get('content', ''))

        def handle_data(self, data):
            if self.recording:
                self.recorded.append(data)

        def handle_charref(self, ref):
            if self.recording:
                self.recorded.append(replace_entities("&#%s;" % ref))

        def handle_entityref(self, ref):
            if self.recording:
                self.recorded.append(replace_entities("&%s;" % ref))

        def handle_endtag(self, tag):
            if tag == 'title':
                self.recording = False
                self.title_tag = ''.join(self.recorded)

        def handle_comment(self, data):
            for match in re.finditer(r'''(?P<name>\S+)\s*=\s*%s''' % (attr_pat), data):
                x = match.group('name')
                field = None
                try:
                    field = self.rmap_comment[x]
                except KeyError:
                    pass
                if field:
                    self.comment_tags[field].append(replace_entities(match.group('content')))

    parser = MetadataParser()
    parser.feed(src)

    return (parser.comment_tags, parser.meta_tags, parser.meta_tag_ids, parser.title_tag)

def get_metadata_(src, encoding=None):
    # Meta data definitions as in
    # https://www.mobileread.com/forums/showpost.php?p=712544&postcount=9

    if isbytestring(src):
        if not encoding:
            src = xml_to_unicode(src)[0]
        else:
            src = src.decode(encoding, 'replace')
    src = src[:150000]  # Searching shouldn't take too long
    (comment_tags, meta_tags, meta_tag_ids, title_tag) = parse_metadata(src)

    def get_all(field):
        ans = comment_tags.get(field, meta_tags.get(field, None))
        if ans:
            ans = [x.strip() for x in ans if x.strip()]
        if not ans:
            ans = None
        return ans

    def get(field):
        ans = get_all(field)
        if ans:
            ans = ans[0]
        return ans

    # Title
    title = get('title') or title_tag.strip() or _('Unknown')

    # Author
    authors = authors_to_string(get_all('authors')) or _('Unknown')

    # Create MetaInformation with Title and Author
    mi = Metadata(title, string_to_authors(authors))

    # Single-value text fields
    for field in ('publisher', 'isbn', 'comments'):
        val = get(field)
        if val:
            setattr(mi, field, val)

    # Multi-value text fields
    for field in ('languages',):
        val = get_all(field)
        if val:
            setattr(mi, field, val)

    # Date fields
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
    tags = get_all('tags')
    if tags:
        tags = [x.strip() for s in tags for x in s.split(',') if x.strip()]
        if tags:
            mi.tags = tags

    # IDENTIFIERS
    for (k,v) in iteritems(meta_tag_ids):
        v = [x.strip() for x in v if x.strip()]
        if v:
            mi.set_identifier(k, v[0])

    return mi
