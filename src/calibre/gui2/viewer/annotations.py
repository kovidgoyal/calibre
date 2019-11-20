#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2019, Kovid Goyal <kovid at kovidgoyal.net>


from collections import defaultdict
from io import BytesIO
from operator import itemgetter

from calibre.srv.render_book import (
    EPUB_FILE_TYPE_MAGIC, parse_annotation, parse_annotations as _parse_annotations
)
from calibre.utils.serialize import json_dumps
from calibre.utils.zipfile import safe_replace
from polyglot.binary import as_base64_bytes
from polyglot.builtins import iteritems, itervalues


def parse_annotations(raw):
    return list(_parse_annotations(raw))


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
        annot = parse_annotation(annot)
        annots_map[annot.pop('type')].append(annot)
    lr = annots_map['last-read']
    if lr:
        lr.sort(key=itemgetter('timestamp'), reverse=True)
    for annot_type in ('bookmark',):
        a = annots_map.get(annot_type)
        if a and len(a) > 1:
            annots_map[annot_type] = list(merge_annots_with_identical_titles(a))


def serialize_annotation(annot):
    annot['timestamp'] = annot['timestamp'].isoformat()
    return annot


def serialize_annotations(annots_map):
    ans = []
    for atype, annots in iteritems(annots_map):
        for annot in annots:
            annot = serialize_annotation(annot.copy())
            annot['type'] = atype
            ans.append(annot)
    return json_dumps(ans)


def split_lines(chunk, length=80):
    pos = 0
    while pos < len(chunk):
        yield chunk[pos:pos+length]
        pos += length


def save_annots_to_epub(path, serialized_annots):
    try:
        zf = open(path, 'r+b')
    except IOError:
        return
    with zf:
        serialized_annots = EPUB_FILE_TYPE_MAGIC + b'\n'.join(split_lines(as_base64_bytes(serialized_annots)))
        safe_replace(zf, 'META-INF/calibre_bookmarks.txt', BytesIO(serialized_annots), add_missing=True)
