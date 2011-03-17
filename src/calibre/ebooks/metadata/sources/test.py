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


from calibre.customize.ui import metadata_plugins
from calibre import prints
from calibre.ebooks.metadata import check_isbn
from calibre.ebooks.metadata.sources.base import create_log

def isbn_test(isbn):
    isbn_ = check_isbn(isbn)

    def test(mi):
        misbn = check_isbn(mi.isbn)
        return misbn and misbn == isbn_

    return test

def title_test(title, exact=False):

    title = title.lower()

    def test(mi):
        mt = mi.title.lower()
        return (exact and mt == title) or \
                (not exact and title in mt)

    return test

def test_identify_plugin(name, tests):
    '''
    :param name: Plugin name
    :param tests: List of 2-tuples. Each two tuple is of the form (args,
                  test_funcs). args is a dict of keyword arguments to pass to
                  the identify method. test_funcs are callables that accept a
                  Metadata object and return True iff the object passes the
                  test.
    '''
    plugin = None
    for x in metadata_plugins(['identify']):
        if x.name == name:
            plugin = x
            break
    prints('Testing the identify function of', plugin.name)

    tdir = tempfile.gettempdir()
    lf = os.path.join(tdir, plugin.name.replace(' ', '')+'_identify_test.txt')
    log = create_log(open(lf, 'wb'))
    abort = Event()
    prints('Log saved to', lf)

    times = []
    for kwargs, test_funcs in tests:
        prints('Running test with:', kwargs)
        rq = Queue()
        args = (log, rq, abort)
        start_time = time.time()
        err = plugin.identify(*args, **kwargs)
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

        prints('Found', len(results), 'matches:')

        for mi in results:
            prints(mi)
            prints('\n\n')

        match_found = None
        for mi in results:
            test_failed = False
            for tfunc in test_funcs:
                if not tfunc(mi):
                    test_failed = True
                    break
            if not test_failed:
                match_found = mi
                break

        if match_found is None:
            prints('ERROR: No results that passed all tests were found')
            prints('Log saved to', lf)
            raise SystemExit(1)

    for key in plugin.touched_fields:
        if key.startswith('identifier:'):
            key = key.partition(':')[-1]
            if not match_found.has_identifier(key):
                prints('Failed to find identifier:', key)
                raise SystemExit(1)
        elif match_found.is_null(key):
            prints('Failed to find', key)
            raise SystemExit(1)

    prints('Average time per query', sum(times)/len(times))

    if os.stat(lf).st_size > 10:
        prints('There were some errors, see log', lf)

