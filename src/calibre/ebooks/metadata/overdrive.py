#!/usr/bin/env  python
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

'''
Fetch metadata using Overdrive Content Reserve
'''
import sys, re, random, urllib, mechanize, copy
from threading import RLock

from lxml import html, etree
from lxml.html import soupparser

from calibre import browser
from calibre.ebooks.metadata import check_isbn
from calibre.ebooks.metadata.sources.base import Source
from calibre.ebooks.metadata.book.base import Metadata
from calibre.ebooks.chardet import xml_to_unicode
from calibre.library.comments import sanitize_comments_html

ovrdrv_data_cache = {}
cover_url_cache = {}
cache_lock = RLock()
base_url = 'http://search.overdrive.com/'


def create_query(self, title=None, authors=None, identifiers={}):
    q = ''
    if title or authors:
        def build_term(prefix, parts):
            return ' '.join('in'+prefix + ':' + x for x in parts)
        title_tokens = list(self.get_title_tokens(title, False))
        if title_tokens:
            q += build_term('title', title_tokens)
        author_tokens = self.get_author_tokens(authors,
                only_first_author=True)
        if author_tokens:
            q += ('+' if q else '') + build_term('author',
                    author_tokens)

    if isinstance(q, unicode):
        q = q.encode('utf-8')
    if not q:
        return None
    return BASE_URL+urlencode({
        'q':q,
        })


def get_base_referer():
    choices = [
        'http://overdrive.chipublib.org/82DC601D-7DDE-4212-B43A-09D821935B01/10/375/en/',
        'http://emedia.clevnet.org/9D321DAD-EC0D-490D-BFD8-64AE2C96ECA8/10/241/en/',
        'http://singapore.lib.overdrive.com/F11D55BE-A917-4D63-8111-318E88B29740/10/382/en/',
        'http://ebooks.nypl.org/20E48048-A377-4520-BC43-F8729A42A424/10/257/en/',
        'http://spl.lib.overdrive.com/5875E082-4CB2-4689-9426-8509F354AFEF/10/335/en/'
    ]
    return choices[random.randint(0, len(choices)-1)]

def format_results(reserveid, od_title, subtitle, series, publisher, creators, thumbimage, worldcatlink, formatid):
    fix_slashes = re.compile(r'\\/')
    thumbimage = fix_slashes.sub('/', thumbimage)
    worldcatlink = fix_slashes.sub('/', worldcatlink)
    cover_url = re.sub('(?P<img>(Ima?g(eType-)?))200', '\g<img>100', thumbimage)
    social_metadata_url = base_url+'TitleInfo.aspx?ReserveID='+reserveid+'&FormatID='+formatid
    series_num = ''
    if not series:
        if subtitle:
            title = od_title+': '+subtitle
        else:
            title = od_title
    else:
        title = od_title
        m = re.search("([0-9]+$)", subtitle)
        if m:
            series_num = float(m.group(1))
    return [cover_url, social_metadata_url, worldcatlink, series, series_num, publisher, creators, reserveid, title]

def safe_query(br, query_url):
    '''
    The query must be initialized by loading an empty search results page
    this page attempts to set a cookie that Mechanize doesn't like
    copy the cookiejar to a separate instance and make a one-off request with the temp cookiejar
    '''
    goodcookies = br._ua_handlers['_cookies'].cookiejar
    clean_cj = mechanize.CookieJar()
    cookies_to_copy = []
    for cookie in goodcookies:
        copied_cookie = copy.deepcopy(cookie)
        cookies_to_copy.append(copied_cookie)
    for copied_cookie in cookies_to_copy:
        clean_cj.set_cookie(copied_cookie)

    br.open_novisit(query_url)
    
    br.set_cookiejar(clean_cj)


def overdrive_search(br, q, title, author):
    q_query = q+'default.aspx/SearchByKeyword'
    q_init_search = q+'SearchResults.aspx'
    # get first author as string - convert this to a proper cleanup function later
    s = Source(None)
    print "printing list with string:"
    #print list(s.get_author_tokens(['J. R. R. Tolkien']))
    print "printing list with author "+str(author)+":"
    print list(s.get_author_tokens(author))
    author_tokens = list(s.get_author_tokens(author))
    print "there are "+str(len(author_tokens))+" author tokens"
    for token in author_tokens:
        print "cleaned up author token is: "+str(token)


    title_tokens = list(s.get_title_tokens(title))
    print "there are "+str(len(title_tokens))+" title tokens"
    for token in title_tokens:
        print "cleaned up title token is: "+str(token)

    if len(title_tokens) >= len(author_tokens):
        initial_q = ' '.join(title_tokens)
        xref_q = '+'.join(author_tokens)
    else:
        initial_q = ' '.join(author_tokens)
        xref_q = '+'.join(title_tokens)

    print "initial query is "+str(initial_q)
    print "cross reference query is "+str(xref_q)
    q_xref = q+'SearchResults.svc/GetResults?iDisplayLength=50&sSearch='+xref_q
    query = '{"szKeyword":"'+initial_q+'"}'

    # main query, requires specific Content Type header
    req = mechanize.Request(q_query)
    req.add_header('Content-Type', 'application/json; charset=utf-8')
    br.open_novisit(req, query)

    print "q_init_search is "+q_init_search
    # initiate the search without messing up the cookiejar
    safe_query(br, q_init_search)

    # get the search results object
    results = False
    while results == False:
        xreq = mechanize.Request(q_xref)
        xreq.add_header('X-Requested-With', 'XMLHttpRequest')
        xreq.add_header('Referer', q_init_search)
        xreq.add_header('Accept', 'application/json, text/javascript, */*')
        raw = br.open_novisit(xreq).read()
        print "overdrive search result is:\n"+raw
        for m in re.finditer(ur'"iTotalDisplayRecords":(?P<displayrecords>\d+).*?"iTotalRecords":(?P<totalrecords>\d+)', raw):
            if int(m.group('displayrecords')) >= 1:
                results = True
            elif int(m.group('totalrecords')) >= 1:
                xref_q = ''
                q_xref = q+'SearchResults.svc/GetResults?iDisplayLength=50&sSearch='+xref_q
        
    print "\n\nsorting results"
    return sort_ovrdrv_results(raw, title, title_tokens, author, author_tokens)


def sort_ovrdrv_results(raw, title=None, title_tokens=None, author=None, author_tokens=None, ovrdrv_id=None):
    print "\ntitle to search for is "+str(title)+"\nauthor to search for is "+str(author)
    close_matches = []
    raw = re.sub('.*?\[\[(?P<content>.*?)\]\].*', '[[\g<content>]]', raw)
    results = eval(raw)
    print "\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n"
    #print results
    # The search results are either from a keyword search or a multi-format list from a single ID,
    # sort through the results for closest match/format
    if results:
        for reserveid, od_title, subtitle, edition, series, publisher, format, formatid, creators, \
                thumbimage, shortdescription, worldcatlink, excerptlink, creatorfile, sorttitle, \
                availabletolibrary, availabletoretailer, relevancyrank, unknown1, unknown2, unknown3 in results:
            print "this record's title is "+od_title+", subtitle is "+subtitle+", author[s] are "+creators+", series is "+series
            if ovrdrv_id is not None and int(formatid) in [1, 50, 410, 900]:
                print "overdrive id is not None, searching based on format type priority"
                return format_results(reserveid, od_title, subtitle, series, publisher, creators, thumbimage, worldcatlink, formatid)            
            else:
                creators = creators.split(', ')
                print "split creators from results are: "+str(creators)
                # if an exact match in a preferred format occurs
                if creators[0] == author[0] and od_title == title and int(formatid) in [1, 50, 410, 900]:
                    print "Got Exact Match!!!"
                    return format_results(reserveid, od_title, subtitle, series, publisher, creators, thumbimage, worldcatlink, formatid)
                else:
                    close_title_match = False
                    close_author_match = False
                    for token in title_tokens:
                        if od_title.lower().find(token.lower()) != -1:
                            close_title_match = True
                        else:
                            close_title_match = False
                            break
                    for token in author_tokens:
                        if creators[0].lower().find(token.lower()) != -1:
                            close_author_match = True
                        else:
                            close_author_match = False
                            break
                    if close_title_match and close_author_match and int(formatid) in [1, 50, 410, 900]:
                        if subtitle and series:
                            close_matches.insert(0, format_results(reserveid, od_title, subtitle, series, publisher, creators, thumbimage, worldcatlink, formatid))
                        else:
                            close_matches.append(format_results(reserveid, od_title, subtitle, series, publisher, creators, thumbimage, worldcatlink, formatid))
        if close_matches:
            return close_matches[0]
        else:
            return ''
    else:
        return ''



def overdrive_get_record(br, q, ovrdrv_id):
    search_url = q+'SearchResults.aspx?ReserveID={'+ovrdrv_id+'}'
    results_url = q+'SearchResults.svc/GetResults?sEcho=1&iColumns=18&sColumns=ReserveID%2CTitle%2CSubtitle%2CEdition%2CSeries%2CPublisher%2CFormat%2CFormatID%2CCreators%2CThumbImage%2CShortDescription%2CWorldCatLink%2CExcerptLink%2CCreatorFile%2CSortTitle%2CAvailableToLibrary%2CAvailableToRetailer%2CRelevancyRank&iDisplayStart=0&iDisplayLength=10&sSearch=&bEscapeRegex=true&iSortingCols=1&iSortCol_0=17&sSortDir_0=asc'

    # get the base url to set the proper session cookie
    br.open_novisit(q)

    # initialize the search
    safe_query(br, search_url)

    # get the results
    req = mechanize.Request(results_url)
    req.add_header('X-Requested-With', 'XMLHttpRequest')
    req.add_header('Referer', search_url)
    req.add_header('Accept', 'application/json, text/javascript, */*')
    raw = br.open_novisit(req)
    raw = str(list(raw))
    return sort_ovrdrv_results(raw, None, None, None, ovrdrv_id)


def find_ovrdrv_data(br, title, author, isbn, ovrdrv_id=None):
    print "in find_ovrdrv_data, title is "+str(title)+", author is "+str(author)+", overdrive id is "+str(ovrdrv_id)
    q = base_url
    if ovrdrv_id is None:
       return overdrive_search(br, q, title, author)
    else:
       return overdrive_get_record(br, q, ovrdrv_id)



def to_ovrdrv_data(br, title, author, isbn, ovrdrv_id=None):
    print "starting to_ovrdrv_data"
    with cache_lock:
        ans = ovrdrv_data_cache.get(isbn, None)
    if ans:
        print "inside to_ovrdrv_data, cache lookup successful, ans is "+str(ans)
        return ans
    if ans is False:
        print "inside to_ovrdrv_data, ans returned False"
        return None
    try:
        print "trying to retrieve data, running find_ovrdrv_data"
        ovrdrv_data = find_ovrdrv_data(br, title, author, isbn, ovrdrv_id)
        print "ovrdrv_data is "+str(ovrdrv_data)
    except:
        import traceback
        traceback.print_exc()
        ovrdrv_data = None

    with cache_lock:
        ovrdrv_data_cache[isbn] = ovrdrv_data if ovrdrv_data else False
    if ovrdrv_data:
        from calibre.ebooks.metadata.xisbn import xisbn
        for i in xisbn.get_associated_isbns(isbn):
            with cache_lock:
                ovrdrv_data_cache[i] = ovrdrv_data

    return ovrdrv_data


def get_social_metadata(title, authors, isbn, ovrdrv_id=None):
    author = authors[0]
    mi = Metadata(title, authors)
    br = browser()
    print "calling to_ovrdrv_data from inside get_social_metadata"
    ovrdrv_data = to_ovrdrv_data(br, title, authors, isbn, ovrdrv_id)

    #[cover_url, social_metadata_url, worldcatlink, series, series_num, publisher, creators, reserveid, title]

    if len(ovrdrv_data[3]) > 1:
        mi.series = ovrdrv_data[3]
        if ovrdrv_data[4]:
            mi.series_index = ovrdrv_data[4]
    mi.publisher = ovrdrv_data[5]
    mi.authors = ovrdrv_data[6]
    if ovrdrv_id is None:
        ovrdrv_id = ovrdrv_data[7]
    mi.set_identifier('overdrive', ovrdrv_id)
    mi.title = ovrdrv_data[8]
    print "populated basic social metadata, getting detailed metadata"
    if ovrdrv_data and get_metadata_detail(br, ovrdrv_data[1], mi, isbn):
        return mi
    print "failed to get detailed metadata, returning basic info"
    return mi

def get_cover_url(isbn, title, author, br, ovrdrv_id=None):
    print "starting get_cover_url"
    print "title is "+str(title)
    print "author is "+str(author[0])
    print "isbn is "+str(isbn)
    print "ovrdrv_id is "+str(ovrdrv_id)

    with cache_lock:
        ans = cover_url_cache.get(isbn, None)
        #ans = cover_url_cache.get(ovrdrv_id, None)
    if ans:
        print "cover url cache lookup returned positive, ans is "+str(ans)
        return ans
    if ans is False:
        "cover url cache lookup returned false"
        return None
    print "in get_cover_url, calling to_ovrdrv_data function"
    ovrdrv_data = to_ovrdrv_data(br, title, author, isbn, ovrdrv_id)
    if ovrdrv_data:
        ans = ovrdrv_data[0]
        print "inside get_cover_url, got url from to_ovrdrv_data, ans is "+str(ans)
        if ans:
            print "writing cover url to url cache"
            with cache_lock:
                cover_url_cache[isbn] = ans
                #cover_url_cache[ovrdrv_id] = ans
            return ans
            
    with cache_lock:
        print "marking cover url cache for this isbn false"
        cover_url_cache[isbn] = False
    return None

def _get_cover_url(br, ovrdrv_data):
    q = ovrdrv_data[1]
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

def get_metadata_detail(br, metadata_url, mi, isbn=None):
    try:
        raw = br.open_novisit(metadata_url).read()
    except Exception, e:
        if callable(getattr(e, 'getcode', None)) and \
                e.getcode() == 404:
            return False
        raise   
    raw = xml_to_unicode(raw, strip_encoding_pats=True,
            resolve_entities=True)[0]
    try:
        root = soupparser.fromstring(raw)
    except:
        return False

    isbn = check_isbn(isbn)

    pub_date = root.xpath("//div/label[@id='ctl00_ContentPlaceHolder1_lblPubDate']/text()")
    lang = root.xpath("//div/label[@id='ctl00_ContentPlaceHolder1_lblLanguage']/text()")
    subjects = root.xpath("//div/label[@id='ctl00_ContentPlaceHolder1_lblSubjects']/text()")
    ebook_isbn = root.xpath("//div/label[@id='ctl00_ContentPlaceHolder1_lblIdentifier']/text()")
    desc = root.xpath("//div/label[@id='ctl00_ContentPlaceHolder1_lblDescription']/ancestor::div[1]")

    if pub_date:
        from calibre.utils.date import parse_date
        mi.pubdate = parse_date(pub_date[0].strip())
    if lang:
        mi.language = lang[0].strip()
        print "languages is "+str(mi.language)
    if ebook_isbn and isbn is None:
        print "ebook isbn is "+str(ebook_isbn[0])
        mi.set_identifier('isbn', ebook_isbn)
    #elif isbn is not None:
    #    mi.set_identifier('isbn', isbn)
    if subjects:
        mi.tags = [tag.strip() for tag in subjects[0].split(',')]
        print "tags are "+str(mi.tags)
    if desc:
        desc = desc[0]
        desc = html.tostring(desc, method='html', encoding=unicode).strip()
        # remove all attributes from tags
        desc = re.sub(r'<([a-zA-Z0-9]+)\s[^>]+>', r'<\1>', desc)
        # Remove comments
        desc = re.sub(r'(?s)<!--.*?-->', '', desc)
        mi.comments = sanitize_comments_html(desc)

    return True

def main(args=sys.argv):
    print "running through main tests"
    import tempfile, os, time
    tdir = tempfile.gettempdir()
    br = browser()
    for ovrdrv_id, isbn, title, author in [
            #(None, '0899661343', 'On the Road', ['Jack Kerouac']), # basic test, no series, single author
            #(None, '9780061952838', 'The Fellowship of the Ring', ['J. R. R. Tolkien']), # Series test, multi-author
            #(None, '9780061952838', 'The Two Towers (The Lord of the Rings, Book II)', ['J. R. R. Tolkien']), # Series test, book 2
            #(None, '9780618153985', 'The Fellowship of the Ring (The Lord of the Rings, Part 1)', ['J.R.R. Tolkien']),
            #('57844706-20fa-4ace-b5ee-3470b1b52173', None, 'The Two Towers', ['J. R. R. Tolkien']), # Series test, w/ ovrdrv id
            #(None, '9780345505057', 'Deluge', ['Anne McCaffrey']) # Multiple authors
            #(None, None, 'Deluge', ['Anne McCaffrey']) # Empty ISBN
            #(None, None, 'On the Road', ['Jack Kerouac']), # Nonetype ISBN
            #(None, '9780345435279', 'A Caress of Twilight', ['Laurell K. Hamilton']),
            #(None, '9780606087230', 'The Omnivore\'s Dilemma : A Natural History of Four Meals', ['Michael Pollan']), # Subtitle colon
            #(None, '9780061747649', 'Mental_Floss Presents: Condensed Knowledge', ['Will Pearson', 'Mangesh Hattikudur']),
            #(None, '9781400050802', 'The Zombie Survival Guide', ['Max Brooks']), # Two books with this title by this author
            #(None, '9781775414315', 'The Worst Journey in the World / Antarctic 1910-1913', ['Apsley Cherry-Garrard']), # Garbage sub-title
            #(None, '9780440335160', 'Outlander', ['Diana Gabaldon']), # Returns lots of results to sort through to get the best match
            (None, '9780345509741', 'The Horror Stories of Robert E. Howard', ['Robert E. Howard']), # Complex title with initials/dots stripped, some results don't have a cover
            ]:
        cpath = os.path.join(tdir, title+'.jpg')
        print "cpath is "+cpath
        st = time.time()
        curl = get_cover_url(isbn, title, author, br, ovrdrv_id)
        print '\n\n Took ', time.time() - st, ' to get basic metadata\n\n'
        if curl is None:
            print 'No cover found for', title
        else:
            print "curl is "+curl
            #open(cpath, 'wb').write(br.open_novisit(curl).read())
            #print 'Cover for', title, 'saved to', cpath
        st = time.time()
        print get_social_metadata(title, author, isbn, ovrdrv_id)
        print '\n\n Took ', time.time() - st, ' to get detailed metadata\n\n'

    return 0

if __name__ == '__main__':
    sys.exit(main())
