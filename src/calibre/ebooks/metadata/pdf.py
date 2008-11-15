__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
'''Read meta information from PDF files'''

import sys, os, re

from calibre.ebooks.metadata import MetaInformation, authors_to_string, get_parser
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

def set_metadata(stream, mi):
    stream.seek(0)
    raw = stream.read()
    if mi.title:
        tit = mi.title.encode('utf-8') if isinstance(mi.title, unicode) else mi.title
        raw = re.compile(r'<<.*?/Title\((.+?)\)', re.DOTALL).sub(lambda m: m.group().replace(m.group(1), tit), raw)
    if mi.authors:
        au = authors_to_string(mi.authors)
        if isinstance(au, unicode):
            au = au.encode('utf-8')
        raw = re.compile(r'<<.*?/Author\((.+?)\)', re.DOTALL).sub(lambda m: m.group().replace(m.group(1), au), raw)
    stream.seek(0)
    stream.truncate()
    stream.write(raw)
    stream.seek(0)

def option_parser():
    p = get_parser('pdf')
    p.remove_option('--category')
    p.remove_option('--comment')
    return p
            
def main(args=sys.argv):
    #p = option_parser()
    #opts, args = p.parse_args(args)
    if len(args) != 2:
        print >>sys.stderr, _('Usage: pdf-meta file.pdf')
        print >>sys.stderr, _('No filename specified.')
        return 1
    
    stream = open(os.path.abspath(os.path.expanduser(args[1])), 'r+b')
    #mi = MetaInformation(opts.title, opts.authors)
    #if mi.title or mi.authors:
    #    set_metadata(stream, mi)
    print unicode(get_metadata(stream)).encode('utf-8')
    
    return 0

if __name__ == '__main__':
    sys.exit(main())