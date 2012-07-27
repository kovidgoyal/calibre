#!/usr/bin/python
# -*- coding: utf-8 -*-
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai
#
# Copyright (C) 2006 Søren Roug, European Environment Agency
#
# This is free software.  You may redistribute it under the terms
# of the Apache license and the GNU General Public License Version
# 2 or at your option any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public
# License along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301  USA
#
# Contributor(s):
#
from __future__ import division

import zipfile, re
import xml.sax.saxutils
from cStringIO import StringIO

from odf.namespaces import OFFICENS, DCNS, METANS
from odf.opendocument import load as odLoad
from odf.draw import Image as odImage, Frame as odFrame

from calibre.ebooks.metadata import MetaInformation, string_to_authors, check_isbn
from calibre.utils.magick.draw import identify_data
from calibre.utils.date import parse_date
from calibre.utils.localization import canonicalize_lang

whitespace = re.compile(r'\s+')

fields = {
'title':            (DCNS,u'title'),
'description':      (DCNS,u'description'),
'subject':          (DCNS,u'subject'),
'creator':          (DCNS,u'creator'),
'date':             (DCNS,u'date'),
'language':         (DCNS,u'language'),
'generator':        (METANS,u'generator'),
'initial-creator':  (METANS,u'initial-creator'),
'keyword':          (METANS,u'keyword'),
'editing-duration': (METANS,u'editing-duration'),
'editing-cycles':   (METANS,u'editing-cycles'),
'printed-by':       (METANS,u'printed-by'),
'print-date':       (METANS,u'print-date'),
'creation-date':    (METANS,u'creation-date'),
'user-defined':     (METANS,u'user-defined'),
#'template':         (METANS,u'template'),
}

def normalize(str):
    """
    The normalize-space function returns the argument string with whitespace
    normalized by stripping leading and trailing whitespace and replacing
    sequences of whitespace characters by a single space.
    """
    return whitespace.sub(' ', str).strip()

class MetaCollector:
    """
    The MetaCollector is a pseudo file object, that can temporarily ignore write-calls
    It could probably be replaced with a StringIO object.
    """
    def __init__(self):
        self._content = []
        self.dowrite = True

    def write(self, str):
        if self.dowrite:
            self._content.append(str)

    def content(self):
        return ''.join(self._content)


class odfmetaparser(xml.sax.saxutils.XMLGenerator):
    """ Parse a meta.xml file with an event-driven parser and replace elements.
        It would probably be a cleaner approach to use a DOM based parser and
        then manipulate in memory.
        Small issue: Reorders elements
    """

    def __init__(self, deletefields={}, yieldfields={}, addfields={}):
        self.deletefields = deletefields
        self.yieldfields = yieldfields
        self.addfields = addfields
        self._mimetype = ''
        self.output = MetaCollector()
        self._data = []
        self.seenfields = {}
        xml.sax.saxutils.XMLGenerator.__init__(self, self.output, 'utf-8')

    def startElementNS(self, name, qname, attrs):
        self._data = []
        field = name
# I can't modify the template until the tool replaces elements at the same
# location and not at the end
#       if name == (METANS,u'template'):
#           self._data = [attrs.get((XLINKNS,u'title'),'')]
        if name == (METANS,u'user-defined'):
            field = attrs.get((METANS,u'name'))
        if field in self.deletefields:
            self.output.dowrite = False
        elif field in self.yieldfields:
            del self.addfields[field]
            xml.sax.saxutils.XMLGenerator.startElementNS(self, name, qname, attrs)
        else:
            xml.sax.saxutils.XMLGenerator.startElementNS(self, name, qname, attrs)
        self._tag = field

    def endElementNS(self, name, qname):
        field = name
        if name == (METANS,u'user-defined'):
            field = self._tag
        if name == (OFFICENS,u'meta'):
            for k,v in self.addfields.items():
                if len(v) > 0:
                    if type(k) == type(''):
                        xml.sax.saxutils.XMLGenerator.startElementNS(self,(METANS,u'user-defined'),None,{(METANS,u'name'):k})
                        xml.sax.saxutils.XMLGenerator.characters(self, v)
                        xml.sax.saxutils.XMLGenerator.endElementNS(self, (METANS,u'user-defined'),None)
                    else:
                        xml.sax.saxutils.XMLGenerator.startElementNS(self, k, None, {})
                        xml.sax.saxutils.XMLGenerator.characters(self, v)
                        xml.sax.saxutils.XMLGenerator.endElementNS(self, k, None)
        if isinstance(self._tag, tuple):
            texttag = self._tag[1]
        else:
            texttag = self._tag
        self.seenfields[texttag] = self.data()
        # OpenOffice has the habit to capitalize custom properties, so we add a
        # lowercase version for easy access
        if texttag[:4].lower() == u'opf.':
            self.seenfields[texttag.lower()] = self.data()

        if field in self.deletefields:
            self.output.dowrite = True
        else:
            xml.sax.saxutils.XMLGenerator.endElementNS(self, name, qname)

    def characters(self, content):
        xml.sax.saxutils.XMLGenerator.characters(self, content)
        self._data.append(content)

    def meta(self):
        return self.output.content()

    def data(self):
        return normalize(''.join(self._data))

def get_metadata(stream, extract_cover=True):
    zin = zipfile.ZipFile(stream, 'r')
    odfs = odfmetaparser()
    parser = xml.sax.make_parser()
    parser.setFeature(xml.sax.handler.feature_namespaces, 1)
    parser.setContentHandler(odfs)
    content = zin.read('meta.xml')
    parser.parse(StringIO(content))
    data = odfs.seenfields
    mi = MetaInformation(None, [])
    if data.has_key('title'):
        mi.title = data['title']
    if data.get('initial-creator', '').strip():
        mi.authors = string_to_authors(data['initial-creator'])
    elif data.has_key('creator'):
        mi.authors = string_to_authors(data['creator'])
    if data.has_key('description'):
        mi.comments = data['description']
    if data.has_key('language'):
        mi.language = data['language']
    if data.get('keywords', ''):
        mi.tags = [x.strip() for x in data['keywords'].split(',') if x.strip()]
    opfmeta = False # we need this later for the cover
    opfnocover = False
    if data.get('opf.metadata','') == 'true':
        # custom metadata contains OPF information
        opfmeta = True
        if data.get('opf.titlesort', ''):
            mi.title_sort = data['opf.titlesort']
        if data.get('opf.authors', ''):
            mi.authors = string_to_authors(data['opf.authors'])
        if data.get('opf.authorsort', ''):
            mi.author_sort = data['opf.authorsort']
        if data.get('opf.isbn', ''):
            isbn = check_isbn(data['opf.isbn'])
            if isbn is not None:
                mi.isbn = isbn
        if data.get('opf.publisher', ''):
            mi.publisher = data['opf.publisher']
        if data.get('opf.pubdate', ''):
            mi.pubdate = parse_date(data['opf.pubdate'], assume_utc=True)
        if data.get('opf.language', ''):
            cl = canonicalize_lang(data['opf.language'])
            if cl:
                mi.languages = [cl]
        opfnocover = data.get('opf.nocover', 'false') == 'true'
    # search for an draw:image in a draw:frame with the name 'opf.cover'
    # if opf.metadata prop is false, just use the first image that
    # has a proper size (borrowed from docx)
    try:
        read_cover(stream, zin, mi, opfmeta, opfnocover, extract_cover)
    except:
        pass # Do not let an error reading the cover prevent reading other data

def read_cover(stream, zin, mi, opfmeta, opfnocover, extract_cover):
    otext = odLoad(stream)
    cover_href = None
    cover_data = None
    # check that it's really a ODT
    if otext.mimetype == u'application/vnd.oasis.opendocument.text':
        for elem in otext.text.getElementsByType(odFrame):
            img = elem.getElementsByType(odImage)
            if len(img) > 0: # there should be only one
                i_href = img[0].getAttribute('href')
                try:
                    raw = zin.read(i_href)
                except KeyError:
                    continue
                try:
                    width, height, fmt = identify_data(raw)
                except:
                    continue
            else:
                continue
            if opfmeta and elem.getAttribute('name').lower() == u'opf.cover':
                cover_href = i_href
                cover_data = (fmt, raw)
                break
            if cover_href is None and 0.8 <= height/width <= 1.8 and height*width >= 12000:
                cover_href = i_href
                cover_data = (fmt, raw)
                if not opfmeta:
                    break

    if not opfnocover and cover_href is not None:
        mi.cover = cover_href
        if extract_cover:
            if not cover_data:
                raw = zin.read(cover_href)
                try:
                    width, height, fmt = identify_data(raw)
                except:
                    pass
                else:
                    cover_data = (fmt, raw)
            mi.cover_data = cover_data

    return mi

