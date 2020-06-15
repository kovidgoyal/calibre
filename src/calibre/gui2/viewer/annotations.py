#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2019, Kovid Goyal <kovid at kovidgoyal.net>


import os
from collections import defaultdict
from io import BytesIO
from operator import itemgetter
from threading import Thread

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


def parse_annotations(raw):
    return list(_parse_annotations(raw))


def merge_annots_with_identical_field(annots, field='title'):
    title_groups = defaultdict(list)
    for a in annots:
        title_groups[a[field]].append(a)
    for tg in itervalues(title_groups):
        tg.sort(key=itemgetter('timestamp'), reverse=True)
    seen = set()
    for a in annots:
        title = a[field]
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
