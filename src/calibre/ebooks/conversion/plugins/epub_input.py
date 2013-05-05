from __future__ import with_statement
__license__ = 'GPL 3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os
from itertools import cycle

from calibre.customize.conversion import InputFormatPlugin, OptionRecommendation

ADOBE_OBFUSCATION =  'http://ns.adobe.com/pdf/enc#RC'
IDPF_OBFUSCATION = 'http://www.idpf.org/2008/embedding'

def decrypt_font(key, path, algorithm):
    is_adobe = algorithm == ADOBE_OBFUSCATION
    crypt_len = 1024 if is_adobe else 1040
    with open(path, 'rb') as f:
        raw = f.read()
    crypt = bytearray(raw[:crypt_len])
    key = cycle(iter(bytearray(key)))
    decrypt = bytes(bytearray(x^key.next() for x in crypt))
    with open(path, 'wb') as f:
        f.write(decrypt)
        f.write(raw[crypt_len:])

class EPUBInput(InputFormatPlugin):

    name        = 'EPUB Input'
    author      = 'Kovid Goyal'
    description = 'Convert EPUB files (.epub) to HTML'
    file_types  = set(['epub'])
    output_encoding = None

    recommendations = set([('page_breaks_before', '/', OptionRecommendation.MED)])

    def process_encryption(self, encfile, opf, log):
        from lxml import etree
        import uuid, hashlib
        idpf_key = opf.unique_identifier
        if idpf_key:
            idpf_key = hashlib.sha1(idpf_key).digest()
        key = None
        for item in opf.identifier_iter():
            scheme = None
            for xkey in item.attrib.keys():
                if xkey.endswith('scheme'):
                    scheme = item.get(xkey)
            if (scheme and scheme.lower() == 'uuid') or \
                    (item.text and item.text.startswith('urn:uuid:')):
                try:
                    key = bytes(item.text).rpartition(':')[-1]
                    key = uuid.UUID(key).bytes
                except:
                    import traceback
                    traceback.print_exc()
                    key = None

        try:
            root = etree.parse(encfile)
            for em in root.xpath('descendant::*[contains(name(), "EncryptionMethod")]'):
                algorithm = em.get('Algorithm', '')
                if algorithm not in {ADOBE_OBFUSCATION, IDPF_OBFUSCATION}:
                    return False
                cr = em.getparent().xpath('descendant::*[contains(name(), "CipherReference")]')[0]
                uri = cr.get('URI')
                path = os.path.abspath(os.path.join(os.path.dirname(encfile), '..', *uri.split('/')))
                tkey = (key if algorithm == ADOBE_OBFUSCATION else idpf_key)
                if (tkey and os.path.exists(path)):
                    self._encrypted_font_uris.append(uri)
                    decrypt_font(tkey, path, algorithm)
            return True
        except:
            import traceback
            traceback.print_exc()
        return False

    def rationalize_cover(self, opf, log):
        removed = None
        from lxml import etree
        guide_cover, guide_elem = None, None
        for guide_elem in opf.iterguide():
            if guide_elem.get('type', '').lower() == 'cover':
                guide_cover = guide_elem.get('href', '').partition('#')[0]
                break
        if not guide_cover:
            return
        spine = list(opf.iterspine())
        if not spine:
            return
        # Check if the cover specified in the guide is also
        # the first element in spine
        idref = spine[0].get('idref', '')
        manifest = list(opf.itermanifest())
        if not manifest:
            return
        elem = [x for x in manifest if x.get('id', '') == idref]
        if not elem or elem[0].get('href', None) != guide_cover:
            return
        log('Found HTML cover', guide_cover)

        # Remove from spine as covers must be treated
        # specially
        if not self.for_viewer:
            spine[0].getparent().remove(spine[0])
            removed = guide_cover
        else:
            # Ensure the cover is displayed as the first item in the book, some
            # epub files have it set with linear='no' which causes the cover to
            # display in the end
            spine[0].attrib.pop('linear', None)
            opf.spine[0].is_linear = True
        guide_elem.set('href', 'calibre_raster_cover.jpg')
        from calibre.ebooks.oeb.base import OPF
        t = etree.SubElement(elem[0].getparent(), OPF('item'),
        href=guide_elem.get('href'), id='calibre_raster_cover')
        t.set('media-type', 'image/jpeg')
        for elem in list(opf.iterguide()):
            if elem.get('type', '').lower() == 'titlepage':
                elem.getparent().remove(elem)
        t = etree.SubElement(guide_elem.getparent(), OPF('reference'))
        t.set('type', 'titlepage')
        t.set('href', guide_cover)
        t.set('title', 'Title Page')
        from calibre.ebooks import render_html_svg_workaround
        if os.path.exists(guide_cover):
            renderer = render_html_svg_workaround(guide_cover, log)
            if renderer is not None:
                open('calibre_raster_cover.jpg', 'wb').write(
                    renderer)
        return removed

    def find_opf(self):
        from lxml import etree
        def attr(n, attr):
            for k, v in n.attrib.items():
                if k.endswith(attr):
                    return v
        try:
            with open('META-INF/container.xml') as f:
                root = etree.fromstring(f.read())
                for r in root.xpath('//*[local-name()="rootfile"]'):
                    if attr(r, 'media-type') != "application/oebps-package+xml":
                        continue
                    path = attr(r, 'full-path')
                    if not path:
                        continue
                    path = os.path.join(os.getcwdu(), *path.split('/'))
                    if os.path.exists(path):
                        return path
        except:
            import traceback
            traceback.print_exc()

    def convert(self, stream, options, file_ext, log, accelerators):
        from calibre.utils.zipfile import ZipFile
        from calibre import walk
        from calibre.ebooks import DRMError
        from calibre.ebooks.metadata.opf2 import OPF
        try:
            zf = ZipFile(stream)
            zf.extractall(os.getcwdu())
        except:
            log.exception('EPUB appears to be invalid ZIP file, trying a'
                    ' more forgiving ZIP parser')
            from calibre.utils.localunzip import extractall
            stream.seek(0)
            extractall(stream)
        encfile = os.path.abspath(os.path.join('META-INF', 'encryption.xml'))
        opf = self.find_opf()
        if opf is None:
            for f in walk(u'.'):
                if f.lower().endswith('.opf') and '__MACOSX' not in f and \
                        not os.path.basename(f).startswith('.'):
                    opf = os.path.abspath(f)
                    break
        path = getattr(stream, 'name', 'stream')

        if opf is None:
            raise ValueError('%s is not a valid EPUB file (could not find opf)'%path)

        opf = os.path.relpath(opf, os.getcwdu())
        parts = os.path.split(opf)
        opf = OPF(opf, os.path.dirname(os.path.abspath(opf)))

        self._encrypted_font_uris = []
        if os.path.exists(encfile):
            if not self.process_encryption(encfile, opf, log):
                raise DRMError(os.path.basename(path))
        self.encrypted_fonts = self._encrypted_font_uris

        if len(parts) > 1 and parts[0]:
            delta = '/'.join(parts[:-1])+'/'
            for elem in opf.itermanifest():
                elem.set('href', delta+elem.get('href'))
            for elem in opf.iterguide():
                elem.set('href', delta+elem.get('href'))

        self.removed_cover = self.rationalize_cover(opf, log)

        self.optimize_opf_parsing = opf
        for x in opf.itermanifest():
            if x.get('media-type', '') == 'application/x-dtbook+xml':
                raise ValueError(
                    'EPUB files with DTBook markup are not supported')

        not_for_spine = set()
        for y in opf.itermanifest():
            id_ = y.get('id', None)
            if id_ and y.get('media-type', None) in {
                    'application/vnd.adobe-page-template+xml', 'application/vnd.adobe.page-template+xml',
                    'application/adobe-page-template+xml', 'application/adobe.page-template+xml',
                    'application/text'}:
                not_for_spine.add(id_)

        seen = set()
        for x in list(opf.iterspine()):
            ref = x.get('idref', None)
            if not ref or ref in not_for_spine or ref in seen:
                x.getparent().remove(x)
                continue
            seen.add(ref)

        if len(list(opf.iterspine())) == 0:
            raise ValueError('No valid entries in the spine of this EPUB')

        with open('content.opf', 'wb') as nopf:
            nopf.write(opf.render())

        return os.path.abspath(u'content.opf')

    def postprocess_book(self, oeb, opts, log):
        rc = getattr(self, 'removed_cover', None)
        if rc:
            cover_toc_item = None
            for item in oeb.toc.iterdescendants():
                if item.href and item.href.partition('#')[0] == rc:
                    cover_toc_item = item
                    break
            spine = {x.href for x in oeb.spine}
            if (cover_toc_item is not None and cover_toc_item not in spine):
                oeb.toc.item_that_refers_to_cover = cover_toc_item


