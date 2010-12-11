from __future__ import with_statement
__license__ = 'GPL 3'
__copyright__ = '2010, sengian <sengian1@gmail.com>'
__docformat__ = 'restructuredtext en'

import sys, textwrap, re, traceback, socket
from urllib import urlencode
from math import ceil
from copy import deepcopy

from lxml.html import soupparser

from calibre.utils.date import parse_date, utcnow, replace_months
from calibre.utils.cleantext import clean_ascii_chars
from calibre import browser, preferred_encoding
from calibre.ebooks.chardet import xml_to_unicode
from calibre.ebooks.metadata import MetaInformation, check_isbn, \
    authors_to_sort_string
from calibre.ebooks.metadata.fetch import MetadataSource
from calibre.ebooks.metadata.covers import CoverDownload
from calibre.utils.config import OptionParser

class NiceBooks(MetadataSource):

    name = 'Nicebooks'
    description = _('Downloads metadata from French Nicebooks')
    supported_platforms = ['windows', 'osx', 'linux']
    author = 'Sengian'
    version             = (1, 0, 0)

    def fetch(self):
        try:
            self.results = search(self.title, self.book_author, self.publisher,
                                  self.isbn, max_results=10, verbose=self.verbose)
        except Exception, e:
            self.exception = e
            self.tb = traceback.format_exc()

class NiceBooksCovers(CoverDownload):

    name = 'Nicebooks covers'
    description = _('Downloads covers from french Nicebooks')
    supported_platforms = ['windows', 'osx', 'linux']
    author = 'Sengian'
    type = _('Cover download')
    version             = (1, 0, 0)

    def has_cover(self, mi, ans, timeout=5.):
        if not mi.isbn:
            return False
        br = browser()
        try:
            entry = Query(isbn=mi.isbn, max_results=1)(br, False, timeout)[0]
            if Covers(mi.isbn)(entry).check_cover():
                self.debug('cover for', mi.isbn, 'found')
                ans.set()
        except Exception, e:
            self.debug(e)

    def get_covers(self, mi, result_queue, abort, timeout=5.):
        if not mi.isbn:
            return
        br = browser()
        try:
            entry = Query(isbn=mi.isbn, max_results=1)(br, False, timeout)[0]
            cover_data, ext = Covers(mi.isbn)(entry).get_cover(br, timeout)
            if not ext:
                ext = 'jpg'
            result_queue.put((True, cover_data, ext, self.name))
        except Exception, e:
            result_queue.put((False, self.exception_to_string(e),
                traceback.format_exc(), self.name))


class NiceBooksError(Exception):
    pass

class ISBNNotFound(NiceBooksError):
    pass

def report(verbose):
    if verbose:
        traceback.print_exc()


class Query(object):

    BASE_URL = 'http://fr.nicebooks.com/'

    def __init__(self, title=None, author=None, publisher=None, isbn=None, keywords=None, max_results=20):
        assert not(title is None and author is None and publisher is None \
            and isbn is None and keywords is None)
        assert (max_results < 21)

        self.max_results = int(max_results)

        if isbn is not None:
            q = isbn
        else:
            q = ' '.join([i for i in (title, author, publisher, keywords) \
                if i is not None])

        if isinstance(q, unicode):
            q = q.encode('utf-8')
        self.urldata = 'search?' + urlencode({'q':q,'s':'Rechercher'})

    def __call__(self, browser, verbose, timeout = 5.):
        if verbose:
            print _('Query: %s') % self.BASE_URL+self.urldata

        try:
            raw = browser.open_novisit(self.BASE_URL+self.urldata, timeout=timeout).read()
        except Exception, e:
            report(verbose)
            if callable(getattr(e, 'getcode', None)) and \
                    e.getcode() == 404:
                return None
            if isinstance(getattr(e, 'args', [None])[0], socket.timeout):
                raise NiceBooksError(_('Nicebooks timed out. Try again later.'))
            raise NiceBooksError(_('Nicebooks encountered an error.'))
        if '<title>404 - ' in raw:
            return
        raw = xml_to_unicode(raw, strip_encoding_pats=True,
                resolve_entities=True)[0]
        try:
            feed = soupparser.fromstring(raw)
        except:
            try:
                #remove ASCII invalid chars
                feed = soupparser.fromstring(clean_ascii_chars(raw))
            except:
                return None

        #nb of page to call
        try:
            nbresults = int(feed.xpath("//div[@id='topbar']/b")[0].text)
        except:
            #direct hit
            return [feed], False

        nbpagetoquery = int(ceil(float(min(nbresults, self.max_results))/10))
        pages =[feed]
        if nbpagetoquery > 1:
            for i in xrange(2, nbpagetoquery + 1):
                try:
                    urldata = self.urldata + '&p=' + str(i)
                    raw = browser.open_novisit(self.BASE_URL+urldata, timeout=timeout).read()
                except Exception, e:
                    continue
                if '<title>404 - ' in raw:
                    continue
                raw = xml_to_unicode(raw, strip_encoding_pats=True,
                        resolve_entities=True)[0]
                try:
                    feed = soupparser.fromstring(raw)
                except:
                    try:
                        #remove ASCII invalid chars
                        feed = soupparser.fromstring(clean_ascii_chars(raw))
                    except:
                        continue
                pages.append(feed)

        results = []
        for x in pages:
            results.extend([i.find_class('title')[0].get('href') \
                for i in x.xpath("//ul[@id='results']/li")])
        return results[:self.max_results], True

class ResultList(list):

    BASE_URL = 'http://fr.nicebooks.com'

    def __init__(self, islink):
        self.islink = islink
        self.repub = re.compile(u'\s*.diteur\s*', re.I)
        self.reauteur = re.compile(u'\s*auteur.*', re.I)
        self.reautclean = re.compile(u'\s*\(.*\)\s*')

    def get_title(self, entry):
        title = deepcopy(entry)
        title.remove(title.find("dl[@title='Informations sur le livre']"))
        title = ' '.join([i.text_content() for i in title.iterchildren()])
        return unicode(title.replace('\n', ''))

    def get_authors(self, entry):
        author = entry.find("dl[@title='Informations sur le livre']")
        authortext = []
        for x in author.getiterator('dt'):
            if self.reauteur.match(x.text):
                elt = x.getnext()
                while elt.tag == 'dd':
                    authortext.append(unicode(elt.text_content()))
                    elt = elt.getnext()
                break
        if len(authortext) == 1:
            authortext = [self.reautclean.sub('', authortext[0])]
        return authortext

    def get_description(self, entry, verbose):
        try:
            return u'RESUME:\n' + unicode(entry.getparent().xpath("//p[@id='book-description']")[0].text)
        except:
            report(verbose)
            return None

    def get_book_info(self, entry, mi, verbose):
        entry = entry.find("dl[@title='Informations sur le livre']")
        for x in entry.getiterator('dt'):
            if x.text == 'ISBN':
                isbntext = x.getnext().text_content().replace('-', '')
                if check_isbn(isbntext):
                    mi.isbn = unicode(isbntext)
            elif self.repub.match(x.text):
                mi.publisher = unicode(x.getnext().text_content())
            elif x.text == 'Langue':
                mi.language = unicode(x.getnext().text_content())
            elif x.text == 'Date de parution':
                d = x.getnext().text_content()
                try:
                    default = utcnow().replace(day=15)
                    d = replace_months(d, 'fr')
                    d = parse_date(d, assume_utc=True, default=default)
                    mi.pubdate = d
                except:
                    report(verbose)
        return mi

    def fill_MI(self, data, verbose):
        '''create and return an mi if possible, None otherwise'''
        try:
            entry = data.xpath("//div[@id='container']/div[@id='book-info']")[0]
            title = self.get_title(entry)
            authors = self.get_authors(entry)
        except Exception, e:
            if verbose:
                print 'Failed to get all details for an entry'
                print e
            return None
        mi = MetaInformation(title, authors)
        mi.author_sort = authors_to_sort_string(authors)
        try:
            mi.comments = self.get_description(entry, verbose)
            mi = self.get_book_info(entry, mi, verbose)
        except:
            pass
        return mi

    def get_individual_metadata(self, url, br, verbose):
        try:
            raw = br.open_novisit(url).read()
        except Exception, e:
            report(verbose)
            if callable(getattr(e, 'getcode', None)) and \
                    e.getcode() == 404:
                return None
            if isinstance(getattr(e, 'args', [None])[0], socket.timeout):
                raise NiceBooksError(_('NiceBooks timed out. Try again later.'))
            raise NiceBooksError(_('NiceBooks encountered an error.'))
        if '<title>404 - ' in raw:
            report(verbose)
            return None
        raw = xml_to_unicode(raw, strip_encoding_pats=True,
                resolve_entities=True)[0]
        try:
            return soupparser.fromstring(raw)
        except:
            try:
                #remove ASCII invalid chars
                return soupparser.fromstring(clean_ascii_chars(raw))
            except:
                report(verbose)
                return None

    def populate(self, entries, br, verbose=False):
        if not self.islink:
            #single entry
            self.append(self.fill_MI(entries[0], verbose))
        else:
            #multiple entries
            for x in entries:
                entry = self.get_individual_metadata(self.BASE_URL+x, br, verbose)
                if entry is not None:
                    self.append(self.fill_MI(entry, verbose))

class Covers(object):

    def __init__(self, isbn = None):
        assert isbn is not None
        self.urlimg = ''
        self.isbn = isbn
        self.isbnf = False

    def __call__(self, entry = None):
        try:
            self.urlimg = entry.xpath("//div[@id='book-picture']/a")[0].get('href')
        except:
            return self
        isbno = entry.get_element_by_id('book-info').find("dl[@title='Informations sur le livre']")
        for x in isbno.getiterator('dt'):
            if x.text == 'ISBN' and check_isbn(x.getnext().text_content()):
                self.isbnf = True
                break
        return self

    def check_cover(self):
        return True if self.urlimg else False

    def get_cover(self, browser, timeout = 5.):
        try:
            cover, ext = browser.open_novisit(self.urlimg, timeout=timeout).read(), \
                self.urlimg.rpartition('.')[-1]
            return cover, ext if ext else 'jpg'
        except Exception, err:
            if isinstance(getattr(err, 'args', [None])[0], socket.timeout):
                raise NiceBooksError(_('Nicebooks timed out. Try again later.'))
            if not len(self.urlimg):
                if not self.isbnf:
                    raise ISBNNotFound(_('ISBN: %s not found.') % self.isbn)
                raise NiceBooksError(_('An errror occured with Nicebooks cover fetcher'))


def search(title=None, author=None, publisher=None, isbn=None,
           max_results=5, verbose=False, keywords=None):
    br = browser()
    islink = False
    entries, islink = Query(title=title, author=author, isbn=isbn, publisher=publisher,
        keywords=keywords, max_results=max_results)(br, verbose, timeout = 10.)

    if entries is None or len(entries) == 0:
        return None

    #List of entry
    ans = ResultList(islink)
    ans.populate(entries, br, verbose)
    return [x for x in ans if x is not None]

def check_for_cover(isbn):
    br = browser()
    entry = Query(isbn=isbn, max_results=1)(br, False)[0]
    return Covers(isbn)(entry).check_cover()

def cover_from_isbn(isbn, timeout = 5.):
    br = browser()
    entry = Query(isbn=isbn, max_results=1)(br, False, timeout)[0]
    return Covers(isbn)(entry).get_cover(br, timeout)


def option_parser():
    parser = OptionParser(textwrap.dedent(\
    _('''\
        %prog [options]

        Fetch book metadata from Nicebooks. You must specify one of title, author,
        ISBN, publisher or keywords. Will fetch a maximum of 20 matches,
        so you should make your query as specific as possible.
        It can also get covers if the option is activated.
    ''')
    ))
    parser.add_option('-t', '--title', help=_('Book title'))
    parser.add_option('-a', '--author', help=_('Book author(s)'))
    parser.add_option('-p', '--publisher', help=_('Book publisher'))
    parser.add_option('-i', '--isbn', help=_('Book ISBN'))
    parser.add_option('-k', '--keywords', help=_('Keywords'))
    parser.add_option('-c', '--covers', default=0,
                      help=_('Covers: 1-Check/ 2-Download'))
    parser.add_option('-p', '--coverspath', default='',
                      help=_('Covers files path'))
    parser.add_option('-m', '--max-results', default=20,
                      help=_('Maximum number of results to fetch'))
    parser.add_option('-v', '--verbose', default=0, action='count',
                      help=_('Be more verbose about errors'))
    return parser

def main(args=sys.argv):
    import os
    parser = option_parser()
    opts, args = parser.parse_args(args)
    try:
        results = search(opts.title, opts.author, isbn=opts.isbn, publisher=opts.publisher,
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
        covact = int(opts.covers)
        if  covact == 1:
            textcover = _('No cover found!')
            if check_for_cover(result.isbn):
                textcover = _('A cover was found for this book')
            print textcover
        elif covact == 2:
            cover_data, ext = cover_from_isbn(result.isbn)
            cpath = result.isbn
            if len(opts.coverspath):
                cpath = os.path.normpath(opts.coverspath + '/' + result.isbn)
            oname = os.path.abspath(cpath+'.'+ext)
            open(oname, 'wb').write(cover_data)
            print _('Cover saved to file '), oname
        print

if __name__ == '__main__':
    sys.exit(main())

# calibre-debug -e "H:\Mes eBooks\Developpement\calibre\src\calibre\ebooks\metadata\nicebooks.py" -m 5 -a mankel >data.html