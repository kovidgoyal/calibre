#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from calibre.ebooks.pdf.render.common import (
    Dictionary, Name)

STANDARD_FONTS = {
    'Times-Roman', 'Helvetica', 'Courier', 'Symbol', 'Times-Bold',
    'Helvetica-Bold', 'Courier-Bold', 'ZapfDingbats', 'Times-Italic',
    'Helvetica-Oblique', 'Courier-Oblique', 'Times-BoldItalic',
    'Helvetica-BoldOblique', 'Courier-BoldOblique', }

class FontManager(object):

    def __init__(self, objects):
        self.objects = objects
        self.std_map = {}

    def add_standard_font(self, name):
        if name not in STANDARD_FONTS:
            raise ValueError('%s is not a standard font'%name)
        if name not in self.std_map:
                self.std_map[name] = self.objects.add(Dictionary({
                'Type':Name('Font'),
                'Subtype':Name('Type1'),
                'BaseFont':Name(name)
            }))
        return self.std_map[name]

