#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2020, Kovid Goyal <kovid at kovidgoyal.net>

from collections import defaultdict
from itertools import chain

from calibre.ebooks.epub.cfi.parse import cfi_sort_key
from polyglot.builtins import itervalues

no_cfi_sort_key = cfi_sort_key('/99999999')


def bookmark_sort_key(b):
    if b.get('pos_type') == 'epubcfi':
        return cfi_sort_key(b['pos'], only_path=False)
    return no_cfi_sort_key


def highlight_sort_key(hl):
    cfi = hl.get('start_cfi')
    if cfi:
        return cfi_sort_key(cfi, only_path=False)
    return no_cfi_sort_key


def sort_annot_list_by_position_in_book(annots, annot_type):
    annots.sort(key={'bookmark': bookmark_sort_key, 'highlight': highlight_sort_key}[annot_type])


def merge_annots_with_identical_field(a, b, field='title'):
    title_groups = defaultdict(list)
    for x in chain(a, b):
        title_groups[x[field]].append(x)
    for tg in itervalues(title_groups):
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
    return aid, text
