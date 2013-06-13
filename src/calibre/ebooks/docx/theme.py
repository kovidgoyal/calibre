#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

from calibre.ebooks.docx.names import XPath


class Theme(object):

    def __init__(self):
        self.major_latin_font = 'Cambria'
        self.minor_latin_font = 'Calibri'

    def __call__(self, root):
        for fs in XPath('//a:fontScheme')(root):
            for mj in XPath('./a:majorFont')(fs):
                for l in XPath('./a:latin[@typeface]')(mj):
                    self.major_latin_font = l.get('typeface')
            for mj in XPath('./a:minorFont')(fs):
                for l in XPath('./a:latin[@typeface]')(mj):
                    self.minor_latin_font = l.get('typeface')

    def resolve_font_family(self, ff):
        if ff.startswith('|'):
            ff = ff[1:-1]
            ff = self.major_latin_font if ff.startswith('major') else self.minor_latin_font
        return ff
