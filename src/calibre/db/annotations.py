#!/usr/bin/env python
# License: GPL v3 Copyright: 2020, Kovid Goyal <kovid at kovidgoyal.net>

import sys
from collections import defaultdict
from collections.abc import Callable
from itertools import chain
from typing import Self
from urllib.parse import quote

from calibre.ebooks.epub.cfi.parse import cfi_sort_key
from calibre.utils.date import EPOCH, format_date
from calibre.utils.iso8601 import parse_iso8601
from calibre.utils.localization import _

no_cfi = '/99999999'
no_cfi_sort_key = cfi_sort_key(no_cfi)


def unicode_normalize(text):
    if text:
        from unicodedata import normalize

        text = normalize('NFKC', text)
    return text


def bookmark_sort_key(b):
    if b.get('pos_type') == 'epubcfi' and (pos := b.get('pos')):
        return cfi_sort_key(pos, only_path=False)
    return no_cfi_sort_key


def highlight_sort_key(hl):
    cfi = hl.get('start_cfi')
    if cfi:
        if cfi.startswith('epubcfi('):
            return cfi_sort_key(cfi, only_path=False)
        # The CFI of a highlight is relative to its spine item, so prefix the
        # spine index, as is done in the viewer
        si = hl.get('spine_index')
        return cfi_sort_key((no_cfi if si is None else f'/{si}') + cfi)
    return no_cfi_sort_key


def annotations_as_copied_list(annots_map):
    for atype, annots in annots_map.items():
        for annot in annots:
            ts = (parse_iso8601(annot['timestamp'], assume_utc=True) - EPOCH).total_seconds()
            annot = annot.copy()
            annot['type'] = atype
            yield annot, ts


def sort_annot_list_by_position_in_book(annots, annot_type):
    annots.sort(key={'bookmark': bookmark_sort_key, 'highlight': highlight_sort_key}[annot_type])


def merge_annots_with_identical_field(a, b, field='title'):
    title_groups = defaultdict(list)
    for x in chain(a, b):
        title_groups[x[field]].append(x)
    for tg in title_groups.values():
        tg.sort(key=safe_timestamp_sort_key, reverse=True)
    seen = set()
    changed = False
    ans = []
    for x in chain(a, b):
        title = x[field]
        if title not in seen:
            seen.add(title)
            grp = title_groups[title]
            if len(grp) > 1 and grp[0]['timestamp'] != grp[1]['timestamp']:
                changed = True
            ans.append(grp[0])
    if len(ans) != len(a) or len(ans) != len(b):
        changed = True
    return changed, ans


merge_field_map = {'bookmark': 'title', 'highlight': 'uuid'}


def merge_annot_lists(a, b, annot_type):
    if not a:
        return list(b)
    if not b:
        return list(a)
    if annot_type == 'last-read':
        ans = a + b
        ans.sort(key=safe_timestamp_sort_key, reverse=True)
        return ans
    merge_field = merge_field_map.get(annot_type)
    if merge_field is None:
        return a + b
    changed, c = merge_annots_with_identical_field(a, b, merge_field)
    if changed:
        sort_annot_list_by_position_in_book(c, annot_type)
    return c


def safe_timestamp_sort_key(x):
    # ensure we return a string, so python 3 does not barf
    # also if the timestamp is a datetime instance convert it to
    # a string, since we expect it to always be a string
    ans = x.get('timestamp')
    if hasattr(ans, 'isoformat'):
        ans = x['timestamp'] = ans.isoformat()
    if not isinstance(ans, str):
        try:
            ans = str(ans)
        except Exception:
            ans = 'zzzz'
    return ans


def merge_annotations(annots, annots_map, merge_last_read=True):
    # If you make changes to this algorithm also update the
    # implementation in read_book.annotations
    if isinstance(annots, dict):
        amap = annots
    else:
        amap = defaultdict(list)
        for annot in annots:
            amap[annot['type']].append(annot)

    if merge_last_read:
        lr = amap.get('last-read')
        if lr:
            existing = annots_map.get('last-read')
            if existing:
                lr = existing + lr
            if lr:
                lr.sort(key=safe_timestamp_sort_key, reverse=True)
                annots_map['last-read'] = [lr[0]]

    for annot_type, field in merge_field_map.items():
        a = annots_map.get(annot_type)
        b = amap.get(annot_type)
        if not b:
            continue
        changed, annots_map[annot_type] = merge_annots_with_identical_field(a or [], b, field=field)


def annot_db_data(annot):
    aid = text = None
    atype = annot['type'].lower()
    if atype == 'bookmark':
        aid = text = annot['title']
    elif atype == 'highlight':
        aid = annot['uuid']
        text = annot.get('highlighted_text') or ''
        notes = annot.get('notes') or ''
        if notes:
            text += '\n\x1f\n' + notes
    return aid, unicode_normalize(text)


# Rendering as text {{{


def format_annotation_timestamp(ts: str) -> str:
    "Format the ISO 8601 timestamp of an annotation in the local timezone"
    try:
        return format_date(parse_iso8601(ts, assume_utc=True), 'yyyy-MM-dd hh:mm')
    except ValueError as err:
        print(f'Invalid annotation timestamp: {ts!r} with error: {err}', file=sys.stderr)
        return ts


def render_highlight_as_text(
    hl: dict, lines: list[str], render_timestamp: Callable[[str], str], as_markdown: bool = False, link_prefix: str | None = None
) -> None:
    lines.append(hl['highlighted_text'])
    date = render_timestamp(hl['timestamp'])
    if as_markdown and link_prefix:
        cfi = hl['start_cfi']
        spine_index = (1 + hl['spine_index']) * 2
        link = (link_prefix + quote(f'epubcfi(/{spine_index}{cfi})')).replace(')', '%29')
        date = f'[{date}]({link})'
    if as_markdown:
        date = f'*{date}*'
    lines.append(date)
    notes = hl.get('notes')
    if notes:
        lines.append('')
        lines.append(notes)
    lines.append('')
    if as_markdown:
        lines.append('-' * 20)
    else:
        lines.append('───')
    lines.append('')


def render_bookmark_as_text(
    b: dict, lines: list[str], render_timestamp: Callable[[str], str], as_markdown: bool = False, link_prefix: str | None = None
) -> None:
    lines.append(b['title'])
    date = render_timestamp(b['timestamp'])
    if as_markdown and link_prefix and b['pos_type'] == 'epubcfi':
        link = (link_prefix + quote(b['pos'])).replace(')', '%29')
        date = f'[{date}]({link})'
    lines.append(date)
    lines.append('')
    if as_markdown:
        lines.append('-' * 20)
    else:
        lines.append('───')
    lines.append('')


class ChapterGroup:
    "Group annotations by the chapters they are in, for export"

    def __init__(self, title: str = '', level: int = 0):
        self.title = title
        self.subgroups: dict[str, Self] = {}
        self.annotations: list[dict] = []
        self.level = level

    def render_timestamp(self, ts: str) -> str:
        return format_annotation_timestamp(ts)

    def add_annot(self, a: dict) -> None:
        titles = a.get('toc_family_titles', (_('Unknown chapter'),))
        node = self
        for title in titles:
            node = node.group_for_title(title)
        node.annotations.append(a)

    def group_for_title(self, title: str) -> Self:
        ans = self.subgroups.get(title)
        if ans is None:
            ans = self.__class__(title, self.level + 1)
            self.subgroups[title] = ans
        return ans

    def render_as_text(self, lines: list[str], as_markdown: bool, link_prefix: str | None) -> None:
        if self.title:
            lines.append('#' * self.level + ' ' + self.title)
            lines.append('')
        for hl in self.annotations:
            atype = hl.get('type', 'highlight')
            if atype == 'bookmark':
                render_bookmark_as_text(hl, lines, self.render_timestamp, as_markdown=as_markdown, link_prefix=link_prefix)
            else:
                render_highlight_as_text(hl, lines, self.render_timestamp, as_markdown=as_markdown, link_prefix=link_prefix)
        for sg in self.subgroups.values():
            sg.render_as_text(lines, as_markdown, link_prefix)


# }}}
