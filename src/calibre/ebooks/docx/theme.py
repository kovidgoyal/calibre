#!/usr/bin/env python
# License: GPLv3 Copyright: 2013, Kovid Goyal <kovid at kovidgoyal.net>

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lxml.etree import _Element

    from calibre.ebooks.docx.names import DOCXNamespace


class Theme:
    def __init__(self, namespace: DOCXNamespace) -> None:
        self.major_latin_font = 'Cambria'
        self.minor_latin_font = 'Calibri'
        self.namespace = namespace

    def __call__(self, root: _Element) -> None:
        for fs in self.namespace.XPath('//a:fontScheme')(root):
            for mj in self.namespace.XPath('./a:majorFont')(fs):
                for l in self.namespace.XPath('./a:latin[@typeface]')(mj):
                    self.major_latin_font = l.get('typeface')
            for mj in self.namespace.XPath('./a:minorFont')(fs):
                for l in self.namespace.XPath('./a:latin[@typeface]')(mj):
                    self.minor_latin_font = l.get('typeface')

    def resolve_font_family(self, ff: str) -> str:
        if ff.startswith('|'):
            ff = ff[1:-1]
            ff = self.major_latin_font if ff.startswith('major') else self.minor_latin_font
        return ff
