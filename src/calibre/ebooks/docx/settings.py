#!/usr/bin/env python
# License: GPLv3 Copyright: 2013, Kovid Goyal <kovid at kovidgoyal.net>

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lxml.etree import _Element

    from calibre.ebooks.docx.names import DOCXNamespace


class Settings:
    def __init__(self, namespace: DOCXNamespace) -> None:
        self.default_tab_stop = 720 / 20
        self.namespace = namespace

    def __call__(self, root: _Element) -> None:
        for dts in self.namespace.XPath('//w:defaultTabStop[@w:val]')(root):
            try:
                self.default_tab_stop = int(self.namespace.get(dts, 'w:val', '')) / 20
            except ValueError, TypeError, AttributeError:
                pass
