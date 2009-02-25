'''Read meta information from PDF files'''

from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'

import sys, os, re, StringIO

from calibre.ebooks.metadata import MetaInformation, authors_to_string, get_parser
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

def get_cover(stream):
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
            
            data = StringIO.StringIO()
            img.save(data, 'JPEG')
            return data.getvalue()
    except:
        import traceback
        traceback.print_exc()

def option_parser():
    p = get_parser('pdf')
    p.remove_option('--category')
    p.remove_option('--comment')
    p.add_option('--get-cover', default=False, action='store_true',
                      help=_('Extract the cover'))
    return p
            
def main(args=sys.argv):
    p = option_parser()
    opts, args = p.parse_args(args)

    with open(os.path.abspath(os.path.expanduser(args[1])), 'r+b') as stream:
        mi = get_metadata(stream, extract_cover=opts.get_cover)
        changed = False
        if opts.title:
            mi.title = opts.title
            changed = True
        if opts.authors:
            mi.authors = opts.authors.split(',')
            changed = True
        
        if changed:
            set_metadata(stream, mi)
        print unicode(get_metadata(stream, extract_cover=False)).encode('utf-8')
        
    if mi.cover_data[1] is not None:
        cpath = os.path.splitext(os.path.basename(args[1]))[0] + '_cover.jpg'
        with open(cpath, 'wb') as f:
            f.write(mi.cover_data[1])
            print 'Cover saved to', f.name
        
    return 0

if __name__ == '__main__':
    sys.exit(main())
