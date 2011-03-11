#!/usr/bin/env  python
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

'''
Fetch metadata using Amazon AWS
'''
import sys, re
from threading import RLock

from lxml import html
from lxml.html import soupparser

from calibre import browser
from calibre.ebooks.metadata import check_isbn
from calibre.ebooks.metadata.book.base import Metadata
from calibre.ebooks.chardet import xml_to_unicode
from calibre.library.comments import sanitize_comments_html

asin_cache = {}
cover_url_cache = {}
cache_lock = RLock()

def find_asin(br, isbn):
    q = 'http://www.amazon.com/s/?search-alias=aps&field-keywords='+isbn
    res = br.open_novisit(q)
    raw = res.read()
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
    if root.xpath('//*[@id="errorMessage"]'):
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
                    mi.rating = float(m.group(1))/float(m.group(2)) * 5
                    break
                except:
                    pass

    desc = root.xpath('//div[@id="productDescription"]/*[@class="content"]')
    if desc:
        desc = desc[0]
        for c in desc.xpath('descendant::*[@class="seeAll" or'
                ' @class="emptyClear" or @href]'):
            c.getparent().remove(c)
        desc = html.tostring(desc, method='html', encoding=unicode).strip()
        # remove all attributes from tags
        desc = re.sub(r'<([a-zA-Z0-9]+)\s[^>]+>', r'<\1>', desc)
        # Collapse whitespace
        #desc = re.sub('\n+', '\n', desc)
        #desc = re.sub(' +', ' ', desc)
        # Remove the notice about text referring to out of print editions
        desc = re.sub(r'(?s)<em>--This text ref.*?</em>', '', desc)
        # Remove comments
        desc = re.sub(r'(?s)<!--.*?-->', '', desc)
        mi.comments = sanitize_comments_html(desc)

    return True


def main(args=sys.argv):
    import tempfile, os
    tdir = tempfile.gettempdir()
    br = browser()
    for title, isbn in [
            ('The Heroes', '9780316044981'), # Test find_asin
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
        mi = get_social_metadata(title, None, None, isbn)
        if not mi.comments:
            print 'Failed to downlaod social metadata for', title
            return 1
        #print '\n\n', time.time() - st, '\n\n'
        print '\n'

    return 0

if __name__ == '__main__':
    sys.exit(main())
