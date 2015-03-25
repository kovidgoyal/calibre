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

def get_image_margins(style):
    ans = {}
    for edge in 'Left Right Top Bottom'.split():
        val = getattr(style, 'padding' + edge) + getattr(style, 'margin' + edge)
        ans['dist' + edge[0]] = str(pt_to_emu(val))
    return ans

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
        # TODO: img inside a link (clickable image)
        style = stylizer.style(html_img)
        floating = style['float']
        if floating not in {'left', 'right'}:
            floating = None
        fake_margins = floating is None
        self.count += 1
        img = self.images[href]
        name = urlunquote(posixpath.basename(href))
        width, height = map(pt_to_emu, style.img_size(img.width, img.height))

        root = etree.Element('root', nsmap=namespaces)
        ans = makeelement(root, 'w:drawing', append=False)
        if floating is None:
            parent = makeelement(ans, 'wp:inline')
        else:
            parent = makeelement(ans, 'wp:anchor', **get_image_margins(style))
            # The next three lines are boilerplate that Word requires, even
            # though the DOCX specs define defaults for all of them
            parent.set('simplePos', '0'), parent.set('relativeHeight', '1'), parent.set('behindDoc',"0"), parent.set('locked', "0")
            parent.set('layoutInCell', "1"), parent.set('allowOverlap', '1')
            makeelement(parent, 'wp:simplePos', x='0', y='0')
            makeelement(makeelement(parent, 'wp:positionH', relativeFrom='margin'), 'wp:align').text = floating
            makeelement(makeelement(parent, 'wp:positionV', relativeFrom='line'), 'wp:align').text = 'top'
        makeelement(parent, 'wp:extent', cx=str(width), cy=str(width))
        if fake_margins:
            # DOCX does not support setting margins for inline images, so we
            # fake it by using effect extents to simulate margins
            makeelement(parent, 'wp:effectExtent', **{k[-1].lower():v for k, v in get_image_margins(style).iteritems()})
        else:
            makeelement(parent, 'wp:effectExtent', l='0', r='0', t='0', b='0')
        if floating is not None:
            # The idiotic Word requires this to be after the extent settings
            makeelement(parent, 'wp:wrapSquare', wrapText='bothSides')
        makeelement(parent, 'wp:docPr', id=str(self.count), name=name, descr=html_img.get('alt') or name)
        makeelement(makeelement(parent, 'wp:cNvGraphicFramePr'), 'a:graphicFrameLocks', noChangeAspect="1")
        g = makeelement(parent, 'a:graphic')
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
