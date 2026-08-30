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
            result = fork_job(
                'calibre.utils.podofo',
                'set_metadata_',
                (tdir, mi.title, mi.authors, mi.book_producer, mi.tags, xmp_packet),
            )
            touched = result['result']
        except WorkerError as e:
            raise Exception(f'Failed to set PDF metadata in ({mi.title}): {e.orig_tb}')
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
        tags = prep(', '.join(x.strip() for x in tags if x.strip()))
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


def add_image_page(pdf_doc, image_data, page_size=None, page_num=1, preserve_aspect_ratio=True):
    if page_size is None:
        from qt.core import QPageSize

        p = QPageSize(QPageSize.PageSizeId.A4).rect(QPageSize.Unit.Point)
        page_size = p.left(), p.top(), p.width(), p.height()
    pdf_doc.add_image_page(image_data, *page_size, *page_size, page_num, preserve_aspect_ratio)


def get_page_count(path: str) -> int:
    podofo = get_podofo()
    p = podofo.PDFDoc()
    with open(path, 'rb') as f:
        raw = f.read()
    p.load(raw)
    return p.page_count()


def test_add_image_page(image='/t/t.jpg', dest='/t/t.pdf', **kw):
    image_data = open(image, 'rb').read()
    podofo = get_podofo()
    p = podofo.PDFDoc()
    add_image_page(p, image_data, **kw)
    p.save(dest)


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


def test_roundtrip(src, dest):
    podofo = get_podofo()
    p = podofo.PDFDoc()
    p.open(src)
    p.save(dest)


def sample_pdf_data() -> bytes:
    # {{{
    raw = b"%PDF-1.1\n%\xe2\xe3\xcf\xd3\n1 0 obj<</Type/Catalog/Metadata 6 0 R/Pages 2 0 R>>\nendobj\n2 0 obj<</Type/Pages/Count 1/Kids[ 3 0 R]/MediaBox[ 0 0 300 144]>>\nendobj\n3 0 obj<</Type/Page/Contents 4 0 R/Parent 2 0 R/Resources<</Font<</F1<</Type/Font/BaseFont/Times-Roman/Subtype/Type1>>>>>>>>\nendobj\n4 0 obj<</Length 55>>\nstream\n  BT\n    /F1 18 Tf\n    0 0 Td\n    (Hello World) Tj\n  ET\nendstream\nendobj\n5 0 obj<</Author(\xfe\xff\x00U\x00n\x00k\x00n\x00o\x00w\x00n)/CreationDate(D:20140919134038+05'00')/Producer(PoDoFo - http://podofo.sf.net)/Title(\xfe\xff\x00n\x00e\x00w\x00t)>>\nendobj\n6 0 obj<</Type/Metadata/Filter/FlateDecode/Length 584/Subtype/XML>>\nstream\nx\x9c\xed\x98\xcd\xb2\x930\x14\xc7\xf7}\n&.\x1d\x1ahoGa\x80\x8e\xb6\xe3x\x17ua\xaf\xe3\xd2\t\xc9i\x1b\x0b\x81&a\xc0\xfbj.|$_\xc1\xd0r\xe9\xb7V\x9d\xbb\x83\x15\x9c\x9c\xff\xff\x97\x8fs\xb2 \x18W9\xa1k\xd0V\x0cK.B\xf4\xf3\xfb\x0fdq\x16\xa2\xcf\xa3\x993\xcb'\xb0\xe2\xef\x1f%\xcc\x1f?<\xd0\xc75\xf5\x18\x1aG\xbd\xa0\xf2\xab4OA\x13\xabJ\x13\xa1\xfc*D\x84e1\xf8\xe6\xbd\x0ec\x14\xf5,+\x90l\xe1\x7f\x9c\xbek\x92\xccW\x88VZ\xe7>\xc6eY\xf6\xcba?\x93K\xecz\x9e\x87\x9d\x01\x1e\x0cl\x93a\xaboB\x93\xca\x16\xea\xc5\xd6\xa3q\x99\x82\xa2\x92\xe7\x9ag\xa2qc\xb45\xcb\x0b\x99l\xad\x18\xc5\x90@\nB+\xec\xf6]\x8c\xacZK\xe2\xac\xd0!j\xec\x8c!\xa3>\xdb\xfb=\x85\x1b\xd2\x9bD\xef#M,\xe15\xd4O\x88X\x86\xa8\xb2\x19,H\x91h\x14\x05x7z`\x81O<\x02|\x99VOBs\x9d\xc0\x7f\xe0\x05\x94\xfa\xd6)\x1c\xb1jx^\xc4\tW+\x90'\x13xK\x96\xf8Hy\x96X\xabU\x11\x7f\x05\xaa\xff\xa4=I\xab\x95T\x02\xd1\xd9)u\x0e\x9b\x0b\xcb\x8e>\x89\xb5\xc8Jqm\x91\x07\xaa-\xee\xc8{\x972=\xdd\xfa+\xe5d\xea\xb9\xad'\xa1\xfa\xdbj\xee\xd3,\xc5\x15\xc9M-9\xa6\x96\xdaD\xce6Wr\xd3\x1c\xdf3S~|\xc1A\xe2MA\x92F{\xb1\x0eM\xba?3\xdd\xc2\x88&S\xa2!\x1a8\xee\x9d\xedx\xb6\xeb=\xb8C\xff\xce\xf1\x87\xaf\xfb\xde\xe0\xd5\xc8\xf3^:#\x7f\xe8\x04\xf8L\xf2\x0fK\xcd%W\xe9\xbey\xea/\xa5\x89`D\xb2m\x17\t\x92\x822\xb7\x02(\x1c\x13\xc5)\x1e\x9c-\x01\xff\x1e\xc0\x16\xd5\xe5\r\xaaG\xcc\x8e\x0c\xff\xca\x8e\x92\x84\xc7\x12&\x93\xd6\xb3\x89\xd8\x10g\xd9\xfai\xe7\xedv\xde6-\x94\xceR\x9bfI\x91\n\x85\x8e}nu9\x91\xcd\xefo\xc6+\x90\x1c\x94\xcd\x05\x83\xea\xca\xd17\x16\xbb\xb6\xfc\xa22\xa9\x9bn\xbe0p\xfd\x88wAs\xc3\x9a+\x19\xb7w\xf2a#=\xdf\xd3A:H\x07\xe9 \x1d\xa4\x83t\x90\x0e\xd2A:H\x07yNH/h\x7f\xd6\x80`!*\xd18\xfa\x05\x94\x80P\xb0\nendstream\nendobj\nxref\n0 7\n0000000000 65535 f \n0000000015 00000 n \n0000000074 00000 n \n0000000148 00000 n \n0000000280 00000 n \n0000000382 00000 n \n0000000522 00000 n \ntrailer\n<</ID[<4D028D512DEBEFD964756764AD8FF726><4D028D512DEBEFD964756764AD8FF726>]/Info 5 0 R/Root 1 0 R/Size 7>>\nstartxref\n1199\n%%EOF\n"  # noqa: E501
    # }}}
    return raw


def test_podofo():
    import tempfile

    from calibre.ebooks.metadata.book.base import Metadata
    from calibre.ebooks.metadata.xmp import metadata_to_xmp_packet

    mi = Metadata('title1', ['xmp_author'])
    podofo = get_podofo()
    p = podofo.PDFDoc()
    raw = sample_pdf_data()
    p.load(raw)
    p.title = 'info title'
    p.author = 'info author'
    p.keywords = 'a, b'
    if p.version != '1.1':
        raise ValueError('Incorrect PDF version')
    xmp_packet = metadata_to_xmp_packet(mi)
    # print(p.get_xmp_metadata().decode())
    p.set_xmp_metadata(xmp_packet)
    # print(p.get_xmp_metadata().decode())
    with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f:
        p.save_to_fileobj(f)
        f.seek(0)
        fraw = f.read()
        wraw = p.write()
        if fraw != wraw:
            raise ValueError('write() and save_to_fileobj() resulted in different output')
    try:
        p = podofo.PDFDoc()
        p.open(f.name)
        if (p.title, p.author, p.keywords) != ('info title', 'info author', 'a, b'):
            raise ValueError(
                'podofo failed to set title and author in Info dict {} != {}'.format((p.title, p.author, p.keywords), ('info title', 'info author', 'a, b'))
            )
        xmp = p.get_xmp_metadata().decode()
        if 'xmp_author' not in xmp:
            raise ValueError('Failed to set XML block, received:\n' + xmp)
        del p
    finally:
        os.remove(f.name)
    a = podofo.PDFDoc()
    a.load(raw)
    b = podofo.PDFDoc()
    b.load(raw)
    a.append(b)
    if a.page_count() != 2 * b.page_count():
        raise ValueError('Appending failed')


def develop(path=sys.argv[-1]):
    podofo = get_podofo()
    p = podofo.PDFDoc()
    p.open(path)
    p.title = 'test'


def find_tests():
    import base64
    import unittest

    # A 4x4 red pixel JPEG
    jpeg_data = base64.standard_b64decode(
        '/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0aHBwgJC4nICIsIxwcKDcpLDAx'
        'NDQ0Hyc5PTgyPC4zNDL/2wBDAQkJCQwLDBgNDRgyIRwhMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIy'
        'MjIyMjIyMjL/wAARCAAEAAQDASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUF'
        'BAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVW'
        'V1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi'
        '4+Tl5ufo6erx8vP09fb3+Pn6/8QAHwEAAwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAEC'
        'AxEEBSExBhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVm'
        'Z2hpanN0dXZ3eHl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq'
        '8vP09fb3+Pn6/9oADAMBAAIRAxEAPwDi6KKK+ZP3E//Z'
    )

    class Builder:
        "Builds a PDF file from a list of numbered objects, generating the cross reference table"

        def __init__(self):
            self.objects = []

        def add(self, body):
            "Add an object, return its object number. body must be bytes, use reserve() for forward references"
            self.objects.append(body)
            return len(self.objects)

        def reserve(self):
            self.objects.append(None)
            return len(self.objects)

        def add_stream(self, dict_items, stream_data):
            body = b'<</Length ' + str(len(stream_data)).encode('ascii') + dict_items + b'>>\nstream\n' + stream_data + b'\nendstream'
            return self.add(body)

        def set(self, num, body):
            self.objects[num - 1] = body

        def build(self, info=None):
            ans = []
            pos = 0

            def w(raw):
                nonlocal pos
                ans.append(raw)
                pos += len(raw)

            w(b'%PDF-1.5\n%\xe2\xe3\xcf\xd3\n')
            offsets = []
            for i, body in enumerate(self.objects):
                if body is None:
                    raise ValueError(f'Object {i + 1} was reserved but never set')
                offsets.append(pos)
                w(f'{i + 1} 0 obj\n'.encode('ascii'))
                w(body)
                w(b'\nendobj\n')
            xref_pos = pos
            w(f'xref\n0 {len(self.objects) + 1}\n'.encode('ascii'))
            w(b'0000000000 65535 f \n')
            for off in offsets:
                w(f'{off:010d} 00000 n \n'.encode('ascii'))
            trailer = f'trailer\n<</Size {len(self.objects) + 1}/Root 1 0 R'
            if info is not None:
                trailer += f'/Info {info} 0 R'
            trailer += f'>>\nstartxref\n{xref_pos}\n%%EOF\n'
            w(trailer.encode('ascii'))
            return b''.join(ans)

    def multi_page_pdf(
        num_pages=2,
        uri='',
        dests=False,
        unused_type0_font=False,
        type3_font=False,
        font_file_data=b'FONTFILEDATA',
    ):
        "Build a PDF with num_pages pages, all using an indirect Type1 font with a font file, and various optional features"
        b = Builder()
        catalog = b.reserve()
        pages = b.reserve()
        font_file = b.add_stream(b'', font_file_data)
        descriptor = b.add(b'<</Type/FontDescriptor/FontName/Times-Roman/Flags 34/FontFile2 ' + f'{font_file} 0 R'.encode('ascii') + b'>>')
        font = b.add(f'<</Type/Font/Subtype/Type1/BaseFont/Times-Roman/FontDescriptor {descriptor} 0 R>>'.encode('ascii'))
        annot = 0
        if uri:
            annot = b.add(b'<</Type/Annot/Subtype/Link/Rect[0 0 100 100]/A<</Type/Action/S/URI/URI(' + uri.encode('ascii') + b')>>>>')
        page_nums = []
        unused_font = 0
        if unused_type0_font:
            uff = b.add_stream(b'', b'FAKEFONTDATA')
            ufd = b.add(f'<</Type/FontDescriptor/FontName/Fake/Flags 4/FontFile2 {uff} 0 R>>'.encode('ascii'))
            udf = b.add(f'<</Type/Font/Subtype/CIDFontType2/BaseFont/Fake/FontDescriptor {ufd} 0 R>>'.encode('ascii'))
            unused_font = b.add(f'<</Type/Font/Subtype/Type0/BaseFont/Fake/Encoding/Identity-H/DescendantFonts[{udf} 0 R]>>'.encode('ascii'))
        for i in range(num_pages):
            contents = b.add_stream(b'', f'BT /F1 24 Tf 72 720 Td (Page {i + 1}) Tj ET'.encode('ascii'))
            fonts = f'/F1 {font} 0 R'
            if unused_font:
                # the font is in the page resources, but never selected by a Tf operator in the content stream
                fonts += f'/F2 {unused_font} 0 R'
            page = f'<</Type/Page/Parent {pages} 0 R/MediaBox[0 0 612 792]/Contents {contents} 0 R/Resources<</Font<<{fonts}>>>>'
            if annot and i == 0:
                page += f'/Annots[{annot} 0 R]'
            page += '>>'
            page_nums.append(b.add(page.encode('ascii')))
        kids = ' '.join(f'{n} 0 R' for n in page_nums)
        b.set(pages, f'<</Type/Pages/Count {num_pages}/Kids[{kids}]>>'.encode('ascii'))
        catalog_body = f'<</Type/Catalog/Pages {pages} 0 R'
        if dests:
            d = b.add(f'<</anchor1[{page_nums[0]} 0 R/XYZ 10.5 20.5 3]>>'.encode('ascii'))
            catalog_body += f'/Dests {d} 0 R'
        if type3_font:
            cp1 = b.add_stream(b'', b'10 0 0 0 10 10 d1')
            cp2 = b.add_stream(b'', b'10 0 0 0 10 10 d1')
            b.add(
                (
                    '<</Type/Font/Subtype/Type3/FontBBox[0 0 10 10]/FontMatrix[0.001 0 0 0.001 0 0]'
                    f'/CharProcs<</a {cp1} 0 R/b {cp2} 0 R>>/Encoding<</Type/Encoding/Differences[97/a 98/b]>>/FirstChar 97/LastChar 98/Widths[10 10]>>'
                ).encode('ascii')
            )
        b.set(catalog, (catalog_body + '>>').encode('ascii'))
        return b.build()

    def load(raw):
        p = get_podofo().PDFDoc()
        p.load(raw)
        return p

    def roundtrip(p):
        return load(p.write())

    class TestPodofo(unittest.TestCase):
        def test_podofo_basic(self):
            test_podofo()

        def test_podofo_load_open_save(self):
            import tempfile

            raw = multi_page_pdf(num_pages=3)
            p = load(raw)
            self.assertEqual(p.page_count(), 3)
            with tempfile.TemporaryDirectory() as tdir:
                path = os.path.join(tdir, 'test.pdf')
                p.save(path)
                q = get_podofo().PDFDoc()
                q.open(path)
                self.assertEqual(q.page_count(), 3)

        def test_podofo_pages(self):
            p = load(multi_page_pdf(num_pages=3))
            self.assertEqual(p.page_count(), 3)
            self.assertEqual(p.pages, 3)
            p.copy_page(1, 3)
            self.assertEqual(p.page_count(), 4)
            p.delete_pages(2, 2)
            self.assertEqual(p.page_count(), 2)
            other = load(multi_page_pdf(num_pages=2))
            p.insert_existing_page(other, 0, 0)
            self.assertEqual(p.page_count(), 3)
            p.extract_first_page()
            self.assertEqual(p.page_count(), 1)
            self.assertEqual(roundtrip(p).page_count(), 1)

        def test_podofo_append(self):
            a = load(multi_page_pdf(num_pages=2))
            b = load(multi_page_pdf(num_pages=3))
            c = load(multi_page_pdf(num_pages=1))
            a.append(b, c)
            self.assertEqual(a.page_count(), 6)
            q = roundtrip(a)
            self.assertEqual(q.page_count(), 6)

        def test_podofo_page_boxes(self):
            p = load(multi_page_pdf())
            self.assertEqual(p.get_page_box('MediaBox', 1), (0, 0, 612, 792))
            p.set_page_box('CropBox', 1, 10, 20, 300, 400)
            p = roundtrip(p)
            self.assertEqual(p.get_page_box('CropBox', 1), (10, 20, 300, 400))
            self.assertRaises(KeyError, p.get_page_box, 'MoosBox', 1)
            self.assertRaises(ValueError, p.get_page_box, 'CropBox', 33)

        def test_podofo_uncompress(self):
            p = load(sample_pdf_data())
            self.assertNotIn(b'xpacket', p.write())
            p.uncompress()
            self.assertIn(b'xpacket', p.write())

        def test_podofo_outlines(self):
            p = load(multi_page_pdf(num_pages=3))
            root = p.create_outline('Root', 1)
            child = root.create('Child', 2, True, 11.0, 22.0, 1.5)
            child.create('Grandchild', 3, True)
            root.create('Sibling', 3, False)
            p = roundtrip(p)
            outline = p.get_outline()
            self.assertEqual(len(outline['children']), 2)
            r = outline['children'][0]
            self.assertEqual(r['title'], 'Root')
            self.assertEqual(r['dest'], {'page': 1, 'top': 0.0, 'left': 0.0, 'zoom': 0.0})
            c = r['children'][0]
            self.assertEqual(c['title'], 'Child')
            self.assertEqual(c['dest'], {'page': 2, 'top': 22.0, 'left': 11.0, 'zoom': 1.5})
            self.assertEqual(c['children'][0]['title'], 'Grandchild')
            s = outline['children'][1]
            self.assertEqual(s['title'], 'Sibling')
            self.assertEqual(s['dest']['page'], 3)

        def test_podofo_extract_anchors(self):
            p = load(multi_page_pdf(num_pages=2, dests=True))
            self.assertEqual(p.extract_anchors(), {'anchor1': (1, 10.5, 20.5, 3)})

        def test_podofo_alter_links(self):
            url = 'https://example.com'
            p = load(multi_page_pdf(num_pages=2, uri=url))
            seen = []

            def callback(uri):
                seen.append(uri)
                return (2, 10.0, 20.0, 1.5)

            p.alter_links(callback, True)
            self.assertEqual(seen, [url])
            raw = p.write()
            self.assertNotIn(url.encode('ascii'), raw)
            self.assertIn(b'/Dest', raw)
            self.assertIn(b'/XYZ', raw)
            self.assertIn(b'/Border', raw)
            # a callback that returns None leaves the link alone
            p = load(multi_page_pdf(num_pages=2, uri=url))
            p.alter_links(lambda uri: None, False)
            self.assertIn(url.encode('ascii'), p.write())

        def test_podofo_list_fonts(self):
            p = load(multi_page_pdf(num_pages=2, font_file_data=b'FONTFILEDATA'))
            fonts = p.list_fonts(True)
            self.assertEqual(len(fonts), 1)
            f = fonts[0]
            self.assertEqual(f['BaseFont'], 'Times-Roman')
            self.assertEqual(f['Subtype'], 'Type1')
            self.assertEqual(f['Data'], b'FONTFILEDATA')

        def test_podofo_remove_unused_fonts(self):
            p = load(multi_page_pdf(num_pages=2, unused_type0_font=True))
            self.assertEqual(len(p.list_fonts()), 3)
            p.uncompress()
            self.assertIn(b'FAKEFONTDATA', p.write())
            self.assertEqual(p.remove_unused_fonts(), 1)
            p = roundtrip(p)
            p.uncompress()
            raw = p.write()
            self.assertNotIn(b'FAKEFONTDATA', raw)
            self.assertIn(b'FONTFILEDATA', raw)
            self.assertEqual(len(p.list_fonts()), 1)

        def test_podofo_replace_font_data(self):
            p = load(multi_page_pdf(font_file_data=b'OLDDATA'))
            ref = p.list_fonts(True)[0]['Reference']
            p.replace_font_data(b'NEWDATA', *ref)
            p = roundtrip(p)
            self.assertEqual(p.list_fonts(True)[0]['Data'], b'NEWDATA')

        def test_podofo_dedup_type3_fonts(self):
            p = load(multi_page_pdf(type3_font=True))
            self.assertEqual(p.dedup_type3_fonts(), 1)

        def test_podofo_images(self):
            page_size = (0.0, 0.0, 612.0, 792.0)
            p = get_podofo().PDFDoc()
            add_image_page(p, jpeg_data, page_size=page_size)
            add_image_page(p, jpeg_data, page_size=page_size, page_num=2)
            p = roundtrip(p)
            self.assertEqual(p.page_count(), 2)
            self.assertEqual(p.image_count(), 2)
            self.assertGreaterEqual(p.dedup_images(), 1)

        def test_podofo_impose(self):
            p = load(multi_page_pdf(num_pages=2))
            p.impose(1, 2, 1)
            self.assertEqual(p.page_count(), 1)
            p.uncompress()
            raw = p.write()
            self.assertIn(b' Do', raw)
            q = load(raw)
            self.assertEqual(q.page_count(), 1)
            self.assertEqual(q.image_count(), 1)  # the form xobject created by impose

    return unittest.defaultTestLoader.loadTestsFromTestCase(TestPodofo)


if __name__ == '__main__':
    develop()
