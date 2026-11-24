#!/usr/bin/env python
# License: GPL v3 Copyright: 2018, Kovid Goyal <kovid at kovidgoyal.net>

import sys
from time import monotonic_ns
from typing import TYPE_CHECKING, Literal, TypedDict

from calibre.constants import DEBUG

if TYPE_CHECKING:
    from calibre.db.book_storage import BookStorageEntry
    from calibre.gui2.viewer.ui import EbookViewer

    class BookLibraryDetails(TypedDict):
        dbpath: str
        book_id: int
        fmt: str
        library_id: str

    class TOCNode(TypedDict, total=False):
        # A node in the Table of Contents in the book manifest
        id: int
        title: str
        dest: str | None
        frag: str | None
        children: list[TOCNode]

    class BookManifest(TypedDict, total=False):
        # The subset of the calibre-book-manifest.json data used in Python
        spine: list[str]
        toc: TOCNode
        book_format: str

    class BookMetadata(TypedDict, total=False):
        # The subset of the calibre-book-metadata.json data used in Python
        title: str
        authors: list[str]

    class LastReadData(TypedDict, total=False):
        cfi: str
        timestamp: str
        pos_frac: float

    StandaloneExtraSettings = TypedDict('StandaloneExtraSettings', {'toolbar-actions': list[str | None] | None}, total=False)

    class ViewerProfileSettings(TypedDict, total=False):
        # The subset of the keys in a viewer settings profile used in Python
        __timestamp__: str
        __standalone_extra_settings__: StandaloneExtraSettings

    class CalibreBookData(TypedDict, total=False):
        # Data passed to the viewer by calibre, see calibre.gui2.actions.view
        book_id: int
        uuid: str
        fmt: str
        library_id: str
        annotations_map: dict[str, list[dict]]
        book_storage: object

    class CurrentBookData(TypedDict, total=False):
        # Set by EbookViewer._load_ebook_worker()
        base: str
        pathtoebook: str
        open_at: str | None
        reloaded: bool
        # Set only when loading the book failed
        exception: Exception
        tb: str
        # Set by EbookViewer.load_finished() and load_book_data()
        # The annotations are JSON objects, see calibre.db.annotations
        annotations_map: dict[str, list[dict]]
        path_key: str
        annotations_path_key: str
        book_library_details: BookLibraryDetails | None
        calibre_book_id: int
        calibre_book_uuid: str
        calibre_book_fmt: str
        calibre_library_id: str
        book_storage: BookStorageEntry
        manifest: BookManifest
        metadata: BookMetadata
        pos_frac: float
        reading_rates: object


def get_current_book_data(set_val: CurrentBookData | Literal[False] = False) -> CurrentBookData:
    if set_val is not False:
        setattr(get_current_book_data, 'ans', set_val)
    empty: CurrentBookData = {}
    return getattr(get_current_book_data, 'ans', empty)


_boss: EbookViewer | None = None


def get_boss(set_val: EbookViewer | Literal[False] = False) -> EbookViewer:
    global _boss
    if set_val:
        _boss = set_val
    assert _boss is not None
    return _boss


def link_prefix_for_location_links(add_open_at: bool = True) -> str | None:
    cbd = get_current_book_data()
    link_prefix = library_id = None
    if 'calibre_library_id' in cbd:
        library_id = cbd['calibre_library_id']
        book_id = cbd['calibre_book_id']
        book_fmt = cbd['calibre_book_fmt']
    elif bld := cbd.get('book_library_details'):
        book_id = bld['book_id']
        book_fmt = bld['fmt'].upper()
        library_id = bld['library_id']
    if library_id:
        library_id = '_hex_-' + library_id.encode('utf-8').hex()
        link_prefix = f'calibre://view-book/{library_id}/{book_id}/{book_fmt}'
        if add_open_at:
            link_prefix += '?open_at='
    return link_prefix


def url_for_book_in_library() -> str | None:
    cbd = get_current_book_data()
    ans = library_id = None
    if 'calibre_library_id' in cbd:
        library_id = cbd['calibre_library_id']
        book_id = cbd['calibre_book_id']
    elif bld := cbd.get('book_library_details'):
        book_id = bld['book_id']
        library_id = bld['library_id']
    if library_id:
        library_id = '_hex_-' + library_id.encode('utf-8').hex()
        ans = f'calibre://show-book/{library_id}/{book_id}'
    return ans


class PerformanceMonitor:
    def __init__(self) -> None:
        self.start_time = monotonic_ns()

    def __call__(self, desc: str = '', reset: bool = False) -> None:
        if DEBUG:
            at = monotonic_ns()
            if reset:
                self.start_time = at
            if desc:
                ts = (at - self.start_time) / 1e9
                print(f'[{ts:.3f}] {desc}', file=sys.stderr)


performance_monitor = PerformanceMonitor()
