#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import copy

import cssutils

from calibre.ebooks.oeb.base import (OEB_DOCS, OEB_STYLES, SVG_MIME)

XML_DOCS = OEB_DOCS | {SVG_MIME}

class KF8Writer(object):

    def __init__(self, oeb, opts):
        self.oeb, self.opts, self.log = oeb, opts, oeb.log
        self.dup_data()

        self.create_pieces()

    def dup_data(self):
        ''' Duplicate data so that any changes we make to markup/CSS only
        affect KF8 output and not MOBI 6 output '''
        self._data_cache = {}
        for item in self.oeb.manifest:
            if item.media_type in XML_DOCS:
                self._data_cache[item.href] = copy.deepcopy(item.data)
            elif item.media_type in OEB_STYLES:
                # I can't figure out how to make an efficient copy of the
                # in-memory CSSStylesheet, as deepcopy doesn't work (raises an
                # exception)
                self._data_cache[item.href] = cssutils.parseString(
                        item.data.cssText)

    def data(self, item):
        return self._data_cache.get(item.href, item.data)

    def create_pieces(self):
        self.flows = [None] # First flow item is reserved for the text

        for item in self.oeb.spine:
            root = self.data(item)
            root

