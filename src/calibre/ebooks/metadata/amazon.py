from __future__ import with_statement
__license__ = 'GPL 3'
__copyright__ = '2010, sengian <sengian1@gmail.com>'

import sys, re
from threading import RLock

from lxml import html
from lxml.html import soupparser

from calibre import browser
from calibre.ebooks.metadata import check_isbn
from calibre.ebooks.metadata.book.base import Metadata
from calibre.ebooks.chardet import xml_to_unicode
from calibre.ebooks.metadata import MetaInformation, check_isbn, \
    authors_to_sort_string
from calibre.ebooks.metadata.fetch import MetadataSource
from calibre.utils.config import OptionParser
from calibre.library.comments import sanitize_comments_html

asin_cache = {}
cover_url_cache = {}
cache_lock = RLock()

def find_asin(br, isbn):
    q = 'http://www.amazon.com/s?field-keywords='+isbn
    raw = br.open_novisit(q).read()
    raw = xml_to_unicode(raw, strip_encoding_pats=True,
            resolve_entities=True)[0]
    root = html.fromstring(raw)
    revs = root.xpath('//*[@class="asinReviewsSummary" and @name]')
    revs = [x.get('name') for x in revs]
    if revs:
        return revs[0]

def to_asin(br, isbn):
    with cache_lock:
        ans = asin_cache.get(isbn, None)
    if ans:
        return ans
    if ans is False:
        return None
    if len(isbn) == 13:
        try:
            asin = find_asin(br, isbn)
        except:
            import traceback
            traceback.print_exc()
            asin = None
    else:
        asin = isbn
    with cache_lock:
        asin_cache[isbn] = asin if asin else False
    return asin


def get_social_metadata(title, authors, publisher, isbn):
    mi = Metadata(title, authors)
    if not isbn:
        return mi
    isbn = check_isbn(isbn)
    if not isbn:
        return mi
    br = browser()
    asin = to_asin(br, isbn)
    if asin and get_metadata(br, asin, mi):
        return mi
    from calibre.ebooks.metadata.xisbn import xisbn
    for i in xisbn.get_associated_isbns(isbn):
        asin = to_asin(br, i)
        if asin and get_metadata(br, asin, mi):
            return mi
    return mi

def get_cover_url(isbn, br):
    isbn = check_isbn(isbn)
    if not isbn:
        return None
    with cache_lock:
        ans = cover_url_cache.get(isbn, None)
    if ans:
        return ans
    if ans is False:
        return None
    asin = to_asin(br, isbn)
    if asin:
        ans = _get_cover_url(br, asin)
        if ans:
            with cache_lock:
                cover_url_cache[isbn] = ans
            return ans
    from calibre.ebooks.metadata.xisbn import xisbn
    for i in xisbn.get_associated_isbns(isbn):
        asin = to_asin(br, i)
        if asin:
            ans = _get_cover_url(br, asin)
            if ans:
                with cache_lock:
                    cover_url_cache[isbn] = ans
                    cover_url_cache[i] = ans
                return ans
    with cache_lock:
        cover_url_cache[isbn] = False
    return None

def _get_cover_url(br, asin):
    q = 'http://amzn.com/'+asin
    try:
        raw = br.open_novisit(q).read()
    except Exception, e:
        if callable(getattr(e, 'getcode', None)) and \
                e.getcode() == 404:
            return None
        raise
    if '<title>404 - ' in raw:
        return None
    raw = xml_to_unicode(raw, strip_encoding_pats=True,
            resolve_entities=True)[0]
    try:
        root = soupparser.fromstring(raw)
    except:
        return False

    imgs = root.xpath('//img[@id="prodImage" and @src]')
    if imgs:
        src = imgs[0].get('src')
        parts = src.split('/')
        if len(parts) > 3:
            bn = parts[-1]
            sparts = bn.split('_')
            if len(sparts) > 2:
                bn = sparts[0] + sparts[-1]
                return ('/'.join(parts[:-1]))+'/'+bn
    return None


def get_metadata(br, asin, mi):
    q = 'http://amzn.com/'+asin
    try:
        raw = br.open_novisit(q).read()
    except Exception, e:
        if callable(getattr(e, 'getcode', None)) and \
                e.getcode() == 404:
            return False
        raise
    if '<title>404 - ' in raw:
        return False
    raw = xml_to_unicode(raw, strip_encoding_pats=True,
            resolve_entities=True)[0]
    try:
        root = soupparser.fromstring(raw)
    except:
        return False
    ratings = root.xpath('//form[@id="handleBuy"]/descendant::*[@class="asinReviewsSummary"]')
    if ratings:
        pat = re.compile(r'([0-9.]+) out of (\d+) stars')
        r = ratings[0]
        for elem in r.xpath('descendant::*[@title]'):
            t = elem.get('title')
            m = pat.match(t)
            if m is not None:
                try:
                    default = utcnow().replace(day=15)
                    if self.lang != 'all':
                        d = replace_months(d, self.lang)
                    d = parse_date(d, assume_utc=True, default=default)
                    mi.pubdate = d
                except:
                    report(verbose)
        #ISBN
        elt = filter(lambda x: self.reisbn.search(x.find('b').text), elts)
        if elt:
            isbn = elt[0].find('b').tail.replace('-', '').strip()
            if check_isbn(isbn):
                    mi.isbn = unicode(isbn)
            elif len(elt) > 1:
                isbnone = elt[1].find('b').tail.replace('-', '').strip()
                if check_isbn(isbnone):
                    mi.isbn = unicode(isbnone)
            else:
                #assume ASIN-> find a check for asin
                mi.isbn = unicode(isbn)
        #Langue
        elt = filter(lambda x: self.relang.search(x.find('b').text), elts)
        if elt:
            langue = elt[0].find('b').tail.strip()
            if langue:
                mi.language = unicode(langue)
        #ratings
        elt = filter(lambda x: self.reratelt.search(x.find('b').text), elts)
        if elt:
            ratings = elt[0].find_class('swSprite')
            if ratings:
                ratings = self.rerat.findall(ratings[0].get('title'))
                if len(ratings) == 2:
                    mi.rating = float(ratings[0])/float(ratings[1]) * 5
        return mi

    def fill_MI(self, entry, verbose):
        try:
            title = self.get_title(entry)
            authors = self.get_authors(entry)
        except Exception, e:
            if verbose:
                print _('Failed to get all details for an entry')
                print e
                print _('URL who failed: %s') % x
                report(verbose)
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
            import socket
            report(verbose)
            if callable(getattr(e, 'getcode', None)) and \
                    e.getcode() == 404:
                return None
            attr = getattr(e, 'args', [None])
            attr = attr if attr else [None]
            if isinstance(attr[0], socket.timeout):
                raise AmazonError(_('Amazon timed out. Try again later.'))
            raise AmazonError(_('Amazon encountered an error.'))
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

    def fetchdatathread(self, qbr, qsync, nb, url, verbose):
        try:
            browser = qbr.get(True)
            entry = self.get_individual_metadata(url, browser, verbose)
        except:
            report(verbose)
            entry = None
        finally:
            qbr.put(browser, True)
            qsync.put((nb, entry), True)

    def producer(self, sync, urls, br, verbose=False):
        for i in xrange(len(urls)):
            thread = Thread(target=self.fetchdatathread, 
                        args=(br, sync, i, urls[i], verbose))
            thread.start()

    def consumer(self, sync, syncbis, br, total_entries, verbose=False):
        i=0
        self.extend([None]*total_entries)
        while i < total_entries:
            rq = sync.get(True)
            nb = int(rq[0])
            entry = rq[1]
            i+=1
            if entry is not None:
                mi = self.fill_MI(entry, verbose)
                if mi is not None:
                    mi.tags, atag = self.get_tags(entry, verbose)
                    self[nb] = mi
                    if atag:
                        thread = Thread(target=self.fetchdatathread, 
                                args=(br, syncbis, nb, mi.tags, verbose))
                        thread.start()
                    else:
                        syncbis.put((nb, None), True)

    def final(self, sync, total_entries, verbose):
        i=0
        while i < total_entries:
            rq = sync.get(True)
            nb = int(rq[0])
            tags = rq[1]
            i+=1
            if tags is not None:
                self[nb].tags = self.get_tags(tags, verbose)[0]

    def populate(self, entries, ibr, verbose=False, brcall=3):
        br = Queue(brcall)
        cbr = Queue(brcall-1)
        
        syncp = Queue(1)
        syncc = Queue(1)
        
        for i in xrange(brcall-1):
            br.put(browser(), True)
            cbr.put(browser(), True)
        br.put(ibr, True)
        
        prod_thread = Thread(target=self.producer, args=(syncp, entries, br, verbose))
        cons_thread = Thread(target=self.consumer, args=(syncp, syncc, cbr, len(entries), verbose))
        fin_thread = Thread(target=self.final, args=(syncc, len(entries), verbose))
        prod_thread.start()
        cons_thread.start()
        fin_thread.start()
        prod_thread.join()
        cons_thread.join()
        fin_thread.join()


def search(title=None, author=None, publisher=None, isbn=None,
           max_results=5, verbose=False, keywords=None, lang='all'):
    br = browser()
    entries, baseurl = Query(title=title, author=author, isbn=isbn, publisher=publisher,
        keywords=keywords, max_results=max_results,rlang=lang)(br, verbose)

    if entries is None or len(entries) == 0:
        return None

    #List of entry
    ans = ResultList(baseurl, lang)
    ans.populate(entries, br, verbose)
    return [x for x in ans if x is not None]

def get_social_metadata(title, authors, publisher, isbn, verbose=False,
        max_results=1, lang='all'):
    mi = MetaInformation(title, authors)
    if not isbn or not check_isbn(isbn):
        return [mi]

    amazresults = search(isbn=isbn, verbose=verbose,
                max_results=max_results, lang=lang)
    if amazresults is None or amazresults[0] is None:
        from calibre.ebooks.metadata.xisbn import xisbn
        for i in xisbn.get_associated_isbns(isbn):
            amazresults = search(isbn=i, verbose=verbose,
                max_results=max_results, lang=lang)
            if amazresults is not None and amazresults[0] is not None:
                break
    if amazresults is None or amazresults[0] is None:
        return [mi]
    
    miaz = amazresults[0]
    if miaz.rating is not None:
        mi.rating = miaz.rating
    if miaz.comments is not None:
        mi.comments = miaz.comments
    if miaz.tags is not None:
        mi.tags = miaz.tags
    return [mi]

def option_parser():
    import textwrap
    parser = OptionParser(textwrap.dedent(\
    _('''\
        %prog [options]

        Fetch book metadata from Amazon. You must specify one of title, author,
        ISBN, publisher or keywords. Will fetch a maximum of 20 matches,
        so you should make your query as specific as possible.
        You can chose the language for metadata retrieval:
        english & french & german
    '''
    )))
    parser.add_option('-t', '--title', help=_('Book title'))
    parser.add_option('-a', '--author', help=_('Book author(s)'))
    parser.add_option('-p', '--publisher', help=_('Book publisher'))
    parser.add_option('-i', '--isbn', help=_('Book ISBN'))
    parser.add_option('-k', '--keywords', help=_('Keywords'))
    parser.add_option('-s', '--social', default=0, action='count',
                      help=_('Get social data only'))
    parser.add_option('-m', '--max-results', default=10,
                      help=_('Maximum number of results to fetch'))
    parser.add_option('-l', '--lang', default='all',
                      help=_('Chosen language for metadata search (en, fr, de)'))
    parser.add_option('-v', '--verbose', default=0, action='count',
                      help=_('Be more verbose about errors'))
    return parser

def main(args=sys.argv):
    import tempfile, os
    tdir = tempfile.gettempdir()
    br = browser()
    for title, isbn in [
            ('Learning Python', '8324616489'), # Test xisbn
            ('Angels & Demons', '9781416580829'), # Test sophisticated comment formatting
            # Random tests
            ('Star Trek: Destiny: Mere Mortals', '9781416551720'),
            ('The Great Gatsby', '0743273567'),
            ]:
        cpath = os.path.join(tdir, title+'.jpg')
        curl = get_cover_url(isbn, br)
        if curl is None:
            print 'No cover found for', title
        else:
            open(cpath, 'wb').write(br.open_novisit(curl).read())
            print 'Cover for', title, 'saved to', cpath

        #import time
        #st = time.time()
        print get_social_metadata(title, None, None, isbn)
        #print '\n\n', time.time() - st, '\n\n'

    return 0

if __name__ == '__main__':
    sys.exit(main())
    # import cProfile
    # sys.exit(cProfile.run("import calibre.ebooks.metadata.amazonbis; calibre.ebooks.metadata.amazonbis.main()"))
    # sys.exit(cProfile.run("import calibre.ebooks.metadata.amazonbis; calibre.ebooks.metadata.amazonbis.main()", "profile"))

# calibre-debug -e "D:\Mes eBooks\Developpement\calibre\src\calibre\ebooks\metadata\amazon.py" -m 5 -a gore -v>data.html