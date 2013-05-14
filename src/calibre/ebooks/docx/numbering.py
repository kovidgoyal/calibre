#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

import re
from collections import Counter

from lxml.html.builder import OL, UL, SPAN

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
        self.is_numbered = False
        self.num_template = None

        if lvl is not None:
            self.read_from_xml(lvl)

    def copy(self):
        ans = Level()
        for x in ('restart', 'start', 'fmt', 'para_link', 'paragraph_style', 'character_style', 'is_numbered', 'num_template'):
            setattr(ans, x, getattr(self, x))
        return ans

    def format_template(self, counter, ilvl):
        def sub(m):
            x = int(m.group(1)) - 1
            if x > ilvl or x not in counter:
                return ''
            return '%d' % (counter[x] - (0 if x == ilvl else 1))
        return re.sub(r'%(\d+)', sub, self.num_template).rstrip() + '\xa0'

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
                self.is_numbered = False
                self.fmt = {'\uf0a7':'square', 'o':'circle'}.get(lt, 'disc')
            else:
                self.is_numbered = True
                self.fmt = STYLE_MAP.get(val, 'decimal')
                if lt and re.match(r'%\d+\.$', lt) is None:
                    self.num_template = lt

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
        self.counters = {}

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
            return nd

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

        for num_id, d in self.instances.iteritems():
            self.counters[num_id] = Counter({lvl:d.levels[lvl].start for lvl in d.levels})

    def get_pstyle(self, num_id, style_id):
        d = self.instances.get(num_id, None)
        if d is not None:
            for ilvl, lvl in d.levels.iteritems():
                if lvl.para_link == style_id:
                    return ilvl

    def get_para_style(self, num_id, lvl):
        d = self.instances.get(num_id, None)
        if d is not None:
            lvl = d.levels.get(lvl, None)
            return getattr(lvl, 'paragraph_style', None)

    def update_counter(self, counter, levelnum, levels):
        counter[levelnum] += 1
        for ilvl, lvl in levels.iteritems():
            restart = lvl.restart
            if (restart is None and ilvl == levelnum + 1) or restart == levelnum + 1:
                counter[ilvl] = lvl.start

    def apply_markup(self, items, body, styles, object_map):
        for p, num_id, ilvl in items:
            d = self.instances.get(num_id, None)
            if d is not None:
                lvl = d.levels.get(ilvl, None)
                if lvl is not None:
                    counter = self.counters[num_id]
                    p.tag = 'li'
                    p.set('value', '%s' % counter[ilvl])
                    p.set('list-lvl', str(ilvl))
                    p.set('list-id', num_id)
                    if lvl.num_template is not None:
                        val = lvl.format_template(counter, ilvl)
                        p.set('list-template', val)
                    self.update_counter(counter, ilvl, d.levels)

        def commit(current_run):
            if not current_run:
                return
            start = current_run[0]
            parent = start.getparent()
            idx = parent.index(start)

            d = self.instances[start.get('list-id')]
            ilvl = int(start.get('list-lvl'))
            lvl = d.levels[ilvl]
            lvlid = start.get('list-id') + start.get('list-lvl')
            wrap = (OL if lvl.is_numbered else UL)('\n\t')
            has_template = 'list-template' in start.attrib
            if has_template:
                wrap.set('lvlid', lvlid)
            else:
                wrap.set('class', styles.register({'list-style-type': lvl.fmt}, 'list'))
            parent.insert(idx, wrap)
            last_val = None
            for child in current_run:
                wrap.append(child)
                child.tail = '\n\t'
                if has_template:
                    span = SPAN()
                    span.text = child.text
                    child.text = None
                    for gc in child:
                        span.append(gc)
                    child.append(span)
                    span = SPAN(child.get('list-template'))
                    child.insert(0, span)
                for attr in ('list-lvl', 'list-id', 'list-template'):
                    child.attrib.pop(attr, None)
                val = int(child.get('value'))
                if last_val == val - 1 or wrap.tag == 'ul':
                    child.attrib.pop('value')
                last_val = val
            current_run[-1].tail = '\n'
            del current_run[:]

        parents = set()
        for child in body.iterdescendants('li'):
            parents.add(child.getparent())

        for parent in parents:
            current_run = []
            for child in parent:
                if child.tag == 'li':
                    if current_run:
                        last = current_run[-1]
                        if (last.get('list-id') , last.get('list-lvl')) != (child.get('list-id'), child.get('list-lvl')):
                            commit(current_run)
                    current_run.append(child)
                else:
                    commit(current_run)
            commit(current_run)

        for wrap in body.xpath('//ol[@lvlid]'):
            wrap.attrib.pop('lvlid')
            wrap.tag = 'div'
            for i, li in enumerate(wrap.iterchildren('li')):
                li.tag = 'div'
                li.attrib.pop('value', None)
                li.set('style', 'display:table-row')
                obj = object_map[li]
                bs = styles.para_cache[obj]
                if i == 0:
                    wrap.set('style', 'display:table; margin-left: %s' % (bs.css.get('margin-left', 0)))
                bs.css.pop('margin-left', None)
                for child in li:
                    child.set('style', 'display:table-cell')

