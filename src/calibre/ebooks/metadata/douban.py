from __future__ import with_statement
__license__ = 'GPL 3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>; 2010, Li Fanxi <lifanxi@freemindworld.com>'
__docformat__ = 'restructuredtext en'

import sys, textwrap
import traceback
from urllib import urlencode
from functools import partial
from lxml import etree

from calibre import browser, preferred_encoding
from calibre.ebooks.metadata import MetaInformation
from calibre.utils.config import OptionParser
from calibre.ebooks.metadata.fetch import MetadataSource
from calibre.utils.date import parse_date, utcnow

NAMESPACES = {
              'openSearch':'http://a9.com/-/spec/opensearchrss/1.0/',
              'atom' : 'http://www.w3.org/2005/Atom',
              'db': 'http://www.douban.com/xmlns/'
            }
XPath = partial(etree.XPath, namespaces=NAMESPACES)
total_results  = XPath('//openSearch:totalResults')
start_index    = XPath('//openSearch:startIndex')
items_per_page = XPath('//openSearch:itemsPerPage')
entry          = XPath('//atom:entry')
entry_id       = XPath('descendant::atom:id')
title          = XPath('descendant::atom:title')
description    = XPath('descendant::atom:summary')
publisher      = XPath("descendant::db:attribute[@name='publisher']")
isbn           = XPath("descendant::db:attribute[@name='isbn13']")
date           = XPath("descendant::db:attribute[@name='pubdate']")
creator        = XPath("descendant::db:attribute[@name='author']")
tag            = XPath("descendant::db:tag")

CALIBRE_DOUBAN_API_KEY = '0bd1672394eb1ebf2374356abec15c3d'

class DoubanBooks(MetadataSource):

    name = 'Douban Books'
    description = _('Downloads metadata from Douban.com')
    supported_platforms = ['windows', 'osx', 'linux'] # Platforms this plugin will run on
    author              = 'Li Fanxi <lifanxi@freemindworld.com>' # The author of this plugin
    version             = (1, 0, 1)   # The version number of this plugin

    def fetch(self):
        try:
            self.results = search(self.title, self.book_author, self.publisher,
                                  self.isbn, max_results=10,
                                  verbose=self.verbose)
        except Exception as e:
            self.exception = e
            self.tb = traceback.format_exc()

def report(verbose):
    if verbose:
        import traceback
        traceback.print_exc()

class Query(object):

    SEARCH_URL = 'http://api.douban.com/book/subjects?'
    ISBN_URL = 'http://api.douban.com/book/subject/isbn/'

    type = "search"

    def __init__(self, title=None, author=None, publisher=None, isbn=None,
                 max_results=20, start_index=1, api_key=''):
        assert not(title is None and author is None and publisher is None and \
                   isbn is None)
        assert (int(max_results) < 21)
        q = ''
        if isbn is not None:
            q = isbn
            self.type = 'isbn'
        else:
            def build_term(parts):
                return ' '.join(x for x in parts)
            if title is not None:
                q += build_term(title.split())
            if author is not None:
                q += (' ' if q else '') + build_term(author.split())
            if publisher is not None:
                q += (' ' if q else '') + build_term(publisher.split())
            self.type = 'search'

        if isinstance(q, unicode):
            q = q.encode('utf-8')

        if self.type == "isbn":
            self.url = self.ISBN_URL + q
            if api_key != '':
                self.url = self.url + "?apikey=" + api_key
        else:
            self.url = self.SEARCH_URL+urlencode({
                    'q':q,
                    'max-results':max_results,
                    'start-index':start_index,
                    })
            if api_key != '':
                self.url = self.url + "&apikey=" + api_key

    def __call__(self, browser, verbose):
        if verbose:
            print 'Query:', self.url
        if self.type == "search":
            feed = etree.fromstring(browser.open(self.url).read())
            total = int(total_results(feed)[0].text)
            start = int(start_index(feed)[0].text)
            entries = entry(feed)
            new_start = start + len(entries)
            if new_start > total:
                new_start = 0
            return entries, new_start
        elif self.type == "isbn":
            feed = etree.fromstring(browser.open(self.url).read())
            entries = entry(feed)
            return entries, 0

class ResultList(list):

    def get_description(self, entry, verbose):
        try:
            desc = description(entry)
            if desc:
                return 'SUMMARY:\n'+desc[0].text
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

    def get_tags(self, entry, verbose):
        try:
            btags = [x.attrib["name"] for x in tag(entry)]
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

    def get_isbn(self, entry, verbose):
        try:
            isbn13 = isbn(entry)[0].text
        except Exception:
            isbn13 = None
        return isbn13

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

    def populate(self, entries, browser, verbose=False, api_key=''):
        for x in entries:
            try:
                id_url = entry_id(x)[0].text
                title = self.get_title(x)
            except:
                report(verbose)
            mi = MetaInformation(title, self.get_authors(x))
            try:
                if api_key != '':
                    id_url = id_url + "?apikey=" + api_key
                raw = browser.open(id_url).read()
                feed = etree.fromstring(raw)
                x = entry(feed)[0]
            except Exception as e:
                if verbose:
                    print 'Failed to get all details for an entry'
                    print e
            mi.comments = self.get_description(x, verbose)
            mi.tags = self.get_tags(x, verbose)
            mi.isbn = self.get_isbn(x, verbose)
            mi.publisher = self.get_publisher(x, verbose)
            mi.pubdate = self.get_date(x, verbose)
            self.append(mi)

def search(title=None, author=None, publisher=None, isbn=None,
           verbose=False, max_results=40, api_key=None):
    br   = browser()
    start, entries = 1, []

    if api_key is None:
        api_key = CALIBRE_DOUBAN_API_KEY

    while start > 0 and len(entries) <= max_results:
        new, start = Query(title=title, author=author, publisher=publisher,
                       isbn=isbn, max_results=max_results, start_index=start, api_key=api_key)(br, verbose)
        if not new:
            break
        entries.extend(new)

    entries = entries[:max_results]

    ans = ResultList()
    ans.populate(entries, br, verbose, api_key)
    return ans

def option_parser():
    parser = OptionParser(textwrap.dedent(
        '''\
        %prog [options]

        Fetch book metadata from Douban. You must specify one of title, author,
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
                         verbose=opts.verbose, max_results=int(opts.max_results))
    except AssertionError:
        report(True)
        parser.print_help()
        return 1
    for result in results:
        print unicode(result).encode(preferred_encoding)
        print

if __name__ == '__main__':
    sys.exit(main())
