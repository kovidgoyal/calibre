#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

import os, sys

from lxml import etree

from calibre import walk, guess_type
from calibre.ebooks.docx import InvalidDOCX
from calibre.ebooks.docx.names import DOCUMENT
from calibre.ptempfile import PersistentTemporaryDirectory
from calibre.utils.logging import default_log
from calibre.utils.zipfile import ZipFile

class DOCX(object):

    def __init__(self, path_or_stream, log=None):
        stream = path_or_stream if hasattr(path_or_stream, 'read') else open(path_or_stream, 'rb')
        self.name = getattr(stream, 'name', None) or '<stream>'
        self.log = log or default_log
        self.tdir = PersistentTemporaryDirectory('docx_container')

        self.extract(stream)
        self.read_content_types()
        self.read_package_relationships()

    def extract(self, stream):
        try:
            zf = ZipFile(stream)
            zf.extractall(self.tdir)
        except:
            self.log.exception('DOCX appears to be invalid ZIP file, trying a'
                    ' more forgiving ZIP parser')
            from calibre.utils.localunzip import extractall
            stream.seek(0)
            extractall(stream, self.tdir)

        self.names = {}
        for f in walk(self.tdir):
            name = os.path.relpath(f, self.tdir).replace(os.sep, '/')
            self.names[name] = f

    def read(self, name):
        path = self.names[name]
        with open(path, 'rb') as f:
            return f.read()

    def read_content_types(self):
        try:
            raw = self.read('[Content_Types].xml')
        except KeyError:
            raise InvalidDOCX('The file %s docx file has no [Content_Types].xml' % self.name)
        root = etree.fromstring(raw)
        self.content_types = {}
        self.default_content_types = {}
        for item in root.xpath('//*[local-name()="Types"]/*[local-name()="Default" and @Extension and @ContentType]'):
            self.default_content_types[item.get('Extension').lower()] = item.get('ContentType')
        for item in root.xpath('//*[local-name()="Types"]/*[local-name()="Override" and @PartName and @ContentType]'):
            name = item.get('PartName').lstrip('/')
            self.content_types[name] = item.get('ContentType')

    def content_type(self, name):
        if name in self.content_types:
            return self.content_types[name]
        ext = name.rpartition('.')[-1].lower()
        if ext in self.default_content_types:
            return self.default_content_types[ext]
        return guess_type(name)[0]

    def read_package_relationships(self):
        try:
            raw = self.read('_rels/.rels')
        except KeyError:
            raise InvalidDOCX('The file %s docx file has no _rels/.rels' % self.name)
        root = etree.fromstring(raw)
        self.relationships = {}
        self.relationships_rmap = {}
        for item in root.xpath('//*[local-name()="Relationships"]/*[local-name()="Relationship" and @Type and @Target]'):
            target = item.get('Target').lstrip('/')
            typ = item.get('Type')
            self.relationships[typ] = target
            self.relationships_rmap[target] = typ

    @property
    def document(self):
        name = self.relationships.get(DOCUMENT, None)
        if name is None:
            names = tuple(n for n in self.names if n == 'document.xml' or n.endswith('/document.xml'))
            if not names:
                raise InvalidDOCX('The file %s docx file has no main document' % self.name)
            name = names[0]
        return etree.fromstring(self.read(name))

if __name__ == '__main__':
    d = DOCX(sys.argv[-1])
