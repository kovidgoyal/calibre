__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
'''
Interface to isbndb.com. My key HLLXQX2A.
'''

import sys, re
from urllib import urlencode

from lxml import etree

from calibre import browser, preferred_encoding
from calibre.ebooks.chardet import xml_to_unicode
from calibre.ebooks.metadata.fetch import MetadataSource
from calibre.ebooks.metadata import MetaInformation, authors_to_sort_string
from calibre.utils.cleantext import clean_ascii_chars
from calibre.utils.config import OptionParser


class ISBNDB(MetadataSource):

    name = 'IsbnDB'
    description = _('Downloads metadata from isbndb.com')
    version = (1, 0, 1)

    def fetch(self):
        if not self.site_customization:
            return None
        try:
            self.results = search(self.title, self.book_author, self.publisher, self.isbn,
                                   max_results=10, verbose=self.verbose, key=self.site_customization)
        except Exception, e:
            import traceback
            self.exception = e
            self.tb = traceback.format_exc()

    @property
    def string_customization_help(self):
        ans = _('To use isbndb.com you must sign up for a %sfree account%s '
                'and enter your access key below.')
        return '<p>'+ans%('<a href="http://www.isbndb.com">', '</a>')


class ISBNDBError(Exception):
    pass

def report(verbose):
    if verbose:
        import traceback
        traceback.print_exc()


class Query(object):

    BASE_URL = 'http://isbndb.com/api/books.xml?'

    def __init__(self, key, title=None, author=None, publisher=None, isbn=None,
                    keywords=None, max_results=40):
        assert not(title is None and author is None and publisher is None and \
                   isbn is None and keywords is None)
        assert (max_results < 41)
        
        if title == _('Unknown'):
            title=None
        if author == _('Unknown'):
            author=None
        self.maxresults = int(max_results)
        
        if isbn is not None:
            q = isbn
            i = 'isbn'
        elif keywords is not None:
            q = ' '.join([e for e in (title, author, publisher, keywords) \
                if e is not None ])
            q = q.strip()
            i = 'full'
        else:
            q = ' '.join([e for e in (title, author, publisher) \
                if e is not None ])
            q = q.strip()
            if len(q) == 0:
                raise ISBNDBError(_('You must specify at least one of author, title or publisher'))
            i = 'combined'

        if isinstance(q, unicode):
            q = q.encode('utf-8')
        self.url = self.BASE_URL+urlencode({
            'value1':q,
            'results':'subjects,authors,texts,details',
            'access_key':key,
            'index1':i,
            })+'&page_number='

    def brcall(self, browser, url, verbose, timeout):
        if verbose:
            print _('Query: %s') % url
        
        try:
            raw = browser.open_novisit(url, timeout=timeout).read()
        except Exception, e:
            import socket
            report(verbose)
            if callable(getattr(e, 'getcode', None)) and \
                    e.getcode() == 404:
                return None
            attr = getattr(e, 'args', [None])
            attr = attr if attr else [None]
            if isinstance(attr[0], socket.timeout):
                raise ISBNDBError(_('ISBNDB timed out. Try again later.'))
            raise ISBNDBError(_('ISBNDB encountered an error.'))
        if '<title>404 - ' in raw:
            return None
        raw = xml_to_unicode(raw, strip_encoding_pats=True,
                resolve_entities=True)[0]
        try:
            return etree.fromstring(raw)
        except:
            try:
                #remove ASCII invalid chars (normally not needed)
                return etree.fromstring(clean_ascii_chars(raw))
            except:
                return None

    def __call__(self, browser, verbose, timeout = 5.):
        url = self.url+str(1)
        feed = self.brcall(browser, url, verbose, timeout)
        if feed is None:
            return None
        
        # print etree.tostring(feed, pretty_print=True)
        total = int(feed.find('BookList').get('total_results'))
        nbresultstoget = total if total < self.maxresults else self.maxresults
        entries = feed.xpath("./BookList/BookData")
        i=2
        while len(entries) < nbresultstoget:
            url = self.url+str(i)
            feed = self.brcall(browser, url, verbose, timeout)
            i+=1
            if feed is None:
                break
            entries.extend(feed.xpath("./BookList/BookData"))
        return entries[:nbresultstoget]

class ResultList(list):

    def get_description(self, entry, verbose):
        try:
            desc = entry.find('Summary')
            if desc:
                return _(u'SUMMARY:\n%s') % self.output_entry(desc)
        except:
            report(verbose)

    def get_language(self, entry, verbose):
        try:
            return entry.find('Details').get('language')
        except:
            report(verbose)

    def get_title(self, entry):
        title = entry.find('TitleLong')
        if not title:
            title = entry.find('Title')
        return self.output_entry(title)

    def get_authors(self, entry):
        authors = []
        au = entry.find('AuthorsText')
        if au is not None:
            au = self.output_entry(au)
            temp = au.split(u',')
            for au in temp:
                if not au: continue
                authors.extend([a.strip() for a in au.split(u'&')])
        return authors

    def get_author_sort(self, entry, verbose):
        try:
            return self.output_entry(entry.find('Authors').find('Person'))
        except:
            report(verbose)
            return None

    def get_isbn(self, entry, verbose):
        try:
            return unicode(entry.get('isbn13', entry.get('isbn')))
        except:
            report(verbose)

    def get_publisher(self, entry, verbose):
        try:
            return self.output_entry(entry.find('PublisherText'))
        except:
            report(verbose)
            return None
    
    def output_entry(self, entry):
        out = etree.tostring(entry, encoding=unicode, method="text")
        return out.strip()

    def populate(self, entries, verbose):
        for x in entries:
            try:
                title = self.get_title(x)
                authors = self.get_authors(x)
            except Exception, e:
                if verbose:
                    print _('Failed to get all details for an entry')
                    print e
                continue
            mi = MetaInformation(title, authors)
            tmpautsort = self.get_author_sort(x, verbose)
            mi.author_sort = tmpautsort if tmpautsort is not None \
                                else authors_to_sort_string(authors)
            mi.comments = self.get_description(x, verbose)
            mi.isbn = self.get_isbn(x, verbose)
            mi.publisher = self.get_publisher(x, verbose)
            mi.language = self.get_language(x, verbose)
            self.append(mi)


def search(title=None, author=None, publisher=None, isbn=None,
           max_results=10, verbose=False, keywords=None, key=None):
    br = browser()
    entries = Query(key, title=title, author=author, isbn=isbn, publisher=publisher,
        keywords=keywords, max_results=max_results)(br, verbose, timeout = 10.)

    if entries is None or len(entries) == 0:
        return None

    #List of entry
    ans = ResultList()
    ans.populate(entries, verbose)
    ans = [x for x in ans if x is not None]
    return list(dict((book.isbn, book) for book in ans).values())

def option_parser():
    import textwrap
    parser = OptionParser(textwrap.dedent(\
    _('''\
        %prog [options] key

        Fetch metadata for books from isndb.com. You can specify either the
        books ISBN ID or keywords or its title and author.
        If you specify the title and author or keywords, then more than one book may be returned.

        key is the account key you generate after signing up for a free account from isbndb.com.

    ''')))
    parser.add_option('-i', '--isbn', default=None, dest='isbn',
                      help=_('The ISBN ID of the book you want metadata for.'))
    parser.add_option('-a', '--author', dest='author',
                      default=None, help=_('The author whose book to search for.'))
    parser.add_option('-t', '--title', dest='title',
                      default=None, help=_('The title of the book to search for.'))
    parser.add_option('-p', '--publisher', default=None, dest='publisher',
                      help=_('The publisher of the book to search for.'))
    parser.add_option('-k', '--keywords', help=_('Keywords to search for.'))
    parser.add_option('-m', '--max-results', default=10,
                      help=_('Maximum number of results to fetch'))
    parser.add_option('-v', '--verbose', default=0, action='count',
                      help=_('Be more verbose about errors'))
    return parser

def main(args=sys.argv):
    parser = option_parser()
    opts, args = parser.parse_args(args)
    if len(args) != 2:
        parser.print_help()
        print
        print _('You must supply the isbndb.com key')
        return 1
    try:
        results = search(opts.title, opts.author, opts.publisher, opts.isbn, key=args[1],
            keywords=opts.keywords, verbose=opts.verbose, max_results=opts.max_results)
    except AssertionError:
        report(True)
        parser.print_help()
        return 1
    if results is None or len(results) == 0:
        print _('No result found for this search!')
        return 0
    for result in results:
        print unicode(result).encode(preferred_encoding, 'replace')
        print
    return 0

if __name__ == '__main__':
    sys.exit(main())

# calibre-debug -e "H:\Mes eBooks\Developpement\calibre\src\calibre\ebooks\metadata\isbndb.py" -m 5 -a gore -v HLLXQX2A>data.html