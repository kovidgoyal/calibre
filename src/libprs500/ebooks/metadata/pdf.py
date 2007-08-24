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

import sys, os, copy

from libprs500.ebooks.metadata import MetaInformation, get_parser
from libprs500.ptempfile import PersistentTemporaryFile

def get_metadata(stream):
    """ Return metadata as a L{MetaInfo} object """
    if hasattr(stream, 'name'):
        title = stream.name
    else:
        title = 'Unknown'
    mi = MetaInformation(title, 'Unknown')

    stream.seek(0)
    pt = PersistentTemporaryFile('.pdf')
    pt.write(stream.read())
    pt.close()
    return get_metadata_from_file(pt.name, mi)
    
def set_metadata(path, options):
    try:
        import podofo
        doc = podofo.PdfDocument()
        doc.Load(path)
        info = doc.GetInfo()
        if options.title:
            info.SetTitle(options.title)
        if options.authors:
            info.SetAuthor(options.authors)
        if options.category:
            info.SetSubject(options.category)
        pt = PersistentTemporaryFile('.pdf')
        pt.close() 
        doc.Write(pt.name)
        stream = open(path, 'wb')
        stream.write(open(pt.name, 'rb').read())
        stream.close()
    except ImportError:
        return False
    return True

def get_metadata_from_file(path, default_mi=None):
    if not default_mi:
        title = os.path.splitext(os.path.basename(path))[0]
        mi = MetaInformation(title, 'Unknown')
    else:
        mi = copy.copy(default_mi)
    try:
        import podofo
        doc = podofo.PdfDocument()
        doc.Load(path)
        info = doc.GetInfo()
        if info.GetTitle():
            mi.title = info.GetTitle()
        if info.GetAuthor():
            mi.authors = info.GetAuthor().split(',')
        if info.GetSubject():
            mi.category = info.GetSubject()
    except ImportError:        
        pass
    finally:
        return mi
    

def main(args=sys.argv):
    parser = get_parser('pdf')
    options, args = parser.parse_args(args)
    if len(args) != 2:
        print >>sys.stderr, 'No filename specified.'
        return 1
    
    path = os.path.abspath(os.path.expanduser(args[1]))
    if not set_metadata(path, options):
        print >>sys.stderr, 'You do not have the podofo python extension installed. Cannot read PDF files.'
        return 1
    
    print get_metadata_from_file(path)
    return 0

if __name__ == '__main__':
    sys.exit(main())