#!/usr/bin/env python


__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

import sys, os

from lxml import etree

from calibre import prepare_string_for_xml, CurrentDir
from calibre.ptempfile import TemporaryDirectory
from calibre.ebooks.oeb.base import serialize
from calibre.ebooks.metadata import authors_to_string
from calibre.ebooks.metadata.opf2 import metadata_to_opf
from calibre.ebooks.oeb.polish.parsing import parse
from calibre.ebooks.oeb.polish.container import OPF_NAMESPACES, opf_to_azw3, Container
from calibre.ebooks.oeb.polish.utils import guess_type
from calibre.ebooks.oeb.polish.pretty import pretty_xml_tree, pretty_html_tree
from calibre.ebooks.oeb.polish.toc import TOC, create_ncx
from calibre.utils.localization import lang_as_iso639_1
from calibre.utils.logging import DevNull
from calibre.utils.zipfile import ZipFile, ZIP_STORED
from polyglot.builtins import as_bytes

valid_empty_formats = {'epub', 'txt', 'docx', 'azw3', 'md'}


def create_toc(mi, opf, html_name, lang):
    uuid = ''
    for u in opf.xpath('//*[@id="uuid_id"]'):
        uuid = u.text
    toc = TOC()
    toc.add(_('Start'), html_name)
    return create_ncx(toc, lambda x:x, mi.title, lang, uuid)


def create_book(mi, path, fmt='epub', opf_name='metadata.opf', html_name='start.xhtml', toc_name='toc.ncx'):
    ''' Create an empty book in the specified format at the specified location. '''
    if fmt not in valid_empty_formats:
        raise ValueError('Cannot create empty book in the %s format' % fmt)
    if fmt == 'txt':
        with open(path, 'wb') as f:
            if not mi.is_null('title'):
                f.write(as_bytes(mi.title))
        return
    if fmt == 'md':
        with open(path, 'w', encoding='utf-8') as f:
            if not mi.is_null('title'):
                print('#', mi.title, file=f)
        return
    if fmt == 'docx':
        from calibre.ebooks.conversion.plumber import Plumber
        from calibre.ebooks.docx.writer.container import DOCX
        from calibre.utils.logging import default_log
        p = Plumber('a.docx', 'b.docx', default_log)
        p.setup_options()
        # Use the word default of one inch page margins
        for x in 'left right top bottom'.split():
            setattr(p.opts, 'margin_' + x, 72)
        DOCX(p.opts, default_log).write(path, mi, create_empty_document=True)
        return
    path = os.path.abspath(path)
    lang = 'und'
    opf = metadata_to_opf(mi, as_string=False)
    for l in opf.xpath('//*[local-name()="language"]'):
        if l.text:
            lang = l.text
            break
    lang = lang_as_iso639_1(lang) or lang

    opfns = OPF_NAMESPACES['opf']
    m = opf.makeelement('{%s}manifest' % opfns)
    opf.insert(1, m)
    i = m.makeelement('{%s}item' % opfns, href=html_name, id='start')
    i.set('media-type', guess_type('a.xhtml'))
    m.append(i)
    i = m.makeelement('{%s}item' % opfns, href=toc_name, id='ncx')
    i.set('media-type', guess_type(toc_name))
    m.append(i)
    s = opf.makeelement('{%s}spine' % opfns, toc="ncx")
    opf.insert(2, s)
    i = s.makeelement('{%s}itemref' % opfns, idref='start')
    s.append(i)
    CONTAINER = '''\
<?xml version="1.0"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
   <rootfiles>
      <rootfile full-path="{}" media-type="application/oebps-package+xml"/>
   </rootfiles>
</container>
    '''.format(prepare_string_for_xml(opf_name, True)).encode('utf-8')
    HTML = P('templates/new_book.html', data=True).decode('utf-8').replace(
        '_LANGUAGE_', prepare_string_for_xml(lang, True)
    ).replace(
        '_TITLE_', prepare_string_for_xml(mi.title)
    ).replace(
        '_AUTHORS_', prepare_string_for_xml(authors_to_string(mi.authors))
    ).encode('utf-8')
    h = parse(HTML)
    pretty_html_tree(None, h)
    HTML = serialize(h, 'text/html')
    ncx = etree.tostring(create_toc(mi, opf, html_name, lang), encoding='utf-8', xml_declaration=True, pretty_print=True)
    pretty_xml_tree(opf)
    opf = etree.tostring(opf, encoding='utf-8', xml_declaration=True, pretty_print=True)
    if fmt == 'azw3':
        with TemporaryDirectory('create-azw3') as tdir, CurrentDir(tdir):
            for name, data in ((opf_name, opf), (html_name, HTML), (toc_name, ncx)):
                with open(name, 'wb') as f:
                    f.write(data)
            c = Container(os.path.dirname(os.path.abspath(opf_name)), opf_name, DevNull())
            opf_to_azw3(opf_name, path, c)
    else:
        with ZipFile(path, 'w', compression=ZIP_STORED) as zf:
            zf.writestr('mimetype', b'application/epub+zip', compression=ZIP_STORED)
            zf.writestr('META-INF/', b'', 0o755)
            zf.writestr('META-INF/container.xml', CONTAINER)
            zf.writestr(opf_name, opf)
            zf.writestr(html_name, HTML)
            zf.writestr(toc_name, ncx)


if __name__ == '__main__':
    from calibre.ebooks.metadata.book.base import Metadata
    mi = Metadata('Test book', authors=('Kovid Goyal',))
    path = sys.argv[-1]
    ext = path.rpartition('.')[-1].lower()
    if ext not in valid_empty_formats:
        print('Unsupported format:', ext)
        raise SystemExit(1)
    create_book(mi, path, fmt=ext)
