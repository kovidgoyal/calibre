from __future__ import with_statement
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
'''Read meta information from PDF files'''

import sys, os, cStringIO
from threading import Thread

from calibre import FileWrapper
from calibre.ebooks.metadata import MetaInformation, authors_to_string, get_parser
from pyPdf import PdfFileReader, PdfFileWriter

def get_metadata(stream):
    """ Return metadata as a L{MetaInfo} object """
    mi = MetaInformation(_('Unknown'), [_('Unknown')])
    stream.seek(0)
    try:
        with FileWrapper(stream) as stream:
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

class MetadataWriter(Thread):

    def __init__(self, out_pdf, buf):
        self.out_pdf = out_pdf
        self.buf = buf
        Thread.__init__(self)
        self.daemon = True

    def run(self):
        try:
            self.out_pdf.write(self.buf)
        except RuntimeError:
            pass

def set_metadata(stream, mi):
    stream.seek(0)

    # Use a StringIO object for the pdf because we will want to over
    # write it later and if we are working on the stream directly it
    # could cause some issues.
    raw = cStringIO.StringIO(stream.read())
    orig_pdf = PdfFileReader(raw)

    title = mi.title if mi.title else orig_pdf.documentInfo.title
    author = authors_to_string(mi.authors) if mi.authors else orig_pdf.documentInfo.author

    out_pdf = PdfFileWriter(title=title, author=author)
    out_str = cStringIO.StringIO()
    writer = MetadataWriter(out_pdf, out_str)
    for page in orig_pdf.pages:
        out_pdf.addPage(page)

    writer.start()
    writer.join(15) # Wait 15 secs for writing to complete
    out_pdf.killed = True
    writer.join()
    if out_pdf.killed:
        print 'Failed to set metadata: took too long'
        return

    stream.seek(0)
    stream.truncate()
    out_str.seek(0)
    stream.write(out_str.read())
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
