#!/usr/bin/env python2
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2015, Kovid Goyal <kovid at kovidgoyal.net>'

from collections import defaultdict

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
    stylizer = tag_style.stylizer
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

class NumberingDefinition(object):

    def __init__(self):
        pass

class Level(object):

    def __init__(self, list_type, container, items, ilvl=0):
        self.ilvl = ilvl
        try:
            self.start = int(container.get('start'))
        except Exception:
            self.start = 1
        if list_type in {'disc', 'circle', 'square'}:
            self.num_fmt = 'bullet'
            self.lvl_text = '%1' if list_type == 'disc' else STYLE_MAP['list_type']
        else:
            self.lvl_text = '%1.'
            self.num_fmt = STYLE_MAP.get(list_type, 'decimal')

class ListManager(object):

    def __init__(self, docx):
        self.namespace = docx.namespace

    def finalize(self, all_blocks):
        lists = defaultdict(list)
        for block in all_blocks:
            if block.list_tag is not None:
                list_tag, tag_style = block.list_tag
                list_type = (tag_style['list-style-type'] or '').lower()
                if list_type not in LIST_STYLES:
                    continue
                container_tags = find_list_containers(list_tag, tag_style)
                if not container_tags:
                    continue
                lists[(tuple(container_tags), list_type)].append((list_tag, tag_style))
