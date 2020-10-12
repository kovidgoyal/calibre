#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2019, Kovid Goyal <kovid at kovidgoyal.net>


import os
from io import BytesIO
from operator import itemgetter
from threading import Thread

from calibre.db.annotations import merge_annot_lists
from calibre.gui2.viewer.convert_book import update_book
from calibre.gui2.viewer.integration import save_annotations_list_to_library
from calibre.gui2.viewer.web_view import viewer_config_dir
from calibre.srv.render_book import EPUB_FILE_TYPE_MAGIC
from calibre.utils.date import EPOCH
from calibre.utils.iso8601 import parse_iso8601
from calibre.utils.serialize import json_dumps, json_loads
from calibre.utils.zipfile import safe_replace
from polyglot.binary import as_base64_bytes
from polyglot.builtins import iteritems
from polyglot.queue import Queue

annotations_dir = os.path.join(viewer_config_dir, 'annots')
parse_annotations = json_loads


def annotations_as_copied_list(annots_map):
    for atype, annots in iteritems(annots_map):
        for annot in annots:
            ts = (parse_iso8601(annot['timestamp'], assume_utc=True) - EPOCH).total_seconds()
            annot = annot.copy()
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


def save_annotations(annotations_list, annotations_path_key, bld, pathtoebook, in_book_file, sync_annots_user):
    annots = annot_list_as_bytes(annotations_list)
    with open(os.path.join(annotations_dir, annotations_path_key), 'wb') as f:
        f.write(annots)
    if in_book_file and os.access(pathtoebook, os.W_OK):
        before_stat = os.stat(pathtoebook)
        save_annots_to_epub(pathtoebook, annots)
        update_book(pathtoebook, before_stat, {'calibre-book-annotations.json': annots})
    if bld:
        save_annotations_list_to_library(bld, annotations_list, sync_annots_user)


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
            sync_annots_user = x['sync_annots_user']
            try:
                save_annotations(annotations_list, annotations_path_key, bld, pathtoebook, in_book_file, sync_annots_user)
            except Exception:
                import traceback
                traceback.print_exc()

    def save_annotations(self, current_book_data, in_book_file=True, sync_annots_user=''):
        alist = tuple(annotations_as_copied_list(current_book_data['annotations_map']))
        ebp = current_book_data['pathtoebook']
        can_save_in_book_file = ebp.lower().endswith('.epub')
        self.queue.put({
            'annotations_list': alist,
            'annotations_path_key': current_book_data['annotations_path_key'],
            'book_library_details': current_book_data['book_library_details'],
            'pathtoebook': current_book_data['pathtoebook'],
            'in_book_file': in_book_file and can_save_in_book_file,
            'sync_annots_user': sync_annots_user,
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
