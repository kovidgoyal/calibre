#!/usr/bin/env python
from __future__ import with_statement
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'

'''Read meta information from epub files'''

import os, re, posixpath
from cStringIO import StringIO
from contextlib import closing

from calibre.utils.zipfile import ZipFile, BadZipfile, safe_replace
from calibre.utils.localunzip import LocalZipFile
from calibre.ebooks.BeautifulSoup import BeautifulStoneSoup
from calibre.ebooks.metadata import MetaInformation
from calibre.ebooks.metadata.opf2 import OPF
from calibre.ptempfile import TemporaryDirectory, PersistentTemporaryFile
from calibre import CurrentDir, walk
from calibre.constants import isosx
from calibre.utils.localization import lang_as_iso639_1

class EPubException(Exception):
    pass

class OCFException(EPubException):
    pass

class ContainerException(OCFException):
    pass

class Container(dict):
    def __init__(self, stream=None):
        if not stream: return
        soup = BeautifulStoneSoup(stream.read())
        container = soup.find(name=re.compile(r'container$', re.I))
        if not container:
            raise OCFException("<container> element missing")
        if container.get('version', None) != '1.0':
            raise EPubException("unsupported version of OCF")
        rootfiles = container.find(re.compile(r'rootfiles$', re.I))
        if not rootfiles:
            raise EPubException("<rootfiles/> element missing")
        for rootfile in rootfiles.findAll(re.compile(r'rootfile$', re.I)):
            try:
                self[rootfile['media-type']] = rootfile['full-path']
            except KeyError:
                raise EPubException("<rootfile/> element malformed")

class OCF(object):
    MIMETYPE        = 'application/epub+zip'
    CONTAINER_PATH  = 'META-INF/container.xml'
    ENCRYPTION_PATH = 'META-INF/encryption.xml'

    def __init__(self):
        raise NotImplementedError('Abstract base class')

class Encryption(object):

    OBFUSCATION_ALGORITHMS = frozenset(['http://ns.adobe.com/pdf/enc#RC',
            'http://www.idpf.org/2008/embedding'])

    def __init__(self, raw):
        from lxml import etree
        self.root = etree.fromstring(raw) if raw else None
        self.entries = {}
        if self.root is not None:
            for em in self.root.xpath('descendant::*[contains(name(), "EncryptionMethod")]'):
                algorithm = em.get('Algorithm', '')
                cr = em.getparent().xpath('descendant::*[contains(name(), "CipherReference")]')
                if cr:
                    uri = cr[0].get('URI', '')
                    if uri and algorithm:
                        self.entries[uri] = algorithm

    def is_encrypted(self, uri):
        algo = self.entries.get(uri, None)
        return algo is not None and algo not in self.OBFUSCATION_ALGORITHMS


class OCFReader(OCF):
    def __init__(self):
        try:
            mimetype = self.open('mimetype').read().rstrip()
            if mimetype != OCF.MIMETYPE:
                print 'WARNING: Invalid mimetype declaration', mimetype
        except:
            print 'WARNING: Epub doesn\'t contain a mimetype declaration'

        try:
            with closing(self.open(OCF.CONTAINER_PATH)) as f:
                self.container = Container(f)
        except KeyError:
            raise EPubException("missing OCF container.xml file")
        self.opf_path = self.container[OPF.MIMETYPE]
        try:
            with closing(self.open(self.opf_path)) as f:
                self.opf = OPF(f, self.root, populate_spine=False)
        except KeyError:
            raise EPubException("missing OPF package file")
        try:
            with closing(self.open(self.ENCRYPTION_PATH)) as f:
                self.encryption_meta = Encryption(f.read())
        except:
            self.encryption_meta = Encryption(None)


class OCFZipReader(OCFReader):
    def __init__(self, stream, mode='r', root=None):
        if isinstance(stream, (LocalZipFile, ZipFile)):
            self.archive = stream
        else:
            try:
                self.archive = ZipFile(stream, mode=mode)
            except BadZipfile:
                raise EPubException("not a ZIP .epub OCF container")
        self.root = root
        if self.root is None:
            name = getattr(stream, 'name', False)
            if name:
                self.root = os.path.abspath(os.path.dirname(name))
            else:
                self.root = os.getcwdu()
        super(OCFZipReader, self).__init__()

    def open(self, name, mode='r'):
        if isinstance(self.archive, LocalZipFile):
            return self.archive.open(name)
        return StringIO(self.archive.read(name))

def get_zip_reader(stream, root=None):
    try:
        zf = ZipFile(stream, mode='r')
    except:
        stream.seek(0)
        zf = LocalZipFile(stream)
    return OCFZipReader(zf, root=root)

class OCFDirReader(OCFReader):
    def __init__(self, path):
        self.root = path
        super(OCFDirReader, self).__init__()

    def open(self, path, *args, **kwargs):
        return open(os.path.join(self.root, path), *args, **kwargs)

def render_cover(opf, opf_path, zf, reader=None):
    from calibre.ebooks import render_html_svg_workaround
    from calibre.utils.logging import default_log

    cpage = opf.first_spine_item()
    if not cpage:
        return
    if reader is not None and reader.encryption_meta.is_encrypted(cpage):
        return

    with TemporaryDirectory('_epub_meta') as tdir:
        with CurrentDir(tdir):
            zf.extractall()
            opf_path = opf_path.replace('/', os.sep)
            cpage = os.path.join(tdir, os.path.dirname(opf_path), cpage)
            if not os.path.exists(cpage):
                return

            if isosx:
                # On OS X trying to render a HTML cover which uses embedded
                # fonts more than once in the same process causes a crash in Qt
                # so be safe and remove the fonts as well as any @font-face
                # rules
                for f in walk('.'):
                    if os.path.splitext(f)[1].lower() in ('.ttf', '.otf'):
                        os.remove(f)
                ffpat = re.compile(br'@font-face.*?{.*?}',
                        re.DOTALL|re.IGNORECASE)
                with open(cpage, 'r+b') as f:
                    raw = f.read()
                    f.truncate(0)
                    f.seek(0)
                    raw = ffpat.sub(b'', raw)
                    f.write(raw)
                from calibre.ebooks.chardet import xml_to_unicode
                raw = xml_to_unicode(raw,
                        strip_encoding_pats=True, resolve_entities=True)[0]
                from lxml import html
                for link in html.fromstring(raw).xpath('//link'):
                    href = link.get('href', '')
                    if href:
                        path = os.path.join(os.path.dirname(cpage), href)
                        if os.path.exists(path):
                            with open(path, 'r+b') as f:
                                raw = f.read()
                                f.truncate(0)
                                f.seek(0)
                                raw = ffpat.sub(b'', raw)
                                f.write(raw)

            return render_html_svg_workaround(cpage, default_log)

def get_cover(opf, opf_path, stream, reader=None):
    raster_cover = opf.raster_cover
    stream.seek(0)
    try:
        zf = ZipFile(stream)
    except:
        stream.seek(0)
        zf = LocalZipFile(stream)

    if raster_cover:
        base = posixpath.dirname(opf_path)
        cpath = posixpath.normpath(posixpath.join(base, raster_cover))
        if reader is not None and \
            reader.encryption_meta.is_encrypted(cpath):
                return
        try:
            member = zf.getinfo(cpath)
        except:
            pass
        else:
            f = zf.open(member)
            data = f.read()
            f.close()
            zf.close()
            return data

    return render_cover(opf, opf_path, zf, reader=reader)

def get_metadata(stream, extract_cover=True):
    """ Return metadata as a :class:`Metadata` object """
    stream.seek(0)
    reader = get_zip_reader(stream)
    mi = reader.opf.to_book_metadata()
    if extract_cover:
        try:
            cdata = get_cover(reader.opf, reader.opf_path, stream, reader=reader)
            if cdata is not None:
                mi.cover_data = ('jpg', cdata)
        except:
            import traceback
            traceback.print_exc()
    mi.timestamp = None
    return mi

def get_quick_metadata(stream):
    return get_metadata(stream, False)

def _write_new_cover(new_cdata, cpath):
    from calibre.utils.magick.draw import save_cover_data_to
    new_cover = PersistentTemporaryFile(suffix=os.path.splitext(cpath)[1])
    new_cover.close()
    save_cover_data_to(new_cdata, new_cover.name)
    return new_cover

def set_metadata(stream, mi, apply_null=False, update_timestamp=False):
    stream.seek(0)
    reader = get_zip_reader(stream, root=os.getcwdu())
    raster_cover = reader.opf.raster_cover
    mi = MetaInformation(mi)
    new_cdata = None
    replacements = {}
    try:
        new_cdata = mi.cover_data[1]
        if not new_cdata:
            raise Exception('no cover')
    except:
        try:
            new_cdata = open(mi.cover, 'rb').read()
        except:
            pass
    new_cover = cpath = None
    if new_cdata and raster_cover:
        try:
            cpath = posixpath.join(posixpath.dirname(reader.opf_path),
                    raster_cover)
            cover_replacable = not reader.encryption_meta.is_encrypted(cpath) and \
                    os.path.splitext(cpath)[1].lower() in ('.png', '.jpg', '.jpeg')
            if cover_replacable:
                new_cover = _write_new_cover(new_cdata, cpath)
                replacements[cpath] = open(new_cover.name, 'rb')
        except:
            import traceback
            traceback.print_exc()

    for x in ('guide', 'toc', 'manifest', 'spine'):
        setattr(mi, x, None)
    if mi.languages:
        langs = []
        for lc in mi.languages:
            lc2 = lang_as_iso639_1(lc)
            if lc2: lc = lc2
            langs.append(lc)
        mi.languages = langs

    reader.opf.smart_update(mi)
    reader.opf.add_uuid_identifier(mi.uuid)

    if apply_null:
        if not getattr(mi, 'series', None):
            reader.opf.series = None
        if not getattr(mi, 'tags', []):
            reader.opf.tags = []
        if not getattr(mi, 'isbn', None):
            reader.opf.isbn = None
    if update_timestamp and mi.timestamp is not None:
        reader.opf.timestamp = mi.timestamp

    newopf = StringIO(reader.opf.render())
    if isinstance(reader.archive, LocalZipFile):
        reader.archive.safe_replace(reader.container[OPF.MIMETYPE], newopf,
            extra_replacements=replacements)
    else:
        safe_replace(stream, reader.container[OPF.MIMETYPE], newopf,
            extra_replacements=replacements)
    try:
        if cpath is not None:
            replacements[cpath].close()
            os.remove(replacements[cpath].name)
    except:
        pass


