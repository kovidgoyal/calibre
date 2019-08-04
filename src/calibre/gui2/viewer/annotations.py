#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2019, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import absolute_import, division, print_function, unicode_literals

from collections import defaultdict
from operator import itemgetter

from calibre.utils.iso8601 import parse_iso8601
from calibre.utils.serialize import json_dumps, json_loads
from polyglot.builtins import iteritems, itervalues


def merge_annots_with_identical_titles(annots):
    title_groups = defaultdict(list)
    for a in annots:
        title_groups[a['title']].append(a)
    for tg in itervalues(title_groups):
        tg.sort(key=itemgetter('timestamp'), reverse=True)
    seen = set()
    for a in annots:
        title = a['title']
        if title not in seen:
            seen.add(title)
            yield title_groups[title][0]


def merge_annotations(annots, annots_map):
    for annot in annots:
        annots_map[annot.pop('type')].append(annot)
    lr = annots_map['last-read']
    if lr:
        lr.sort(key=itemgetter('timestamp'), reverse=True)
    for annot_type in ('bookmark',):
        a = annots_map.get(annot_type)
        if a and len(a) > 1:
            annots_map[annot_type] = list(merge_annots_with_identical_titles(a))


def parse_annotations(raw):
    ans = []
    for annot in json_loads(raw):
        annot['timestamp'] = parse_iso8601(annot['timestamp'], assume_utc=True)
        ans.append(annot)
    return ans


def serialize_annotations(annots_map):
    ans = []
    for atype, annots in iteritems(annots_map):
        for annot in annots:
            annot = annot.copy()
            annot['type'] = atype
            annot['timestamp'] = annot['timestamp'].isoformat()
            ans.append(annot)
    return json_dumps(ans)
