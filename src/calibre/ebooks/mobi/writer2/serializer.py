#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from calibre.ebooks.oeb.base import (OEB_DOCS, XHTML, XHTML_NS, XML_NS,
        namespace, prefixname, urlnormalize)
from calibre.ebooks.mobi.mobiml import MBP_NS

from collections import defaultdict
from urlparse import urldefrag
from cStringIO import StringIO


class Serializer(object):
    NSRMAP = {'': None, XML_NS: 'xml', XHTML_NS: '', MBP_NS: 'mbp'}

    def __init__(self, oeb, images, write_page_breaks_after_item=True):
        '''
        Write all the HTML markup in oeb into a single in memory buffer
        containing a single html document with links replaced by offsets into
        the buffer.

        :param oeb: OEBBook object that encapsulates the document to be
        processed.

        :param images: Mapping of image hrefs (urlnormalized) to image record
        indices.

        :param write_page_breaks_after_item: If True a MOBIpocket pagebreak tag
        is written after every element of the spine in ``oeb``.
        '''
        self.oeb = oeb
        self.images = images
        self.logger = oeb.logger
        self.write_page_breaks_after_item = write_page_breaks_after_item

        # Mapping of hrefs (urlnormalized) to the offset in the buffer where
        # the resource pointed to by the href lives. Used at the end to fill in
        # the correct values into all filepos="..." links.
        self.id_offsets = {}

        # Mapping of hrefs (urlnormalized) to a list of offsets into the buffer
        # where filepos="..." elements are written corresponding to links that
        # point to the href. This is used at the end to fill in the correct values.
        self.href_offsets = defaultdict(list)

        # List of offsets in the buffer of non linear items in the spine. These
        # become uncrossable breaks in the MOBI
        self.breaks = []

    def __call__(self):
        '''
        Return the document serialized as a single UTF-8 encoded bytestring.
        '''
        buf = self.buf = StringIO()
        buf.write(b'<html>')
        self.serialize_head()
        self.serialize_body()
        buf.write(b'</html>')
        self.fixup_links()
        return buf.getvalue()

    def serialize_head(self):
        buf = self.buf
        buf.write(b'<head>')
        if len(self.oeb.guide) > 0:
            self.serialize_guide()
        buf.write(b'</head>')

    def serialize_guide(self):
        '''
        The Kindle decides where to open a book based on the presence of
        an item in the guide that looks like
        <reference type="text" title="Start" href="chapter-one.xhtml"/>

        Similarly an item with type="toc" controls where the Goto Table of
        Contents operation on the kindle goes.
        '''

        buf = self.buf
        hrefs = self.oeb.manifest.hrefs
        buf.write(b'<guide>')
        for ref in self.oeb.guide.values():
            path = urldefrag(ref.href)[0]
            if path not in hrefs or hrefs[path].media_type not in OEB_DOCS:
                continue

            buf.write(b'<reference type="')
            if ref.type.startswith('other.') :
                self.serialize_text(ref.type.replace('other.',''), quot=True)
            else:
                self.serialize_text(ref.type, quot=True)
            buf.write(b'" ')
            if ref.title is not None:
                buf.write(b'title="')
                self.serialize_text(ref.title, quot=True)
                buf.write(b'" ')
            self.serialize_href(ref.href)
            # Space required or won't work, I kid you not
            buf.write(b' />')

        buf.write(b'</guide>')

    def serialize_href(self, href, base=None):
        '''
        Serialize the href attribute of an <a> or <reference> tag. It is
        serialized as filepos="000000000" and a pointer to its location is
        stored in self.href_offsets so that the correct value can be filled in
        at the end.
        '''
        hrefs = self.oeb.manifest.hrefs
        path, frag = urldefrag(urlnormalize(href))
        if path and base:
            path = base.abshref(path)
        if path and path not in hrefs:
            return False
        buf = self.buf
        item = hrefs[path] if path else None
        if item and item.spine_position is None:
            return False
        path = item.href if item else base.href
        href = '#'.join((path, frag)) if frag else path
        buf.write(b'filepos=')
        self.href_offsets[href].append(buf.tell())
        buf.write(b'0000000000')
        return True

    def serialize_body(self):
        '''
        Serialize all items in the spine of the document. Non linear items are
        moved to the end.
        '''
        buf = self.buf
        self.anchor_offset = buf.tell()
        buf.write(b'<body>')
        self.body_start_offset = buf.tell()
        spine = [item for item in self.oeb.spine if item.linear]
        spine.extend([item for item in self.oeb.spine if not item.linear])
        for item in spine:
            self.serialize_item(item)
        self.body_end_offset = buf.tell()
        buf.write(b'</body>')

    def serialize_item(self, item):
        '''
        Serialize an individual item from the spine of the input document.
        A reference to this item is stored in self.href_offsets
        '''
        buf = self.buf
        if not item.linear:
            self.breaks.append(buf.tell() - 1)
        self.id_offsets[urlnormalize(item.href)] = buf.tell()
        # Kindle periodical articles are contained in a <div> tag
        buf.write(b'<div>')
        for elem in item.data.find(XHTML('body')):
            self.serialize_elem(elem, item)
        # Kindle periodical article end marker
        buf.write(b'<div></div>')
        if self.write_page_breaks_after_item:
            buf.write(b'<mbp:pagebreak/>')
        buf.write(b'</div>')
        self.anchor_offset = None

    def serialize_elem(self, elem, item, nsrmap=NSRMAP):
        buf = self.buf
        if not isinstance(elem.tag, basestring) \
            or namespace(elem.tag) not in nsrmap:
                return
        tag = prefixname(elem.tag, nsrmap)
        # Previous layers take care of @name
        id_ = elem.attrib.pop('id', None)
        if id_:
            href = '#'.join((item.href, id_))
            offset = self.anchor_offset or buf.tell()
            self.id_offsets[urlnormalize(href)] = offset
        if self.anchor_offset is not None and \
            tag == 'a' and not elem.attrib and \
            not len(elem) and not elem.text:
                return
        self.anchor_offset = buf.tell()
        buf.write(b'<')
        buf.write(tag.encode('utf-8'))
        if elem.attrib:
            for attr, val in elem.attrib.items():
                if namespace(attr) not in nsrmap:
                    continue
                attr = prefixname(attr, nsrmap)
                buf.write(b' ')
                if attr == 'href':
                    if self.serialize_href(val, item):
                        continue
                elif attr == 'src':
                    href = urlnormalize(item.abshref(val))
                    if href in self.images:
                        index = self.images[href]
                        buf.write(b'recindex="%05d"' % index)
                        continue
                buf.write(attr.encode('utf-8'))
                buf.write(b'="')
                self.serialize_text(val, quot=True)
                buf.write(b'"')
        buf.write(b'>')
        if elem.text or len(elem) > 0:
            if elem.text:
                self.anchor_offset = None
                self.serialize_text(elem.text)
            for child in elem:
                self.serialize_elem(child, item)
                if child.tail:
                    self.anchor_offset = None
                    self.serialize_text(child.tail)
        buf.write(b'</%s>' % tag.encode('utf-8'))

    def serialize_text(self, text, quot=False):
        text = text.replace('&', '&amp;')
        text = text.replace('<', '&lt;')
        text = text.replace('>', '&gt;')
        text = text.replace(u'\u00AD', '') # Soft-hyphen
        if quot:
            text = text.replace('"', '&quot;')
        self.buf.write(text.encode('utf-8'))

    def fixup_links(self):
        '''
        Fill in the correct values for all filepos="..." links with the offsets
        of the linked to content (as stored in id_offsets).
        '''
        buf = self.buf
        id_offsets = self.id_offsets
        for href, hoffs in self.href_offsets.items():
            # Iterate over all filepos items
            if href not in id_offsets:
                self.logger.warn('Hyperlink target %r not found' % href)
                # Link to the top of the document, better than just ignoring
                href, _ = urldefrag(href)
            if href in self.id_offsets:
                ioff = self.id_offsets[href]
                for hoff in hoffs:
                    buf.seek(hoff)
                    buf.write(b'%010d' % ioff)


