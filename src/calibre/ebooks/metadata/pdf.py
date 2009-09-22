from __future__ import with_statement
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
'''Read meta information from PDF files'''

from functools import partial

from calibre import plugins, prints
from calibre.ebooks.metadata import MetaInformation, string_to_authors#, authors_to_string

pdfreflow, pdfreflow_error = plugins['pdfreflow']

def get_metadata(stream, cover=True):
    if pdfreflow is None:
        raise RuntimeError(pdfreflow_error)
    info = pdfreflow.get_metadata(stream.read(), cover)
    title = info.get('Title', None)
    au = info.get('Author', None)
    if au is None:
        au = [_('Unknown')]
    else:
        au = string_to_authors(au)
    mi = MetaInformation(title, au)

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
            prints(title, 'is an encrypted document, cover extraction not allowed.')
        else:
            mi.cover_data = ('png', data)

    return mi



get_quick_metadata = partial(get_metadata, cover=False)

'''
import sys, os, cStringIO
from threading import Thread

from calibre import StreamReadWrapper
from calibre.ptempfile import TemporaryDirectory
try:
    from calibre.utils.PythonMagickWand import \
        NewMagickWand, MagickReadImage, MagickSetImageFormat, \
        MagickWriteImage, ImageMagick
    _imagemagick_loaded = True
except:
    _imagemagick_loaded = False
from calibre.ebooks.metadata import MetaInformation, string_to_authors, authors_to_string
from calibre.utils.pdftk import set_metadata as pdftk_set_metadata
from calibre.utils.podofo import get_metadata as podofo_get_metadata, \
    set_metadata as podofo_set_metadata, Unavailable, get_metadata_quick
from calibre.utils.poppler import get_metadata as get_metadata_poppler, NotAvailable

def get_quick_metadata(stream):
    try:
       return get_metadata_poppler(stream, False)
    except NotAvailable:
        pass

    return get_metadata_pypdf(stream)
    raw = stream.read()
    mi = get_metadata_quick(raw)
    if mi.title == '_':
        mi.title = getattr(stream, 'name', _('Unknown'))
        mi.title = mi.title.rpartition('.')[0]
    return mi


def get_metadata(stream, extract_cover=True):
    try:
       return get_metadata_poppler(stream, extract_cover)
    except NotAvailable:
        pass
    try:
        with TemporaryDirectory('_pdfmeta') as tdir:
            cpath = os.path.join(tdir, 'cover.pdf')
            if not extract_cover:
                cpath = None
            mi = podofo_get_metadata(stream, cpath=cpath)
            if mi.cover is not None:
                cdata = get_cover(mi.cover)
                mi.cover = None
                if cdata is not None:
                    mi.cover_data = ('jpg', cdata)
    except Unavailable:
        mi = get_metadata_pypdf(stream)
    return mi


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


def get_metadata_pypdf(stream):
    """ Return metadata as a L{MetaInfo} object """
    from pyPdf import PdfFileReader
    mi = MetaInformation(_('Unknown'), [_('Unknown')])
    try:
        with StreamReadWrapper(stream) as stream:
            info = PdfFileReader(stream).getDocumentInfo()
            if info.title:
                mi.title = info.title
            if info.author:
                mi.author = info.author
                mi.authors = string_to_authors(info.author)
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

def get_cover(cover_path):
    with ImageMagick():
        wand = NewMagickWand()
        MagickReadImage(wand, cover_path)
        MagickSetImageFormat(wand, 'JPEG')
        MagickWriteImage(wand, '%s.jpg' % cover_path)
    return open('%s.jpg' % cover_path, 'rb').read()
'''


