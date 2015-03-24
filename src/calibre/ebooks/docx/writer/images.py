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

from calibre.ebooks.oeb.base import urlunquote
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
        return self.images[href].rid

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
