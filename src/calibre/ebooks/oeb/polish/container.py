#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os, posixpath, logging, sys, hashlib, uuid
from urllib import unquote as urlunquote

from lxml import etree

from calibre import guess_type, CurrentDir
from calibre.ebooks.chardet import xml_to_unicode
from calibre.ebooks.conversion.plugins.epub_input import (
    ADOBE_OBFUSCATION, IDPF_OBFUSCATION, decrypt_font)
from calibre.ebooks.conversion.preprocess import HTMLPreProcessor, CSSPreProcessor
from calibre.ebooks.mobi import MobiError
from calibre.ebooks.mobi.reader.headers import MetadataHeader
from calibre.ebooks.oeb.base import OEB_DOCS, _css_logger, OEB_STYLES, OPF2_NS
from calibre.ebooks.oeb.polish.errors import InvalidBook, DRMError
from calibre.ebooks.oeb.parse_utils import NotHTML, parse_html, RECOVER_PARSER
from calibre.ptempfile import PersistentTemporaryDirectory
from calibre.utils.fonts.sfnt.container import Sfnt
from calibre.utils.ipc.simple_worker  import fork_job, WorkerError
from calibre.utils.logging import default_log
from calibre.utils.zipfile import ZipFile

exists, join, relpath = os.path.exists, os.path.join, os.path.relpath

OEB_FONTS = {guess_type('a.ttf')[0], guess_type('b.ttf')[0]}

class Container(object):

    def __init__(self, rootpath, opfpath, log):
        self.root = os.path.abspath(rootpath)
        self.log = log
        self.html_preprocessor = HTMLPreProcessor()
        self.css_preprocessor = CSSPreProcessor()

        self.parsed_cache = {}
        self.mime_map = {}
        self.name_path_map = {}

        # Map of relative paths with '/' separators from root of unzipped ePub
        # to absolute paths on filesystem with os-specific separators
        opfpath = os.path.abspath(opfpath)
        for dirpath, _dirnames, filenames in os.walk(self.root):
            for f in filenames:
                path = join(dirpath, f)
                name = relpath(path, self.root).replace(os.sep, '/')
                self.name_path_map[name] = path
                self.mime_map[name] = guess_type(path)[0]
                # Special case if we have stumbled onto the opf
                if path == opfpath:
                    self.opf_name = name
                    self.opf_dir = posixpath.dirname(path)
                    self.mime_map[name] = guess_type('a.opf')[0]

        # Update mime map with data from the OPF
        for item in self.opf.xpath(
                '//opf:manifest/opf:item[@href and @media-type]',
                namespaces={'opf':OPF2_NS}):
            href = item.get('href')
            self.mime_map[self.href_to_name(href)] = item.get('media-type')


    def href_to_name(self, href, base=None):
        if base is None:
            base = self.opf_dir
        href = urlunquote(href.partition('#')[0])
        fullpath = posixpath.abspath(posixpath.join(base, href))
        return self.relpath(fullpath)

    def relpath(self, path):
        return relpath(path, self.root)

    def decode(self, data):
        """Automatically decode :param:`data` into a `unicode` object."""
        def fix_data(d):
            return d.replace('\r\n', '\n').replace('\r', '\n')
        if isinstance(data, unicode):
            return fix_data(data)
        bom_enc = None
        if data[:4] in {b'\0\0\xfe\xff', b'\xff\xfe\0\0'}:
            bom_enc = {b'\0\0\xfe\xff':'utf-32-be',
                       b'\xff\xfe\0\0':'utf-32-le'}[data[:4]]
            data = data[4:]
        elif data[:2] in {b'\xff\xfe', b'\xfe\xff'}:
            bom_enc = {b'\xff\xfe':'utf-16-le', b'\xfe\xff':'utf-16-be'}[data[:2]]
            data = data[2:]
        elif data[:3] == b'\xef\xbb\xbf':
            bom_enc = 'utf-8'
            data = data[3:]
        if bom_enc is not None:
            try:
                return fix_data(data.decode(bom_enc))
            except UnicodeDecodeError:
                pass
        try:
            return fix_data(data.decode('utf-8'))
        except UnicodeDecodeError:
            pass
        data, _ = xml_to_unicode(data)
        return fix_data(data)

    def parse_xml(self, data):
        data = xml_to_unicode(data, strip_encoding_pats=True, assume_utf8=True,
                             resolve_entities=True)[0].strip()
        return etree.fromstring(data, parser=RECOVER_PARSER)

    def parse_xhtml(self, data, fname):
        try:
            return parse_html(data, log=self.log,
                    decoder=self.decode,
                    preprocessor=self.html_preprocessor,
                    filename=fname, non_html_file_tags={'ncx'})
        except NotHTML:
            return self.parse_xml(data)

    def parse(self, path, mime):
        with open(path, 'rb') as src:
            data = src.read()
        if mime in OEB_DOCS:
            data = self.parse_xhtml(data, self.relpath(path))
        elif mime[-4:] in {'+xml', '/xml'}:
            data = self.parse_xml(data)
        elif mime in OEB_STYLES:
            data = self.parse_css(data, self.relpath(path))
        elif mime in OEB_FONTS or path.rpartition('.')[-1].lower() in {'ttf', 'otf'}:
            data = Sfnt(data)
        return data

    def parse_css(self, data, fname):
        from cssutils import CSSParser, log
        log.setLevel(logging.WARN)
        log.raiseExceptions = False
        data = self.decode(data)
        data = self.css_preprocessor(data, add_namespace=False)
        parser = CSSParser(loglevel=logging.WARNING,
                           # We dont care about @import rules
                           fetcher=lambda x: (None, None), log=_css_logger)
        data = parser.parseString(data, href=fname, validate=False)
        return data

    def parsed(self, name):
        ans = self.parsed_cache.get(name, None)
        if ans is None:
            mime = self.mime_map.get(name, guess_type(name)[0])
            ans = self.parse(self.name_path_map[name], mime)
            self.parsed_cache[name] = ans
        return ans

    @property
    def opf(self):
        return self.parsed(self.opf_name)

    @property
    def spine_items(self):
        manifest_id_map = {item.get('id'):self.href_to_name(item.get('href'))
            for item in self.opf.xpath('//opf:manifest/opf:item[@href and @id]',
                namespaces={'opf':OPF2_NS})}

        linear, non_linear = [], []
        for item in self.opf.xpath('//opf:spine/opf:itemref[@idref]',
                                   namespaces={'opf':OPF2_NS}):
            idref = item.get('idref')
            name = manifest_id_map.get(idref, None)
            path = self.name_path_map.get(name, None)
            if path:
                if item.get('linear', 'yes') == 'yes':
                    yield path
                else:
                    non_linear.append(path)
        for path in non_linear:
            yield path

class InvalidEpub(InvalidBook):
    pass

OCF_NS = 'urn:oasis:names:tc:opendocument:xmlns:container'

class EpubContainer(Container):

    META_INF = {
            'container.xml' : True,
            'manifest.xml' : False,
            'encryption.xml' : False,
            'metadata.xml' : False,
            'signatures.xml' : False,
            'rights.xml' : False,
    }

    def __init__(self, pathtoepub, log):
        self.pathtoepub = pathtoepub
        tdir = self.root = PersistentTemporaryDirectory('_epub_container')
        with open(self.pathtoepub, 'rb') as stream:
            try:
                zf = ZipFile(stream)
                zf.extractall(tdir)
            except:
                log.exception('EPUB appears to be invalid ZIP file, trying a'
                        ' more forgiving ZIP parser')
                from calibre.utils.localunzip import extractall
                stream.seek(0)
                extractall(stream)
        try:
            os.remove(join(tdir, 'mimetype'))
        except EnvironmentError:
            pass

        container_path = join(self.root, 'META-INF', 'container.xml')
        if not exists(container_path):
            raise InvalidEpub('No META-INF/container.xml in epub')
        self.container = etree.fromstring(open(container_path, 'rb').read())
        opf_files = self.container.xpath((
            r'child::ocf:rootfiles/ocf:rootfile'
            '[@media-type="%s" and @full-path]'%guess_type('a.opf')[0]
            ), namespaces={'ocf':OCF_NS}
        )
        if not opf_files:
            raise InvalidEpub('META-INF/container.xml contains no link to OPF file')
        opf_path = os.path.join(self.root, *opf_files[0].get('full-path').split('/'))
        if not exists(opf_path):
            raise InvalidEpub('OPF file does not exist at location pointed to'
                    ' by META-INF/container.xml')

        super(EpubContainer, self).__init__(tdir, opf_path, log)

        self.obfuscated_fonts = {}
        if 'META-INF/encryption.xml' in self.name_path_map:
            self.process_encryption()

    def process_encryption(self):
        fonts = {}
        enc = self.parsed('META-INF/encryption.xml')
        for em in enc.xpath('//*[local-name()="EncryptionMethod" and @Algorithm]'):
            alg = em.get('Algorithm')
            if alg not in {ADOBE_OBFUSCATION, IDPF_OBFUSCATION}:
                raise DRMError()
            cr = em.getparent().xpath('descendant::*[local-name()="CipherReference" and @URI]')[0]
            name = self.href_to_name(cr.get('URI'), self.root)
            path = self.name_path_map.get(name, None)
            if path is not None:
                fonts[name] = alg
        if not fonts:
            return

        package_id = unique_identifier = idpf_key = None
        for attrib, val in self.opf.attrib.iteritems():
            if attrib.endswith('unique-identifier'):
                package_id = val
                break
        if package_id is not None:
            for elem in self.opf.xpath('//*[@id=%r]'%package_id):
                if elem.text:
                    unique_identifier = elem.text.rpartition(':')[-1]
                    break
        if unique_identifier is not None:
            idpf_key = hashlib.sha1(unique_identifier).digest()
        key = None
        for item in self.opf.xpath('//*[local-name()="metadata"]/*'
                                   '[local-name()="identifier"]'):
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
                    self.log.exception('Failed to parse obfuscation key')
                    key = None

        for font, alg in fonts.iteritems():
            path = self.name_path_map[font]
            tkey = key if alg == ADOBE_OBFUSCATION else idpf_key
            if not tkey:
                raise InvalidBook('Failed to find obfuscation key')
            decrypt_font(tkey, path, alg)
            self.obfuscated_fonts[name] = (alg, tkey)

class InvalidMobi(InvalidBook):
    pass

def do_explode(path, dest):
    from calibre.ebooks.mobi.reader.mobi6 import MobiReader
    from calibre.ebooks.mobi.reader.mobi8 import Mobi8Reader
    with open(path, 'rb') as stream:
        mr = MobiReader(stream, default_log, None, None)

        with CurrentDir(dest):
            mr = Mobi8Reader(mr, default_log)
            opf = os.path.abspath(mr())
            obfuscated_fonts = mr.encrypted_fonts
            try:
                os.remove('debug-raw.html')
            except:
                pass

    return opf, obfuscated_fonts

class AZW3Container(Container):

    def __init__(self, pathtoazw3, log):
        self.pathtoazw3 = pathtoazw3
        tdir = self.root = PersistentTemporaryDirectory('_azw3_container')
        with open(pathtoazw3, 'rb') as stream:
            raw = stream.read(3)
            if raw == b'TPZ':
                raise InvalidMobi(_('This is not a MOBI file. It is a Topaz file.'))

            try:
                header = MetadataHeader(stream, default_log)
            except MobiError:
                raise InvalidMobi(_('This is not a MOBI file.'))

            if header.encryption_type != 0:
                raise DRMError()

            kf8_type = header.kf8_type

            if kf8_type is None:
                raise InvalidMobi(_('This MOBI file does not contain a KF8 format '
                        'book. KF8 is the new format from Amazon. calibre can '
                        'only edit MOBI files that contain KF8 books. Older '
                        'MOBI files without KF8 are not editable.'))

            if kf8_type == 'joint':
                raise InvalidMobi(_('This MOBI file contains both KF8 and '
                    'older Mobi6 data. calibre can only edit MOBI files '
                    'that contain only KF8 data.'))

        try:
            opf_path, obfuscated_fonts = fork_job(
            'calibre.ebooks.oeb.polish.container', 'do_explode',
            args=(pathtoazw3, tdir), no_output=True)['result']
        except WorkerError as e:
            log(e.orig_tb)
            raise InvalidMobi('Failed to explode MOBI')
        super(AZW3Container, self).__init__(tdir, opf_path, log)
        self.obfuscated_fonts = {x.replace(os.sep, '/') for x in obfuscated_fonts}

if __name__ == '__main__':
    f = sys.argv[-1]
    ebook = (AZW3Container if f.rpartition('.')[-1].lower() in {'azw3', 'mobi'}
            else EpubContainer)(f, default_log)
    for s in ebook.spine_items:
        print (ebook.relpath(s))

