__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
'''Read meta information from PDF files'''

import sys, os

from calibre.ebooks.metadata import MetaInformation
from pyPdf import PdfFileReader

def get_metadata(stream):
    """ Return metadata as a L{MetaInfo} object """
    mi = MetaInformation(_('Unknown'), [_('Unknown')])
    stream.seek(0)
    try:
        info = PdfFileReader(stream).getDocumentInfo()
        if info.title:
            mi.title = info.title
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
        msg = u'Couldn\'t read metadata from pdf: %s with error %s'%(mi.title, unicode(err))
        print >>sys.stderr, msg.encode('utf8')
    return mi
        
            
def main(args=sys.argv):
    if len(args) != 2:
        print >>sys.stderr, _('Usage: pdf-meta file.pdf')
        print >>sys.stderr, _('No filename specified.')
        return 1
    
    path = os.path.abspath(os.path.expanduser(args[1]))
    print get_metadata(open(path, 'rb'))
    return 0

if __name__ == '__main__':
    sys.exit(main())