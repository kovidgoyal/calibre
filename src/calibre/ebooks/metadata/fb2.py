#!/usr/bin/env python
from __future__ import with_statement
__license__   = 'GPL v3'
__copyright__ = '2008, Anatoly Shipitsin <norguhtar at gmail.com>'

'''Read meta information from fb2 files'''

import sys, os, mimetypes
from base64 import b64decode

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
    cp = soup.find('coverpage')
    cdata = None
    if cp:
        cimage = cp.find('image', attrs={'l:href':True})
        if cimage:
            id = cimage['l:href'].replace('#', '')
            binary = soup.find('binary', id=id, attrs={'content-type':True})
            if binary:
                mt = binary['content-type']
                exts = mimetypes.guess_all_extensions(mt)
                if not exts:
                    exts = ['.jpg']
                cdata = (exts[0][1:], b64decode(binary.string.strip()))
                
    if comments:
        comments = u''.join(comments.findAll(text=True))
    series = soup.find("sequence")
    mi = MetaInformation(title, author)
    mi.comments = comments
    mi.author_sort = lastname+'; '+firstname
    if series:
        mi.series = series.get('name', None)
        try:
            mi.series_index = int(series.get('number', None))
        except (TypeError, ValueError):
            pass
    if cdata:
        mi.cover_data = cdata
    return mi

def main(args=sys.argv):
    if len(args) != 2 or '--help' in args or '-h' in args:
        print >>sys.stderr, _('Usage:'), args[0], 'mybook.fb2'
        return 1
    
    path = os.path.abspath(os.path.expanduser(args[1]))
    print unicode(get_metadata(open(path, 'rb')))
    return 0

if __name__ == '__main__':
    sys.exit(main())
