#!/usr/bin/env  python
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

'''
Fetch metadata using Amazon AWS
'''
import sys, re

from lxml import etree

from calibre import browser
from calibre.utils.date import parse_date, utcnow
from calibre.ebooks.metadata import MetaInformation, string_to_authors

AWS_NS = 'http://webservices.amazon.com/AWSECommerceService/2005-10-05'

def AWS(tag):
    return '{%s}%s'%(AWS_NS, tag)

class ISBNNotFound(ValueError):
    pass

def check_for_errors(root, isbn):
    err = root.find('.//'+AWS('Error'))
    if err is not None:
        text = etree.tostring(err, method='text', pretty_print=True,
                    encoding=unicode)
        if 'AWS.InvalidParameterValue'+isbn in text:
            raise ISBNNotFound(isbn)
        raise Exception('Failed to get metadata with error: '\
                + text)

def get_social_metadata(title, authors, publisher, isbn):
    mi = MetaInformation(title, authors)
    if isbn:
        br = browser()
        response_xml = br.open('http://status.calibre-ebook.com/aws/metadata/'+isbn).read()
        root = etree.fromstring(response_xml)
        try:
            check_for_errors(root, isbn)
        except ISBNNotFound:
            return mi
        mi.title = root.findtext('.//'+AWS('Title'))
        authors = [x.text for x in root.findall('.//'+AWS('Author'))]
        if authors:
            mi.authors = []
            for x in authors:
                mi.authors.extend(string_to_authors(x))
        mi.publisher = root.findtext('.//'+AWS('Publisher'))
        try:
            d = root.findtext('.//'+AWS('PublicationDate'))
            if d:
                default = utcnow().replace(day=15)
                d = parse_date(d[0].text, assume_utc=True, default=default)
                mi.pubdate = d
        except:
            pass
        try:
            rating = float(root.findtext('.//'+AWS('AverageRating')))
            num_of_reviews = int(root.findtext('.//'+AWS('TotalReviews')))
            if num_of_reviews > 4 and rating > 0 and rating < 5:
                mi.rating = rating
        except:
            pass
        tags = [x.text for x in root.findall('.//%s/%s'%(AWS('Subjects'),
            AWS('Subject')))]
        if tags:
            mi.tags = []
            for x in tags:
                mi.tags.extend([y.strip() for y in x.split('/')])
            mi.tags = [x.replace(',', ';') for x in mi.tags]
        comments = root.find('.//%s/%s'%(AWS('EditorialReview'),
            AWS('Content')))
        if comments is not None:
            mi.comments = etree.tostring(comments,
                    method='text', encoding=unicode)
            mi.comments = re.sub('<([pP]|DIV)>', '\n\n', mi.comments)
            mi.comments = re.sub('</?[iI]>', '*', mi.comments)
            mi.comments = re.sub('</?[bB]>', '**', mi.comments)
            mi.comments = re.sub('<BR>', '\n\n', mi.comments)
            mi.comments = re.sub('<[^>]+>', '', mi.comments)
            mi.comments = mi.comments.strip()
            mi.comments = _('EDITORIAL REVIEW')+':\n\n'+mi.comments

        return mi



def main(args=sys.argv):
    print get_social_metadata(None, None, None, '9781416551720')
    return 0

if __name__ == '__main__':
    sys.exit(main())
