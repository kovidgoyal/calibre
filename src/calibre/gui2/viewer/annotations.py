#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2019, Kovid Goyal <kovid at kovidgoyal.net>


import os
from collections import defaultdict
from io import BytesIO
from itertools import chain
from operator import itemgetter
from threading import Thread

from calibre.ebooks.epub.cfi.parse import cfi_sort_key
from calibre.gui2.viewer.convert_book import update_book
from calibre.gui2.viewer.integration import save_annotations_list_to_library
from calibre.gui2.viewer.web_view import viewer_config_dir
from calibre.srv.render_book import (
    EPUB_FILE_TYPE_MAGIC, parse_annotation, parse_annotations as _parse_annotations
)
from calibre.utils.date import EPOCH
from calibre.utils.serialize import json_dumps
from calibre.utils.zipfile import safe_replace
from polyglot.binary import as_base64_bytes
from polyglot.builtins import iteritems, itervalues
from polyglot.queue import Queue

annotations_dir = os.path.join(viewer_config_dir, 'annots')
no_cfi_sort_key = cfi_sort_key('/99999999')


def parse_annotations(raw):
    return list(_parse_annotations(raw))


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
        tg.sort(key=itemgetter('timestamp'), reverse=True)
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


def merge_annot_lists(a, b, annot_type):
    if not a:
        return list(b)
    if not b:
        return list(a)
    if annot_type == 'last-read':
        ans = a + b
        ans.sort(key=itemgetter('timestamp'), reverse=True)
        return ans
    merge_field = {'bookmark': 'title', 'highlight': 'uuid'}.get(annot_type)
    if merge_field is None:
        return a + b
    changed, c = merge_annots_with_identical_field(a, b, merge_field)
    if changed:
        sort_annot_list_by_position_in_book(c, annot_type)
    return c


def merge_annotations(annots, annots_map):
    amap = {}
    for annot in annots:
        annot = parse_annotation(annot)
        atype = annot.pop('type')
        amap.setdefault(atype, []).append(annot)
    lr = annots_map['last-read']
    if lr:
        lr.sort(key=itemgetter('timestamp'), reverse=True)
    for annot_type, field in {'bookmark': 'title', 'highlight': 'uuid'}.items():
        a = annots_map.get(annot_type)
        if a and len(a) > 1:
            annots_map[annot_type] = list(merge_annots_with_identical_field(a, field=field))


def serialize_annotation(annot):
    annot = annot.copy()
    annot['timestamp'] = annot['timestamp'].isoformat()
    return annot


def annotations_as_copied_list(annots_map):
    for atype, annots in iteritems(annots_map):
        for annot in annots:
            ts = (annot['timestamp'] - EPOCH).total_seconds()
            annot = serialize_annotation(annot)
            annot['type'] = atype
            yield annot, ts


def annot_list_as_bytes(annots):
    return json_dumps(tuple(annot for annot, seconds in annots))


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


def save_annotations(annotations_list, annotations_path_key, bld, pathtoebook, in_book_file):
    annots = annot_list_as_bytes(annotations_list)
    with open(os.path.join(annotations_dir, annotations_path_key), 'wb') as f:
        f.write(annots)
    if in_book_file and os.access(pathtoebook, os.W_OK):
        before_stat = os.stat(pathtoebook)
        save_annots_to_epub(pathtoebook, annots)
        update_book(pathtoebook, before_stat, {'calibre-book-annotations.json': annots})
    if bld:
        save_annotations_list_to_library(bld, annotations_list)


class AnnotationsSaveWorker(Thread):

    def __init__(self):
        Thread.__init__(self, name='AnnotSaveWorker')
        self.daemon = True
        self.queue = Queue()

    def shutdown(self):
        if self.is_alive():
            self.queue.put(None)
            self.join()

    def run(self):
        while True:
            x = self.queue.get()
            if x is None:
                return
            annotations_list = x['annotations_list']
            annotations_path_key = x['annotations_path_key']
            bld = x['book_library_details']
            pathtoebook = x['pathtoebook']
            in_book_file = x['in_book_file']
            try:
                save_annotations(annotations_list, annotations_path_key, bld, pathtoebook, in_book_file)
            except Exception:
                import traceback
                traceback.print_exc()

    def save_annotations(self, current_book_data, in_book_file=True):
        alist = tuple(annotations_as_copied_list(current_book_data['annotations_map']))
        ebp = current_book_data['pathtoebook']
        can_save_in_book_file = ebp.lower().endswith('.epub')
        self.queue.put({
            'annotations_list': alist,
            'annotations_path_key': current_book_data['annotations_path_key'],
            'book_library_details': current_book_data['book_library_details'],
            'pathtoebook': current_book_data['pathtoebook'],
            'in_book_file': in_book_file and can_save_in_book_file
        })


def find_tests():
    import unittest

    def bm(title, bmid, year=20, first_cfi_number=1):
        return {
            'title': title, 'id': bmid, 'timestamp': '20{}-06-29T03:21:48.895323+00:00'.format(year),
            'pos_type': 'epubcfi', 'pos': 'epubcfi(/{}/4/8)'.format(first_cfi_number)
        }

    def hl(uuid, hlid, year=20, first_cfi_number=1):
        return {
            'uuid': uuid, 'id': hlid, 'timestamp': '20{}-06-29T03:21:48.895323+00:00'.format(year),
            'start_cfi': 'epubcfi(/{}/4/8)'.format(first_cfi_number)
        }

    class AnnotationsTest(unittest.TestCase):

        def test_merge_annotations(self):
            for atype in 'bookmark highlight'.split():
                f = bm if atype == 'bookmark' else hl
                a = [f('one', 1, 20, 2), f('two', 2, 20, 4), f('a', 3, 20, 16),]
                b = [f('one', 10, 30, 2), f('two', 20, 10, 4), f('b', 30, 20, 8),]
                c = merge_annot_lists(a, b, atype)
                self.assertEqual(tuple(map(itemgetter('id'), c)), (10, 2, 30, 3))

    return unittest.TestLoader().loadTestsFromTestCase(AnnotationsTest)
