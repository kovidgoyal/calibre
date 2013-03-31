#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os, logging, sys, hashlib, uuid, re
from collections import defaultdict
from io import BytesIO
from urllib import unquote as urlunquote, quote as urlquote
from urlparse import urlparse

from lxml import etree

from calibre import guess_type as _guess_type, CurrentDir
from calibre.customize.ui import (plugin_for_input_format,
        plugin_for_output_format)
from calibre.ebooks.chardet import xml_to_unicode
from calibre.ebooks.conversion.plugins.epub_input import (
    ADOBE_OBFUSCATION, IDPF_OBFUSCATION, decrypt_font)
from calibre.ebooks.conversion.preprocess import HTMLPreProcessor, CSSPreProcessor
from calibre.ebooks.mobi import MobiError
from calibre.ebooks.mobi.reader.headers import MetadataHeader
from calibre.ebooks.mobi.tweak import set_cover
from calibre.ebooks.oeb.base import (
    serialize, OEB_DOCS, _css_logger, OEB_STYLES, OPF2_NS, DC11_NS, OPF)
from calibre.ebooks.oeb.polish.errors import InvalidBook, DRMError
from calibre.ebooks.oeb.parse_utils import NotHTML, parse_html, RECOVER_PARSER
from calibre.ptempfile import PersistentTemporaryDirectory, PersistentTemporaryFile
from calibre.utils.ipc.simple_worker  import fork_job, WorkerError
from calibre.utils.logging import default_log
from calibre.utils.zipfile import ZipFile

exists, join, relpath = os.path.exists, os.path.join, os.path.relpath

def guess_type(x):
    return _guess_type(x)[0] or 'application/octet-stream'

OEB_FONTS = {guess_type('a.ttf'), guess_type('b.ttf')}
OPF_NAMESPACES = {'opf':OPF2_NS, 'dc':DC11_NS}

class Container(object):

    '''
    A container represents an Open EBook as a directory full of files and an
    opf file. There are two important concepts:

        * The root directory. This is the base of the ebook. All the ebooks
          files are inside this directory or in its sub-directories.

        * Names: These are paths to the books' files relative to the root
          directory. They always contain POSIX separators and are unquoted. They
          can be thought of as canonical identifiers for files in the book.
          Most methods on the container object work with names.

    When converting between hrefs and names use the methods provided by this
    class, they assume all hrefs are quoted.
    '''

    book_type = 'oeb'

    def __init__(self, rootpath, opfpath, log):
        self.root = os.path.abspath(rootpath)
        self.log = log
        self.html_preprocessor = HTMLPreProcessor()
        self.css_preprocessor = CSSPreProcessor()

        self.parsed_cache = {}
        self.mime_map = {}
        self.name_path_map = {}
        self.dirtied = set()
        self.encoding_map = {}
        self.pretty_print = set()

        # Map of relative paths with '/' separators from root of unzipped ePub
        # to absolute paths on filesystem with os-specific separators
        opfpath = os.path.abspath(opfpath)
        for dirpath, _dirnames, filenames in os.walk(self.root):
            for f in filenames:
                path = join(dirpath, f)
                name = self.abspath_to_name(path)
                self.name_path_map[name] = path
                self.mime_map[name] = guess_type(path)
                # Special case if we have stumbled onto the opf
                if path == opfpath:
                    self.opf_name = name
                    self.opf_dir = os.path.dirname(path)
                    self.mime_map[name] = guess_type('a.opf')

        if not hasattr(self, 'opf_name'):
            raise InvalidBook('Could not locate opf file: %r'%opfpath)

        # Update mime map with data from the OPF
        for item in self.opf_xpath('//opf:manifest/opf:item[@href and @media-type]'):
            href = item.get('href')
            name = self.href_to_name(href, self.opf_name)
            if name in self.mime_map:
                self.mime_map[name] = item.get('media-type')

    def abspath_to_name(self, fullpath):
        return self.relpath(os.path.abspath(fullpath)).replace(os.sep, '/')

    def name_to_abspath(self, name):
        return os.path.abspath(join(self.root, *name.split('/')))

    def exists(self, name):
        return os.path.exists(self.name_to_abspath(name))

    def href_to_name(self, href, base=None):
        '''
        Convert an href (relative to base) to a name. base must be a name or
        None, in which case self.root is used.
        '''
        if base is None:
            base = self.root
        else:
            base = os.path.dirname(self.name_to_abspath(base))
        purl = urlparse(href)
        if purl.scheme or not purl.path or purl.path.startswith('/'):
            return None
        href = urlunquote(purl.path)
        fullpath = os.path.join(base, *href.split('/'))
        return self.abspath_to_name(fullpath)

    def name_to_href(self, name, base=None):
        '''Convert a name to a href relative to base, which must be a name or
        None in which case self.root is used as the base'''
        fullpath = self.name_to_abspath(name)
        basepath = self.root if base is None else os.path.dirname(self.name_to_abspath(base))
        path = relpath(fullpath, basepath).replace(os.sep, '/')
        return urlquote(path)

    def opf_xpath(self, expr):
        return self.opf.xpath(expr, namespaces=OPF_NAMESPACES)

    def has_name(self, name):
        return name in self.name_path_map

    def relpath(self, path, base=None):
        '''Convert an absolute path (with os separators) to a path relative to
        base (defaults to self.root). The relative path is *not* a name. Use
        abspath_to_name() for that.'''
        return relpath(path, base or self.root)

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
                self.used_encoding = bom_enc
                return fix_data(data.decode(bom_enc))
            except UnicodeDecodeError:
                pass
        try:
            self.used_encoding = 'utf-8'
            return fix_data(data.decode('utf-8'))
        except UnicodeDecodeError:
            pass
        data, self.used_encoding = xml_to_unicode(data)
        return fix_data(data)

    def parse_xml(self, data):
        data, self.used_encoding = xml_to_unicode(
            data, strip_encoding_pats=True, assume_utf8=True, resolve_entities=True)
        return etree.fromstring(data, parser=RECOVER_PARSER)

    def parse_xhtml(self, data, fname):
        try:
            return parse_html(
                data, log=self.log, decoder=self.decode,
                preprocessor=self.html_preprocessor, filename=fname,
                non_html_file_tags={'ncx'})
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
            self.used_encoding = None
            mime = self.mime_map.get(name, guess_type(name))
            ans = self.parse(self.name_path_map[name], mime)
            self.parsed_cache[name] = ans
            self.encoding_map[name] = self.used_encoding
        return ans

    def replace(self, name, obj):
        self.parsed_cache[name] = obj
        self.dirty(name)

    @property
    def opf(self):
        return self.parsed(self.opf_name)

    @property
    def mi(self):
        from calibre.ebooks.metadata.opf2 import OPF as O
        mi = self.serialize_item(self.opf_name)
        return O(BytesIO(mi), basedir=self.opf_dir, unquote_urls=False,
                populate_spine=False).to_book_metadata()

    @property
    def manifest_id_map(self):
        return {item.get('id'):self.href_to_name(item.get('href'), self.opf_name)
            for item in self.opf_xpath('//opf:manifest/opf:item[@href and @id]')}

    @property
    def manifest_type_map(self):
        ans = defaultdict(list)
        for item in self.opf_xpath('//opf:manifest/opf:item[@href and @media-type]'):
            ans[item.get('media-type').lower()].append(self.href_to_name(
                item.get('href'), self.opf_name))
        return {mt:tuple(v) for mt, v in ans.iteritems()}

    @property
    def guide_type_map(self):
        return {item.get('type', ''):self.href_to_name(item.get('href'), self.opf_name)
            for item in self.opf_xpath('//opf:guide/opf:reference[@href and @type]')}

    @property
    def spine_items(self):
        manifest_id_map = self.manifest_id_map

        linear, non_linear = [], []
        for item in self.opf_xpath('//opf:spine/opf:itemref[@idref]'):
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

    def remove_item(self, name):
        '''
        Remove the item identified by name from this container. This removes all
        references to the item in the OPF manifest, guide and spine as well as from
        any internal caches.
        '''
        removed = set()
        for elem in self.opf_xpath('//opf:manifest/opf:item[@href]'):
            if self.href_to_name(elem.get('href'), self.opf_name) == name:
                id_ = elem.get('id', None)
                if id_ is not None:
                    removed.add(id_)
                self.remove_from_xml(elem)
                self.dirty(self.opf_name)
        if removed:
            for item in self.opf_xpath('//opf:spine/opf:itemref[@idref]'):
                idref = item.get('idref')
                if idref in removed:
                    self.remove_from_xml(item)
                    self.dirty(self.opf_name)

        for item in self.opf_xpath('//opf:guide/opf:reference[@href]'):
            if self.href_to_name(item.get('href'), self.opf_name) == name:
                self.remove_from_xml(item)
                self.dirty(self.opf_name)

        path = self.name_path_map.pop(name, None)
        if path and os.path.exists(path):
            os.remove(path)
        self.mime_map.pop(name, None)
        self.parsed_cache.pop(name, None)
        self.dirtied.discard(name)

    def dirty(self, name):
        self.dirtied.add(name)

    def remove_from_xml(self, item):
        'Removes item from parent, fixing indentation (works only with self closing items)'
        parent = item.getparent()
        idx = parent.index(item)
        if idx == 0:
            # We are removing the first item - only care about adjusting
            # the tail if this was the only child
            if len(parent) == 1:
                parent.text = item.tail
        else:
            # Make sure the preceding item has this tail
            parent[idx-1].tail = item.tail
        parent.remove(item)
        return item

    def insert_into_xml(self, parent, item, index=None):
        '''Insert item into parent (or append if index is None), fixing
        indentation. Only works with self closing items.'''
        if index is None:
            parent.append(item)
        else:
            parent.insert(index, item)
        idx = parent.index(item)
        if idx == 0:
            item.tail = parent.text
            # If this is the only child of this parent element, we need a
            # little extra work as we have gone from a self-closing <foo />
            # element to <foo><item /></foo>
            if len(parent) == 1:
                sibling = parent.getprevious()
                if sibling is None:
                    # Give up!
                    return
                parent.text = sibling.text
                item.tail = sibling.tail
        else:
            item.tail = parent[idx-1].tail
            if idx == len(parent)-1:
                parent[idx-1].tail = parent.text

    def opf_get_or_create(self, name):
        ans = self.opf_xpath('//opf:'+name)
        if ans:
            return ans[0]
        self.dirty(self.opf_name)
        package = self.opf_xpath('//opf:package')[0]
        item = package.makeelement(OPF(name))
        item.tail = '\n'
        package.append(item)
        return item

    def generate_item(self, name, id_prefix=None, media_type=None):
        '''Add an item to the manifest with href derived from the given
        name. Ensures uniqueness of href and id automatically. Returns
        generated item.'''
        id_prefix = id_prefix or 'id'
        media_type = media_type or guess_type(name)
        href = self.name_to_href(name, self.opf_name)
        base, ext = href.rpartition('.')[0::2]
        all_ids = {x.get('id') for x in self.opf_xpath('//*[@id]')}
        c = 0
        item_id = id_prefix
        while item_id in all_ids:
            c += 1
            item_id = id_prefix + '%d'%c
        all_names = {x.get('href') for x in self.opf_xpath(
                '//opf:manifest/opf:item[@href]')}

        def exists(h):
            return self.exists(self.href_to_name(h, self.opf_name))

        c = 0
        while href in all_names or exists(href):
            c += 1
            href = '%s_%d.%s'%(base, c, ext)
        manifest = self.opf_xpath('//opf:manifest')[0]
        item = manifest.makeelement(OPF('item'),
                                    id=item_id, href=href)
        item.set('media-type', media_type)
        self.insert_into_xml(manifest, item)
        self.dirty(self.opf_name)
        name = self.href_to_name(href, self.opf_name)
        self.name_path_map[name] = self.name_to_abspath(name)
        self.mime_map[name] = media_type
        return item

    def format_opf(self):
        mdata = self.opf_xpath('//opf:metadata')[0]
        mdata.text = '\n    '
        remove = set()
        for child in mdata:
            child.tail = '\n    '
            try:
                if (child.get('name', '').startswith('calibre:') and
                    child.get('content', '').strip() in {'{}', ''}):
                    remove.add(child)
            except AttributeError:
                continue # Happens for XML comments
        for child in remove: mdata.remove(child)
        if len(mdata) > 0:
            mdata[-1].tail = '\n  '

    def serialize_item(self, name):
        data = self.parsed(name)
        if name == self.opf_name:
            self.format_opf()
        data = serialize(data, self.mime_map[name], pretty_print=name in
                         self.pretty_print)
        if name == self.opf_name:
            # Needed as I can't get lxml to output opf:role and
            # not output <opf:metadata> as well
            data = re.sub(br'(<[/]{0,1})opf:', r'\1', data)
        return data

    def commit_item(self, name, keep_parsed=False):
        if name not in self.parsed_cache:
            return
        data = self.serialize_item(name)
        self.dirtied.discard(name)
        if not keep_parsed:
            self.parsed_cache.pop(name)
        with open(self.name_path_map[name], 'wb') as f:
            f.write(data)

    def open(self, name, mode='rb'):
        ''' Open the file pointed to by name for direct read/write. Note that
        this will commit the file if it is dirtied and remove it from the parse
        cache. You must finish with this file before accessing the parsed
        version of it again, or bad things will happen. '''
        if name in self.dirtied:
            self.commit_item(name)
        self.parsed_cache.pop(name, False)
        path = self.name_to_abspath(name)
        base = os.path.dirname(path)
        if not os.path.exists(base):
            os.makedirs(base)
        return open(path, mode)

    def commit(self, outpath=None):
        for name in tuple(self.dirtied):
            self.commit_item(name)

    def compare_to(self, other):
        if set(self.name_path_map) != set(other.name_path_map):
            return 'Set of files is not the same'
        mismatches = []
        for name, path in self.name_path_map.iteritems():
            opath = other.name_path_map[name]
            with open(path, 'rb') as f1, open(opath, 'rb') as f2:
                if f1.read() != f2.read():
                    mismatches.append('The file %s is not the same'%name)
        return '\n'.join(mismatches)

# EPUB {{{
class InvalidEpub(InvalidBook):
    pass

OCF_NS = 'urn:oasis:names:tc:opendocument:xmlns:container'

class EpubContainer(Container):

    book_type = 'epub'

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
            '[@media-type="%s" and @full-path]'%guess_type('a.opf')
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
            name = self.href_to_name(cr.get('URI'))
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
            for elem in self.opf_xpath('//*[@id=%r]'%package_id):
                if elem.text:
                    unique_identifier = elem.text.rpartition(':')[-1]
                    break
        if unique_identifier is not None:
            idpf_key = hashlib.sha1(unique_identifier).digest()
        key = None
        for item in self.opf_xpath('//*[local-name()="metadata"]/*'
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
            self.obfuscated_fonts[font] = (alg, tkey)

    def commit(self, outpath=None):
        super(EpubContainer, self).commit()
        for name in self.obfuscated_fonts:
            if name not in self.name_path_map:
                continue
            alg, key = self.obfuscated_fonts[name]
            # Decrypting and encrypting are the same operation (XOR with key)
            decrypt_font(key, self.name_path_map[name], alg)
        if outpath is None:
            outpath = self.pathtoepub
        from calibre.ebooks.tweak import zip_rebuilder
        with open(join(self.root, 'mimetype'), 'wb') as f:
            f.write(guess_type('a.epub'))
        zip_rebuilder(self.root, outpath)

# }}}

# AZW3 {{{
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

    book_type = 'azw3'

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

    def commit(self, outpath=None):
        super(AZW3Container, self).commit()
        if outpath is None:
            outpath = self.pathtoazw3
        from calibre.ebooks.conversion.plumber import Plumber, create_oebbook
        opf = self.name_path_map[self.opf_name]
        plumber = Plumber(opf, outpath, self.log)
        plumber.setup_options()
        inp = plugin_for_input_format('azw3')
        outp = plugin_for_output_format('azw3')
        plumber.opts.mobi_passthrough = True
        oeb = create_oebbook(default_log, opf, plumber.opts)
        set_cover(oeb)
        outp.convert(oeb, outpath, inp, plumber.opts, default_log)
# }}}

def get_container(path, log=None):
    if log is None: log = default_log
    ebook = (AZW3Container if path.rpartition('.')[-1].lower() in {'azw3', 'mobi'}
            else EpubContainer)(path, log)
    return ebook

def test_roundtrip():
    ebook = get_container(sys.argv[-1])
    p = PersistentTemporaryFile(suffix='.'+sys.argv[-1].rpartition('.')[-1])
    p.close()
    ebook.commit(outpath=p.name)
    ebook2 = get_container(p.name)
    ebook3 = get_container(p.name)
    diff = ebook3.compare_to(ebook2)
    if diff is not None:
        print (diff)

if __name__ == '__main__':
    test_roundtrip()


