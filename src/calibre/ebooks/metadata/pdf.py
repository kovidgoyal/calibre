from __future__ import with_statement
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
'''Read meta information from PDF files'''

#import re
from functools import partial

from calibre import prints
from calibre.constants import plugins
from calibre.ebooks.metadata import MetaInformation, string_to_authors, authors_to_string

pdfreflow, pdfreflow_error = plugins['pdfreflow']

#_isbn_pat = re.compile(r'ISBN[: ]*([-0-9Xx]+)')

def get_metadata(stream, cover=True):
    if pdfreflow is None:
        raise RuntimeError(pdfreflow_error)
    raw = stream.read()
    #isbn = _isbn_pat.search(raw)
    #if isbn is not None:
    #    isbn = isbn.group(1).replace('-', '').replace(' ', '')
    info = pdfreflow.get_metadata(raw, cover)
    title = info.get('Title', None)
    au = info.get('Author', None)
    if au is None:
        au = [_('Unknown')]
    else:
        au = string_to_authors(au)
    mi = MetaInformation(title, au)
    #if isbn is not None:
    #    mi.isbn = isbn

    creator = info.get('Creator', None)
    if creator:
        mi.book_producer = creator

    keywords = info.get('Keywords', None)
    mi.tags = []
    if keywords:
        mi.tags = [x.strip() for x in keywords.split(',')]

    subject = info.get('Subject', None)
    if subject:
        mi.tags.insert(0, subject)

    if cover and 'cover' in info:
        data = info['cover']
        if data is None:
            prints(title, 'has no pages, cover extraction impossible.')
        else:
            mi.cover_data = ('png', data)

    return mi

get_quick_metadata = partial(get_metadata, cover=False)

import cStringIO
from threading import Thread

from calibre.utils.pdftk import set_metadata as pdftk_set_metadata
from calibre.utils.podofo import set_metadata as podofo_set_metadata, Unavailable

def set_metadata(stream, mi):
    stream.seek(0)
    try:
        return podofo_set_metadata(stream, mi)
    except Unavailable:
        pass
    try:
        return pdftk_set_metadata(stream, mi)
    except:
        pass
    set_metadata_pypdf(stream, mi)


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

def set_metadata_pypdf(stream, mi):
    # Use a StringIO object for the pdf because we will want to over
    # write it later and if we are working on the stream directly it
    # could cause some issues.

    from pyPdf import PdfFileReader, PdfFileWriter
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
    writer.join(10) # Wait 10 secs for writing to complete
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


