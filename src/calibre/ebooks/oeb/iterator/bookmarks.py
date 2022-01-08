#!/usr/bin/env python


__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os, numbers
from io import BytesIO

from calibre.utils.zipfile import safe_replace
from polyglot.builtins import as_unicode

BM_FIELD_SEP = '*|!|?|*'
BM_LEGACY_ESC = 'esc-text-%&*#%(){}ads19-end-esc'


def parse_bookmarks(raw):
    raw = as_unicode(raw)
    for line in raw.splitlines():
        if '^' in line:
            tokens = line.rpartition('^')
            title, ref = tokens[0], tokens[2]
            try:
                spine, _, pos = ref.partition('#')
                spine = int(spine.strip())
            except Exception:
                continue
            yield {'type':'legacy', 'title':title, 'spine':spine, 'pos':pos}
        elif BM_FIELD_SEP in line:
            try:
                title, spine, pos = line.strip().split(BM_FIELD_SEP)
                spine = int(spine)
            except Exception:
                continue
            # Unescape from serialization
            pos = pos.replace(BM_LEGACY_ESC, '^')
            # Check for pos being a scroll fraction
            try:
                pos = float(pos)
            except Exception:
                pass
            yield {'type':'cfi', 'title':title, 'pos':pos, 'spine':spine}


class BookmarksMixin:

    def __init__(self, copy_bookmarks_to_file=True):
        self.copy_bookmarks_to_file = copy_bookmarks_to_file

    def parse_bookmarks(self, raw):
        for bm in parse_bookmarks(raw):
            self.bookmarks.append(bm)

    def serialize_bookmarks(self, bookmarks):
        dat = []
        for bm in bookmarks:
            if bm['type'] == 'legacy':
                rec = '%s^%d#%s'%(bm['title'], bm['spine'], bm['pos'])
            else:
                pos = bm['pos']
                if isinstance(pos, numbers.Number):
                    pos = str(pos)
                else:
                    pos = pos.replace('^', BM_LEGACY_ESC)
                rec = BM_FIELD_SEP.join([bm['title'], str(bm['spine']), pos])
            dat.append(rec)
        return ('\n'.join(dat) +'\n')

    def read_bookmarks(self):
        self.bookmarks = []
        raw = self.config['bookmarks_'+self.pathtoebook] or ''
        if not raw:
            # Look for bookmarks saved inside the ebook
            bmfile = os.path.join(self.base, 'META-INF', 'calibre_bookmarks.txt')
            if os.path.exists(bmfile):
                with open(bmfile, 'rb') as f:
                    raw = f.read()
        if isinstance(raw, bytes):
            raw = raw.decode('utf-8')
        self.parse_bookmarks(raw)

    def save_bookmarks(self, bookmarks=None, no_copy_to_file=False):
        if bookmarks is None:
            bookmarks = self.bookmarks
        dat = self.serialize_bookmarks(bookmarks)
        self.config['bookmarks_'+self.pathtoebook] = dat
        if not no_copy_to_file and self.copy_bookmarks_to_file and os.path.splitext(
                self.pathtoebook)[1].lower() == '.epub' and os.access(self.pathtoebook, os.W_OK):
            try:
                with open(self.pathtoebook, 'r+b') as zf:
                    safe_replace(zf, 'META-INF/calibre_bookmarks.txt',
                            BytesIO(dat.encode('utf-8')),
                            add_missing=True)
            except OSError:
                return

    def add_bookmark(self, bm, no_copy_to_file=False):
        self.bookmarks = [x for x in self.bookmarks if x['title'] !=
                bm['title']]
        self.bookmarks.append(bm)
        self.save_bookmarks(no_copy_to_file=no_copy_to_file)

    def set_bookmarks(self, bookmarks):
        self.bookmarks = bookmarks
