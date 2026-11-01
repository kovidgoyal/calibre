#!/usr/bin/env python
# License: GPLv3 Copyright: 2009, Kovid Goyal <kovid@kovidgoyal.net>

from typing import TYPE_CHECKING

from lxml import etree

from calibre.ebooks.oeb.base import OEB_DOCS, XHTML, XPath

if TYPE_CHECKING:
    from optparse import Values

    from lxml.etree import _Element

    from calibre.ebooks.conversion.plumber import OptionValues
    from calibre.ebooks.oeb.base import OEBBook


class LinearizeTables:
    def linearize(self, root: _Element) -> None:
        for x in XPath('//h:table|//h:td|//h:tr|//h:th|//h:caption|//h:tbody|//h:tfoot|//h:thead|//h:colgroup|//h:col')(root):
            x.tag = XHTML('div')
            for attr in (
                'style',
                'font',
                'valign',
                'colspan',
                'width',
                'height',
                'rowspan',
                'summary',
                'align',
                'cellspacing',
                'cellpadding',
                'frames',
                'rules',
                'border',
            ):
                if attr in x.attrib:
                    del x.attrib[attr]

    def __call__(self, oeb: OEBBook, context: Values | OptionValues) -> None:
        for x in oeb.manifest.items:
            if x.media_type in OEB_DOCS:
                root = x.data
                assert isinstance(root, etree._Element)  # media_type is in OEB_DOCS
                self.linearize(root)
