#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import copy
from functools import partial
from collections import defaultdict

import cssutils
from lxml import etree

from calibre import isbytestring, force_unicode
from calibre.ebooks.mobi.utils import to_base
from calibre.ebooks.oeb.base import (OEB_DOCS, OEB_STYLES, SVG_MIME, XPath,
        extract, XHTML)

XML_DOCS = OEB_DOCS | {SVG_MIME}

# References to record numbers in KF8 are stored as base-32 encoded integers,
# with 4 digits
to_ref = partial(to_base, base=32, min_num_digits=4)

class KF8Writer(object):

    def __init__(self, oeb, opts, resources):
        self.oeb, self.opts, self.log = oeb, opts, oeb.log
        self.used_images = set()
        self.resources = resources
        self.dup_data()
        self.flows = [None] # First flow item is reserved for the text

        self.replace_resource_links()
        self.extract_css_into_flows()

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
                idx = to_ref(idx)
                if is_image:
                    self.used_images.add(ref)
                    return 'kindle:embed:%s?mime=%s'%(idx,
                            self.resources.mime_map[ref])
                else:
                    return 'kindle:embed:%s'%idx
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

    def extract_css_into_flows(self):
        inlines = defaultdict(list) # Ensure identical <style>s not repeated
        sheets = {}

        for item in self.oeb.manifest:
            if item.media_type in OEB_STYLES:
                data = self.data(item).cssText
                self.flows.append(force_unicode(data, 'utf-8'))
                sheets[item.href] = len(self.flows)

        for item in self.oeb.spine:
            root = self.data(item)
            if not hasattr(root, 'xpath'): continue

            for link in XPath('//h:link[@href]')(root):
                href = item.abshref(link.get('href'))
                idx = sheets.get(href, None)
                if idx is not None:
                    idx = to_ref(idx)
                    link.set('href', 'kindle:flow:%s?mime=text/css'%idx)

            for tag in XPath('//h:style')(root):
                p = tag.getparent()
                idx = p.index(tag)
                raw = tag.text
                if not raw or not raw.strip():
                    extract(tag)
                    continue
                repl = etree.Element(XHTML('link'), type='text/css',
                        rel='stylesheet')
                p.insert(idx, repl)
                extract(tag)
                inlines[raw].append(repl)

        for raw, elems in inlines.iteritems():
            self.flows.append(raw)
            idx = to_ref(len(self.flows))
            for link in elems:
                link.set('href', 'kindle:flow:%s?mime=text/css'%idx)


