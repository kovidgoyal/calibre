'''
OPF manifest trimming transform.
'''
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2008, Marshall T. Vandegrift <llasram@gmail.com>'

import sys
import os
from itertools import chain
from urlparse import urldefrag
from lxml import etree
import cssutils
from calibre.ebooks.oeb.base import XPNSMAP, CSS_MIME, OEB_DOCS
from calibre.ebooks.oeb.base import LINK_SELECTORS, CSSURL_RE
from calibre.ebooks.oeb.base import urlnormalize

class ManifestTrimmer(object):
    def transform(self, oeb, context):
        oeb.logger.info('Trimming unused files from manifest...')
        used = set()
        hrefs = oeb.manifest.hrefs
        for term in oeb.metadata:
            for item in oeb.metadata[term]:
                if item.value in oeb.manifest.hrefs:
                    used.add(oeb.manifest.hrefs[item.value])
                elif item.value in oeb.manifest.ids:
                    used.add(oeb.manifest.ids[item.value])
        for ref in oeb.guide.values():
            path, _ = urldefrag(ref.href)
            if path in oeb.manifest.hrefs:
                used.add(oeb.manifest.hrefs[path])
        # TOC items are required to be in the spine
        for item in oeb.spine:
            used.add(item)
        unchecked = used
        while unchecked:
            new = set()
            for item in unchecked:
                if (item.media_type in OEB_DOCS or 
                    item.media_type[-4:] in ('/xml', '+xml')) and \
                   item.data is not None:
                    hrefs = [sel(item.data) for sel in LINK_SELECTORS]
                    for href in chain(*hrefs):
                        href = item.abshref(urlnormalize(href))
                        if href in oeb.manifest.hrefs:
                            found = oeb.manifest.hrefs[href]
                            if found not in used:
                                new.add(found)
                elif item.media_type == CSS_MIME:
                    for match in CSSURL_RE.finditer(item.data):
                        href = match.group('url')
                        href = item.abshref(urlnormalize(href))
                        if href in oeb.manifest.hrefs:
                            found = oeb.manifest.hrefs[href]
                            if found not in used:
                                new.add(found)
            used.update(new)
            unchecked = new
        for item in oeb.manifest.values():
            if item not in used:
                oeb.logger.info('Trimming %r from manifest' % item.href)
                oeb.manifest.remove(item)
