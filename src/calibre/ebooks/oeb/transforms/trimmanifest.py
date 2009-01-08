'''
OPF manifest trimming transform.
'''
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2008, Marshall T. Vandegrift <llasram@gmail.com>'

import sys
import os
from lxml import etree
from calibre.ebooks.oeb.base import XPNSMAP, CSS_MIME

LINK_SELECTORS = []
for expr in ('//h:link/@href', '//h:img/@src', '//h:object/@data',
             '//*/@xl:href'):
    LINK_SELECTORS.append(etree.XPath(expr, namespaces=XPNSMAP))

class ManifestTrimmer(object):
    def transform(self, oeb, context):
        oeb.logger.info('Trimming unused files from manifest...')
        used = set()
        for item in oeb.spine:
            used.add(item.href)
            for selector in LINK_SELECTORS:
                for href in selector(item.data):
                    used.add(item.abshref(href))
        # TODO: Things mentioned in CSS
        # TODO: Things mentioned in SVG
        # Who knows what people will do...
        for term in oeb.metadata:
            for item in oeb.metadata[term]:
                if item.value in oeb.manifest.hrefs:
                    used.add(item.value)
                elif item.value in oeb.manifest.ids:
                    used.add(oeb.manifest.ids[item.value].href)
        for item in oeb.manifest.values():
            if item.href not in used:
                oeb.logger.info('Trimming %r from manifest' % item.href)
                oeb.manifest.remove(item)
