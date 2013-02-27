#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os, tempfile, time
from Queue import Queue, Empty
from threading import Event

from calibre.customize.ui import all_metadata_plugins
from calibre import prints, sanitize_file_name2
from calibre.ebooks.metadata import check_isbn
from calibre.ebooks.metadata.sources.base import (create_log,
        get_cached_cover_urls, msprefs)

def isbn_test(isbn):
    isbn_ = check_isbn(isbn)

    def test(mi):
        misbn = check_isbn(mi.isbn)
        if misbn and misbn == isbn_:
            return True
        prints('ISBN test failed. Expected: \'%s\' found \'%s\''%(isbn_, misbn))
        return False

    return test

def title_test(title, exact=False):

    title = title.lower()

    def test(mi):
        mt = mi.title.lower()
        if (exact and mt == title) or \
                (not exact and title in mt):
            return True
        prints('Title test failed. Expected: \'%s\' found \'%s\''%(title, mt))
        return False

    return test

def authors_test(authors):
    authors = set([x.lower() for x in authors])

    def test(mi):
        au = set([x.lower() for x in mi.authors])
        if msprefs['swap_author_names']:
            def revert_to_fn_ln(a):
                if ',' not in a:
                    return a
                parts = a.split(',', 1)
                t = parts[-1]
                parts = parts[:-1]
                parts.insert(0, t)
                return ' '.join(parts)

            au = set([revert_to_fn_ln(x) for x in au])

        if au == authors:
            return True
        prints('Author test failed. Expected: \'%s\' found \'%s\''%(authors, au))
        return False

    return test

def series_test(series, series_index):
    series = series.lower()

    def test(mi):
        ms = mi.series.lower() if mi.series else ''
        if (ms == series) and (series_index == mi.series_index):
            return True
        if mi.series:
            prints('Series test failed. Expected: \'%s [%d]\' found \'%s[%d]\''% \
                        (series, series_index, ms, mi.series_index))
        else:
            prints('Series test failed. Expected: \'%s [%d]\' found no series'% \
                        (series, series_index))
        return False

    return test

def comments_test(sentinel):

    def test(mi):
        comm = mi.comments.lower() if mi.comments else ''
        if sentinel and sentinel.lower() in comm:
            return True
        prints('comments test failed. %s not in comments'%sentinel)
        return False
    return test

def pubdate_test(year, month, day):

    def test(mi):
        p = mi.pubdate
        if p is not None and p.year == year and p.month == month and p.day == day:
            return True
        return False

    return test

def init_test(tdir_name):
    tdir = tempfile.gettempdir()
    lf = os.path.join(tdir, tdir_name.replace(' ', '')+'_identify_test.txt')
    log = create_log(open(lf, 'wb'))
    abort = Event()
    return tdir, lf, log, abort

def test_identify(tests): # {{{
    '''
    :param tests: List of 2-tuples. Each two tuple is of the form (args,
                  test_funcs). args is a dict of keyword arguments to pass to
                  the identify method. test_funcs are callables that accept a
                  Metadata object and return True iff the object passes the
                  test.
    '''
    from calibre.ebooks.metadata.sources.identify import identify

    tdir, lf, log, abort = init_test('Full Identify')
    prints('Log saved to', lf)

    times = []

    for kwargs, test_funcs in tests:
        log('#'*80)
        log('### Running test with:', kwargs)
        log('#'*80)
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
            prints('*'*30, 'Relevance:', i, '*'*30)
            prints(mi)
            prints('\nCached cover URLs    :',
                    [x[0].name for x in get_cached_cover_urls(mi)])
            prints('*'*75, '\n\n')

        possibles = []
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
            prints('Log saved to', lf)
            raise SystemExit(1)

        if results[0] is not possibles[0]:
            prints('Most relevant result failed the tests')
            raise SystemExit(1)

        log('\n\n')

    prints('Average time per query', sum(times)/len(times))

    prints('Full log is at:', lf)

# }}}

def test_identify_plugin(name, tests, modify_plugin=lambda plugin:None,
        fail_missing_meta=True): # {{{
    '''
    :param name: Plugin name
    :param tests: List of 2-tuples. Each two tuple is of the form (args,
                  test_funcs). args is a dict of keyword arguments to pass to
                  the identify method. test_funcs are callables that accept a
                  Metadata object and return True iff the object passes the
                  test.
    '''
    plugin = None
    for x in all_metadata_plugins():
        if x.name == name and 'identify' in x.capabilities:
            plugin = x
            break
    modify_plugin(plugin)
    prints('Testing the identify function of', plugin.name)
    prints('Using extra headers:', plugin.browser.addheaders)

    tdir, lf, log, abort = init_test(plugin.name)
    prints('Log saved to', lf)

    times = []
    for kwargs, test_funcs in tests:
        prints('Running test with:', kwargs)
        rq = Queue()
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

        results = []
        while True:
            try:
                results.append(rq.get_nowait())
            except Empty:
                break

        prints('Found', len(results), 'matches:', end=' ')
        prints('Smaller relevance means better match')

        results.sort(key=plugin.identify_results_keygen(
            title=kwargs.get('title', None), authors=kwargs.get('authors',
                None), identifiers=kwargs.get('identifiers', {})))

        for i, mi in enumerate(results):
            prints('*'*30, 'Relevance:', i, '*'*30)
            prints(mi)
            prints('\nCached cover URL    :',
                    plugin.get_cached_cover_url(mi.identifiers))
            prints('*'*75, '\n\n')

        possibles = []
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
            prints('Log saved to', lf)
            raise SystemExit(1)

        good = [x for x in possibles if plugin.test_fields(x) is
                None]
        if not good:
            prints('Failed to find', plugin.test_fields(possibles[0]))
            if fail_missing_meta:
                raise SystemExit(1)

        if results[0] is not possibles[0]:
            prints('Most relevant result failed the tests')
            raise SystemExit(1)

        if 'cover' in plugin.capabilities:
            rq = Queue()
            mi = results[0]
            plugin.download_cover(log, rq, abort, title=mi.title,
                    authors=mi.authors, identifiers=mi.identifiers)
            results = []
            while True:
                try:
                    results.append(rq.get_nowait())
                except Empty:
                    break
            if not results and fail_missing_meta:
                prints('Cover download failed')
                raise SystemExit(1)
            elif results:
                cdata = results[0]
                cover = os.path.join(tdir, plugin.name.replace(' ',
                    '')+'-%s-cover.jpg'%sanitize_file_name2(mi.title.replace(' ',
                        '_')))
                with open(cover, 'wb') as f:
                    f.write(cdata[-1])

                prints('Cover downloaded to:', cover)

                if len(cdata[-1]) < 10240:
                    prints('Downloaded cover too small')
                    raise SystemExit(1)

    prints('Average time per query', sum(times)/len(times))

    if os.stat(lf).st_size > 10:
        prints('There were some errors/warnings, see log', lf)
# }}}

