from __future__ import with_statement
__license__ = 'GPL 3'
__copyright__ = '2010, sengian <sengian1@gmail.com>'

import sys, re
from threading import Thread
from Queue import Queue
from urllib import urlencode
from math import ceil

from lxml.html import soupparser, tostring

from calibre.utils.date import parse_date, utcnow, replace_months
from calibre.utils.cleantext import clean_ascii_chars
from calibre.utils.localization import get_lang
from calibre import browser, preferred_encoding
from calibre.ebooks.chardet import xml_to_unicode
from calibre.ebooks.metadata import MetaInformation, check_isbn, \
    authors_to_sort_string
from calibre.ebooks.metadata.fetch import MetadataSource
from calibre.utils.config import OptionParser
from calibre.library.comments import sanitize_comments_html


class Amazon(MetadataSource):

    name = 'Amazon'
    description = _('Downloads metadata from amazon.com')
    supported_platforms = ['windows', 'osx', 'linux']
    author = 'Kovid Goyal & Sengian'
    version = (1, 0, 0)
    has_html_comments = True

    def fetch(self):
        try:
            lang = get_lang()
            lang = lang[:2] if re.match(r'(fr.*|de.*)', lang) else 'all'
            if lang == 'all':
                self.results = search(self.title, self.book_author, self.publisher,
                                  self.isbn, max_results=10, verbose=self.verbose, lang='all')
            else:
                tmploc = ThreadwithResults(search, self.title, self.book_author, 
                                self.publisher,self.isbn, max_results=5,
                                    verbose=self.verbose, lang=lang)
                tmpnoloc = ThreadwithResults(search, self.title, self.book_author,
                                self.publisher, self.isbn, max_results=5,
                                    verbose=self.verbose, lang='all')
                tmploc.start()
                tmpnoloc.start()
                tmploc.join()
                tmpnoloc.join()
                tmploc= tmploc.get_result()
                tmpnoloc= tmpnoloc.get_result()
                
                tempres = None
                if tmpnoloc is not None:
                    tempres = tmpnoloc
                if tmploc is not None:
                    tempres = tmploc
                    if tmpnoloc is not None:
                        tempres.extend(tmpnoloc)
                self.results = tempres
        except Exception, e:
            import traceback
            self.exception = e
            self.tb = traceback.format_exc()

class AmazonSocial(MetadataSource):

    name = 'AmazonSocial'
    metadata_type = 'social'
    description = _('Downloads social metadata from amazon.com')
    supported_platforms = ['windows', 'osx', 'linux']
    author = 'Kovid Goyal & Sengian'
    version = (1, 0, 1)
    has_html_comments = True

    def fetch(self):
        if not self.isbn:
            return
        try:
            lang = get_lang()
            lang = lang[:2] if re.match(r'(fr.*|de.*)', lang) else 'all'
            if lang == 'all':
                self.results = get_social_metadata(self.title, self.book_author, self.publisher,
                                    self.isbn, verbose=self.verbose, lang='all')[0]
            else:
                tmploc = ThreadwithResults(get_social_metadata, self.title, self.book_author, 
                                    self.publisher,self.isbn, verbose=self.verbose, lang=lang)
                tmpnoloc = ThreadwithResults(get_social_metadata, self.title, self.book_author,
                                    self.publisher, self.isbn, verbose=self.verbose, lang='all')
                tmploc.start()
                tmpnoloc.start()
                tmploc.join()
                tmpnoloc.join()
                tmploc= tmploc.get_result()
                if tmploc is not None:
                    tmploc = tmploc[0]
                tmpnoloc= tmpnoloc.get_result()
                if tmpnoloc is not None:
                    tmpnoloc = tmpnoloc[0]
                    if tmpnoloc is not None:
                        if tmploc.rating is None:
                            tmploc.rating = tmpnoloc.rating
                        if tmploc.comments is not None:
                            tmploc.comments = tmpnoloc.comments
                        if tmploc.tags is None:
                            tmploc.tags = tmpnoloc.tags
                self.results = tmploc
        except Exception, e:
            import traceback
            self.exception = e
            self.tb = traceback.format_exc()


def report(verbose):
    if verbose:
        import traceback
        traceback.print_exc()

class AmazonError(Exception):
    pass

class ThreadwithResults(Thread):
    def __init__(self, func, *args, **kargs):
        self.func = func
        self.args = args
        self.kargs = kargs
        self.result = None
        Thread.__init__(self)

    def get_result(self):
        return self.result

    def run(self):
        self.result = self.func(*self.args, **self.kargs)

class Query(object):

    BASE_URL_ALL = 'http://www.amazon.com'
    BASE_URL_FR = 'http://www.amazon.fr'
    BASE_URL_DE = 'http://www.amazon.de'

    def __init__(self, title=None, author=None, publisher=None, isbn=None, keywords=None,
        max_results=20, rlang='all'):
        assert not(title is None and author is None and publisher is None \
            and isbn is None and keywords is None)
        assert (max_results < 21)

        self.max_results = int(max_results)
        self.renbres = re.compile(u'\s*([0-9.,]+)\s*')

        q = {   'search-alias' : 'stripbooks' ,
                'unfiltered' : '1',
                'field-keywords' : '',
                'field-author' : '',
                'field-title' : '',
                'field-isbn' : '',
                'field-publisher' : ''
                #get to amazon detailed search page to get all options
                # 'node' : '',
                # 'field-binding' : '',
                #before, during, after
                # 'field-dateop' : '',
                #month as number
                # 'field-datemod' : '',
                # 'field-dateyear' : '',
                #french only
                # 'field-collection' : '',
                #many options available
            }

        if rlang =='all' or rlang =='en':
            q['sort'] = 'relevanceexprank'
            self.urldata = self.BASE_URL_ALL
        # elif rlang =='es':
            # q['sort'] = 'relevanceexprank'
            # q['field-language'] = 'Spanish'
            # self.urldata = self.BASE_URL_ALL
        # elif rlang =='en':
            # q['sort'] = 'relevanceexprank'
            # q['field-language'] = 'English'
            # self.urldata = self.BASE_URL_ALL
        elif rlang =='fr':
            q['sort'] = 'relevancerank'
            self.urldata = self.BASE_URL_FR
        elif rlang =='de':
            q['sort'] = 'relevancerank'
            self.urldata = self.BASE_URL_DE
        self.baseurl = self.urldata
        
        if title == _('Unknown'):
            title=None
        if author == _('Unknown'):
            author=None
        
        if isbn is not None:
            q['field-isbn'] = isbn.replace('-', '')
        else:
            if title is not None:
                q['field-title'] = title
            if author is not None:
                q['field-author'] = author
            if publisher is not None:
                q['field-publisher'] = publisher
            if keywords is not None:
                q['field-keywords'] = keywords

        if isinstance(q, unicode):
            q = q.encode('utf-8')
        self.urldata += '/gp/search/ref=sr_adv_b/?' + urlencode(q)

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
                raise AmazonError(_('Amazon timed out. Try again later.'))
            raise AmazonError(_('Amazon encountered an error.'))
        if '<title>404 - ' in raw:
            return
        raw = xml_to_unicode(raw, strip_encoding_pats=True,
                resolve_entities=True)[0]
        try:
            return soupparser.fromstring(raw)
        except:
            try:
                #remove ASCII invalid chars
                return soupparser.fromstring(clean_ascii_chars(raw))
            except:
                return None

    def __call__(self, browser, verbose, timeout = 5.):
        feed = self.brcall(browser, self.urldata, verbose, timeout)
        if feed is None:
            return None, self.urldata

        #nb of page
        try:
            nbresults = self.renbres.findall(feed.xpath("//*[@class='resultCount']")[0].text)
            nbresults = [re.sub(r'[.,]', '', x) for x in nbresults]
        except:
            return None, self.urldata

        pages =[feed]
        if len(nbresults) > 1:
            nbpagetoquery = int(ceil(float(min(int(nbresults[2]), self.max_results))/ int(nbresults[1])))
            for i in xrange(2, nbpagetoquery + 1):
                urldata = self.urldata + '&page=' + str(i)
                feed = self.brcall(browser, urldata, verbose, timeout)
                if feed is None:
                    continue
                pages.append(feed)

        results = []
        for x in pages:
            results.extend([i.getparent().get('href') \
                for i in x.xpath("//a/span[@class='srTitle']")])
        return results[:self.max_results], self.baseurl

class ResultList(list):

    def __init__(self, baseurl, lang = 'all'):
        self.baseurl = baseurl
        self.lang = lang
        self.repub = re.compile(u'\((.*)\)')
        self.rerat = re.compile(u'([0-9.]+)')
        self.reattr = re.compile(r'<([a-zA-Z0-9]+)\s[^>]+>')
        self.reoutp = re.compile(r'(?s)<em>--This text ref.*?</em>')
        self.recom = re.compile(r'(?s)<!--.*?-->')
        self.republi = re.compile(u'(Editeur|Publisher|Verlag)', re.I)
        self.reisbn = re.compile(u'(ISBN-10|ISBN-10|ASIN)', re.I)
        self.relang = re.compile(u'(Language|Langue|Sprache)', re.I)
        self.reratelt = re.compile(u'(Average\s*Customer\s*Review|Moyenne\s*des\s*commentaires\s*client|Durchschnittliche\s*Kundenbewertung)', re.I)
        self.reprod = re.compile(u'(Product\s*Details|D.tails\s*sur\s*le\s*produit|Produktinformation)', re.I)

    def strip_tags_etree(self, etreeobj, invalid_tags):
        for (itag, rmv) in invalid_tags.iteritems():
            if rmv:
                for elts in etreeobj.getiterator(itag):
                    elts.drop_tree()
            else:
                for elts in etreeobj.getiterator(itag):
                    elts.drop_tag()

    def clean_entry(self, entry, invalid_tags = {'script': True},
                invalid_id = (), invalid_class=()):
        #invalid_tags: remove tag and keep content if False else remove
        #remove tags
        if invalid_tags:
            self.strip_tags_etree(entry, invalid_tags)
        #remove id
        if invalid_id:
            for eltid in invalid_id:
                elt = entry.get_element_by_id(eltid)
                if elt is not None:
                    elt.drop_tree()
        #remove class
        if invalid_class:
            for eltclass in invalid_class:
                elts = entry.find_class(eltclass)
                if elts is not None:
                    for elt in elts:
                        elt.drop_tree()

    def get_title(self, entry):
        title = entry.get_element_by_id('btAsinTitle')
        if title is not None:
            title = title.text
        return unicode(title.replace('\n', '').strip())

    def get_authors(self, entry):
        author = entry.get_element_by_id('btAsinTitle')
        while author.getparent().tag != 'div':
            author = author.getparent()
        author = author.getparent()
        authortext = []
        for x in author.getiterator('a'):
            authortext.append(unicode(x.text_content().strip()))
        return authortext

    def get_description(self, entry, verbose):
        try:
            description = entry.get_element_by_id("productDescription").find("div[@class='content']")
            inv_class = ('seeAll', 'emptyClear')
            inv_tags ={'img': True, 'a': False}
            self.clean_entry(description, invalid_tags=inv_tags, invalid_class=inv_class)
            description = tostring(description, method='html', encoding=unicode).strip()
            # remove all attributes from tags
            description = self.reattr.sub(r'<\1>', description)
            # Remove the notice about text referring to out of print editions
            description = self.reoutp.sub('', description)
            # Remove comments
            description = self.recom.sub('', description)
            return unicode(sanitize_comments_html(description))
        except:
            report(verbose)
            return None

    def get_tags(self, entry, verbose):
        try:
            tags = entry.get_element_by_id('tagContentHolder')
            testptag = tags.find_class('see-all')
            if testptag:
                for x in testptag:
                    alink = x.xpath('descendant-or-self::a')
                    if alink:
                        if alink[0].get('class') == 'tgJsActive':
                            continue
                        return self.baseurl + alink[0].get('href'), True
            tags = [a.text for a in tags.getiterator('a') if a.get('rel') == 'tag']
        except:
            report(verbose)
            tags = [], False
        return tags, False

    def get_book_info(self, entry, mi, verbose):
        try:
            entry = entry.get_element_by_id('SalesRank').getparent()
        except:
            try:
                for z in entry.getiterator('h2'):
                    if self.reprod.search(z.text_content()):
                        entry = z.getparent().find("div[@class='content']/ul")
                        break
            except:
                report(verbose)
                return mi
        elts = entry.findall('li')
        #pub & date
        elt = filter(lambda x: self.republi.search(x.find('b').text), elts)
        if elt:
            pub = elt[0].find('b').tail
            mi.publisher = unicode(self.repub.sub('', pub).strip())
            d = self.repub.search(pub)
            if d is not None:
                d = d.group(1)
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
    parser = option_parser()
    opts, args = parser.parse_args(args)
    try:
        if opts.social:
            results = get_social_metadata(opts.title, opts.author,
                opts.publisher, opts.isbn, verbose=opts.verbose, lang=opts.lang)
        else:
            results = search(opts.title, opts.author, isbn=opts.isbn,
                publisher=opts.publisher, keywords=opts.keywords, verbose=opts.verbose,
                    max_results=opts.max_results, lang=opts.lang)
    except AssertionError:
        report(True)
        parser.print_help()
        return 1
    if results is None and len(results) == 0:
        print _('No result found for this search!')
        return 0
    for result in results:
        print unicode(result).encode(preferred_encoding, 'replace')
        print
    
    #test social
    # '''Test xisbn'''
    # print get_social_metadata('Learning Python', None, None, '8324616489')[0]
    # print
    # '''Test sophisticated comment formatting'''
    # print get_social_metadata('Angels & Demons', None, None, '9781416580829')[0]
    # print
    # '''Random tests'''
    # print get_social_metadata('Star Trek: Destiny: Mere Mortals', None, None, '9781416551720')[0]
    # print
    # print get_social_metadata('The Great Gatsby', None, None, '0743273567')[0]

if __name__ == '__main__':
    sys.exit(main())
    # import cProfile
    # sys.exit(cProfile.run("import calibre.ebooks.metadata.amazonbis; calibre.ebooks.metadata.amazonbis.main()"))
    # sys.exit(cProfile.run("import calibre.ebooks.metadata.amazonbis; calibre.ebooks.metadata.amazonbis.main()", "profile"))

# calibre-debug -e "H:\Mes eBooks\Developpement\calibre\src\calibre\ebooks\metadata\amazon.py" -m 5 -a gore -v>data.html