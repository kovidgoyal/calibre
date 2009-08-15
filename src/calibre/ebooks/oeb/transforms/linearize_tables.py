#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from calibre.ebooks.oeb.base import OEB_DOCS, XPNSMAP

class LinearizeTables(object):

    def linearize(self, root):
        for x in root.xpath('//h:table|//h:td|//h:tr|//h:th',
                namespaces=XPNSMAP):
            x.tag = 'div'
            for attr in ('valign', 'colspan', 'rowspan', 'width', 'halign'):
                if attr in x.attrib:
                    del x.attrib[attr]

    def __call__(self, oeb, context):
        for x in oeb.manifest.items:
            if x.media_type in OEB_DOCS:
                self.linearize(x.data)
