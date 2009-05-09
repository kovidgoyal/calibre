from __future__ import with_statement
__license__ = 'GPL 3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os, re, uuid
from itertools import cycle

from lxml import etree

from calibre.customize.conversion import InputFormatPlugin

class EPUBInput(InputFormatPlugin):

    name        = 'EPUB Input'
    author      = 'Kovid Goyal'
    description = 'Convert EPUB files (.epub) to HTML'
    file_types  = set(['epub'])

    @classmethod
    def decrypt_font(cls, key, path):
        raw = open(path, 'rb').read()
        crypt = raw[:1024]
        key = cycle(iter(key))
        decrypt = ''.join([chr(ord(x)^key.next()) for x in crypt])
        with open(path, 'wb') as f:
            f.write(decrypt)
            f.write(raw[1024:])

    @classmethod
    def process_ecryption(cls, encfile, opf, log):
        key = None
        m = re.search(r'(?i)(urn:uuid:[0-9a-f-]+)', open(opf, 'rb').read())
        if m:
            key = m.group(1)
            key = list(map(ord, uuid.UUID(key).bytes))
        try:
            root = etree.parse(encfile)
            for em in root.xpath('descendant::*[contains(name(), "EncryptionMethod")]'):
                algorithm = em.get('Algorithm', '')
                if algorithm != 'http://ns.adobe.com/pdf/enc#RC':
                    return False
                cr = em.getparent().xpath('descendant::*[contains(name(), "CipherReference")]')[0]
                uri = cr.get('URI')
                path = os.path.abspath(os.path.join(os.path.dirname(encfile), '..', *uri.split('/')))
                if os.path.exists(path):
                    cls.decrypt_font(key, path)
            return True
        except:
            import traceback
            traceback.print_exc()
        return False

    @classmethod
    def rationalize_cover(self, opf):
        guide_cover, guide_elem = None, None
        for guide_elem in opf.iterguide():
            if guide_elem.get('type', '').lower() == 'cover':
                guide_cover = guide_elem.get('href', '')
                break
        if not guide_cover:
            return
        spine = list(opf.iterspine())
        if not spine:
            return
        idref = spine[0].get('idref', '')
        manifest = list(opf.itermanifest())
        if not manifest:
            return
        if manifest[0].get('id', False) != idref:
            return
        spine[0].getparent().remove(spine[0])
        guide_elem.set('href', 'calibre_raster_cover.jpg')
        for elem in list(opf.iterguide()):
            if elem.get('type', '').lower() == 'titlepage':
                elem.getparent().remove(elem)
        from calibre.ebooks.oeb.base import OPF
        t = etree.SubElement(guide_elem.getparent(), OPF('reference'))
        t.set('type', 'titlepage')
        t.set('href', guide_cover)
        t.set('title', 'Title Page')
        from calibre.ebooks import render_html
        renderer = render_html(guide_cover)
        if renderer is not None:
            open('calibre_raster_cover.jpg', 'wb').write(
                renderer.data)


    def convert(self, stream, options, file_ext, log, accelerators):
        from calibre.utils.zipfile import ZipFile
        from calibre import walk
        from calibre.ebooks import DRMError
        from calibre.ebooks.metadata.opf2 import OPF
        zf = ZipFile(stream)
        zf.extractall(os.getcwd())
        encfile = os.path.abspath(os.path.join('META-INF', 'encryption.xml'))
        opf = None
        for f in walk(u'.'):
            if f.lower().endswith('.opf'):
                opf = os.path.abspath(f)
                break
        path = getattr(stream, 'name', 'stream')

        if opf is None:
            raise ValueError('%s is not a valid EPUB file'%path)

        if os.path.exists(encfile):
            if not self.process_encryption(encfile, opf, log):
                raise DRMError(os.path.basename(path))

        opf = os.path.relpath(opf, os.getcwdu())
        parts = os.path.split(opf)
        opf = OPF(opf, os.path.dirname(os.path.abspath(opf)))

        if len(parts) > 1 and parts[0]:
            delta = '/'.join(parts[:-1])+'/'
            for elem in opf.itermanifest():
                elem.set('href', delta+elem.get('href'))
            for elem in opf.iterguide():
                elem.set('href', delta+elem.get('href'))

        self.rationalize_cover(opf)

        with open('content.opf', 'wb') as nopf:
            nopf.write(opf.render())

        return os.path.abspath('content.opf')
