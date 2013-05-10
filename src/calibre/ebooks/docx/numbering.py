#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

from calibre.ebooks.docx.block_styles import ParagraphStyle
from calibre.ebooks.docx.char_styles import RunStyle
from calibre.ebooks.docx.names import XPath, get

STYLE_MAP = {
    'aiueo': 'hiragana',
    'aiueoFullWidth': 'hiragana',
    'hebrew1': 'hebrew',
    'iroha': 'katakana-iroha',
    'irohaFullWidth': 'katakana-iroha',
    'lowerLetter': 'lower-alpha',
    'lowerRoman': 'lower-roman',
    'none': 'none',
    'upperLetter': 'upper-alpha',
    'upperRoman': 'upper-roman',
    'chineseCounting': 'cjk-ideographic',
    'decimalZero': 'decimal-leading-zero',
}

class Level(object):

    def __init__(self, lvl=None):
        self.restart = None
        self.start = 0
        self.fmt = 'decimal'
        self.para_link = None
        self.paragraph_style = self.character_style = None

        if lvl is not None:
            self.read_from_xml(lvl)

    def read_from_xml(self, lvl, override=False):
        for lr in XPath('./w:lvlRestart[@w:val]')(lvl):
            try:
                self.restart = int(get(lr, 'w:val'))
            except (TypeError, ValueError):
                pass

        for lr in XPath('./w:start[@w:val]')(lvl):
            try:
                self.start = int(get(lr, 'w:val'))
            except (TypeError, ValueError):
                pass

        lt = None
        for lr in XPath('./w:lvlText[@w:val]')(lvl):
            lt = get(lr, 'w:val')

        for lr in XPath('./w:numFmt[@w:val]')(lvl):
            val = get(lr, 'w:val')
            if val == 'bullet':
                self.fmt = {'\uf0a7':'square', 'o':'circle'}.get(lt, 'disc')
            else:
                self.fmt = STYLE_MAP.get(val, 'decimal')

        for lr in XPath('./w:pStyle[@w:val]')(lvl):
            self.para_link = get(lr, 'w:val')

        for pPr in XPath('./w:pPr')(lvl):
            ps = ParagraphStyle(pPr)
            if self.paragraph_style is None:
                self.paragraph_style = ps
            else:
                self.paragraph_style.update(ps)

        for rPr in XPath('./w:rPr')(lvl):
            ps = RunStyle(rPr)
            if self.character_style is None:
                self.character_style = ps
            else:
                self.character_style.update(ps)

    def copy(self):
        ans = Level()
        for x in ('restart', 'start', 'fmt', 'para_link', 'paragraph_style', 'character_style'):
            setattr(ans, x, getattr(self, x))
        return ans

class NumberingDefinition(object):

    def __init__(self, parent=None):
        self.levels = {}
        if parent is not None:
            for lvl in XPath('./w:lvl')(parent):
                try:
                    ilvl = int(get(lvl, 'w:ilvl', 0))
                except (TypeError, ValueError):
                    ilvl = 0
                self.levels[ilvl] = Level(lvl)

    def copy(self):
        ans = NumberingDefinition()
        for l, lvl in self.levels.iteritems():
            ans.levels[l] = lvl.copy()
        return ans

class Numbering(object):

    def __init__(self):
        self.definitions = {}
        self.instances = {}

    def __call__(self, root, styles):
        ' Read all numbering style definitions '
        lazy_load = {}
        for an in XPath('./w:abstractNum[@w:abstractNumId]')(root):
            an_id = get(an, 'w:abstractNumId')
            nsl = XPath('./w:numStyleLink[@w:val]')(an)
            if nsl:
                lazy_load[an_id] = get(nsl[0], 'w:val')
            else:
                nd = NumberingDefinition(an)
                self.definitions[an_id] = nd

        def create_instance(n, definition):
            nd = definition.copy()
            for lo in XPath('./w:lvlOverride')(n):
                ilvl = get(lo, 'w:ilvl')
                for lvl in XPath('./w:lvl')(lo)[:1]:
                    nilvl = get(lvl, 'w:ilvl')
                    ilvl = nilvl if ilvl is None else ilvl
                    alvl = nd.levels.get(ilvl, None)
                    if alvl is None:
                        alvl = Level()
                    alvl.read_from_xml(lvl, override=True)

        next_pass = {}
        for n in XPath('./w:num[@w:numId]')(root):
            an_id = None
            num_id = get(n, 'w:numId')
            for an in XPath('./w:abstractNumId[@w:val]')(n):
                an_id = get(an, 'w:val')
            d = self.definitions.get(an_id, None)
            if d is None:
                next_pass[num_id] = (an_id, n)
                continue
            self.instances[num_id] = create_instance(n, d)

        numbering_links = styles.numbering_style_links
        for an_id, style_link in lazy_load.iteritems():
            num_id = numbering_links[style_link]
            self.definitions[an_id] = self.instances[num_id].copy()

        for num_id, (an_id, n) in next_pass.iteritems():
            d = self.definitions.get(an_id, None)
            if d is not None:
                self.instances[num_id] = create_instance(n, d)

