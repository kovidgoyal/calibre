#!/usr/bin/env python
# License: GPLv3 Copyright: 2009, Kovid Goyal <kovid at kovidgoyal.net>


import os
import shutil
import sys

from calibre.constants import preferred_encoding
from calibre.ebooks.metadata import authors_to_string
from calibre.ptempfile import TemporaryDirectory
from calibre.utils.ipc.simple_worker import WorkerError, fork_job


def get_podofo():
    from calibre_extensions import podofo
    return podofo


def prep(val):
    if not val:
        return ''
    if not isinstance(val, str):
        val = val.decode(preferred_encoding, 'replace')
    return val.strip()


def set_metadata(stream, mi):
    with TemporaryDirectory('_podofo_set_metadata') as tdir:
        with open(os.path.join(tdir, 'input.pdf'), 'wb') as f:
            shutil.copyfileobj(stream, f)
        from calibre.ebooks.metadata.xmp import metadata_to_xmp_packet
        xmp_packet = metadata_to_xmp_packet(mi)

        try:
            result = fork_job('calibre.utils.podofo', 'set_metadata_', (tdir,
                mi.title, mi.authors, mi.book_producer, mi.tags, xmp_packet))
            touched = result['result']
        except WorkerError as e:
            raise Exception('Failed to set PDF metadata in (%s): %s'%(mi.title, e.orig_tb))
        if touched:
            with open(os.path.join(tdir, 'output.pdf'), 'rb') as f:
                f.seek(0, 2)
                if f.tell() > 100:
                    f.seek(0)
                    stream.seek(0)
                    stream.truncate()
                    shutil.copyfileobj(f, stream)
                    stream.flush()
    stream.seek(0)


def set_metadata_implementation(pdf_doc, title, authors, bkp, tags, xmp_packet):
    title = prep(title)
    touched = False
    if title and title != pdf_doc.title:
        pdf_doc.title = title
        touched = True

    author = prep(authors_to_string(authors))
    if author and author != pdf_doc.author:
        pdf_doc.author = author
        touched = True

    bkp = prep(bkp)
    if bkp and bkp != pdf_doc.creator:
        pdf_doc.creator = bkp
        touched = True
    if bkp and bkp != pdf_doc.producer:
        pdf_doc.producer = bkp
        touched = True

    try:
        tags = prep(', '.join([x.strip() for x in tags if x.strip()]))
        if tags != pdf_doc.keywords:
            pdf_doc.keywords = tags
            touched = True
    except Exception:
        pass

    try:
        current_xmp_packet = pdf_doc.get_xmp_metadata()
        if current_xmp_packet:
            from calibre.ebooks.metadata.xmp import merge_xmp_packet
            xmp_packet = merge_xmp_packet(current_xmp_packet, xmp_packet)
        pdf_doc.set_xmp_metadata(xmp_packet)
        touched = True
    except Exception:
        pass
    return touched


def set_metadata_(tdir, title, authors, bkp, tags, xmp_packet):
    podofo = get_podofo()
    os.chdir(tdir)
    p = podofo.PDFDoc()
    p.open('input.pdf')

    touched = set_metadata_implementation(p, title, authors, bkp, tags, xmp_packet)
    if touched:
        p.save('output.pdf')

    return touched


def get_xmp_metadata(path):
    podofo = get_podofo()
    p = podofo.PDFDoc()
    with open(path, 'rb') as f:
        raw = f.read()
    p.load(raw)
    return p.get_xmp_metadata()


def get_outline(path=None):
    if path is None:
        path = sys.argv[-1]
    podofo = get_podofo()
    p = podofo.PDFDoc()
    with open(path, 'rb') as f:
        raw = f.read()
    p.load(raw)
    return p.get_outline()['children']


def get_image_count(path):
    podofo = get_podofo()
    p = podofo.PDFDoc()
    with open(path, 'rb') as f:
        raw = f.read()
    p.load(raw)
    return p.image_count()


def list_fonts(pdf_doc):
    fonts = pdf_doc.list_fonts()
    ref_map = {f['Reference']: f for f in fonts}
    return ref_map


def remove_unused_fonts(pdf_doc):
    return pdf_doc.remove_unused_fonts()


def test_remove_unused_fonts(src):
    podofo = get_podofo()
    p = podofo.PDFDoc()
    p.open(src)
    remove_unused_fonts(p)
    dest = src.rpartition('.')[0] + '-removed.pdf'
    p.save(dest)
    print('Modified pdf saved to:', dest)


def dedup_type3_fonts(pdf_doc):
    return pdf_doc.dedup_type3_fonts()


def test_dedup_type3_fonts(src):
    podofo = get_podofo()
    p = podofo.PDFDoc()
    p.open(src)
    num = dedup_type3_fonts(p)
    dest = src.rpartition('.')[0] + '-removed.pdf'
    p.save(dest)
    print(f'Modified pdf with {num} glyphs removed saved to:', dest)


def test_list_fonts(src):
    podofo = get_podofo()
    p = podofo.PDFDoc()
    with open(src, 'rb') as f:
        raw = f.read()
    p.load(raw)
    import pprint
    pprint.pprint(list_fonts(p))


def test_save_to(src, dest):
    podofo = get_podofo()
    p = podofo.PDFDoc()
    with open(src, 'rb') as f:
        raw = f.read()
    p.load(raw)
    with open(dest, 'wb') as out:
        p.save_to_fileobj(out)
        print('Wrote PDF of size:', out.tell())


def test_podofo():
    import tempfile
    from io import BytesIO
    from calibre.ebooks.metadata.book.base import Metadata
    from calibre.ebooks.metadata.xmp import metadata_to_xmp_packet
    # {{{
    raw = b"%PDF-1.1\n%\xe2\xe3\xcf\xd3\n1 0 obj<</Type/Catalog/Metadata 6 0 R/Pages 2 0 R>>\nendobj\n2 0 obj<</Type/Pages/Count 1/Kids[ 3 0 R]/MediaBox[ 0 0 300 144]>>\nendobj\n3 0 obj<</Type/Page/Contents 4 0 R/Parent 2 0 R/Resources<</Font<</F1<</Type/Font/BaseFont/Times-Roman/Subtype/Type1>>>>>>>>\nendobj\n4 0 obj<</Length 55>>\nstream\n  BT\n    /F1 18 Tf\n    0 0 Td\n    (Hello World) Tj\n  ET\nendstream\nendobj\n5 0 obj<</Author(\xfe\xff\x00U\x00n\x00k\x00n\x00o\x00w\x00n)/CreationDate(D:20140919134038+05'00')/Producer(PoDoFo - http://podofo.sf.net)/Title(\xfe\xff\x00n\x00e\x00w\x00t)>>\nendobj\n6 0 obj<</Type/Metadata/Filter/FlateDecode/Length 584/Subtype/XML>>\nstream\nx\x9c\xed\x98\xcd\xb2\x930\x14\xc7\xf7}\n&.\x1d\x1ahoGa\x80\x8e\xb6\xe3x\x17ua\xaf\xe3\xd2\t\xc9i\x1b\x0b\x81&a\xc0\xfbj.|$_\xc1\xd0r\xe9\xb7V\x9d\xbb\x83\x15\x9c\x9c\xff\xff\x97\x8fs\xb2 \x18W9\xa1k\xd0V\x0cK.B\xf4\xf3\xfb\x0fdq\x16\xa2\xcf\xa3\x993\xcb'\xb0\xe2\xef\x1f%\xcc\x1f?<\xd0\xc75\xf5\x18\x1aG\xbd\xa0\xf2\xab4OA\x13\xabJ\x13\xa1\xfc*D\x84e1\xf8\xe6\xbd\x0ec\x14\xf5,+\x90l\xe1\x7f\x9c\xbek\x92\xccW\x88VZ\xe7>\xc6eY\xf6\xcba?\x93K\xecz\x9e\x87\x9d\x01\x1e\x0cl\x93a\xaboB\x93\xca\x16\xea\xc5\xd6\xa3q\x99\x82\xa2\x92\xe7\x9ag\xa2qc\xb45\xcb\x0b\x99l\xad\x18\xc5\x90@\nB+\xec\xf6]\x8c\xacZK\xe2\xac\xd0!j\xec\x8c!\xa3>\xdb\xfb=\x85\x1b\xd2\x9bD\xef#M,\xe15\xd4O\x88X\x86\xa8\xb2\x19,H\x91h\x14\x05x7z`\x81O<\x02|\x99VOBs\x9d\xc0\x7f\xe0\x05\x94\xfa\xd6)\x1c\xb1jx^\xc4\tW+\x90'\x13xK\x96\xf8Hy\x96X\xabU\x11\x7f\x05\xaa\xff\xa4=I\xab\x95T\x02\xd1\xd9)u\x0e\x9b\x0b\xcb\x8e>\x89\xb5\xc8Jqm\x91\x07\xaa-\xee\xc8{\x972=\xdd\xfa+\xe5d\xea\xb9\xad'\xa1\xfa\xdbj\xee\xd3,\xc5\x15\xc9M-9\xa6\x96\xdaD\xce6Wr\xd3\x1c\xdf3S~|\xc1A\xe2MA\x92F{\xb1\x0eM\xba?3\xdd\xc2\x88&S\xa2!\x1a8\xee\x9d\xedx\xb6\xeb=\xb8C\xff\xce\xf1\x87\xaf\xfb\xde\xe0\xd5\xc8\xf3^:#\x7f\xe8\x04\xf8L\xf2\x0fK\xcd%W\xe9\xbey\xea/\xa5\x89`D\xb2m\x17\t\x92\x822\xb7\x02(\x1c\x13\xc5)\x1e\x9c-\x01\xff\x1e\xc0\x16\xd5\xe5\r\xaaG\xcc\x8e\x0c\xff\xca\x8e\x92\x84\xc7\x12&\x93\xd6\xb3\x89\xd8\x10g\xd9\xfai\xe7\xedv\xde6-\x94\xceR\x9bfI\x91\n\x85\x8e}nu9\x91\xcd\xefo\xc6+\x90\x1c\x94\xcd\x05\x83\xea\xca\xd17\x16\xbb\xb6\xfc\xa22\xa9\x9bn\xbe0p\xfd\x88wAs\xc3\x9a+\x19\xb7w\xf2a#=\xdf\xd3A:H\x07\xe9 \x1d\xa4\x83t\x90\x0e\xd2A:H\x07yNH/h\x7f\xd6\x80`!*\xd18\xfa\x05\x94\x80P\xb0\nendstream\nendobj\nxref\n0 7\n0000000000 65535 f \n0000000015 00000 n \n0000000074 00000 n \n0000000148 00000 n \n0000000280 00000 n \n0000000382 00000 n \n0000000522 00000 n \ntrailer\n<</ID[<4D028D512DEBEFD964756764AD8FF726><4D028D512DEBEFD964756764AD8FF726>]/Info 5 0 R/Root 1 0 R/Size 7>>\nstartxref\n1199\n%%EOF\n"  # noqa
    # }}}
    mi = Metadata('title1', ['author1'])
    xmp_packet = metadata_to_xmp_packet(mi)
    podofo = get_podofo()
    p = podofo.PDFDoc()
    p.load(raw)
    p.title = mi.title
    p.author = mi.authors[0]
    p.set_xmp_metadata(xmp_packet)
    buf = BytesIO()
    p.save_to_fileobj(buf)
    raw = buf.getvalue()
    with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f:
        f.write(raw)
    try:
        p = podofo.PDFDoc()
        p.open(f.name)
        if (p.title, p.author) != (mi.title, mi.authors[0]):
            raise ValueError('podofo failed to set title and author in Info dict {} != {}'.format(
                (p.title, p.author), (mi.title, mi.authors[0])))
        if not p.get_xmp_metadata():
            raise ValueError('podofo failed to write XMP packet')
        del p
    finally:
        os.remove(f.name)


if __name__ == '__main__':
    get_xmp_metadata(sys.argv[-1])
