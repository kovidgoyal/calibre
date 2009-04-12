from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
'''Read meta information from PDF files'''

import sys, os, StringIO

from calibre.ebooks.metadata import MetaInformation, authors_to_string
from calibre.ptempfile import TemporaryDirectory
from pyPdf import PdfFileReader, PdfFileWriter
import Image
try:
    from calibre.utils.PythonMagickWand import \
        NewMagickWand, MagickReadImage, MagickSetImageFormat, MagickWriteImage
    _imagemagick_loaded = True
except:
    _imagemagick_loaded = False

def get_metadata(stream, extract_cover=True):
    """ Return metadata as a L{MetaInfo} object """
    mi = MetaInformation(_('Unknown'), [_('Unknown')])
    stream.seek(0)

    if extract_cover and _imagemagick_loaded:
        try:
            cdata = get_cover(stream)
            if cdata is not None:
                mi.cover_data = ('jpg', cdata)
        except:
            import traceback
            traceback.print_exc()

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

    # Use a StringIO object for the pdf because we will want to over
    # write it later and if we are working on the stream directly it
    # could cause some issues.
    raw = StringIO.StringIO(stream.read())
    orig_pdf = PdfFileReader(raw)

    title = mi.title if mi.title else orig_pdf.documentInfo.title
    author = authors_to_string(mi.authors) if mi.authors else orig_pdf.documentInfo.author

    out_pdf = PdfFileWriter(title=title, author=author)
    for page in orig_pdf.pages:
        out_pdf.addPage(page)

    out_str = StringIO.StringIO()
    out_pdf.write(out_str)

    stream.seek(0)
    stream.truncate()
    out_str.seek(0)
    stream.write(out_str.read())
    stream.seek(0)

def get_cover(stream):
    data = StringIO.StringIO()

    try:
        pdf = PdfFileReader(stream)
        output = PdfFileWriter()

        if len(pdf.pages) >= 1:
            output.addPage(pdf.getPage(0))

        with TemporaryDirectory('_pdfmeta') as tdir:
            cover_path = os.path.join(tdir, 'cover.pdf')

            outputStream = file(cover_path, "wb")
            output.write(outputStream)
            outputStream.close()

            wand = NewMagickWand()
            MagickReadImage(wand, cover_path)
            MagickSetImageFormat(wand, 'JPEG')
            MagickWriteImage(wand, '%s.jpg' % cover_path)

            img = Image.open('%s.jpg' % cover_path)

            img.save(data, 'JPEG')
    except:
        import traceback
        traceback.print_exc()

    return data.getvalue()
