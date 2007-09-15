##    Copyright (C) 2007 Kovid Goyal kovid@kovidgoyal.net
##    This program is free software; you can redistribute it and/or modify
##    it under the terms of the GNU General Public License as published by
##    the Free Software Foundation; either version 2 of the License, or
##    (at your option) any later version.
##
##    This program is distributed in the hope that it will be useful,
##    but WITHOUT ANY WARRANTY; without even the implied warranty of
##    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
##    GNU General Public License for more details.
##
##    You should have received a copy of the GNU General Public License along
##    with this program; if not, write to the Free Software Foundation, Inc.,
##    51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
'''Read meta information from PDF files'''

import sys, os

from libprs500.ebooks.metadata import MetaInformation
from libprs500.ebooks.pyPdf import PdfFileReader

def get_metadata(stream):
    """ Return metadata as a L{MetaInfo} object """
    if hasattr(stream, 'name'):
        title = os.path.splitext(os.path.basename(stream.name))[0]
    else:
        title = 'Unknown'
    mi = MetaInformation(title, ['Unknown'])
    stream.seek(0)
    try:
        info = PdfFileReader(stream).getDocumentInfo()
        if info.title:
            mi.title = title
        if info.author:
            src = info.author.split('&')
            authors = []
            for au in src:
                authors += au.split(',')
            mi.authors = authors
            mi.author = info.author
        if info.subject:
            mi.category = info.subject
    except Exception, err:
        raise
        print >>sys.stderr, 'Couldn\'t read metadata from pdf: %s with error %s'%(mi.title, str(err))
    return mi
        
            
def main(args=sys.argv):
    if len(args) != 2:
        print >>sys.stderr, 'No filename specified.'
        return 1
    
    path = os.path.abspath(os.path.expanduser(args[1]))
    print get_metadata(open(path, 'rb'))
    return 0

if __name__ == '__main__':
    sys.exit(main())