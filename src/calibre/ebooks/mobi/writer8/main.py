#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import copy
from functools import partial

import cssutils

from calibre import isbytestring
from calibre.ebooks.oeb.base import (OEB_DOCS, OEB_STYLES, SVG_MIME, XPath)

XML_DOCS = OEB_DOCS | {SVG_MIME}

class KF8Writer(object):

    def __init__(self, oeb, opts, resources):
        self.oeb, self.opts, self.log = oeb, opts, oeb.log
        self.used_images = set()
        self.resources = resources
        self.dup_data()

        self.replace_resource_links()

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

    def replace_resource_links(self):
        ''' Replace links to resources (raster images/fonts) with pointers to
        the MOBI record containing the resource. The pointers are of the form:
        kindle:embed:XXXX?mime=image/* The ?mime= is apparently optional and
        not used for fonts. '''

        def pointer(item, oref):
            ref = item.abshref(oref)
            idx = self.resources.item_map.get(ref, None)
            if idx is not None:
                is_image = self.resources.records[idx-1][:4] not in {b'FONT'}
                if is_image:
                    self.used_images.add(ref)
                    return 'kindle:embed:%04d?mime=%s'%(idx,
                            self.resources.mime_map[ref])
                else:
                    return 'kindle:embed:%04d'%idx
            return oref

        for item in self.oeb.manifest:

            if item.media_type in XML_DOCS:
                root = self.data(item)
                for tag in XPath('//h:img|//svg:image')(root):
                    for attr, ref in tag.attrib.iteritems():
                        if attr.split('}')[-1].lower() in {'src', 'href'}:
                            tag.attrib[attr] = pointer(item, ref)

                for tag in XPath('//h:style')(root):
                    if tag.text:
                        sheet = cssutils.parseString(tag.text)
                        replacer = partial(pointer, item)
                        cssutils.replaceUrls(sheet, replacer,
                                ignoreImportRules=True)
                        repl = sheet.cssText
                        if isbytestring(repl):
                            repl = repl.decode('utf-8')
                        tag.text = '\n'+ repl + '\n'

            elif item.media_type in OEB_STYLES:
                sheet = self.data(item)
                replacer = partial(pointer, item)
                cssutils.replaceUrls(sheet, replacer, ignoreImportRules=True)


    def create_pieces(self):
        self.flows = [None] # First flow item is reserved for the text

        for item in self.oeb.spine:
            root = self.data(item)
            root

