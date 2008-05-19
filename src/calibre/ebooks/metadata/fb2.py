#!/usr/bin/env python
from __future__ import with_statement
__license__   = 'GPL v3'
__copyright__ = '2008, Anatoly Shipitsin <norguhtar at gmail.com>'

'''Read meta information from fb2 files'''

import sys, os

from calibre.ebooks.BeautifulSoup import BeautifulStoneSoup
from calibre.ebooks.metadata import MetaInformation

def get_metadata(stream):
    """ Return metadata as a L{MetaInfo} object """
    soup =  BeautifulStoneSoup(stream.read())
    firstname = soup.find("first-name").contents[0]
    lastname = soup.find("last-name").contents[0]
    author= [firstname+" "+lastname]
    title = soup.find("book-title").string
    comments = soup.find("annotation")
    if comments and len(comments) > 1:
            comments = comments.p.contents[0]
    series = soup.find("sequence")
    series_name = series['name']
 #   series_index = series.index
    mi = MetaInformation(title, author)
    mi.comments = comments
    mi.category = series_name
 #   mi.series_index = series_index
    return mi

def main(args=sys.argv):
    if len(args) != 2 or '--help' in args or '-h' in args:
        print >>sys.stderr, _('Usage:'), args[0], _('mybook.fb2')
        return 1
    
    path = os.path.abspath(os.path.expanduser(args[1]))
    print unicode(get_metadata(open(path, 'rb')))
    return 0

if __name__ == '__main__':
    sys.exit(main())
