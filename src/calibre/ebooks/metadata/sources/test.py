#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
# License: GPLv3 Copyright: 2011, Kovid Goyal <kovid@kovidgoyal.net>

from __future__ import absolute_import, division, print_function, unicode_literals

import os
import sys
import tempfile
import time
from threading import Event
from typing import TYPE_CHECKING

from calibre import prints, sanitize_file_name
from calibre.customize.ui import all_metadata_plugins
from calibre.ebooks.metadata import check_isbn
from calibre.ebooks.metadata.sources.base import get_cached_cover_urls
from calibre.ebooks.metadata.sources.prefs import msprefs
from calibre.utils.logging import ANSIStream, ThreadSafeLog
from polyglot.queue import Empty, Queue

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Sequence
    from typing import TypedDict

    from calibre.ebooks.metadata.book.base import Metadata
    from calibre.ebooks.metadata.sources.base import CoverQueue, Identifiers, IdentifyQueue, Source

    class IdentifyArgs(TypedDict, total=False):
        title: str
        authors: list[str]
        identifiers: Identifiers
        timeout: float

    #: Returns True iff the Metadata object passes the test
    type MetadataTest = Callable[[Metadata], bool]
    #: (keyword arguments for identify(), tests the results must pass)
    type IdentifyTest = tuple[IdentifyArgs, Sequence[MetadataTest]]


def isbn_test(isbn: str) -> MetadataTest:
    isbn_ = check_isbn(isbn)

    def test(mi: Metadata) -> bool:
        misbn = check_isbn(mi.isbn)
        if misbn and misbn == isbn_:
            return True
        prints("ISBN test failed. Expected: '%s' found '%s'" % (isbn_, misbn))
        return False

    return test


def title_test(title: str, exact: bool = False) -> MetadataTest:

    title = title.lower()

    def test(mi: Metadata) -> bool:
        mt = mi.title.lower()
        if (exact and mt == title) or (not exact and title in mt):
            return True
        prints("Title test failed. Expected: '%s' found '%s'" % (title, mt))
        return False

    return test


def authors_test(authors: Iterable[str], subset: bool = False) -> MetadataTest:
    authors = {x.lower() for x in authors}

    def test(mi: Metadata) -> bool:
        au = {x.lower() for x in mi.authors}
        if msprefs['swap_author_names']:

            def revert_to_fn_ln(a: str) -> str:
                if ',' not in a:
                    return a
                parts = a.split(',', 1)
                t = parts[-1]
                parts = parts[:-1]
                parts.insert(0, t)
                return ' '.join(parts)

            au = {revert_to_fn_ln(x) for x in au}

        if subset and authors.issubset(au):
            return True
        if au == authors:
            return True
        prints("Author test failed. Expected: '%s' found '%s'" % (authors, au))
        return False

    return test


def tags_test(tags: Iterable[str]) -> MetadataTest:
    tags = {x.lower() for x in tags}

    def test(mi: Metadata) -> bool:
        t = {x.lower() for x in mi.tags}
        if t == tags:
            return True
        prints("Tags test failed. Expected: '%s' found '%s'" % (tags, t))
        return False

    return test


def series_test(series: str, series_index: float) -> MetadataTest:
    series = series.lower()

    def test(mi: Metadata) -> bool:
        ms = mi.series.lower() if mi.series else ''
        if (ms == series) and (series_index == mi.series_index):
            return True
        if mi.series:
            prints("Series test failed. Expected: '%s [%d]' found '%s[%d]'" % (series, series_index, ms, mi.series_index))
        else:
            prints("Series test failed. Expected: '%s [%d]' found no series" % (series, series_index))
        return False

    return test


def comments_test(sentinel: str) -> MetadataTest:

    def test(mi: Metadata) -> bool:
        comm = mi.comments.lower() if mi.comments else ''
        if sentinel and sentinel.lower() in comm:
            return True
        prints('comments test failed. %s not in comments' % sentinel)
        return False

    return test


def pubdate_test(year: int, month: int, day: int) -> MetadataTest:

    def test(mi: Metadata) -> bool:
        p = mi.pubdate
        return p is not None and p.year == year and p.month == month and p.day == day

    return test


def init_test(tdir_name: str) -> tuple[str, Event, ThreadSafeLog]:
    tdir = tempfile.gettempdir()
    abort = Event()
    log = ThreadSafeLog(level=ThreadSafeLog.DEBUG)
    log.outputs = [ANSIStream(sys.stderr)]
    return tdir, abort, log


def dump_log(lf: str) -> None:
    with open(lf, 'rb') as f:
        prints(f.read().decode('utf-8'))


def test_identify(tests: Iterable[IdentifyTest]) -> None:  # {{{
    """
    :param tests: List of 2-tuples. Each two tuple is of the form (args,
                  test_funcs). args is a dict of keyword arguments to pass to
                  the identify method. test_funcs are callables that accept a
                  Metadata object and return True iff the object passes the
                  test.
    """
    from calibre.ebooks.metadata.sources.identify import identify

    tdir, abort, log = init_test('Full Identify')

    times: list[float] = []

    for kwargs, test_funcs in tests:
        log('')
        log('#' * 80)
        log('### Running test with:', kwargs)
        log('#' * 80)
        prints('Running test with:', kwargs)
        args = (log, abort)
        start_time = time.time()
        results = identify(*args, **kwargs)
        total_time = time.time() - start_time
        times.append(total_time)
        if not results:
            prints('identify failed to find any results')
            break

        prints('Found', len(results), 'matches:', end=' ')
        prints('Smaller relevance means better match')

        for i, mi in enumerate(results):
            prints('*' * 30, 'Relevance:', i, '*' * 30)
            if mi.rating:
                mi.rating *= 2
            prints(mi)
            prints('\nCached cover URLs    :', [x[0].name for x in get_cached_cover_urls(mi)])
            prints('*' * 75, '\n\n')

        possibles: list[Metadata] = []
        for mi in results:
            test_failed = False
            for tfunc in test_funcs:
                if not tfunc(mi):
                    test_failed = True
                    break
            if not test_failed:
                possibles.append(mi)

        if not possibles:
            prints('ERROR: No results that passed all tests were found')
            log.close()
            raise SystemExit(1)

        if results[0] is not possibles[0]:
            prints('Most relevant result failed the tests')
            raise SystemExit(1)

        log('\n\n')

    prints('Average time per query', sum(times) / len(times))


# }}}


def test_identify_plugin(
    name: str,
    tests: Iterable[IdentifyTest],
    modify_plugin: Callable[[Source], object] = lambda plugin: None,  # {{{
    fail_missing_meta: bool = True,
) -> None:
    """
    :param name: Plugin name
    :param tests: List of 2-tuples. Each two tuple is of the form (args,
                  test_funcs). args is a dict of keyword arguments to pass to
                  the identify method. test_funcs are callables that accept a
                  Metadata object and return True iff the object passes the
                  test.
    """
    plugin = None
    for x in all_metadata_plugins():
        if x.name == name and 'identify' in x.capabilities:
            plugin = x
            break
    assert plugin is not None
    modify_plugin(plugin)
    prints('Testing the identify function of', plugin.name)
    prints('Using extra headers:', plugin.browser.addheaders)

    tdir, abort, log = init_test(plugin.name)

    times: list[float] = []
    for kwargs, test_funcs in tests:
        log('')
        log('#' * 80)
        log('### Running test with:', kwargs)
        log('#' * 80)
        prints('Running test with:', kwargs)
        rq: IdentifyQueue = Queue()
        args = (log, rq, abort)
        start_time = time.time()
        plugin.running_a_test = True
        try:
            err = plugin.identify(*args, **kwargs)
        finally:
            plugin.running_a_test = False
        total_time = time.time() - start_time
        times.append(total_time)
        if err is not None:
            prints('identify returned an error for args', args)
            prints(err)
            break

        results: list[Metadata] = []
        while True:
            try:
                results.append(rq.get_nowait())
            except Empty:
                break

        prints('Found', len(results), 'matches:', end=' ')
        prints('Smaller relevance means better match')

        results.sort(
            key=plugin.identify_results_keygen(
                title=kwargs.get('title', None),
                authors=kwargs.get('authors', None),
                identifiers=kwargs.get('identifiers', {}),
            )
        )

        for i, mi in enumerate(results):
            prints('*' * 30, 'Relevance:', i, '*' * 30)
            if mi.rating:
                mi.rating *= 2
            prints(mi)
            prints('\nCached cover URL    :', plugin.get_cached_cover_url(mi.identifiers))
            prints('*' * 75, '\n\n')

        possibles: list[Metadata] = []
        for mi in results:
            test_failed = False
            for tfunc in test_funcs:
                if not tfunc(mi):
                    test_failed = True
                    break
            if not test_failed:
                possibles.append(mi)

        if not possibles:
            prints('ERROR: No results that passed all tests were found')
            raise SystemExit(1)

        good = [x for x in possibles if plugin.test_fields(x) is None]
        if not good:
            prints('Failed to find', plugin.test_fields(possibles[0]))
            if fail_missing_meta:
                raise SystemExit(1)

        if results[0] is not possibles[0]:
            prints('Most relevant result failed the tests')
            raise SystemExit(1)

        if 'cover' in plugin.capabilities:
            crq: CoverQueue = Queue()
            mi = results[0]
            plugin.download_cover(log, crq, abort, title=mi.title, authors=mi.authors, identifiers=mi.identifiers)
            cover_results: list[tuple[Source, bytes]] = []
            while True:
                try:
                    cover_results.append(crq.get_nowait())
                except Empty:
                    break
            if not cover_results and fail_missing_meta:
                prints('Cover download failed')
                raise SystemExit(1)
            elif cover_results:
                cdata = cover_results[0]
                cover = os.path.join(
                    tdir,
                    plugin.name.replace(' ', '') + '-%s-cover.jpg' % sanitize_file_name(mi.title.replace(' ', '_')),
                )
                with open(cover, 'wb') as f:
                    f.write(cdata[-1])

                prints('Cover downloaded to:', cover)

                if len(cdata[-1]) < 10240:
                    prints('Downloaded cover too small')
                    raise SystemExit(1)

    prints('Average time per query', sum(times) / len(times))


# }}}
