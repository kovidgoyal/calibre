from __future__ import with_statement
__license__ = 'GPL 3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os, re, posixpath
from itertools import cycle

from calibre.customize.conversion import InputFormatPlugin, OptionRecommendation

ADOBE_OBFUSCATION =  'http://ns.adobe.com/pdf/enc#RC'
IDPF_OBFUSCATION = 'http://www.idpf.org/2008/embedding'


def decrypt_font_data(key, data, algorithm):
    is_adobe = algorithm == ADOBE_OBFUSCATION
    crypt_len = 1024 if is_adobe else 1040
    crypt = bytearray(data[:crypt_len])
    key = cycle(iter(bytearray(key)))
    decrypt = bytes(bytearray(x^key.next() for x in crypt))
    return decrypt + data[crypt_len:]


def decrypt_font(key, path, algorithm):
    with open(path, 'r+b') as f:
        data = decrypt_font_data(key, f.read(), algorithm)
        f.seek(0), f.truncate(), f.write(data)


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
        idpf_key = opf.raw_unique_identifier
        if idpf_key:
            idpf_key = re.sub(u'[\u0020\u0009\u000d\u000a]', u'', idpf_key)
            idpf_key = hashlib.sha1(idpf_key.encode('utf-8')).digest()
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

    def set_guide_type(self, opf, gtype, href=None, title=''):
        # Set the specified guide entry
        for elem in list(opf.iterguide()):
            if elem.get('type', '').lower() == gtype:
                elem.getparent().remove(elem)

        if href is not None:
            t = opf.create_guide_item(gtype, title, href)
            for guide in opf.root.xpath('./*[local-name()="guide"]'):
                guide.append(t)
                return
            guide = opf.create_guide_element()
            opf.root.append(guide)
            guide.append(t)
            return t

    def rationalize_cover3(self, opf, log):
        ''' If there is a reference to the cover/titlepage via manifest properties, convert to
        entries in the <guide> so that the rest of the pipeline picks it up. '''
        from calibre.ebooks.metadata.opf3 import items_with_property
        removed = guide_titlepage_href = guide_titlepage_id = None

        # Look for titlepages incorrectly marked in the <guide> as covers
        guide_cover, guide_elem = None, None
        for guide_elem in opf.iterguide():
            if guide_elem.get('type', '').lower() == 'cover':
                guide_cover = guide_elem.get('href', '').partition('#')[0]
                break
        if guide_cover:
            spine = list(opf.iterspine())
            if spine:
                idref = spine[0].get('idref', '')
                for x in opf.itermanifest():
                    if x.get('id') == idref and x.get('href') == guide_cover:
                        guide_titlepage_href = guide_cover
                        guide_titlepage_id = idref
                        break

        raster_cover_href = opf.epub3_raster_cover
        if raster_cover_href:
            self.set_guide_type(opf, 'cover', raster_cover_href, 'Cover Image')
        titlepage_id = titlepage_href = None
        for item in items_with_property(opf.root, 'calibre:title-page'):
            tid, href = item.get('id'), item.get('href')
            if href and tid:
                titlepage_id, titlepage_href = tid, href.partition('#')[0]
                break
        if titlepage_href is None:
            titlepage_href, titlepage_id = guide_titlepage_href, guide_titlepage_id
        if titlepage_href is not None:
            self.set_guide_type(opf, 'titlepage', titlepage_href, 'Title Page')
            spine = list(opf.iterspine())
            if len(spine) > 1:
                for item in spine:
                    if item.get('idref') == titlepage_id:
                        log('Found HTML cover', titlepage_href)
                        if self.for_viewer:
                            item.attrib.pop('linear', None)
                        else:
                            item.getparent().remove(item)
                            removed = titlepage_href
                        return removed

    def rationalize_cover2(self, opf, log):
        ''' Ensure that the cover information in the guide is correct. That
        means, at most one entry with type="cover" that points to a raster
        cover and at most one entry with type="titlepage" that points to an
        HTML titlepage. '''
        from calibre.ebooks.oeb.base import OPF
        removed = None
        from lxml import etree
        guide_cover, guide_elem = None, None
        for guide_elem in opf.iterguide():
            if guide_elem.get('type', '').lower() == 'cover':
                guide_cover = guide_elem.get('href', '').partition('#')[0]
                break
        if not guide_cover:
            raster_cover = opf.raster_cover
            if raster_cover:
                if guide_elem is None:
                    g = opf.root.makeelement(OPF('guide'))
                    opf.root.append(g)
                else:
                    g = guide_elem.getparent()
                guide_cover = raster_cover
                guide_elem = g.makeelement(OPF('reference'), attrib={'href':raster_cover, 'type':'cover'})
                g.append(guide_elem)
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
            if len(spine) == 1:
                log.warn('There is only a single spine item and it is marked as the cover. Removing cover marking.')
                for guide_elem in tuple(opf.iterguide()):
                    if guide_elem.get('type', '').lower() == 'cover':
                        guide_elem.getparent().remove(guide_elem)
                return
            else:
                spine[0].getparent().remove(spine[0])
                removed = guide_cover
        else:
            # Ensure the cover is displayed as the first item in the book, some
            # epub files have it set with linear='no' which causes the cover to
            # display in the end
            spine[0].attrib.pop('linear', None)
            opf.spine[0].is_linear = True
        # Ensure that the guide has a cover entry pointing to a raster cover
        # and a titlepage entry pointing to the html titlepage. The titlepage
        # entry will be used by the epub output plugin, the raster cover entry
        # by other output plugins.

        # Search for a raster cover identified in the OPF
        raster_cover = opf.raster_cover

        # Set the cover guide entry
        if raster_cover is not None:
            guide_elem.set('href', raster_cover)
        else:
            # Render the titlepage to create a raster cover
            from calibre.ebooks import render_html_svg_workaround
            guide_elem.set('href', 'calibre_raster_cover.jpg')
            t = etree.SubElement(
                elem[0].getparent(), OPF('item'), href=guide_elem.get('href'), id='calibre_raster_cover')
            t.set('media-type', 'image/jpeg')
            if os.path.exists(guide_cover):
                renderer = render_html_svg_workaround(guide_cover, log)
                if renderer is not None:
                    open('calibre_raster_cover.jpg', 'wb').write(
                        renderer)

        # Set the titlepage guide entry
        self.set_guide_type(opf, 'titlepage', guide_cover, 'Title Page')
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

        epub3_nav = opf.epub3_nav
        if epub3_nav is not None:
            self.convert_epub3_nav(epub3_nav, opf, log, options)

        if len(parts) > 1 and parts[0]:
            delta = '/'.join(parts[:-1])+'/'

            def normpath(x):
                return posixpath.normpath(delta + elem.get('href'))

            for elem in opf.itermanifest():
                elem.set('href', normpath(elem.get('href')))
            for elem in opf.iterguide():
                elem.set('href', normpath(elem.get('href')))

        f = self.rationalize_cover3 if opf.package_version >= 3.0 else self.rationalize_cover2
        self.removed_cover = f(opf, log)

        for x in opf.itermanifest():
            if x.get('media-type', '') == 'application/x-dtbook+xml':
                raise ValueError(
                    'EPUB files with DTBook markup are not supported')

        not_for_spine = set()
        for y in opf.itermanifest():
            id_ = y.get('id', None)
            if id_:
                mt = y.get('media-type', None)
                if mt in {
                        'application/vnd.adobe-page-template+xml',
                        'application/vnd.adobe.page-template+xml',
                        'application/adobe-page-template+xml',
                        'application/adobe.page-template+xml',
                        'application/text'
                }:
                    not_for_spine.add(id_)
                ext = y.get('href', '').rpartition('.')[-1].lower()
                if mt == 'text/plain' and ext in {'otf', 'ttf'}:
                    # some epub authoring software sets font mime types to
                    # text/plain
                    not_for_spine.add(id_)
                    y.set('media-type', 'application/font')

        seen = set()
        for x in list(opf.iterspine()):
            ref = x.get('idref', None)
            if not ref or ref in not_for_spine or ref in seen:
                x.getparent().remove(x)
                continue
            seen.add(ref)

        if len(list(opf.iterspine())) == 0:
            raise ValueError('No valid entries in the spine of this EPUB')

        with lopen('content.opf', 'wb') as nopf:
            nopf.write(opf.render())

        return os.path.abspath(u'content.opf')

    def convert_epub3_nav(self, nav_path, opf, log, opts):
        from lxml import etree
        from calibre.ebooks.chardet import xml_to_unicode
        from calibre.ebooks.oeb.polish.parsing import parse
        from calibre.ebooks.oeb.base import EPUB_NS, XHTML, NCX_MIME, NCX, urlnormalize
        from calibre.ebooks.oeb.polish.toc import first_child
        from tempfile import NamedTemporaryFile
        with lopen(nav_path, 'rb') as f:
            raw = f.read()
        raw = xml_to_unicode(raw, strip_encoding_pats=True, assume_utf8=True)[0]
        root = parse(raw, log=log)
        ncx = etree.fromstring('<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1" xml:lang="eng"><navMap/></ncx>')
        navmap = ncx[0]
        et = '{%s}type' % EPUB_NS
        bn = os.path.basename(nav_path)

        def add_from_li(li, parent):
            href = text = None
            for x in li.iterchildren(XHTML('a'), XHTML('span')):
                text = etree.tostring(x, method='text', encoding=unicode, with_tail=False).strip() or ' '.join(x.xpath('descendant-or-self::*/@title')).strip()
                href = x.get('href')
                if href:
                    if href.startswith('#'):
                        href = bn + href
                break
            np = parent.makeelement(NCX('navPoint'))
            parent.append(np)
            np.append(np.makeelement(NCX('navLabel')))
            np[0].append(np.makeelement(NCX('text')))
            np[0][0].text = text
            if href:
                np.append(np.makeelement(NCX('content'), attrib={'src':href}))
            return np

        def process_nav_node(node, toc_parent):
            for li in node.iterchildren(XHTML('li')):
                child = add_from_li(li, toc_parent)
                ol = first_child(li, XHTML('ol'))
                if child is not None and ol is not None:
                    process_nav_node(ol, child)

        for nav in root.iterdescendants(XHTML('nav')):
            if nav.get(et) == 'toc':
                ol = first_child(nav, XHTML('ol'))
                if ol is not None:
                    process_nav_node(ol, navmap)
                    break
        else:
            return

        with NamedTemporaryFile(suffix='.ncx', dir=os.path.dirname(nav_path), delete=False) as f:
            f.write(etree.tostring(ncx, encoding='utf-8'))
        ncx_id = opf.add_path_to_manifest(f.name, NCX_MIME)
        for spine in opf.root.xpath('//*[local-name()="spine"]'):
            spine.set('toc', ncx_id)
        href = os.path.relpath(nav_path).replace(os.sep, '/')
        opts.epub3_nav_href = urlnormalize(href)
        opts.epub3_nav_parsed = root

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
