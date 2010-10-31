#!/usr/bin/env  python
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

'''
Fetch metadata using Amazon AWS
'''
import sys, re

from lxml import html

from calibre import browser
from calibre.ebooks.metadata import check_isbn
from calibre.ebooks.metadata.book.base import Metadata
from calibre.ebooks.chardet import xml_to_unicode
from calibre.library.comments import sanitize_comments_html

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
    if len(isbn) == 13:
        try:
            asin = find_asin(br, isbn)
        except:
            import traceback
            traceback.print_exc()
            asin = None
    else:
        asin = isbn
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
    if asin:
        if get_metadata(br, asin, mi):
            return mi
    from calibre.ebooks.metadata.xisbn import xisbn
    for i in xisbn.get_associated_isbns(isbn):
        asin = to_asin(br, i)
        if get_metadata(br, asin, mi):
            return mi
    return mi

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
    root = html.fromstring(raw)
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
    # Test xisbn
    #print get_social_metadata('Learning Python', None, None, '8324616489')
    #print

    # Test sophisticated comment formatting
    print get_social_metadata('Swan Thieves', None, None, '9781416580829')
    print
    return

    # Random tests
    print get_social_metadata('Star Trek: Destiny: Mere Mortals', None, None, '9781416551720')
    print
    print get_social_metadata('The Great Gatsby', None, None, '0743273567')

    return 0

if __name__ == '__main__':
    sys.exit(main())
