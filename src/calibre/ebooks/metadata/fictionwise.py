from __future__ import with_statement
__license__ = 'GPL 3'
__copyright__ = '2010, sengian <sengian1@gmail.com>'
__docformat__ = 'restructuredtext en'

import sys, textwrap, re
from urllib import urlencode

from lxml import html, etree
from lxml.html import soupparser
from lxml.etree import tostring

from calibre import browser, preferred_encoding
from calibre.ebooks.chardet import xml_to_unicode
from calibre.ebooks.metadata import MetaInformation, check_isbn, \
    authors_to_sort_string
from calibre.library.comments import sanitize_comments_html
from calibre.ebooks.metadata.fetch import MetadataSource
from calibre.utils.config import OptionParser
from calibre.utils.date import parse_date, utcnow

class Fictionwise(MetadataSource): # {{{

    author = 'Sengian'
    name = 'Fictionwise'
    description = _('Downloads metadata from Fictionwise')

    has_html_comments = True

    def fetch(self):
        try:
            self.results = search(self.title, self.book_author, self.publisher,
                self.isbn, max_results=10, verbose=self.verbose)
        except Exception, e:
            self.exception = e
            self.tb = traceback.format_exc()

    # }}}


def report(verbose):
    if verbose:
        import traceback
        traceback.print_exc()

class Query(object):

    BASE_URL = 'http://www.fictionwise.com/servlet/mw'

    def __init__(self, title=None, author=None, publisher=None, keywords=None, max_results=20):
        assert not(title is None and author is None and publisher is None and keywords is None)
        assert (max_results < 21)

        self.max_results = int(max_results)
        
        q = {   'template' : 'searchresults_adv.htm' ,
                'searchtitle' : '',
                'searchauthor' : '',
                'searchpublisher' : '',
                'searchkeyword' : '',
                #possibilities startoflast, fullname, lastfirst
                'searchauthortype' : 'startoflast',
                'searchcategory' : '',
                'searchcategory2' : '',
                'searchprice_s' : '0',
                'searchprice_e' : 'ANY',
                'searchformat' : '',
                'searchgeo' : 'US',
                'searchfwdatetype' : '',
                #maybe use dates fields if needed?
                #'sortorder' : 'DESC',
                #many options available: b.SortTitle, a.SortName,
                #b.DateFirstPublished, b.FWPublishDate
                'sortby' : 'b.SortTitle'
            }
        if title is not None:
            q['searchtitle'] = title
        if author is not None:
            q['searchauthor'] = author
        if publisher is not None:
            q['searchpublisher'] = publisher
        if keywords is not None:
            q['searchkeyword'] = keywords

        if isinstance(q, unicode):
            q = q.encode('utf-8')
        self.urldata = urlencode(q)

    def __call__(self, browser, verbose):
        if verbose:
            print 'Query:', self.BASE_URL+self.urldata
        
        try:
            raw = browser.open_novisit(self.BASE_URL, self.urldata).read()
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

        # get list of results as links
        results = feed.xpath("//table[3]/tr/td[2]/table/tr/td/p/table[2]/tr[@valign]")
        results = results[:self.max_results]
        results = [i.xpath('descendant-or-self::a')[0].get('href') for i in results]
        #return feed if no links ie normally a single book or nothing
        if not results:
            results = [feed]
        return results

class ResultList(list):
    
    BASE_URL = 'http://www.fictionwise.com'
    COLOR_VALUES = {'BLUE': 4, 'GREEN': 3, 'YELLOW': 2, 'RED': 1, 'NA': 0}
 
    def __init__(self):
        self.retitle = re.compile(r'\[[^\[\]]+\]')
        self.rechkauth = re.compile(r'.*book\s*by', re.I)
        self.redesc = re.compile(r'book\s*description\s*:\s*(<br[^>]+>)*(?P<desc>.*)' \
            + '<br[^>]+>.{,15}publisher\s*:', re.I)
        self.repub = re.compile(r'.*publisher\s*:\s*', re.I)
        self.redate = re.compile(r'.*release\s*date\s*:\s*', re.I)
        self.retag = re.compile(r'.*book\s*category\s*:\s*', re.I)
        self.resplitbr = re.compile(r'<br[^>]+>', re.I)
        self.recomment = re.compile(r'(?s)<!--.*?-->')
        self.reimg = re.compile(r'<img[^>]*>', re.I)
        self.resanitize = re.compile(r'\[HTML_REMOVED\]\s*', re.I)
        self.renbcom = re.compile('(?P<nbcom>\d+)\s*Reader Ratings:')
        self.recolor = re.compile('(?P<ncolor>[^/]+).gif')
        self.resplitbrdiv = re.compile(r'(<br[^>]+>|</?div[^>]*>)', re.I)
        self.reisbn = re.compile(r'.*ISBN\s*:\s*', re.I)

    def strip_tags_etree(self, etreeobj, invalid_tags):
        for itag in invalid_tags:
            for elt in etreeobj.getiterator(itag):
                elt.drop_tag()
        return etreeobj

    def clean_entry(self, entry, 
            invalid_tags = ('font', 'strong', 'b', 'ul', 'span', 'a'),
                remove_tags_trees = ('script',)):
        for it in entry[0].iterchildren(tag='table'):
            entry[0].remove(it)
        entry[0].remove(entry[0].xpath( 'descendant-or-self::p[1]')[0])
        entry = entry[0]
        cleantree = self.strip_tags_etree(entry, invalid_tags)
        for itag in remove_tags_trees:
            for elts in cleantree.getiterator(itag):
                    elts.drop_tree()
        return cleantree

    def output_entry(self, entry, prettyout = True, htmlrm="\d+"):
        out = tostring(entry, pretty_print=prettyout)
        reclean = re.compile('(\n+|\t+|\r+|&#'+htmlrm+';)')
        return reclean.sub('', out)

    def get_title(self, entry):
        title = entry.findtext('./')
        return self.retitle.sub('', title).strip()

    def get_authors(self, entry):
        authortext = entry.find('./br').tail
        if not self.rechkauth.search(authortext):
            return []
            #TODO: parse all tag if necessary
        authortext = self.rechkauth.sub('', authortext)
        return [a.strip() for a in authortext.split('&')]

    def get_rating(self, entrytable, verbose):
        nbcomment = tostring(entrytable.getprevious())
        try:
            nbcomment = self.renbcom.search(nbcomment).group("nbcom")
        except:
            report(verbose)
            return None
        hval = dict((self.COLOR_VALUES[self.recolor.search(image.get('src', default='NA.gif')).group("ncolor")], 
                    float(image.get('height', default=0))) \
                        for image in entrytable.getiterator('img'))
        #ratings as x/5
        return 1.25*sum(k*v for (k, v) in hval.iteritems())/sum(hval.itervalues())

    def get_description(self, entry):
        description = self.output_entry(entry.find('./p'),htmlrm="")
        description = self.redesc.search(description)
        if not description and not description.group("desc"):
            return None
        #remove invalid tags
        description = self.reimg.sub('', description.group("desc"))
        description = self.recomment.sub('', description)
        description = self.resanitize.sub('', sanitize_comments_html(description))
        return 'SUMMARY:\n' + re.sub(r'\n\s+</p>','\n</p>', description)

    def get_publisher(self, entry):
        publisher = self.output_entry(entry.find('./p'))
        publisher = filter(lambda x: self.repub.search(x) is not None,
            self.resplitbr.split(publisher))
        if not len(publisher):
            return None
        publisher = self.repub.sub('', publisher[0])
        return publisher.split(',')[0].strip()

    def get_tags(self, entry):
        tag = self.output_entry(entry.find('./p'))
        tag = filter(lambda x: self.retag.search(x) is not None,
            self.resplitbr.split(tag))
        if not len(tag):
            return []
        return map(lambda x: x.strip(), self.retag.sub('', tag[0]).split('/'))

    def get_date(self, entry, verbose):
        date = self.output_entry(entry.find('./p'))
        date = filter(lambda x: self.redate.search(x) is not None,
            self.resplitbr.split(date))
        if not len(date):
            return None
            #TODO: parse all tag if necessary
        try:
            d = self.redate.sub('', date[0])
            if d:
                default = utcnow().replace(day=15)
                d = parse_date(d, assume_utc=True, default=default)
            else:
                d = None
        except:
            report(verbose)
            d = None
        return d

    def get_ISBN(self, entry):
        isbns = self.output_entry(entry.getchildren()[2])
        isbns = filter(lambda x: self.reisbn.search(x) is not None,
            self.resplitbrdiv.split(isbns))
        if not len(isbns):
            return None
            #TODO: parse all tag if necessary
        isbns = [self.reisbn.sub('', x) for x in isbns if check_isbn(self.reisbn.sub('', x))]
        return sorted(isbns, cmp=lambda x,y:cmp(len(x), len(y)))[-1]

    def fill_MI(self, entry, title, authors, ratings, verbose):
        mi = MetaInformation(title, authors)
        mi.rating = ratings
        mi.comments = self.get_description(entry)
        mi.publisher = self.get_publisher(entry)
        mi.tags = self.get_tags(entry)
        mi.pubdate = self.get_date(entry, verbose)
        mi.isbn = self.get_ISBN(entry)
        mi.author_sort = authors_to_sort_string(authors)
        # mi.language = self.get_language(x, verbose)
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
        return feed.xpath("//table[3]/tr/td[2]/table[1]/tr/td/font/table/tr/td")

    def populate(self, entries, browser, verbose=False):
        for x in entries:
            try:
                entry = self.get_individual_metadata(browser, x, verbose)
                entry = self.clean_entry(entry)
                title = self.get_title(entry)
                #ratings: get table for rating then drop
                for elt in entry.getiterator('table'):
                    ratings =  self.get_rating(elt, verbose)
                    elt.getprevious().drop_tree()
                    elt.drop_tree()
                authors = self.get_authors(entry)
            except Exception, e:
                if verbose:
                    print 'Failed to get all details for an entry'
                    print e
                continue
            self.append(self.fill_MI(entry, title, authors, ratings, verbose))

    def populate_single(self, feed, verbose=False):
        try:
            entry = feed.xpath("//table[3]/tr/td[2]/table[1]/tr/td/font/table/tr/td")
            entry = self.clean_entry(entry)
            title = self.get_title(entry)
            #ratings: get table for rating then drop
            for elt in entry.getiterator('table'):
                ratings =  self.get_rating(elt, verbose)
                elt.getprevious().drop_tree()
                elt.drop_tree()
            authors = self.get_authors(entry)
        except Exception, e:
            if verbose:
                print 'Failed to get all details for an entry'
                print e
            return
        self.append(self.fill_MI(entry, title, authors, ratings, verbose))


def search(title=None, author=None, publisher=None, isbn=None,
           min_viewability='none', verbose=False, max_results=5,
            keywords=None):
    br = browser()
    entries = Query(title=title, author=author, publisher=publisher,
        keywords=keywords, max_results=max_results)(br, verbose)
    
    #List of entry
    ans = ResultList()
    if len(entries) > 1:
        ans.populate(entries, br, verbose)
    else:
        ans.populate_single(entries[0], verbose)
    return ans


def option_parser():
    parser = OptionParser(textwrap.dedent(\
    '''\
        %prog [options]

        Fetch book metadata from Fictionwise. You must specify one of title, author,
        or keywords. No ISBN specification possible. Will fetch a maximum of 20 matches,
        so you should make your query as specific as possible.
    '''
    ))
    parser.add_option('-t', '--title', help='Book title')
    parser.add_option('-a', '--author', help='Book author(s)')
    parser.add_option('-p', '--publisher', help='Book publisher')
    parser.add_option('-k', '--keywords', help='Keywords')
    parser.add_option('-m', '--max-results', default=20,
                      help='Maximum number of results to fetch')
    parser.add_option('-v', '--verbose', default=0, action='count',
                      help='Be more verbose about errors')
    return parser

def main(args=sys.argv):
    parser = option_parser()
    opts, args = parser.parse_args(args)
    try:
        results = search(opts.title, opts.author, publisher=opts.publisher,
            keywords=opts.keywords, verbose=opts.verbose, max_results=opts.max_results)
    except AssertionError:
        report(True)
        parser.print_help()
        return 1
    for result in results:
        print unicode(result).encode(preferred_encoding, 'replace')
        print

if __name__ == '__main__':
    sys.exit(main())
