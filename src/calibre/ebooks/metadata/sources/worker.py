#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
# License: GPLv3 Copyright: 2012, Kovid Goyal <kovid at kovidgoyal.net>
import os
from collections import Counter
from functools import wraps
from io import BytesIO
from threading import Event, Thread
from typing import TYPE_CHECKING

from calibre.customize.ui import metadata_plugins
from calibre.ebooks.metadata.book.base import Metadata
from calibre.ebooks.metadata.opf2 import OPF, metadata_to_opf
from calibre.ebooks.metadata.sources.base import dump_caches, load_caches
from calibre.ebooks.metadata.sources.covers import download_cover, run_download
from calibre.ebooks.metadata.sources.identify import identify, msprefs
from calibre.ebooks.metadata.sources.update import patch_plugins
from calibre.utils.date import as_utc
from calibre.utils.localization import _
from calibre.utils.logging import GUILog
from polyglot.builtins import iteritems
from polyglot.queue import Empty, Queue

if TYPE_CHECKING:
    from collections.abc import Callable, Collection

    from calibre.ebooks.metadata.sources.base import CachesDump, Identifiers
    from calibre.ebooks.metadata.sources.covers import CoverResult


def merge_result(oldmi: Metadata, newmi: Metadata, ensure_fields: Collection[str] | None = None) -> Metadata:
    dummy = Metadata(_('Unknown'))
    for f in msprefs['ignore_fields']:
        if ':' in f or (ensure_fields and f in ensure_fields):
            continue
        setattr(newmi, f, getattr(dummy, f))
    fields: set[str] = set()
    for plugin in metadata_plugins(['identify']):
        fields |= plugin.touched_fields

    def is_equal(x: object, y: object) -> bool:
        return as_utc(x) == as_utc(y)

    for f in fields:
        # Optimize so that set_metadata does not have to do extra work later
        if not f.startswith('identifier:') and f not in ('series', 'series_index'):
            if not newmi.is_null(f) and is_equal(getattr(newmi, f), getattr(oldmi, f)):
                setattr(newmi, f, getattr(dummy, f))
    if (newmi.series, newmi.series_index) == (oldmi.series, oldmi.series_index):
        newmi.series = None
        newmi.series_index = 1

    return newmi


def shutdown_webengine_workers[**P, R](func: Callable[P, R]) -> Callable[P, R]:
    @wraps(func)
    def wrapper(*a: P.args, **k: P.kwargs) -> R:
        from calibre.scraper.simple import cleanup_overseers

        try:
            return func(*a, **k)
        finally:
            cleanup_overseers()()

    return wrapper


@shutdown_webengine_workers
def main(do_identify: bool, covers: bool, metadata: dict[int, bytes], ensure_fields: Collection[str] | None, tdir: str) -> tuple[set[int], set[int], bool]:
    failed_ids: set[int] = set()
    failed_covers: set[int] = set()
    all_failed = True
    log = GUILog()
    patch_plugins()

    for book_id, mi in iteritems(metadata):
        mi = OPF(BytesIO(mi), basedir=tdir, populate_spine=False).to_book_metadata()
        title, authors, identifiers = mi.title, mi.authors, mi.identifiers
        cdata = None
        log.clear()

        if do_identify:
            results = []
            try:
                results = identify(log, Event(), title=title, authors=authors, identifiers=identifiers)
            except Exception:
                pass
            if results:
                all_failed = False
                mi = merge_result(mi, results[0], ensure_fields=ensure_fields)
                identifiers = mi.identifiers
                if not mi.is_null('rating'):
                    assert mi.rating is not None
                    # set_metadata expects a rating out of 10
                    mi.rating *= 2
                with open(os.path.join(tdir, '%d.mi' % book_id), 'wb') as f:
                    f.write(metadata_to_opf(mi, default_lang='und'))
            else:
                log.error('Failed to download metadata for', title)
                failed_ids.add(book_id)

        if covers:
            cdata = download_cover(log, title=title, authors=authors, identifiers=identifiers)
            if cdata is None:
                failed_covers.add(book_id)
            else:
                with open(os.path.join(tdir, '%d.cover' % book_id), 'wb') as f:
                    f.write(cdata[-1])
                all_failed = False

        with open(os.path.join(tdir, '%d.log' % book_id), 'wb') as f:
            f.write(log.plain_text.encode('utf-8'))

    return failed_ids, failed_covers, all_failed


@shutdown_webengine_workers
def single_identify(
    title: str | None, authors: list[str] | None, identifiers: Identifiers
) -> tuple[list[bytes], list[bool], dict[str, CachesDump], list[object]]:
    log = GUILog()
    patch_plugins()
    results = identify(log, Event(), title=title, authors=authors, identifiers=identifiers)
    has_cached_cover_url: list[bool] = []
    for r in results:
        hccu = r.has_cached_cover_url
        assert isinstance(hccu, bool)  # set by identify()
        has_cached_cover_url.append(hccu)
    return [metadata_to_opf(r) for r in results], has_cached_cover_url, dump_caches(), log.dump()


@shutdown_webengine_workers
def single_covers(title: str | None, authors: list[str] | None, identifiers: Identifiers, caches: dict[str, CachesDump], tdir: str) -> list[object]:
    patch_plugins()
    load_caches(caches)
    log = GUILog()
    results: Queue[CoverResult] = Queue()
    worker = Thread(
        target=run_download,
        args=(log, results, Event()),
        kwargs=dict(title=title, authors=authors, identifiers=identifiers),
    )
    worker.daemon = True
    worker.start()
    c: Counter[str] = Counter()
    while worker.is_alive():
        try:
            plugin, width, height, fmt, data = results.get(True, 1)
        except Empty:
            continue
        else:
            name = plugin.name
            if plugin.can_get_multiple_covers:
                name += '{%d}' % c[plugin.name]
                c[plugin.name] += 1
            name = '%s,,%s,,%s,,%s.cover' % (name, width, height, fmt)
            with open(os.path.join(tdir, name), 'wb') as f:
                f.write(data)
            os.mkdir(os.path.join(tdir, name + '.done'))

    return log.dump()
