#!/usr/bin/env python2
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2015, Kovid Goyal <kovid at kovidgoyal.net>'

import os
import shutil, posixpath
from collections import namedtuple
from functools import partial
from future_builtins import map

from lxml import etree

from calibre.ebooks.oeb.base import urlunquote
from calibre.ebooks.docx.names import makeelement, namespaces
from calibre.ebooks.docx.images import pt_to_emu
from calibre.ptempfile import PersistentTemporaryDirectory
from calibre.utils.filenames import ascii_filename
from calibre.utils.magick.draw import identify_data

Image = namedtuple('Image', 'rid fname width height fmt item')

class ImagesManager(object):

    def __init__(self, oeb, document_relationships):
        self.oeb, self.log = oeb, oeb.log
        self.images = {}
        self.seen_filenames = set()
        self.document_relationships = document_relationships
        self._tdir = None
        self.count = 0

    @property
    def tdir(self):
        if self._tdir is None:
            self._tdir = PersistentTemporaryDirectory(suffix='_docx_output_images')
        return self._tdir

    def cleanup(self):
        if self._tdir is not None:
            shutil.rmtree(self._tdir)
            self._tdir = None

    def add_image(self, img, block, stylizer):
        src = img.get('src')
        if not src:
            return
        href = self.abshref(src)
        if href not in self.images:
            item = self.oeb.manifest.hrefs.get(href)
            if item is None or not isinstance(item.data, bytes):
                return
            width, height, fmt = identify_data(item.data)
            image_fname = 'media/' + self.create_filename(href, fmt)
            image_rid = self.document_relationships.add_image(image_fname)
            self.images[href] = Image(image_rid, image_fname, width, height, fmt, item)
            item.unload_data_from_memory()
        drawing = self.create_image_markup(img, stylizer, href)
        block.add_image(drawing)
        return self.images[href].rid

    def create_image_markup(self, html_img, stylizer, href):
        # TODO: Handle floating images, margin/padding/border on image, img
        # inside a link (clickable image)
        self.count += 1
        img = self.images[href]
        name = urlunquote(posixpath.basename(href))
        width, height = map(pt_to_emu, stylizer.style(html_img).img_size(img.width, img.height))

        root = etree.Element('root', nsmap=namespaces)
        ans = makeelement(root, 'w:drawing', append=False)
        inline = makeelement(ans, 'wp:inline', distT='0', distB='0', distR='0', distL='0')
        makeelement(inline, 'wp:extent', cx=str(width), cy=str(width))
        makeelement(inline, 'wp:effectExtent', l='0', r='0', t='0', b='0')
        makeelement(inline, 'wp:docPr', id=str(self.count), name=name, descr=html_img.get('alt') or name)
        makeelement(makeelement(inline, 'wp:cNvGraphicFramePr'), 'a:graphicFrameLocks', noChangeAspect="1")
        g = makeelement(inline, 'a:graphic')
        gd = makeelement(g, 'a:graphicData', uri=namespaces['pic'])
        pic = makeelement(gd, 'pic:pic')
        nvPicPr = makeelement(pic, 'pic:nvPicPr')
        makeelement(nvPicPr, 'pic:cNvPr', id='0', name=name, descr=html_img.get('alt') or name)
        makeelement(nvPicPr, 'pic:cNvPicPr')
        bf = makeelement(pic, 'pic:blipFill')
        makeelement(bf, 'a:blip', r_embed=img.rid)
        makeelement(makeelement(bf, 'a:stretch'), 'a:fillRect')
        spPr = makeelement(pic, 'pic:spPr')
        xfrm = makeelement(spPr, 'a:xfrm')
        makeelement(xfrm, 'a:off', x='0', y='0'), makeelement(xfrm, 'a:ext', cx=str(width), cy=str(height))
        makeelement(makeelement(spPr, 'a:prstGeom', prst='rect'), 'a:avLst')
        return ans

    def create_filename(self, href, fmt):
        fname = ascii_filename(urlunquote(posixpath.basename(href)))
        fname = posixpath.splitext(fname)[0]
        fname = fname[:75].rstrip('.') or 'image'
        num = 0
        base = fname
        while fname.lower() in self.seen_filenames:
            num += 1
            fname = base + str(num)
        self.seen_filenames.add(fname.lower())
        fname += os.extsep + fmt.lower()
        return fname

    def serialize(self, images_map):
        for img in self.images.itervalues():
            images_map['word/' + img.fname] = partial(self.get_data, img.item)

    def get_data(self, item):
        try:
            return item.data
        finally:
            item.unload_data_from_memory(False)
