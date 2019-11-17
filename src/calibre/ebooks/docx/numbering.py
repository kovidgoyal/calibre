#!/usr/bin/env python
# vim:fileencoding=utf-8


__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

import re, string
from collections import Counter, defaultdict
from functools import partial

from lxml.html.builder import OL, UL, SPAN

from calibre.ebooks.docx.block_styles import ParagraphStyle
from calibre.ebooks.docx.char_styles import RunStyle, inherit
from calibre.ebooks.metadata import roman
from polyglot.builtins import iteritems, unicode_type

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


def alphabet(val, lower=True):
    x = string.ascii_lowercase if lower else string.ascii_uppercase
    return x[(abs(val - 1)) % len(x)]


alphabet_map = {
    'lower-alpha':alphabet, 'upper-alpha':partial(alphabet, lower=False),
    'lower-roman':lambda x:roman(x).lower(), 'upper-roman':roman,
    'decimal-leading-zero': lambda x: '0%d' % x
}


class Level(object):

    def __init__(self, namespace, lvl=None):
        self.namespace = namespace
        self.restart = None
        self.start = 0
        self.fmt = 'decimal'
        self.para_link = None
        self.paragraph_style = self.character_style = None
        self.is_numbered = False
        self.num_template = None
        self.bullet_template = None
        self.pic_id = None

        if lvl is not None:
            self.read_from_xml(lvl)

    def copy(self):
        ans = Level(self.namespace)
        for x in ('restart', 'pic_id', 'start', 'fmt', 'para_link', 'paragraph_style', 'character_style', 'is_numbered', 'num_template', 'bullet_template'):
            setattr(ans, x, getattr(self, x))
        return ans

    def format_template(self, counter, ilvl, template):
        def sub(m):
            x = int(m.group(1)) - 1
            if x > ilvl or x not in counter:
                return ''
            val = counter[x] - (0 if x == ilvl else 1)
            formatter = alphabet_map.get(self.fmt, lambda x: '%d' % x)
            return formatter(val)
        return re.sub(r'%(\d+)', sub, template).rstrip() + '\xa0'

    def read_from_xml(self, lvl, override=False):
        XPath, get = self.namespace.XPath, self.namespace.get
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

        for rPr in XPath('./w:rPr')(lvl):
            ps = RunStyle(self.namespace, rPr)
            if self.character_style is None:
                self.character_style = ps
            else:
                self.character_style.update(ps)

        lt = None
        for lr in XPath('./w:lvlText[@w:val]')(lvl):
            lt = get(lr, 'w:val')

        for lr in XPath('./w:numFmt[@w:val]')(lvl):
            val = get(lr, 'w:val')
            if val == 'bullet':
                self.is_numbered = False
                cs = self.character_style
                if lt in {'\uf0a7', 'o'} or (
                    cs is not None and cs.font_family is not inherit and cs.font_family.lower() in {'wingdings', 'symbol'}):
                    self.fmt = {'\uf0a7':'square', 'o':'circle'}.get(lt, 'disc')
                else:
                    self.bullet_template = lt
                for lpid in XPath('./w:lvlPicBulletId[@w:val]')(lvl):
                    self.pic_id = get(lpid, 'w:val')
            else:
                self.is_numbered = True
                self.fmt = STYLE_MAP.get(val, 'decimal')
                if lt and re.match(r'%\d+\.$', lt) is None:
                    self.num_template = lt

        for lr in XPath('./w:pStyle[@w:val]')(lvl):
            self.para_link = get(lr, 'w:val')

        for pPr in XPath('./w:pPr')(lvl):
            ps = ParagraphStyle(self.namespace, pPr)
            if self.paragraph_style is None:
                self.paragraph_style = ps
            else:
                self.paragraph_style.update(ps)

    def css(self, images, pic_map, rid_map):
        ans = {'list-style-type': self.fmt}
        if self.pic_id:
            rid = pic_map.get(self.pic_id, None)
            if rid:
                try:
                    fname = images.generate_filename(rid, rid_map=rid_map, max_width=20, max_height=20)
                except Exception:
                    fname = None
                else:
                    ans['list-style-image'] = 'url("images/%s")' % fname
        return ans

    def char_css(self):
        try:
            css = self.character_style.css
        except AttributeError:
            css = {}
        css.pop('font-family', None)
        return css


class NumberingDefinition(object):

    def __init__(self, namespace, parent=None, an_id=None):
        self.namespace = namespace
        XPath, get = self.namespace.XPath, self.namespace.get
        self.levels = {}
        self.abstract_numbering_definition_id = an_id
        if parent is not None:
            for lvl in XPath('./w:lvl')(parent):
                try:
                    ilvl = int(get(lvl, 'w:ilvl', 0))
                except (TypeError, ValueError):
                    ilvl = 0
                self.levels[ilvl] = Level(namespace, lvl)

    def copy(self):
        ans = NumberingDefinition(self.namespace, an_id=self.abstract_numbering_definition_id)
        for l, lvl in iteritems(self.levels):
            ans.levels[l] = lvl.copy()
        return ans


class Numbering(object):

    def __init__(self, namespace):
        self.namespace = namespace
        self.definitions = {}
        self.instances = {}
        self.counters = defaultdict(Counter)
        self.starts = {}
        self.pic_map = {}

    def __call__(self, root, styles, rid_map):
        ' Read all numbering style definitions '
        XPath, get = self.namespace.XPath, self.namespace.get
        self.rid_map = rid_map
        for npb in XPath('./w:numPicBullet[@w:numPicBulletId]')(root):
            npbid = get(npb, 'w:numPicBulletId')
            for idata in XPath('descendant::v:imagedata[@r:id]')(npb):
                rid = get(idata, 'r:id')
                self.pic_map[npbid] = rid
        lazy_load = {}
        for an in XPath('./w:abstractNum[@w:abstractNumId]')(root):
            an_id = get(an, 'w:abstractNumId')
            nsl = XPath('./w:numStyleLink[@w:val]')(an)
            if nsl:
                lazy_load[an_id] = get(nsl[0], 'w:val')
            else:
                nd = NumberingDefinition(self.namespace, an, an_id=an_id)
                self.definitions[an_id] = nd

        def create_instance(n, definition):
            nd = definition.copy()
            start_overrides = {}
            for lo in XPath('./w:lvlOverride')(n):
                try:
                    ilvl = int(get(lo, 'w:ilvl'))
                except (ValueError, TypeError):
                    ilvl = None
                for so in XPath('./w:startOverride[@w:val]')(lo):
                    try:
                        start_override = int(get(so, 'w:val'))
                    except (TypeError, ValueError):
                        pass
                    else:
                        start_overrides[ilvl] = start_override
                for lvl in XPath('./w:lvl')(lo)[:1]:
                    nilvl = get(lvl, 'w:ilvl')
                    ilvl = nilvl if ilvl is None else ilvl
                    alvl = nd.levels.get(ilvl, None)
                    if alvl is None:
                        alvl = Level(self.namespace)
                    alvl.read_from_xml(lvl, override=True)
            for ilvl, so in iteritems(start_overrides):
                try:
                    nd.levels[ilvl].start = start_override
                except KeyError:
                    pass
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
        for an_id, style_link in iteritems(lazy_load):
            num_id = numbering_links[style_link]
            self.definitions[an_id] = self.instances[num_id].copy()

        for num_id, (an_id, n) in iteritems(next_pass):
            d = self.definitions.get(an_id, None)
            if d is not None:
                self.instances[num_id] = create_instance(n, d)

        for num_id, d in iteritems(self.instances):
            self.starts[num_id] = {lvl:d.levels[lvl].start for lvl in d.levels}

    def get_pstyle(self, num_id, style_id):
        d = self.instances.get(num_id, None)
        if d is not None:
            for ilvl, lvl in iteritems(d.levels):
                if lvl.para_link == style_id:
                    return ilvl

    def get_para_style(self, num_id, lvl):
        d = self.instances.get(num_id, None)
        if d is not None:
            lvl = d.levels.get(lvl, None)
            return getattr(lvl, 'paragraph_style', None)

    def update_counter(self, counter, levelnum, levels):
        counter[levelnum] += 1
        for ilvl, lvl in iteritems(levels):
            restart = lvl.restart
            if (restart is None and ilvl == levelnum + 1) or restart == levelnum + 1:
                counter[ilvl] = lvl.start

    def apply_markup(self, items, body, styles, object_map, images):
        seen_instances = set()
        for p, num_id, ilvl in items:
            d = self.instances.get(num_id, None)
            if d is not None:
                lvl = d.levels.get(ilvl, None)
                if lvl is not None:
                    an_id = d.abstract_numbering_definition_id
                    counter = self.counters[an_id]
                    if ilvl not in counter or num_id not in seen_instances:
                        counter[ilvl] = self.starts[num_id][ilvl]
                    seen_instances.add(num_id)
                    p.tag = 'li'
                    p.set('value', '%s' % counter[ilvl])
                    p.set('list-lvl', unicode_type(ilvl))
                    p.set('list-id', num_id)
                    if lvl.num_template is not None:
                        val = lvl.format_template(counter, ilvl, lvl.num_template)
                        p.set('list-template', val)
                    elif lvl.bullet_template is not None:
                        val = lvl.format_template(counter, ilvl, lvl.bullet_template)
                        p.set('list-template', val)
                    self.update_counter(counter, ilvl, d.levels)

        templates = {}

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
            has_template = 'list-template' in start.attrib
            wrap = (OL if lvl.is_numbered or has_template else UL)('\n\t')
            if has_template:
                wrap.set('lvlid', lvlid)
            else:
                wrap.set('class', styles.register(lvl.css(images, self.pic_map, self.rid_map), 'list'))
            ccss = lvl.char_css()
            if ccss:
                ccss = styles.register(ccss, 'bullet')
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
                    if ccss:
                        span.set('class', ccss)
                    last = templates.get(lvlid, '')
                    if span.text and len(span.text) > len(last):
                        templates[lvlid] = span.text
                    child.insert(0, span)
                for attr in ('list-lvl', 'list-id', 'list-template'):
                    child.attrib.pop(attr, None)
                val = int(child.get('value'))
                if last_val == val - 1 or wrap.tag == 'ul' or (last_val is None and val == 1):
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

        # Convert the list items that use custom text for bullets into tables
        # so that they display correctly
        for wrap in body.xpath('//ol[@lvlid]'):
            wrap.attrib.pop('lvlid')
            wrap.tag = 'div'
            wrap.set('style', 'display:table')
            for i, li in enumerate(wrap.iterchildren('li')):
                li.tag = 'div'
                li.attrib.pop('value', None)
                li.set('style', 'display:table-row')
                obj = object_map[li]
                bs = styles.para_cache[obj]
                if i == 0:
                    wrap.set('style', 'display:table; padding-left:%s' %
                             bs.css.get('margin-left', '0'))
                bs.css.pop('margin-left', None)
                for child in li:
                    child.set('style', 'display:table-cell')
