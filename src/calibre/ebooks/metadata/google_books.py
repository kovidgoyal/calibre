from __future__ import with_statement
__license__ = 'GPL 3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import sys, textwrap
from urllib import urlencode
from functools import partial

from lxml import etree

from calibre import browser, preferred_encoding
from calibre.ebooks.metadata import MetaInformation
from calibre.utils.config import OptionParser
from calibre.utils.date import parse_date, utcnow

NAMESPACES = {
              'openSearch':'http://a9.com/-/spec/opensearchrss/1.0/',
              'atom' : 'http://www.w3.org/2005/Atom',
              'dc': 'http://purl.org/dc/terms'
            }
XPath = partial(etree.XPath, namespaces=NAMESPACES)

total_results  = XPath('//openSearch:totalResults')
start_index    = XPath('//openSearch:startIndex')
items_per_page = XPath('//openSearch:itemsPerPage')
entry          = XPath('//atom:entry')
entry_id       = XPath('descendant::atom:id')
creator        = XPath('descendant::dc:creator')
identifier     = XPath('descendant::dc:identifier')
title          = XPath('descendant::dc:title')
date           = XPath('descendant::dc:date')
publisher      = XPath('descendant::dc:publisher')
subject        = XPath('descendant::dc:subject')
description    = XPath('descendant::dc:description')
language       = XPath('descendant::dc:language')

def report(verbose):
    if verbose:
        import traceback
        traceback.print_exc()


class Query(object):

    BASE_URL = 'http://books.google.com/books/feeds/volumes?'

    def __init__(self, title=None, author=None, publisher=None, isbn=None,
                 max_results=20, min_viewability='none', start_index=1):
        assert not(title is None and author is None and publisher is None and \
                   isbn is None)
        assert (max_results < 21)
        assert (min_viewability in ('none', 'partial', 'full'))
        q = ''
        if isbn is not None:
            q += 'isbn:'+isbn
        else:
            def build_term(prefix, parts):
                return ' '.join('in'+prefix + ':' + x for x in parts)
            if title is not None:
                q += build_term('title', title.split())
            if author is not None:
                q += ('+' if q else '')+build_term('author', author.split())
            if publisher is not None:
                q += ('+' if q else '')+build_term('publisher', publisher.split())

        if isinstance(q, unicode):
            q = q.encode('utf-8')
        self.url = self.BASE_URL+urlencode({
            'q':q,
            'max-results':max_results,
            'start-index':start_index,
            'min-viewability':min_viewability,
            })

    def __call__(self, browser, verbose):
        if verbose:
            print 'Query:', self.url
        feed = etree.fromstring(browser.open(self.url).read())
        #print etree.tostring(feed, pretty_print=True)
        total = int(total_results(feed)[0].text)
        start = int(start_index(feed)[0].text)
        entries = entry(feed)
        new_start = start + len(entries)
        if new_start > total:
            new_start = 0
        return entries, new_start


class ResultList(list):

    def get_description(self, entry, verbose):
        try:
            desc = description(entry)
            if desc:
                return 'SUMMARY:\n'+desc[0].text
        except:
            report(verbose)

    def get_language(self, entry, verbose):
        try:
            l = language(entry)
            if l:
                return l[0].text
        except:
            report(verbose)

    def get_title(self, entry):
        candidates = [x.text for x in title(entry)]
        return ': '.join(candidates)

    def get_authors(self, entry):
        m = creator(entry)
        if not m:
            m = []
        m = [x.text for x in m]
        return m

    def get_author_sort(self, entry, verbose):
        for x in creator(entry):
            for key, val in x.attrib.items():
                if key.endswith('file-as'):
                    return val

    def get_identifiers(self, entry, mi):
        isbns = []
        for x in identifier(entry):
            t = str(x.text).strip()
            if t[:5].upper() in ('ISBN:', 'LCCN:', 'OCLC:'):
                if t[:5].upper() == 'ISBN:':
                    isbns.append(t[5:])
        if isbns:
            mi.isbn = sorted(isbns, cmp=lambda x,y:cmp(len(x), len(y)))[-1]

    def get_tags(self, entry, verbose):
        try:
            btags = [x.text for x in subject(entry)]
            tags = []
            for t in btags:
                tags.extend([y.strip() for y in t.split('/')])
            tags = list(sorted(list(set(tags))))
        except:
            report(verbose)
            tags = []
        return [x.replace(',', ';') for x in tags]

    def get_publisher(self, entry, verbose):
        try:
            pub = publisher(entry)[0].text
        except:
            pub = None
        return pub

    def get_date(self, entry, verbose):
        try:
            d = date(entry)
            if d:
                default = utcnow().replace(day=15)
                d = parse_date(d[0].text, assume_utc=True, default=default)
            else:
                d = None
        except:
            report(verbose)
            d = None
        return d

    def populate(self, entries, browser, verbose=False):
        for x in entries:
            try:
                id_url = entry_id(x)[0].text
                title = self.get_title(x)
            except:
                report(verbose)
            mi = MetaInformation(title, self.get_authors(x))
            try:
                raw = browser.open(id_url).read()
                feed = etree.fromstring(raw)
                x = entry(feed)[0]
            except Exception as e:
                if verbose:
                    print 'Failed to get all details for an entry'
                    print e
            mi.author_sort = self.get_author_sort(x, verbose)
            mi.comments = self.get_description(x, verbose)
            self.get_identifiers(x, mi)
            mi.tags = self.get_tags(x, verbose)
            mi.publisher = self.get_publisher(x, verbose)
            mi.pubdate = self.get_date(x, verbose)
            mi.language = self.get_language(x, verbose)
            self.append(mi)


def search(title=None, author=None, publisher=None, isbn=None,
           min_viewability='none', verbose=False, max_results=40):
    br   = browser()
    start, entries = 1, []
    while start > 0 and len(entries) <= max_results:
        new, start = Query(title=title, author=author, publisher=publisher,
                       isbn=isbn, min_viewability=min_viewability)(br, verbose)
        if not new:
            break
        entries.extend(new)

    entries = entries[:max_results]

    ans = ResultList()
    ans.populate(entries, br, verbose)
    return ans

def option_parser():
    parser = OptionParser(textwrap.dedent(
        '''\
        %prog [options]

        Fetch book metadata from Google. You must specify one of title, author,
        publisher or ISBN. If you specify ISBN the others are ignored. Will
        fetch a maximum of 100 matches, so you should make your query as
        specific as possible.
        '''
    ))
    parser.add_option('-t', '--title', help='Book title')
    parser.add_option('-a', '--author', help='Book author(s)')
    parser.add_option('-p', '--publisher', help='Book publisher')
    parser.add_option('-i', '--isbn', help='Book ISBN')
    parser.add_option('-m', '--max-results', default=10,
                      help='Maximum number of results to fetch')
    parser.add_option('-v', '--verbose', default=0, action='count',
                      help='Be more verbose about errors')
    return parser

def main(args=sys.argv):
    parser = option_parser()
    opts, args = parser.parse_args(args)
    try:
        results = search(opts.title, opts.author, opts.publisher, opts.isbn,
                         verbose=opts.verbose, max_results=opts.max_results)
    except AssertionError:
        report(True)
        parser.print_help()
        return 1
    for result in results:
        print unicode(result).encode(preferred_encoding)
        print

if __name__ == '__main__':
    sys.exit(main())
