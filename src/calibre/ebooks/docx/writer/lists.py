#!/usr/bin/env python


__license__ = 'GPL v3'
__copyright__ = '2015, Kovid Goyal <kovid at kovidgoyal.net>'

from collections import defaultdict
from operator import attrgetter

from polyglot.builtins import iteritems, itervalues

LIST_STYLES = frozenset(
    'disc circle square decimal decimal-leading-zero lower-roman upper-roman'
    ' lower-greek lower-alpha lower-latin upper-alpha upper-latin hiragana hebrew'
    ' katakana-iroha cjk-ideographic'.split())

STYLE_MAP = {
    'disc': 'bullet',
    'circle': 'o',
    'square': '\uf0a7',
    'decimal': 'decimal',
    'decimal-leading-zero': 'decimalZero',
    'lower-roman': 'lowerRoman',
    'upper-roman': 'upperRoman',
    'lower-alpha': 'lowerLetter',
    'lower-latin': 'lowerLetter',
    'upper-alpha': 'upperLetter',
    'upper-latin': 'upperLetter',
    'hiragana': 'aiueo',
    'hebrew': 'hebrew1',
    'katakana-iroha': 'iroha',
    'cjk-ideographic': 'chineseCounting',
}


def find_list_containers(list_tag, tag_style):
    node = list_tag
    stylizer = tag_style._stylizer
    ans = []
    while True:
        parent = node.getparent()
        if parent is None or parent is node:
            break
        node = parent
        style = stylizer.style(node)
        lst = (style._style.get('list-style-type', None) or '').lower()
        if lst in LIST_STYLES:
            ans.append(node)
    return ans


class NumberingDefinition:

    def __init__(self, top_most, stylizer, namespace):
        self.namespace = namespace
        self.top_most = top_most
        self.stylizer = stylizer
        self.level_map = defaultdict(list)
        self.num_id = None

    def finalize(self):
        items_for_level = defaultdict(list)
        container_for_level = {}
        type_for_level = {}
        for ilvl, items in iteritems(self.level_map):
            for container, list_tag, block, list_type, tag_style in items:
                items_for_level[ilvl].append(list_tag)
                container_for_level[ilvl] = container
                type_for_level[ilvl] = list_type
        self.levels = tuple(
            Level(type_for_level[ilvl], container_for_level[ilvl], items_for_level[ilvl], ilvl=ilvl)
            for ilvl in sorted(self.level_map)
        )

    def __hash__(self):
        return hash(self.levels)

    def link_blocks(self):
        for ilvl, items in iteritems(self.level_map):
            for container, list_tag, block, list_type, tag_style in items:
                block.numbering_id = (self.num_id + 1, ilvl)

    def serialize(self, parent):
        makeelement = self.namespace.makeelement
        an = makeelement(parent, 'w:abstractNum', w_abstractNumId=str(self.num_id))
        makeelement(an, 'w:multiLevelType', w_val='hybridMultilevel')
        makeelement(an, 'w:name', w_val='List %d' % (self.num_id + 1))
        for level in self.levels:
            level.serialize(an, makeelement)


class Level:

    def __init__(self, list_type, container, items, ilvl=0):
        self.ilvl = ilvl
        try:
            self.start = int(container.get('start'))
        except Exception:
            self.start = 1
        if items:
            try:
                self.start = int(items[0].get('value'))
            except Exception:
                pass
        if list_type in {'disc', 'circle', 'square'}:
            self.num_fmt = 'bullet'
            self.lvl_text = '\uf0b7' if list_type == 'disc' else STYLE_MAP[list_type]
        else:
            self.lvl_text = f'%{self.ilvl + 1}.'
            self.num_fmt = STYLE_MAP.get(list_type, 'decimal')

    def __hash__(self):
        return hash((self.start, self.num_fmt, self.lvl_text))

    def serialize(self, parent, makeelement):
        lvl = makeelement(parent, 'w:lvl', w_ilvl=str(self.ilvl))
        makeelement(lvl, 'w:start', w_val=str(self.start))
        makeelement(lvl, 'w:numFmt', w_val=self.num_fmt)
        makeelement(lvl, 'w:lvlText', w_val=self.lvl_text)
        makeelement(lvl, 'w:lvlJc', w_val='left')
        makeelement(makeelement(lvl, 'w:pPr'), 'w:ind', w_hanging='360', w_left=str(1152 + self.ilvl * 360))
        if self.num_fmt == 'bullet':
            ff = {'\uf0b7':'Symbol', '\uf0a7':'Wingdings'}.get(self.lvl_text, 'Courier New')
            makeelement(makeelement(lvl, 'w:rPr'), 'w:rFonts', w_ascii=ff, w_hAnsi=ff, w_hint="default")


class ListsManager:

    def __init__(self, docx):
        self.namespace = docx.namespace
        self.lists = {}

    def finalize(self, all_blocks):
        lists = {}
        for block in all_blocks:
            if block.list_tag is not None:
                list_tag, tag_style = block.list_tag
                list_type = (tag_style['list-style-type'] or '').lower()
                if list_type not in LIST_STYLES:
                    continue
                container_tags = find_list_containers(list_tag, tag_style)
                if not container_tags:
                    continue
                top_most = container_tags[-1]
                if top_most not in lists:
                    lists[top_most] = NumberingDefinition(top_most, tag_style._stylizer, self.namespace)
                l = lists[top_most]
                ilvl = len(container_tags) - 1
                l.level_map[ilvl].append((container_tags[0], list_tag, block, list_type, tag_style))

        [nd.finalize() for nd in itervalues(lists)]
        definitions = {}
        for defn in itervalues(lists):
            try:
                defn = definitions[defn]
            except KeyError:
                definitions[defn] = defn
                defn.num_id = len(definitions) - 1
            defn.link_blocks()
        self.definitions = sorted(itervalues(definitions), key=attrgetter('num_id'))

    def serialize(self, parent):
        for defn in self.definitions:
            defn.serialize(parent)
        makeelement = self.namespace.makeelement
        for defn in self.definitions:
            n = makeelement(parent, 'w:num', w_numId=str(defn.num_id + 1))
            makeelement(n, 'w:abstractNumId', w_val=str(defn.num_id))
