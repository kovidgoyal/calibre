#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import re

from calibre.ebooks.oeb.base import (OEB_DOCS, XHTML, XHTML_NS, XML_NS,
        namespace, prefixname, urlnormalize)
from calibre.ebooks.mobi.mobiml import MBP_NS
from calibre.ebooks.mobi.utils import is_guide_ref_start, utf8_text

from collections import defaultdict
from urlparse import urldefrag
from cStringIO import StringIO


class Serializer(object):
    NSRMAP = {'': None, XML_NS: 'xml', XHTML_NS: '', MBP_NS: 'mbp'}

    def __init__(self, oeb, images, is_periodical, write_page_breaks_after_item=True):
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
        # Map of image hrefs to image index in the MOBI file
        self.images = images
        self.used_images = set()
        self.logger = oeb.logger
        self.is_periodical = is_periodical
        self.write_page_breaks_after_item = write_page_breaks_after_item

        # If not None, this is a number pointing to the location at which to
        # open the MOBI file on the Kindle
        self.start_offset = None

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

        self.find_blocks()

    def find_blocks(self):
        '''
        Mark every item in the spine if it is the start/end of a
        section/article, so that it can be wrapped in divs appropriately.
        '''
        for item in self.oeb.spine:
            item.is_section_start = item.is_section_end = False
            item.is_article_start = item.is_article_end = False

        def spine_item(tocitem):
            href = urldefrag(tocitem.href)[0]
            for item in self.oeb.spine:
                if item.href == href:
                    return item

        for item in self.oeb.toc.iterdescendants():
            if item.klass == 'section':
                articles = list(item)
                if not articles: continue
                spine_item(item).is_section_start = True
                for i, article in enumerate(articles):
                    si = spine_item(article)
                    if si is not None:
                        si.is_article_start = True

        items = list(self.oeb.spine)
        in_sec = in_art = False
        for i, item in enumerate(items):
            try:
                prev_item = items[i-1]
            except:
                prev_item = None
            if in_art and item.is_article_start == True:
                prev_item.is_article_end = True
                in_art = False
            if in_sec and item.is_section_start == True:
                prev_item.is_section_end = True
                in_sec = False
            if item.is_section_start: in_sec = True
            if item.is_article_start: in_art = True

        item.is_section_end = item.is_article_end = True

    def __call__(self):
        '''
        Return the document serialized as a single UTF-8 encoded bytestring.
        '''
        buf = self.buf = StringIO()
        buf.write(b'<html>')
        self.serialize_head()
        self.serialize_body()
        buf.write(b'</html>')
        self.end_offset = buf.tell()
        self.fixup_links()
        if self.start_offset is None and not self.is_periodical:
            # If we don't set a start offset, the stupid Kindle will
            # open the book at the location of the first IndexEntry, which
            # could be anywhere. So ensure the book is always opened at the
            # beginning, instead.
            self.start_offset = self.body_start_offset
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
                if is_guide_ref_start(ref):
                    self._start_href = ref.href
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
        try:
            path, frag = urldefrag(urlnormalize(href))
        except ValueError:
            # Unparseable URL
            return False
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

        def serialize_toc_level(tocref, href=None):
            # add the provided toc level to the output stream
            # if href is provided add a link ref to the toc level output (e.g. feed_0/index.html)
            if href is not None:
                # resolve the section url in id_offsets
                buf.write('<mbp:pagebreak />')
                self.id_offsets[urlnormalize(href)] = buf.tell()

            if tocref.klass == "periodical":
                buf.write('<div> <div height="1em"></div>')
            else:
                t = tocref.title
                if isinstance(t, unicode):
                    t = t.encode('utf-8')
                buf.write('<div></div> <div> <h2 height="1em"><font size="+2"><b>'
                        +t+'</b></font></h2> <div height="1em"></div>')

            buf.write('<ul>')

            for tocitem in tocref.nodes:
                buf.write('<li><a filepos=')
                itemhref = tocitem.href
                if tocref.klass == 'periodical':
                    # This is a section node.
                    # For periodical tocs, the section urls are like r'feed_\d+/index.html'
                    # We dont want to point to the start of the first article
                    # so we change the href.
                    itemhref = re.sub(r'article_\d+/', '', itemhref)
                self.href_offsets[itemhref].append(buf.tell())
                buf.write('0000000000')
                buf.write(' ><font size="+1" color="blue"><b><u>')
                t = tocitem.title
                if isinstance(t, unicode):
                    t = t.encode('utf-8')
                buf.write(t)
                buf.write('</u></b></font></a></li>')

            buf.write('</ul><div height="1em"></div></div><mbp:pagebreak />')

        self.anchor_offset = buf.tell()
        buf.write(b'<body>')
        self.body_start_offset = buf.tell()

        if self.is_periodical:
            top_toc = self.oeb.toc.nodes[0]
            serialize_toc_level(top_toc)

        spine = [item for item in self.oeb.spine if item.linear]
        spine.extend([item for item in self.oeb.spine if not item.linear])

        for item in spine:

            if self.is_periodical and item.is_section_start:
                for section_toc in top_toc.nodes:
                    if urlnormalize(item.href) == section_toc.href:
                        # create section url of the form r'feed_\d+/index.html'
                        section_url = re.sub(r'article_\d+/', '', section_toc.href)
                        serialize_toc_level(section_toc, section_url)
                        section_toc.href = section_url
                        break

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
        if item.is_section_start:
            buf.write(b'<a ></a> ')
        if item.is_article_start:
            buf.write(b'<a ></a> <a ></a>')
        for elem in item.data.find(XHTML('body')):
            self.serialize_elem(elem, item)
        if self.write_page_breaks_after_item:
            buf.write(b'<mbp:pagebreak/>')
        if item.is_article_end:
            # Kindle periodical article end marker
            buf.write(b'<a ></a> <a ></a>')
        if item.is_section_end:
            buf.write(b' <a ></a>')
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
            key = urlnormalize(href)
            # Only set this id_offset if it wasn't previously seen
            self.id_offsets[key] = self.id_offsets.get(key, offset)
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
                        self.used_images.add(href)
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
        self.buf.write(utf8_text(text))

    def fixup_links(self):
        '''
        Fill in the correct values for all filepos="..." links with the offsets
        of the linked to content (as stored in id_offsets).
        '''
        buf = self.buf
        id_offsets = self.id_offsets
        start_href = getattr(self, '_start_href', None)
        for href, hoffs in self.href_offsets.items():
            is_start = (href and href == start_href)
            # Iterate over all filepos items
            if href not in id_offsets:
                self.logger.warn('Hyperlink target %r not found' % href)
                # Link to the top of the document, better than just ignoring
                href, _ = urldefrag(href)
            if href in self.id_offsets:
                ioff = self.id_offsets[href]
                if is_start:
                    self.start_offset = ioff
                for hoff in hoffs:
                    buf.seek(hoff)
                    buf.write(b'%010d' % ioff)


