#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os, posixpath, urllib, sys, re

from lxml import etree
from lxml.etree import XMLSyntaxError

from calibre.ebooks.epub.fix import InvalidEpub, ParseError
from calibre import guess_type, prepare_string_for_xml
from calibre.ebooks.chardet import xml_to_unicode
from calibre.constants import iswindows
from calibre.utils.zipfile import ZipFile, ZIP_STORED

exists, join = os.path.exists, os.path.join

OCF_NS = 'urn:oasis:names:tc:opendocument:xmlns:container'
OPF_NS = 'http://www.idpf.org/2007/opf'

class Container(object):

    META_INF = {
            'container.xml' : True,
            'manifest.xml' : False,
            'encryption.xml' : False,
            'metadata.xml' : False,
            'signatures.xml' : False,
            'rights.xml' : False,
    }

    def __init__(self, path, log):
        self.root = os.path.abspath(path)
        self.log = log
        self.dirtied = set([])
        self.cache = {}
        self.mime_map = {}

        if exists(join(self.root, 'mimetype')):
            os.remove(join(self.root, 'mimetype'))

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
        opf_path = os.path.join(self.root,
                *opf_files[0].get('full-path').split('/'))
        if not exists(opf_path):
            raise InvalidEpub('OPF file does not exist at location pointed to'
                    ' by META-INF/container.xml')

        # Map of relative paths with / separators to absolute
        # paths on filesystem with os separators
        self.name_map = {}
        for dirpath, dirnames, filenames in os.walk(self.root):
            for f in filenames:
                path = join(dirpath, f)
                name = os.path.relpath(path, self.root).replace(os.sep, '/')
                self.name_map[name] = path
                if path == opf_path:
                    self.opf_name = name
                    self.mime_map[name] = guess_type('a.opf')[0]

        for item in self.opf.xpath(
                '//opf:manifest/opf:item[@href and @media-type]',
                namespaces={'opf':OPF_NS}):
            href = item.get('href')
            self.mime_map[self.href_to_name(href,
                posixpath.dirname(self.opf_name))] = item.get('media-type')

    def manifest_worthy_names(self):
        for name in self.name_map:
            if name.endswith('.opf'): continue
            if name.startswith('META-INF') and \
                    posixpath.basename(name) in self.META_INF: continue
            yield name

    def delete_name(self, name):
        self.mime_map.pop(name, None)
        path = self.name_map[name]
        os.remove(path)
        self.name_map.pop(name)

    def manifest_item_for_name(self, name):
        href = self.name_to_href(name,
            posixpath.dirname(self.opf_name))
        q = prepare_string_for_xml(href, attribute=True)
        existing = self.opf.xpath('//opf:manifest/opf:item[@href="%s"]'%q,
                namespaces={'opf':OPF_NS})
        if not existing:
            return None
        return existing[0]

    def add_name_to_manifest(self, name, mt=None):
        item = self.manifest_item_for_name(name)
        if item is not None:
            return
        manifest = self.opf.xpath('//opf:manifest', namespaces={'opf':OPF_NS})[0]
        item = manifest.makeelement('{%s}item'%OPF_NS, nsmap={'opf':OPF_NS},
                href=self.name_to_href(name, posixpath.dirname(self.opf_name)),
                id=self.generate_manifest_id())
        if not mt:
            mt = guess_type(posixpath.basename(name))[0]
        if not mt:
            mt = 'application/octest-stream'
        item.set('media-type', mt)
        manifest.append(item)
        self.fix_tail(item)

    def fix_tail(self, item):
        '''
        Designed only to work with self closing elements after item has
        just been inserted/appended
        '''
        parent = item.getparent()
        idx = parent.index(item)
        if idx == 0:
            item.tail = parent.text
        else:
            item.tail = parent[idx-1].tail
            if idx == len(parent)-1:
                parent[idx-1].tail = parent.text

    def generate_manifest_id(self):
        items = self.opf.xpath('//opf:manifest/opf:item[@id]',
                namespaces={'opf':OPF_NS})
        ids = set([x.get('id') for x in items])
        for x in xrange(sys.maxint):
            c = 'id%d'%x
            if c not in ids:
                return c

    @property
    def opf(self):
        return self.get(self.opf_name)

    def href_to_name(self, href, base=''):
        href = urllib.unquote(href.partition('#')[0])
        name = href
        if base:
            name = posixpath.join(base, href)
        return name

    def name_to_href(self, name, base):
        if not base:
            return name
        return posixpath.relpath(name, base)

    def get_raw(self, name):
        path = self.name_map[name]
        return open(path, 'rb').read()

    def get(self, name):
        if name in self.cache:
            return self.cache[name]
        raw = self.get_raw(name)
        if name in self.mime_map:
            try:
                raw = self._parse(raw, self.mime_map[name])
            except XMLSyntaxError as err:
                raise ParseError(name, unicode(err))
        self.cache[name] = raw
        return raw

    def set(self, name, val):
        self.cache[name] = val
        self.dirtied.add(name)

    def _parse(self, raw, mimetype):
        mt = mimetype.lower()
        if mt.endswith('+xml'):
            parser = etree.XMLParser(no_network=True, huge_tree=not iswindows)
            raw = xml_to_unicode(raw,
                strip_encoding_pats=True, assume_utf8=True,
                resolve_entities=True)[0].strip()
            idx = raw.find('<html')
            if idx == -1:
                idx = raw.find('<HTML')
            if idx > -1:
                pre = raw[:idx]
                raw = raw[idx:]
                if '<!DOCTYPE' in pre:
                    user_entities = {}
                    for match in re.finditer(r'<!ENTITY\s+(\S+)\s+([^>]+)', pre):
                        val = match.group(2)
                        if val.startswith('"') and val.endswith('"'):
                            val = val[1:-1]
                        user_entities[match.group(1)] = val
                    if user_entities:
                        pat = re.compile(r'&(%s);'%('|'.join(user_entities.keys())))
                        raw = pat.sub(lambda m:user_entities[m.group(1)], raw)
            return etree.fromstring(raw, parser=parser)
        return raw

    def write(self, path):
        for name in self.dirtied:
            data = self.cache[name]
            raw = data
            if hasattr(data, 'xpath'):
                raw = etree.tostring(data, encoding='utf-8',
                        xml_declaration=True)
            with open(self.name_map[name], 'wb') as f:
                f.write(raw)
        self.dirtied.clear()
        zf = ZipFile(path, 'w')
        zf.writestr('mimetype', bytes(guess_type('a.epub')[0]),
                compression=ZIP_STORED)
        zf.add_dir(self.root)
        zf.close()

