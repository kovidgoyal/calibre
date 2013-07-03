#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

import os, sys, shutil

from lxml import etree

from calibre import walk, guess_type
from calibre.ebooks.metadata import string_to_authors, authors_to_sort_string
from calibre.ebooks.metadata.book.base import Metadata
from calibre.ebooks.docx import InvalidDOCX
from calibre.ebooks.docx.names import DOCUMENT, DOCPROPS, XPath, APPPROPS
from calibre.ptempfile import PersistentTemporaryDirectory
from calibre.utils.localization import canonicalize_lang
from calibre.utils.logging import default_log
from calibre.utils.zipfile import ZipFile
from calibre.ebooks.oeb.parse_utils import RECOVER_PARSER

def fromstring(raw, parser=RECOVER_PARSER):
    return etree.fromstring(raw, parser=parser)

# Read metadata {{{
def read_doc_props(raw, mi):
    root = fromstring(raw)
    titles = XPath('//dc:title')(root)
    if titles:
        title = titles[0].text
        if title and title.strip():
            mi.title = title.strip()
    tags = []
    for subject in XPath('//dc:subject')(root):
        if subject.text and subject.text.strip():
            tags.append(subject.text.strip().replace(',', '_'))
    for keywords in XPath('//cp:keywords')(root):
        if keywords.text and keywords.text.strip():
            for x in keywords.text.split():
                tags.extend(y.strip() for y in x.split(',') if y.strip())
    if tags:
        mi.tags = tags
    authors = XPath('//dc:creator')(root)
    aut = []
    for author in authors:
        if author.text and author.text.strip():
            aut.extend(string_to_authors(author.text))
    if aut:
        mi.authors = aut
        mi.author_sort = authors_to_sort_string(aut)

    desc = XPath('//dc:description')(root)
    if desc:
        raw = etree.tostring(desc[0], method='text', encoding=unicode)
        mi.comments = raw

    langs = []
    for lang in XPath('//dc:language')(root):
        if lang.text and lang.text.strip():
            l = canonicalize_lang(lang.text)
            if l:
                langs.append(l)
    if langs:
        mi.languages = langs

def read_app_props(raw, mi):
    root = fromstring(raw)
    company = root.xpath('//*[local-name()="Company"]')
    if company and company[0].text and company[0].text.strip():
        mi.publisher = company[0].text.strip()
# }}}

class DOCX(object):

    def __init__(self, path_or_stream, log=None, extract=True):
        stream = path_or_stream if hasattr(path_or_stream, 'read') else open(path_or_stream, 'rb')
        self.name = getattr(stream, 'name', None) or '<stream>'
        self.log = log or default_log
        if extract:
            self.extract(stream)
        else:
            self.init_zipfile(stream)
        self.read_content_types()
        self.read_package_relationships()

    def init_zipfile(self, stream):
        self.zipf = ZipFile(stream)
        self.names = frozenset(self.zipf.namelist())

    def extract(self, stream):
        self.tdir = PersistentTemporaryDirectory('docx_container')
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

    def exists(self, name):
        return name in self.names

    def read(self, name):
        if hasattr(self, 'zipf'):
            return self.zipf.open(name).read()
        path = self.names[name]
        with open(path, 'rb') as f:
            return f.read()

    def read_content_types(self):
        try:
            raw = self.read('[Content_Types].xml')
        except KeyError:
            raise InvalidDOCX('The file %s docx file has no [Content_Types].xml' % self.name)
        root = fromstring(raw)
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
        root = fromstring(raw)
        self.relationships = {}
        self.relationships_rmap = {}
        for item in root.xpath('//*[local-name()="Relationships"]/*[local-name()="Relationship" and @Type and @Target]'):
            target = item.get('Target').lstrip('/')
            typ = item.get('Type')
            self.relationships[typ] = target
            self.relationships_rmap[target] = typ

    @property
    def document_name(self):
        name = self.relationships.get(DOCUMENT, None)
        if name is None:
            names = tuple(n for n in self.names if n == 'document.xml' or n.endswith('/document.xml'))
            if not names:
                raise InvalidDOCX('The file %s docx file has no main document' % self.name)
            name = names[0]
        return name

    @property
    def document(self):
        return fromstring(self.read(self.document_name))

    @property
    def document_relationships(self):
        return self.get_relationships(self.document_name)

    def get_relationships(self, name):
        base = '/'.join(name.split('/')[:-1])
        by_id, by_type = {}, {}
        parts = name.split('/')
        name = '/'.join(parts[:-1] + ['_rels', parts[-1] + '.rels'])
        try:
            raw = self.read(name)
        except KeyError:
            pass
        else:
            root = fromstring(raw)
            for item in root.xpath('//*[local-name()="Relationships"]/*[local-name()="Relationship" and @Type and @Target]'):
                target = item.get('Target')
                if item.get('TargetMode', None) != 'External' and not target.startswith('#'):
                    target = '/'.join((base, target.lstrip('/')))
                typ = item.get('Type')
                Id = item.get('Id')
                by_id[Id] = by_type[typ] = target

        return by_id, by_type

    @property
    def metadata(self):
        mi = Metadata(_('Unknown'))
        name = self.relationships.get(DOCPROPS, None)
        if name is None:
            names = tuple(n for n in self.names if n.lower() == 'docprops/core.xml')
            if names:
                name = names[0]
        if name:
            try:
                raw = self.read(name)
            except KeyError:
                pass
            else:
                read_doc_props(raw, mi)

        name = self.relationships.get(APPPROPS, None)
        if name is None:
            names = tuple(n for n in self.names if n.lower() == 'docprops/app.xml')
            if names:
                name = names[0]
        if name:
            try:
                raw = self.read(name)
            except KeyError:
                pass
            else:
                read_app_props(raw, mi)

        return mi

    def close(self):
        if hasattr(self, 'zipf'):
            self.zipf.close()
        else:
            try:
                shutil.rmtree(self.tdir)
            except EnvironmentError:
                pass

if __name__ == '__main__':
    d = DOCX(sys.argv[-1], extract=False)
    print (d.metadata)
