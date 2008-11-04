#!/usr/bin/env  python
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

'''
Fetch metadata using Amazon AWS
'''
import re

from calibre import browser


BASE_URL = 'http://ecs.amazonaws.com/onca/xml?Service=AWSECommerceService&AWSAccessKeyId=%(key)s&Operation=ItemLookup&ItemId=1416551727&ResponseGroup=%(group)s'

import sys

def get_rating(isbn, key):
    br = browser()
    url = BASE_URL%dict(key=key, group='Reviews')
    raw = br.open(url).read()
    match = re.search(r'<AverageRating>([\d.]+)</AverageRating>', raw)
    if match:
        return float(match.group(1))
    
def get_cover_url(isbn, key):
    br = browser()
    url = BASE_URL%dict(key=key, group='Images')
    raw = br.open(url).read()
    match = re.search(r'<LargeImage><URL>(.+?)</URL>', raw)
    if match:
        return match.group(1)

def get_editorial_review(isbn, key):
    br = browser()
    url = BASE_URL%dict(key=key, group='EditorialReview')
    raw = br.open(url).read()
    match = re.compile(r'<EditorialReview>.*?<Content>(.+?)</Content>', re.DOTALL).search(raw)
    if match:
        return match.group(1)

def main(args=sys.argv):
    print 'Rating:', get_rating(args[1], args[2])
    print 'Cover:', get_rating(args[1], args[2])
    print 'EditorialReview:', get_editorial_review(args[1], args[2])
    
    return 0

if __name__ == '__main__':
    sys.exit(main())