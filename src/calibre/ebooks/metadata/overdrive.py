#!/usr/bin/env  python
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

'''
Fetch metadata using Adobe Overdrive
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
        m = re.search("([0-9]+$)", subtitle)
        if m:
            series_num = float(m.group(1))
    return [cover_url, social_metadata_url, worldcatlink, series, series_num, publisher, creators, reserveid, title]

def overdrive_search(br, q, title, author):
    q_query = q+'default.aspx/SearchByKeyword'
    q_init_search = q+'SearchResults.aspx'

    # query terms
    author_q = re.sub('\s', '+', author)
    q_xref = q+'SearchResults.svc/GetResults?iDisplayLength=10&sSearch='+author_q
    query = '{"szKeyword":"'+title+'"}'

    # main query, requires specific Content Type header
    req = mechanize.Request(q_query)
    req.add_header('Content-Type', 'application/json; charset=utf-8')
    br.open_novisit(req, query)

    print "q_init_search is "+q_init_search
    
    # the query must be initialized by loading an empty search results page
    # this page attempts to set a cookie that Mechanize doesn't like
    # copy the cookiejar to a separate instance and make a one-off request with the temp cookiejar
    goodcookies = br._ua_handlers['_cookies'].cookiejar
    clean_cj = mechanize.CookieJar()
    cookies_to_copy = []
    for cookie in goodcookies:
        copied_cookie = copy.deepcopy(cookie)
        cookies_to_copy.append(copied_cookie)
    for copied_cookie in cookies_to_copy:
        clean_cj.set_cookie(copied_cookie)

    br.open_novisit(q_init_search)
    
    br.set_cookiejar(clean_cj)

    # get the search results object
    xreq = mechanize.Request(q_xref)
    xreq.add_header('X-Requested-With', 'XMLHttpRequest')
    xreq.add_header('Referer', q_init_search)
    xreq.add_header('Accept', 'application/json, text/javascript, */*')
    raw = br.open_novisit(xreq).read()
    print "overdrive search result is:\n"+raw
    raw = re.sub('.*?\[\[(?P<content>.*?)\]\].*', '[[\g<content>]]', raw)
    results = eval(raw)
    print "\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n"
    print results
    # The search results are from a keyword search (overdrive's advanced search is broken), 
    # sort through the results for closest match/format
    for result in results:
        print "\n\n\nthis result is "+str(result)
        for reserveid, od_title, subtitle, edition, series, publisher, format, formatid, creators, \
                thumbimage, shortdescription, worldcatlink, excerptlink, creatorfile, sorttitle, \
                availabletolibrary, availabletoretailer, relevancyrank, unknown1, unknown2, unknown3 in results:
            creators = creators.split(', ')
            print "fixed creators are: "+str(creators)
            # if an exact match occurs
            if creators[0] == author and od_title == title and int(formatid) in [1, 50, 410, 900]:
                print "Got Exact Match!!!"
                return format_results(reserveid, od_title, subtitle, series, publisher, creators, thumbimage, worldcatlink, formatid)
        

def library_search(br, q, title, author):
    q_search = q+'AdvancedSearch.htm'
    q_query = q+'BANGSearch.dll'
    br.open(q_search)
    # Search for cover with audiobooks lowest priority
    for format in ['410','50','900','25','425']:
        query = 'Title='+title+'&Creator='+author+'&Keyword=&ISBN=&Format='+format+'&Language=&Publisher=&Subject=&Award=&CollDate=&PerPage=10&Sort=SortBy%3Dtitle'
        query = re.sub('\s', '+', query)
        #print "search url is "+str(q_search)
        print "query is "+str(query)
        raw = br.open(q_query, query).read()
        #print "raw html is:\n"+str(raw)
        raw = xml_to_unicode(raw, strip_encoding_pats=True,
                resolve_entities=True)[0]
        root = html.fromstring(raw)
        revs = root.xpath("//img[@class='blackborder']")
        if revs:
            #print "revs are "+str(revs)
            # get the first match, as it's the most likely candidate
            x = revs[0]
            id = urllib.unquote(re.sub('.*?/(?P<i>%7B.*?%7D).*', '\g<i>', x.get('src')))
            curl = re.sub('(?P<img>(Ima?g(eType-)?))200', '\g<img>100', x.get('src'))
            murl = root.xpath("//img[@class='blackborder']/parent::*")
            if murl:
                murl = [y.get('href') for y in murl]
                print "murl is"+str(murl)
                murl = q+murl[0]
            else:
                print "didn't get metadata URL"
            print "curl is "+str(curl)+", id is "+str(id)+", murl is "+str(murl)
            ovrdrv_data = [id, curl, murl]
            print "revs final are "+str(revs)
            return ovrdrv_data


def find_ovrdrv_data(br, title, author, isbn):
    print "in fnd_ovrdrv_data, title is "+str(title)+", author is "+str(author)
    q = base_url
    if re.match('http://search\.overdrive\.', q):
       return overdrive_search(br, q, title, author)
    else:
       return library_search(br, q, title, author)
    


def to_ovrdrv_data(br, title, author, isbn):
    print "starting to_ovrdrv_data"
    with cache_lock:
        ans = ovrdrv_data_cache.get(isbn, None)
    if ans:
        print "inside to_ovrdrv_data, ans returned positive, ans is"+str(ans)
        return ans
    if ans is False:
        print "inside to_ovrdrv_data, ans returned False"
        return None
    try:
        ovrdrv_data = find_ovrdrv_data(br, title, author, isbn)
        print "ovrdrv_data = "+str(ovrdrv_data)
    except:
        import traceback
        traceback.print_exc()
        ovrdrv_data = None

    with cache_lock:
        ovrdrv_data_cache[isbn] = ovrdrv_data if ovrdrv_data else False
    return ovrdrv_data


def get_social_metadata(title, authors, publisher, isbn):
    author = authors[0]
    mi = Metadata(title, authors)
    if not isbn:
        return mi
    isbn = check_isbn(isbn)
    if not isbn:
        return mi
    br = browser()
    ovrdrv_data = to_ovrdrv_data(br, title, authors, isbn)
    if ovrdrv_data and get_metadata_detail_ovrdrv(br, ovrdrv_data, mi):
        return mi
    #from calibre.ebooks.metadata.xisbn import xisbn
    #for i in xisbn.get_associated_isbns(isbn):
    #    print "xisbn isbn is "+str(i)
    #    ovrdrv_data = to_ovrdrv_data(br, title, author, i)
    #    if ovrdrv_data and get_metadata_detail(br, ovrdrv_data, mi):
    #        return mi
    return mi

def get_cover_url(isbn, title, author, br):
    print "starting get_cover_url"
    isbn = check_isbn(isbn)
    print "isbn is "+str(isbn)
    print "title is "+str(title)
    print "author is "+str(author[0])
    cleanup = Source()
    author = cleanup.get_author_tokens(author)
    print "cleansed author is "+str(author)

    with cache_lock:
        ans = cover_url_cache.get(isbn, None)
    if ans:
        print "ans returned positive"
        return ans
    if ans is False:
        "ans returned false"
        return None
    print "in get_cover_url, running through ovrdrv_data function"
    ovrdrv_data = to_ovrdrv_data(br, title, author, isbn)
    print "ovrdrv_id is "+str(ovrdrv_data)
    if ovrdrv_data:
        ans = ovrdrv_data[0]
        print "inside get_cover_url, ans is "+str(ans)
        if ans:
            with cache_lock:
                cover_url_cache[isbn] = ans
            return ans
    #from calibre.ebooks.metadata.xisbn import xisbn
    #for i in xisbn.get_associated_isbns(isbn):
    #    print "in get_cover_url, using xisbn list to associate other books"
    #    ovrdrv_data = to_ovrdrv_data(br, title, author, i)
    #    if ovrdrv_data:
    #        ans = _get_cover_url(br, ovrdrv_data)
    #        if ans:
    #            with cache_lock:
    #                cover_url_cache[isbn] = ans
    #                cover_url_cache[i] = ans
    #            return ans
    with cache_lock:
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


def get_metadata_detail(br, ovrdrv_data, mi):
    q = ovrdrv_data[2]
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

    # Check for series name and retrieve it
    series_name = root.xpath("//td/script[re:test(text(), 'szSeries', 'i')]", 
                           namespaces={"re": "http://exslt.org/regular-expressions"})
    if series_name:
        series = html.tostring(series_name[0], method='html', encoding=unicode).strip()
        series = re.sub('(?s).*?szSeries\s*=\s*\"(?P<series>.*?)\";.*', '\g<series>', series)
        if len(series) > 1:
            mi.series = series
            # If series was successful attempt to get the series number
            series_num = root.xpath("//div/strong[re:test(text(), ',\s(Book|Part|Volume)')]", 
                                  namespaces={"re": "http://exslt.org/regular-expressions"})
            if series_num:
                series_num = float(re.sub('(?s).*?,\s*(Book|Part|Volume)\s*(?P<num>\d+).*', '\g<num>', 
                                 etree.tostring(series_num[0])))
                if series_num >= 1:
                    mi.series_index = series_num
            print "series_num is "+str(series_num)

    desc = root.xpath("//td[@class='collection' and re:test(., 'Description', 'i')]/following::div[1]", 
                    namespaces={"re": "http://exslt.org/regular-expressions"})
    if desc:
        desc = desc[0]
        desc = html.tostring(desc, method='html', encoding=unicode).strip()
        # remove all attributes from tags
        desc = re.sub(r'<([a-zA-Z0-9]+)\s[^>]+>', r'<\1>', desc)
        # Remove comments
        desc = re.sub(r'(?s)<!--.*?-->', '', desc)
        mi.comments = sanitize_comments_html(desc)

    publisher = root.xpath("//td/strong[re:test(text(), 'Publisher\:', 'i')]/ancestor::td[1]/following-sibling::td/text()", 
                         namespaces={"re": "http://exslt.org/regular-expressions"})
    if publisher:
        mi.publisher = re.sub('^\s*(?P<pub>.*?)\s*$', '\g<pub>', publisher[0])
        print "publisher is "+str(mi.publisher)

    lang = root.xpath("//td/strong[re:test(text(), 'Language\(s\):', 'i')]/ancestor::td[1]/following-sibling::td/text()", 
                    namespaces={"re": "http://exslt.org/regular-expressions"})
    if lang:
        mi.language = re.sub('^\s*(?P<lang>.*?)\s*$', '\g<lang>', lang[0])
        print "languages is "+str(mi.language)    

    isbn = root.xpath("//tr/td[re:test(text(), 'ISBN:', 'i')]/following::td/text()", 
                    namespaces={"re": "http://exslt.org/regular-expressions"})
    if isbn:
        mi.isbn = re.sub('^\s*(?P<isbn>.*?)\s*$', '\g<isbn>', isbn[0])
        print "ISBN is "+str(mi.isbn)    

    subjects = root.xpath("//td/strong[re:test(text(), 'Subject', 'i')]/ancestor::td[1]/following-sibling::td/a/text()", 
                        namespaces={"re": "http://exslt.org/regular-expressions"})
    if subjects:
        mi.tags = subjects
        print "tags are "+str(mi.tags) 

    creators = root.xpath("//table/tr/td[re:test(text(), '\s*by', 'i')]/ancestor::tr[1]/td[2]/table/tr/td/a/text()", 
                        namespaces={"re": "http://exslt.org/regular-expressions"})
    if creators:
        print "authors are "+str(creators)
        mi.authors = creators

    return True

def main(args=sys.argv):
    print "running through main tests"
    import tempfile, os, time
    tdir = tempfile.gettempdir()
    br = browser()
    for isbn, title, author in [
            #('0899661343', 'On the Road', ['Jack Kerouac']), # basic test, no series, single author
            #('9780061952838', 'The Fellowship of the Ring', ['J. R. R. Tolkien']), # Series test, multi-author
            #('9780061952838', 'The Two Towers', ['J. R. R. Tolkien']), # Series test, book 2
            ('9780345505057', 'Deluge', ['Anne McCaffrey']) # Multiple authors
            #('', 'Deluge', ['Anne McCaffrey']) # Empty ISBN
            #(None, 'On the Road', ['Jack Kerouac']) # Nonetype ISBN
            ]:
        cpath = os.path.join(tdir, title+'.jpg')
        print "cpath is "+cpath
        st = time.time()
        curl = get_cover_url(isbn, title, author, br)
        print '\n\n Took ', time.time() - st, ' to get metadata\n\n'
        if curl is None:
            print 'No cover found for', title
        else:
            print "curl is "+curl
            #open(cpath, 'wb').write(br.open_novisit(curl).read())
            #print 'Cover for', title, 'saved to', cpath

        #import time
        
        #print get_social_metadata(title, author, None, isbn)
        #print '\n\n', time.time() - st, '\n\n'

    return 0

if __name__ == '__main__':
    sys.exit(main())
