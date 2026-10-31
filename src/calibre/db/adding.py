#!/usr/bin/env python
# License: GPLv3 Copyright: 2013, Kovid Goyal <kovid at kovidgoyal.net>

import os
import re
import time
from collections import defaultdict
from contextlib import contextmanager, suppress
from functools import partial
from typing import TYPE_CHECKING

from calibre import prints
from calibre.constants import filesystem_encoding, ismacos, iswindows
from calibre.ebooks import BOOK_EXTENSIONS
from calibre.utils import StreamOrPath
from calibre.utils.filenames import make_long_path_useable
from calibre.utils.icu import lower as icu_lower
from calibre.utils.localization import _

if TYPE_CHECKING:
    from collections.abc import Callable, Generator, Iterable, Iterator, Mapping, Sequence, Sized
    from typing import IO, TypedDict

    from calibre.db.cache import Cache
    from calibre.db.legacy import LibraryDatabase
    from calibre.ebooks.metadata.book.base import Metadata

    #: A compiled filename filter rule: (filename matcher, whether matching files are added)
    type CompiledRule = tuple[Callable[[str], bool], bool]
    type CompiledRules = Iterable[CompiledRule]
    #: Books that were not added because they are duplicates: (metadata, list of format paths)
    type Duplicates = list[tuple[Metadata, list[str]]]

    class ImportContext(TypedDict):
        tdir: str
        group_id: int
        format_map: dict[str, str]


def splitext(path: str) -> tuple[str, str]:
    key, ext = os.path.splitext(path)
    return key, ext[1:].lower()


def formats_ok(formats: Sized) -> bool:
    return len(formats) > 0


def path_ok(path: str) -> bool:
    return not os.path.isdir(path) and os.access(path, os.R_OK)


def compile_glob(pat: str) -> re.Pattern[str]:
    import fnmatch

    return re.compile(fnmatch.translate(pat), flags=re.I)


def compile_rule(rule: Mapping[str, str]) -> CompiledRule:
    mt = rule['match_type']
    if 'with' in mt:
        q = icu_lower(rule['query'])
        if 'startswith' in mt:

            def func(filename: str) -> bool:
                return icu_lower(filename).startswith(q)  # ty: ignore[invalid-argument-type]

        else:

            def func(filename: str) -> bool:
                return icu_lower(filename).endswith(q)  # ty: ignore[invalid-argument-type]

    elif 'glob' in mt:
        q = compile_glob(rule['query'])

        def func(filename: str) -> bool:
            return q.match(filename) is not None

    else:
        q = re.compile(rule['query'])

        def func(filename: str) -> bool:
            return q.match(filename) is not None

    ans = func
    if mt.startswith('not_'):

        def ans(filename: str) -> bool:
            return not func(filename)

    return ans, rule['action'] == 'add'


def filter_filename(compiled_rules: CompiledRules, filename: str) -> bool | None:
    for q, action in compiled_rules:
        if q(filename):
            return action


_metadata_extensions: frozenset[str] | None = None


def metadata_extensions() -> frozenset[str]:
    # Set of all known book extensions + OPF (the OPF is used to read metadata,
    # but not actually added)
    global _metadata_extensions
    if _metadata_extensions is None:
        _metadata_extensions = frozenset(BOOK_EXTENSIONS) | {'opf'}
    return _metadata_extensions


if iswindows or ismacos:
    unicode_listdir = os.listdir
else:

    def unicode_listdir(root: str) -> Iterator[str]:
        root = root.encode(filesystem_encoding)  # ty: ignore[invalid-assignment]
        for x in os.listdir(root):
            try:
                yield x.decode(filesystem_encoding)  # ty: ignore[unresolved-attribute]
            except UnicodeDecodeError:
                prints('Ignoring un-decodable file:', x)


def listdir(root: str, sort_by_mtime: bool = False) -> Iterator[str]:
    items = (make_long_path_useable(os.path.join(root, x)) for x in unicode_listdir(root))
    if sort_by_mtime:

        def safe_mtime(x: str) -> float:
            try:
                return os.path.getmtime(x)
            except OSError:
                return time.time()

        items = sorted(items, key=safe_mtime)

    for path in items:
        if path_ok(path):
            yield path


def list_only_files_in_dir(root: str, sort_by_mtime: bool = False) -> Iterator[str]:
    def files_iter() -> Iterator[os.DirEntry[str]]:
        for x in os.scandir(root):
            with suppress(OSError):
                if x.is_file(follow_symlinks=True):
                    yield x

    items = files_iter()
    if sort_by_mtime:

        def safe_mtime(x: os.DirEntry) -> int:
            with suppress(OSError):
                return x.stat(follow_symlinks=True).st_mtime_ns
            return 0

        items = sorted(items, key=safe_mtime)
    yield from (make_long_path_useable(os.path.join(root, x.name)) for x in items)


def allow_path(path: str, ext: str, compiled_rules: CompiledRules) -> bool:
    ans = filter_filename(compiled_rules, os.path.basename(path))
    if ans is None:
        ans = ext in metadata_extensions()
    return ans


import_ctx: ImportContext | None = None


@contextmanager
def run_import_plugins_before_metadata(tdir: str, group_id: int = 0) -> Generator[ImportContext]:
    global import_ctx
    import_ctx = {'tdir': tdir, 'group_id': group_id, 'format_map': {}}
    yield import_ctx
    import_ctx = None


def run_import_plugins(formats: Sequence[str]) -> list[str]:
    from calibre.ebooks.metadata.worker import run_import_plugins

    assert import_ctx is not None
    import_ctx['group_id'] += 1
    ans = run_import_plugins(formats, import_ctx['group_id'], import_ctx['tdir'])
    fm = import_ctx['format_map']
    for old_path, new_path in zip(formats, ans):
        new_path = make_long_path_useable(new_path)
        fm[new_path] = old_path
    return ans


def find_books_in_directory(
    dirpath: str,
    single_book_per_directory: bool,
    compiled_rules: CompiledRules = (),
    listdir_impl: Callable[..., Iterable[str]] = list_only_files_in_dir,
) -> Iterator[list[str]]:
    dirpath = make_long_path_useable(os.path.abspath(dirpath))
    if single_book_per_directory:
        formats: dict[str, str] = {}
        for path in listdir_impl(dirpath):
            key, ext = splitext(path)
            if allow_path(path, ext, compiled_rules):
                formats[ext] = path
        if formats_ok(formats):
            yield list(formats.values())
    else:
        books: defaultdict[str, dict[str, str]] = defaultdict(dict)
        for path in listdir_impl(dirpath, sort_by_mtime=True):
            key, ext = splitext(path)
            if allow_path(path, ext, compiled_rules):
                books[icu_lower(key) if isinstance(key, str) else key.lower()][ext] = path

        for formats in books.values():
            if formats_ok(formats):
                yield list(formats.values())


def create_format_map(formats: Iterable[str]) -> dict[str, str]:
    format_map: dict[str, str] = {}
    for path in formats:
        ext = os.path.splitext(path)[1][1:].upper()
        if ext == 'OPF':
            continue
        format_map[ext] = path
    return format_map


def import_book_directory_multiple(
    db: LibraryDatabase,
    dirpath: str,
    callback: Callable[[str], object] | None = None,
    added_ids: set[int] | None = None,
    compiled_rules: CompiledRules = (),
    add_duplicates: bool = False,
) -> Duplicates:
    from calibre.ebooks.metadata.meta import metadata_from_formats

    duplicates: Duplicates = []
    for formats in find_books_in_directory(dirpath, False, compiled_rules=compiled_rules):
        mi = metadata_from_formats(formats)
        if mi.title is None:
            continue
        ids, dups = db.new_api.add_books([(mi, create_format_map(formats))], add_duplicates=add_duplicates)
        if dups:
            duplicates.append((mi, formats))
            continue
        book_id = next(iter(ids))
        if added_ids is not None:
            added_ids.add(book_id)
        if callable(callback):
            if callback(mi.title):
                break
    return duplicates


def import_book_directory(
    db: LibraryDatabase,
    dirpath: str,
    callback: Callable[[str], object] | None = None,
    added_ids: set[int] | None = None,
    compiled_rules: CompiledRules = (),
    add_duplicates: bool = False,
) -> Duplicates | None:
    from calibre.ebooks.metadata.meta import metadata_from_formats

    dirpath = os.path.abspath(dirpath)
    formats = None
    for formats in find_books_in_directory(dirpath, True, compiled_rules=compiled_rules):
        break
    if not formats:
        return
    mi = metadata_from_formats(formats)
    if mi.title is None:
        return
    ids, dups = db.new_api.add_books([(mi, create_format_map(formats))], add_duplicates=add_duplicates)
    if dups:
        return [(mi, formats)]
    book_id = next(iter(ids))
    if added_ids is not None:
        added_ids.add(book_id)
    if callable(callback):
        callback(mi.title)


def recursive_import(
    db: LibraryDatabase,
    root: str,
    single_book_per_directory: bool = True,
    callback: Callable[[str], object] | None = None,
    added_ids: set[int] | None = None,
    compiled_rules: CompiledRules = (),
    add_duplicates: bool = False,
) -> Duplicates:
    root = os.path.abspath(root)
    duplicates: Duplicates = []
    for dirpath in os.walk(root):
        func = import_book_directory if single_book_per_directory else import_book_directory_multiple
        res = func(
            db,
            dirpath[0],
            callback=callback,
            added_ids=added_ids,
            compiled_rules=compiled_rules,
            add_duplicates=add_duplicates,
        )
        if res is not None:
            duplicates.extend(res)
        if callable(callback):
            if callback(''):
                break
    return duplicates


def cdb_find_in_dir(dirpath: str, single_book_per_directory: bool, compiled_rules: CompiledRules) -> Iterator[list[str]]:
    return find_books_in_directory(
        dirpath,
        single_book_per_directory=single_book_per_directory,
        compiled_rules=compiled_rules,
        listdir_impl=partial(list_only_files_in_dir, sort_by_mtime=True),
    )


def cdb_recursive_find(root: str, single_book_per_directory: bool = True, compiled_rules: CompiledRules = ()) -> Iterator[list[str]]:
    root = os.path.abspath(root)
    for dirpath in os.walk(root):
        yield from cdb_find_in_dir(dirpath[0], single_book_per_directory, compiled_rules)


def add_catalog(cache: Cache, path: str, title: str, dbapi: LibraryDatabase | None = None) -> tuple[int | None, bool]:
    from calibre.ebooks.metadata.book.base import Metadata
    from calibre.ebooks.metadata.meta import get_metadata
    from calibre.utils.date import utcnow

    fmt = os.path.splitext(path)[1][1:].lower()
    new_book_added = False
    with open(path, 'rb') as stream:
        with cache.write_lock:
            matches = cache._search('title:="{}" and tags:="{}"'.format(title.replace('"', '\\"'), _('Catalog')), None)
            db_id = None
            if matches:
                db_id = list(matches)[0]
            try:
                mi = get_metadata(stream, fmt)
                mi.authors = ['calibre']
            except Exception:
                mi = Metadata(title, ['calibre'])
            mi.title, mi.authors = title, ['calibre']
            mi.author_sort = 'calibre'  # The MOBI/AZW3 format sets author sort to date
            mi.pubdate = mi.timestamp = utcnow()
            if fmt == 'mobi':
                mi.cover, mi.cover_data = None, (None, None)
            if db_id is None:
                mi.tags = [_('Catalog')]
                db_id = cache._create_book_entry(mi, apply_import_tags=False)
                new_book_added = True
            else:
                tags: list[str] = list(cache._field_for('tags', db_id) or ())
                if _('Catalog') not in tags:
                    tags.append(_('Catalog'))
                mi.tags = tags
                cache._set_metadata(db_id, mi)
        cache.add_format(db_id, fmt, stream, dbapi=dbapi)  # Can't keep write lock since post-import hooks might run

    return db_id, new_book_added


def add_news(cache: Cache, path: str | IO[bytes], arg: Mapping[str, object], dbapi: LibraryDatabase | None = None) -> int | None:
    from calibre.ebooks.metadata.meta import get_metadata
    from calibre.utils.date import utcnow

    fmt = os.path.splitext(getattr(path, 'name', path))[1][1:].lower()  # ty: ignore[no-matching-overload]
    with StreamOrPath(path, 'rb') as stream:
        stream.seek(0)
        mi = get_metadata(stream, fmt, use_libprs_metadata=False, force_read_metadata=True)
        # Force the author to calibre as the auto delete of old news checks for
        # both the author==calibre and the tag News
        mi.authors = ['calibre']
        stream.seek(0)
        with cache.write_lock:
            if mi.series_index is None:
                mi.series_index = cache._get_next_series_num_for(mi.series)
            mi.tags = [_('News')]
            if arg.get('add_title_tag'):
                mi.tags += [arg['title']]  # ty: ignore[unsupported-operator]
            if arg.get('custom_tags'):
                mi.tags += arg['custom_tags']  # ty: ignore[unsupported-operator]
            if mi.pubdate is None:
                mi.pubdate = utcnow()
            if mi.timestamp is None:
                mi.timestamp = utcnow()

            db_id = cache._create_book_entry(mi, apply_import_tags=False)
        cache.add_format(db_id, fmt, stream, dbapi=dbapi)  # Can't keep write lock since post-import hooks might run
        return db_id
