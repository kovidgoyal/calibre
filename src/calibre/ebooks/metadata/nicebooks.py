from __future__ import with_statement
__license__ = 'GPL 3'
__copyright__ = '2010, sengian <sengian1@gmail.com>'
__docformat__ = 'restructuredtext en'

import sys, textwrap, re, traceback, socket
from urllib import urlencode
from functools import partial
from math import ceil
from copy import deepcopy

from lxml import html
from lxml.html import soupparser

from calibre.utils.date import parse_date, utcnow
from calibre import browser, preferred_encoding
from calibre.ebooks.chardet import xml_to_unicode
from calibre.ebooks.metadata import MetaInformation, check_isbn, \
    authors_to_sort_string
from calibre.ebooks.metadata.fetch import MetadataSource
from calibre.ebooks.metadata.covers import CoverDownload
from calibre.utils.config import OptionParser

class NiceBooks(MetadataSource):

    name = 'Nicebooks'
    description = _('Downloads metadata from french Nicebooks')
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


def report(verbose):
    if verbose:
        import traceback
        traceback.print_exc()

def replace_monthsfr(datefr):
    # Replace french months by english equivalent for parse_date
    frtoen = {
        u'[jJ]anvier': u'jan',
        u'[fF].vrier': u'feb',
        u'[mM]ars': u'mar',
        u'[aA]vril': u'apr',
        u'[mM]ai': u'may',
        u'[jJ]uin': u'jun',
        u'[jJ]uillet': u'jul',
        u'[aA]o.t': u'aug',
        u'[sS]eptembre': u'sep',
        u'[Oo]ctobre': u'oct',
        u'[nN]ovembre': u'nov',
        u'[dD].cembre': u'dec' }
    for k in frtoen.iterkeys():
        tmp = re.sub(k, frtoen[k], datefr)
        if tmp <> datefr: break
    return tmp

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
            print 'Query:', self.BASE_URL+self.urldata
        
        try:
            raw = browser.open_novisit(self.BASE_URL+self.urldata, timeout=timeout).read()
        except Exception, e:
            report(verbose)
            if callable(getattr(e, 'getcode', None)) and \
                    e.getcode() == 404:
                return
            raise
        if '<title>404 - ' in raw:
            return
        raw = xml_to_unicode(raw, strip_encoding_pats=True,
                resolve_entities=True)[0]
        try:
            feed = soupparser.fromstring(raw)
        except:
            return
        
        #nb of page to call
        try:
            nbresults = int(feed.xpath("//div[@id='topbar']/b")[0].text)
        except:
            #direct hit
            return [feed]
        
        nbpagetoquery = ceil(min(nbresults, self.max_results)/10)
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
                    continue
                pages.append(feed)
        
        results = []
        for x in pages:
            results.extend([i.find_class('title')[0].get('href') \
                for i in x.xpath("//ul[@id='results']/li")])
        return results[:self.max_results]

class ResultList(list):
    
    BASE_URL = 'http://fr.nicebooks.com'
 
    def __init__(self):
        self.repub = re.compile(u'\s*.diteur\s*', re.I)
        self.reauteur = re.compile(u'\s*auteur.*', re.I)
        self.reautclean = re.compile(u'\s*\(.*\)\s*')

    def get_title(self, entry):
        title = deepcopy(entry.find("div[@id='book-info']"))
        title.remove(title.find("dl[@title='Informations sur le livre']"))
        title = ' '.join([i.text_content() for i in title.iterchildren()])
        return unicode(title.replace('\n', ''))

    def get_authors(self, entry):
        author = entry.find("div[@id='book-info']/dl[@title='Informations sur le livre']")
        authortext = []
        for x in author.getiterator('dt'):
            if self.reauteur.match(x.text):
                elt = x.getnext()
                i = 0
                while elt.tag <> 'dt' and i < 20:
                    authortext.append(unicode(elt.text_content()))
                    elt = elt.getnext()
                    i += 1
                break
        if len(authortext) == 1:
            authortext = [self.reautclean.sub('', authortext[0])]
        return authortext

    def get_description(self, entry, verbose):
        try:
            return 'RESUME:\n' + unicode(entry.xpath("//p[@id='book-description']")[0].text)
        except:
            report(verbose)
            return None

    def get_publisher(self, entry):
        publisher = entry.find("div[@id='book-info']/dl[@title='Informations sur le livre']")
        publitext = None
        for x in publisher.getiterator('dt'):
            if self.repub.match(x.text):
                publitext = x.getnext().text_content()
                break
        return unicode(publitext).strip()

    def get_date(self, entry, verbose):
        date = entry.find("div[@id='book-info']/dl[@title='Informations sur le livre']")
        d = ''
        for x in date.getiterator('dt'):
            if x.text == 'Date de parution':
                d = x.getnext().text_content()
                break
        if len(d) == 0:
            return None
        try:
            default = utcnow().replace(day=15)
            d = replace_monthsfr(d)
            d = parse_date(d, assume_utc=True, default=default)
        except:
            report(verbose)
            d = None
        return d

    def get_ISBN(self, entry):
        isbn = entry.find("div[@id='book-info']/dl[@title='Informations sur le livre']")
        isbntext = None
        for x in isbn.getiterator('dt'):
            if x.text == 'ISBN':
                isbntext = x.getnext().text_content()
                if not check_isbn(isbntext):
                    return None
                isbntext = isbntext.replace('-', '')
                break
        return unicode(isbntext)

    def get_language(self, entry):
        language = entry.find("div[@id='book-info']/dl[@title='Informations sur le livre']")
        langtext = None
        for x in language.getiterator('dt'):
            if x.text == 'Langue':
                langtext = x.getnext().text_content()
                break
        return unicode(langtext).strip()

    def fill_MI(self, entry, title, authors, verbose):
        mi = MetaInformation(title, authors)
        mi.comments = self.get_description(entry, verbose)
        mi.publisher = self.get_publisher(entry)
        mi.pubdate = self.get_date(entry, verbose)
        mi.isbn = self.get_ISBN(entry)
        mi.author_sort = authors_to_sort_string(authors)
        mi.language = self.get_language(entry)
        return mi

    def get_individual_metadata(self, browser, linkdata, verbose):
        try:
            raw = browser.open_novisit(self.BASE_URL + linkdata).read()
        except Exception, e:
            report(verbose)
            if callable(getattr(e, 'getcode', None)) and \
                    e.getcode() == 404:
                return
            raise
        if '<title>404 - ' in raw:
            report(verbose)
            return
        raw = xml_to_unicode(raw, strip_encoding_pats=True,
                resolve_entities=True)[0]
        try:
            feed = soupparser.fromstring(raw)
        except:
            return

        # get results
        return feed.xpath("//div[@id='container']")[0]

    def populate(self, entries, browser, verbose=False):
        for x in entries:
            try:
                entry = self.get_individual_metadata(browser, x, verbose)
                title = self.get_title(entry)
                authors = self.get_authors(entry)
            except Exception, e:
                if verbose:
                    print 'Failed to get all details for an entry'
                    print e
                continue
            self.append(self.fill_MI(entry, title, authors, verbose))

    def populate_single(self, feed, verbose=False):
        try:
            entry = feed.xpath("//div[@id='container']")[0]
            title = self.get_title(entry)
            authors = self.get_authors(entry)
        except Exception, e:
            if verbose:
                print 'Failed to get all details for an entry'
                print e
            return
        self.append(self.fill_MI(entry, title, authors, verbose))

class NiceBooksError(Exception):
    pass

class ISBNNotFound(NiceBooksError):
    pass

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
        isbntext = None
        for x in isbno.getiterator('dt'):
            if x.text == 'ISBN':
                isbntext = x.getnext().text_content()
                break
        if isbntext is not None:
            self.isbnf = True
        return self

    def check_cover(self):
        if self.urlimg:
            return True
        else:
            return False

    def get_cover(self, browser, timeout = 5.):
        try:
            return browser.open_novisit(self.urlimg, timeout=timeout).read(), \
                self.urlimg.rpartition('.')[-1]
        except Exception, err:
            if isinstance(getattr(err, 'args', [None])[0], socket.timeout):
                err = NiceBooksError(_('Nicebooks timed out. Try again later.'))
                raise err
            if not len(self.urlimg):
                if not self.isbnf:
                    raise ISBNNotFound('ISBN: '+self.isbn+_(' not found.'))
                raise NiceBooksError(_('An errror occured with Nicebooks cover fetcher'))


def search(title=None, author=None, publisher=None, isbn=None,
           max_results=5, verbose=False, keywords=None):
    br = browser()
    entries = Query(title=title, author=author, isbn=isbn, publisher=publisher,
        keywords=keywords, max_results=max_results)(br, verbose)
    
    if entries is None or len(entries) == 0:
        return
    
    #List of entry
    ans = ResultList()
    if len(entries) > 1:
        ans.populate(entries, br, verbose)
    else:
        ans.populate_single(entries[0], verbose)
    return ans

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
    '''\
        %prog [options]

        Fetch book metadata from Nicebooks. You must specify one of title, author,
        ISBN, publisher or keywords. Will fetch a maximum of 20 matches,
        so you should make your query as specific as possible.
        It can also get covers if the option is activated.
    '''
    ))
    parser.add_option('-t', '--title', help='Book title')
    parser.add_option('-a', '--author', help='Book author(s)')
    parser.add_option('-p', '--publisher', help='Book publisher')
    parser.add_option('-i', '--isbn', help='Book ISBN')
    parser.add_option('-k', '--keywords', help='Keywords')
    parser.add_option('-c', '--covers', default=0,
                      help='Covers: 1-Check/ 2-Download')
    parser.add_option('-p', '--coverspath', default='',
                      help='Covers files path')
    parser.add_option('-m', '--max-results', default=20,
                      help='Maximum number of results to fetch')
    parser.add_option('-v', '--verbose', default=0, action='count',
                      help='Be more verbose about errors')
    return parser

def main(args=sys.argv):
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
        print 'No result found for this search!'
        return 0
    for result in results:
        print unicode(result).encode(preferred_encoding, 'replace')
        covact = int(opts.covers)
        if  covact == 1:
            textcover = 'No cover found!'
            if check_for_cover(result.isbn):
                textcover = 'A cover was found for this book'
            print textcover
        elif covact == 2:
            cover_data, ext = cover_from_isbn(result.isbn)
            if not ext:
                ext = 'jpg'
            cpath = result.isbn
            if len(opts.coverspath):
                cpath = os.path.normpath(opts.coverspath + '/' + result.isbn)
            oname = os.path.abspath(cpath+'.'+ext)
            open(oname, 'wb').write(cover_data)
            print 'Cover saved to file ', oname
        print

if __name__ == '__main__':
    sys.exit(main())