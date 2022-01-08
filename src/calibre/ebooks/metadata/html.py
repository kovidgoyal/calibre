#!/usr/bin/env python


__license__   = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'
'''
Try to read metadata from an HTML file.
'''

import re
import unittest

from collections import defaultdict
from html5_parser import parse
from lxml.etree import Comment

from calibre.ebooks.metadata import string_to_authors, authors_to_string
from calibre.ebooks.metadata.book.base import Metadata
from calibre.ebooks.chardet import xml_to_unicode
from calibre import replace_entities, isbytestring
from calibre.utils.date import parse_date, is_date_undefined
from polyglot.builtins import iteritems


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
rmap_comment = {v:k for k, v in iteritems(COMMENT_NAMES)}
rmap_meta = {v:k for k, l in iteritems(META_NAMES) for v in l}


# Extract an HTML attribute value, supports both single and double quotes and
# single quotes inside double quotes and vice versa.
attr_pat = r'''(?:(?P<sq>')|(?P<dq>"))(?P<content>(?(sq)[^']+|[^"]+))(?(sq)'|")'''


def handle_comment(data, comment_tags):
    if not hasattr(handle_comment, 'pat'):
        handle_comment.pat = re.compile(r'''(?P<name>\S+)\s*=\s*%s''' % attr_pat)
    for match in handle_comment.pat.finditer(data):
        x = match.group('name')
        field = None
        try:
            field = rmap_comment[x]
        except KeyError:
            pass
        if field:
            comment_tags[field].append(replace_entities(match.group('content')))


def parse_metadata(src):
    root = parse(src)
    comment_tags = defaultdict(list)
    meta_tags = defaultdict(list)
    meta_tag_ids = defaultdict(list)
    title = ''
    identifier_pat = re.compile(r'(?:dc|dcterms)[.:]identifier(?:\.|$)', flags=re.IGNORECASE)
    id_pat2 = re.compile(r'(?:dc|dcterms)[.:]identifier$', flags=re.IGNORECASE)

    for comment in root.iterdescendants(tag=Comment):
        if comment.text:
            handle_comment(comment.text, comment_tags)

    for q in root.iterdescendants(tag='title'):
        if q.text:
            title = q.text
            break

    for meta in root.iterdescendants(tag='meta'):
        name, content = meta.get('name'), meta.get('content')
        if not name or not content:
            continue
        if identifier_pat.match(name) is not None:
            scheme = None
            if id_pat2.match(name) is not None:
                scheme = meta.get('scheme')
            else:
                elements = re.split(r'[.:]', name)
                if len(elements) == 3 and not meta.get('scheme'):
                    scheme = elements[2].strip()
            if scheme:
                meta_tag_ids[scheme.lower()].append(content)
        else:
            x = name.lower()
            field = None
            try:
                field = rmap_meta[x]
            except KeyError:
                try:
                    field = rmap_meta[x.replace(':', '.')]
                except KeyError:
                    pass
            if field:
                meta_tags[field].append(content)

    return comment_tags, meta_tags, meta_tag_ids, title


def get_metadata_(src, encoding=None):
    # Meta data definitions as in
    # https://www.mobileread.com/forums/showpost.php?p=712544&postcount=9

    if isbytestring(src):
        if not encoding:
            src = xml_to_unicode(src)[0]
        else:
            src = src.decode(encoding, 'replace')
    src = src[:150000]  # Searching shouldn't take too long
    comment_tags, meta_tags, meta_tag_ids, title_tag = parse_metadata(src)

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
    for field in ('publisher', 'isbn'):
        val = get(field)
        if val:
            setattr(mi, field, val)

    # Multi-value text fields
    for field in ('languages',):
        val = get_all(field)
        if val:
            setattr(mi, field, val)

    # HTML fields
    for field in ('comments',):
        val = get(field)
        if val:
            setattr(mi, field, val.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;').replace("'", '&apos;'))

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
            if mi.rating > 10:
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


class MetadataHtmlTest(unittest.TestCase):

    def compare_metadata(self, meta_a, meta_b):
        for attr in (
            'title', 'authors', 'publisher', 'isbn', 'languages', 'pubdate', 'timestamp', 'series',
            'series_index', 'rating', 'comments', 'tags', 'identifiers'
        ):
            self.assertEqual(getattr(meta_a, attr), getattr(meta_b, attr))

    def get_stream(self, test):
        from io import BytesIO

        raw = b'''\
<html>
    <head>
'''

        if test in {'title', 'meta_single', 'meta_multi', 'comment_single', 'comment_multi'}:
            raw += b'''\
        }
        <title>A Title Tag &amp;amp; Title &#x24B8;</title>
'''

        if test in {'meta_single', 'meta_multi', 'comment_single', 'comment_multi'}:
            raw += b'''\
        <meta name="dc:title" content="A Meta Tag &amp;amp; Title &#9400;" />
        <meta name="dcterms.creator.aut" content="George Washington" />
        <meta name="dc.publisher" content="Publisher A" />
        <meta name="isbn" content="1234567890" />
        <meta name="dc.language" content="English" />
        <meta name="dc.date.published" content="2019-01-01" />
        <meta name="dcterms.created" content="2018-01-01" />
        <meta name="series" content="Meta Series" />
        <meta name="seriesnumber" content="1" />
        <meta name="rating" content="" />
        <meta name="dc.description" content="" />
        <meta name="tags" content="tag a, tag b" />
        <meta name="dc.identifier.url" content="" />
        <meta name="dc.identifier" scheme="" content="invalid" />
        <meta name="dc.identifier." content="still invalid" />
        <meta name="dc.identifier.conflicting" scheme="schemes" content="are also invalid" />
        <meta name="dc.identifier.custom.subid" content="invalid too" />
'''

        if test in {'meta_multi', 'comment_single', 'comment_multi'}:
            raw += b'''\
        <meta name="title" content="A Different Meta Tag &amp;amp; Title &#9400;" />
        <meta name="author" content="John Adams with Thomas Jefferson" />
        <meta name="publisher" content="Publisher B" />
        <meta name="isbn" content="2345678901" />
        <meta name="dcterms.language" content="Spanish" />
        <meta name="date of publication" content="2017-01-01" />
        <meta name="timestamp" content="2016-01-01" />
        <meta name="series" content="Another Meta Series" />
        <meta name="series.index" content="2" />
        <meta name="rating" content="8" />
        <meta name="comments" content="meta &quot;comments&quot; &#x2665; HTML &amp;amp;" />
        <meta name="tags" content="tag c" />
        <meta name="dc.identifier.url" content="http://google.com/search?q=calibre" />
'''

        if test in {'comment_single', 'comment_multi'}:
            raw += b'''\
        <!-- TITLE="A Comment Tag &amp;amp; Title &#9400;" -->
        <!-- AUTHOR="James Madison and James Monroe" -->
        <!-- PUBLISHER="Publisher C" -->
        <!-- ISBN="3456789012" -->
        <!-- LANGUAGE="French" -->
        <!-- PUBDATE="2015-01-01" -->
        <!-- TIMESTAMP="2014-01-01" -->
        <!-- SERIES="Comment Series" -->
        <!-- SERIESNUMBER="3" -->
        <!-- RATING="20" -->
        <!-- COMMENTS="comment &quot;comments&quot; &#x2665; HTML -- too &amp;amp;" -->
        <!-- TAGS="tag d" -->
'''

        if test in {'comment_multi'}:
            raw += b'''\
        <!-- TITLE="Another Comment Tag &amp;amp; Title &#9400;" -->
        <!-- AUTHOR="John Quincy Adams" -->
        <!-- PUBLISHER="Publisher D" -->
        <!-- ISBN="4567890123" -->
        <!-- LANGUAGE="Japanese" -->
        <!-- PUBDATE="2013-01-01" -->
        <!-- TIMESTAMP="2012-01-01" -->
        <!-- SERIES="Comment Series 2" -->
        <!-- SERIESNUMBER="4" -->
        <!-- RATING="1" -->
        <!-- COMMENTS="comment &quot;comments&quot; &#x2665; HTML -- too &amp;amp; for sure" -->
        <!-- TAGS="tag e, tag f" -->
'''

        raw += b'''\
    </head>
    <body>
    </body>
</html>
'''
        return BytesIO(raw)

    def test_input_title(self):
        stream_meta = get_metadata(self.get_stream('title'))
        canon_meta = Metadata('A Title Tag &amp; Title Ⓒ', [_('Unknown')])
        self.compare_metadata(stream_meta, canon_meta)

    def test_input_meta_single(self):
        stream_meta = get_metadata(self.get_stream('meta_single'))
        canon_meta = Metadata('A Meta Tag &amp; Title Ⓒ', ['George Washington'])
        canon_meta.publisher = 'Publisher A'
        canon_meta.languages = ['English']
        canon_meta.pubdate = parse_date('2019-01-01')
        canon_meta.timestamp = parse_date('2018-01-01')
        canon_meta.series = 'Meta Series'
        canon_meta.series_index = float(1)
        # canon_meta.rating = float(0)
        # canon_meta.comments = ''
        canon_meta.tags = ['tag a', 'tag b']
        canon_meta.set_identifiers({'isbn': '1234567890'})
        self.compare_metadata(stream_meta, canon_meta)

    def test_input_meta_multi(self):
        stream_meta = get_metadata(self.get_stream('meta_multi'))
        canon_meta = Metadata('A Meta Tag &amp; Title Ⓒ', ['George Washington', 'John Adams', 'Thomas Jefferson'])
        canon_meta.publisher = 'Publisher A'
        canon_meta.languages = ['English', 'Spanish']
        canon_meta.pubdate = parse_date('2019-01-01')
        canon_meta.timestamp = parse_date('2018-01-01')
        canon_meta.series = 'Meta Series'
        canon_meta.series_index = float(1)
        canon_meta.rating = float(8)
        canon_meta.comments = 'meta &quot;comments&quot; ♥ HTML &amp;amp;'
        canon_meta.tags = ['tag a', 'tag b', 'tag c']
        canon_meta.set_identifiers({'isbn': '1234567890', 'url': 'http://google.com/search?q=calibre'})
        self.compare_metadata(stream_meta, canon_meta)

    def test_input_comment_single(self):
        stream_meta = get_metadata(self.get_stream('comment_single'))
        canon_meta = Metadata('A Comment Tag &amp; Title Ⓒ', ['James Madison', 'James Monroe'])
        canon_meta.publisher = 'Publisher C'
        canon_meta.languages = ['French']
        canon_meta.pubdate = parse_date('2015-01-01')
        canon_meta.timestamp = parse_date('2014-01-01')
        canon_meta.series = 'Comment Series'
        canon_meta.series_index = float(3)
        canon_meta.rating = float(0)
        canon_meta.comments = 'comment &quot;comments&quot; ♥ HTML -- too &amp;amp;'
        canon_meta.tags = ['tag d']
        canon_meta.set_identifiers({'isbn': '3456789012', 'url': 'http://google.com/search?q=calibre'})
        self.compare_metadata(stream_meta, canon_meta)

    def test_input_comment_multi(self):
        stream_meta = get_metadata(self.get_stream('comment_multi'))
        canon_meta = Metadata('A Comment Tag &amp; Title Ⓒ', ['James Madison', 'James Monroe', 'John Quincy Adams'])
        canon_meta.publisher = 'Publisher C'
        canon_meta.languages = ['French', 'Japanese']
        canon_meta.pubdate = parse_date('2015-01-01')
        canon_meta.timestamp = parse_date('2014-01-01')
        canon_meta.series = 'Comment Series'
        canon_meta.series_index = float(3)
        canon_meta.rating = float(0)
        canon_meta.comments = 'comment &quot;comments&quot; ♥ HTML -- too &amp;amp;'
        canon_meta.tags = ['tag d', 'tag e', 'tag f']
        canon_meta.set_identifiers({'isbn': '3456789012', 'url': 'http://google.com/search?q=calibre'})
        self.compare_metadata(stream_meta, canon_meta)


def find_tests():
    return unittest.TestLoader().loadTestsFromTestCase(MetadataHtmlTest)
