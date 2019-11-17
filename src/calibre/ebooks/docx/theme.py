#!/usr/bin/env python
# vim:fileencoding=utf-8


__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'


class Theme(object):

    def __init__(self, namespace):
        self.major_latin_font = 'Cambria'
        self.minor_latin_font = 'Calibri'
        self.namespace = namespace

    def __call__(self, root):
        for fs in self.namespace.XPath('//a:fontScheme')(root):
            for mj in self.namespace.XPath('./a:majorFont')(fs):
                for l in self.namespace.XPath('./a:latin[@typeface]')(mj):
                    self.major_latin_font = l.get('typeface')
            for mj in self.namespace.XPath('./a:minorFont')(fs):
                for l in self.namespace.XPath('./a:latin[@typeface]')(mj):
                    self.minor_latin_font = l.get('typeface')

    def resolve_font_family(self, ff):
        if ff.startswith('|'):
            ff = ff[1:-1]
            ff = self.major_latin_font if ff.startswith('major') else self.minor_latin_font
        return ff
