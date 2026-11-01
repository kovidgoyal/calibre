#!/usr/bin/env python
# License: GPLv3 Copyright: 2012, Kovid Goyal <kovid@kovidgoyal.net>

import numbers
import os
from io import BytesIO
from typing import TYPE_CHECKING, cast

from calibre.utils.zipfile import safe_replace
from polyglot.builtins import as_unicode

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator, MutableMapping
    from typing import TypedDict

    class Bookmark(TypedDict):
        type: str
        title: str
        spine: int
        pos: str | float


BM_FIELD_SEP = '*|!|?|*'
BM_LEGACY_ESC = 'esc-text-%&*#%(){}ads19-end-esc'


def parse_bookmarks(raw: str | bytes) -> Iterator[Bookmark]:
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
            yield {'type': 'legacy', 'title': title, 'spine': spine, 'pos': pos}
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
            yield {'type': 'cfi', 'title': title, 'pos': pos, 'spine': spine}


class BookmarksMixin:
    config: MutableMapping[str, object]
    pathtoebook: str
    base: str

    def __init__(self, copy_bookmarks_to_file: bool = True) -> None:
        self.copy_bookmarks_to_file = copy_bookmarks_to_file

    def parse_bookmarks(self, raw: str) -> None:
        for bm in parse_bookmarks(raw):
            self.bookmarks.append(bm)

    def serialize_bookmarks(self, bookmarks: Iterable[Bookmark]) -> str:
        dat: list[str] = []
        for bm in bookmarks:
            if bm['type'] == 'legacy':
                rec = f"{bm['title']}^{bm['spine']}#{bm['pos']}"
            else:
                pos = bm['pos']
                if isinstance(pos, numbers.Number):
                    pos = str(pos)
                else:
                    pos = pos.replace('^', BM_LEGACY_ESC)  # ty: ignore[unresolved-attribute] numbers are handled above
                rec = BM_FIELD_SEP.join([bm['title'], str(bm['spine']), pos])
            dat.append(rec)
        return '\n'.join(dat) + '\n'

    def read_bookmarks(self) -> None:
        self.bookmarks: list[Bookmark] = []
        raw = cast('str | bytes', self.config['bookmarks_' + self.pathtoebook] or '')  # stored by save_bookmarks() as str
        if not raw:
            # Look for bookmarks saved inside the ebook
            bmfile = os.path.join(self.base, 'META-INF', 'calibre_bookmarks.txt')
            if os.path.exists(bmfile):
                with open(bmfile, 'rb') as f:
                    raw = f.read()
        if isinstance(raw, bytes):
            raw = raw.decode('utf-8')
        self.parse_bookmarks(raw)

    def save_bookmarks(self, bookmarks: list[Bookmark] | None = None, no_copy_to_file: bool = False) -> None:
        if bookmarks is None:
            bookmarks = self.bookmarks
        dat = self.serialize_bookmarks(bookmarks)
        self.config['bookmarks_' + self.pathtoebook] = dat
        if (
            not no_copy_to_file
            and self.copy_bookmarks_to_file
            and os.path.splitext(self.pathtoebook)[1].lower() == '.epub'
            and os.access(self.pathtoebook, os.W_OK)
        ):
            try:
                safe_replace(self.pathtoebook, 'META-INF/calibre_bookmarks.txt', BytesIO(dat.encode('utf-8')), add_missing=True)
            except OSError:
                return

    def add_bookmark(self, bm: Bookmark, no_copy_to_file: bool = False) -> None:
        self.bookmarks = [x for x in self.bookmarks if x['title'] != bm['title']]
        self.bookmarks.append(bm)
        self.save_bookmarks(no_copy_to_file=no_copy_to_file)

    def set_bookmarks(self, bookmarks: list[Bookmark]) -> None:

        self.bookmarks = bookmarks
