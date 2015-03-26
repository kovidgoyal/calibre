#!/usr/bin/env python2
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2015, Kovid Goyal <kovid at kovidgoyal.net>'

from calibre.ebooks.docx.names import makeelement

class FontsManager(object):

    def __init__(self, oeb):
        self.oeb, self.log = oeb, oeb.log

    def serialize(self, text_styles, fonts, embed_relationships):
        font_families, seen = set(), set()
        for ts in text_styles:
            if ts.font_family:
                lf = ts.font_family.lower()
                if lf not in seen:
                    seen.add(lf)
                    font_families.add(ts.font_family)
        for family in sorted(font_families):
            makeelement(fonts, 'w:font', w_name=family)

