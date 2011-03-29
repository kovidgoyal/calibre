#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import time
from Queue import Queue, Empty
from threading import Thread
from io import BytesIO

from calibre.customize.ui import metadata_plugins
from calibre.ebooks.metadata.sources.base import create_log

# How long to wait for more results after first result is found
WAIT_AFTER_FIRST_RESULT = 30 # seconds

class Worker(Thread):

    def __init__(self, plugin, kwargs, abort):
        Thread.__init__(self)
        self.daemon = True

        self.plugin, self.kwargs, self.rq = plugin, kwargs, Queue()
        self.abort = abort
        self.buf = BytesIO()
        self.log = create_log(self.buf)

    def run(self):
        try:
            self.plugin.identify(self.log, self.rq, self.abort, **self.kwargs)
        except:
            self.log.exception('Plugin', self.plugin.name, 'failed')

def is_worker_alive(workers):
    for w in workers:
        if w.is_alive():
            return True
    return False

def identify(log, abort, title=None, authors=None, identifiers=[], timeout=30):
    start_time = time.time()
    plugins = list(metadata_plugins['identify'])

    kwargs = {
            'title': title,
            'authors': authors,
            'identifiers': identifiers,
            'timeout': timeout,
    }

    log('Running identify query with parameters:')
    log(kwargs)
    log('Using plugins:', ', '.join([p.name for p in plugins]))
    log('The log (if any) from individual plugins is below')

    workers = [Worker(p, kwargs, abort) for p in plugins]
    for w in workers:
        w.start()

    first_result_at = None
    results = dict.fromkeys(plugins, [])

    def get_results():
        found = False
        for w in workers:
            try:
                result = w.rq.get_nowait()
            except Empty:
                pass
            else:
                results[w.plugin].append(result)
                found = True
        return found

    while True:
        time.sleep(0.2)

        if get_results() and first_result_at is None:
            first_result_at = time.time()

        if not is_worker_alive(workers):
            break

        if (first_result_at is not None and time.time() - first_result_at <
                WAIT_AFTER_FIRST_RESULT):
            log('Not waiting any longer for more results')
            abort.set()
            break

    get_results()
    sort_kwargs = dict(kwargs)
    for k in list(sort_kwargs.iterkeys()):
        if k not in ('title', 'authors', 'identifiers'):
            sort_kwargs.pop(k)

    for plugin, results in results.iteritems():
        results.sort(key=plugin.identify_results_keygen(**sort_kwargs))
        plog = plugin.buf.getvalue().strip()
        if plog:
            log('\n'+'*'*35, plugin.name, '*'*35)
            log('Found %d results'%len(results))
            log(plog)
            log('\n'+'*'*80)

        for i, result in enumerate(results):
            result.relevance_in_source = i
            result.has_cached_cover_url = \
                plugin.get_cached_cover_url(result.identifiers) is not None
            result.identify_plugin = plugin

    log('The identify phase took %.2f seconds'%(time.time() - start_time))
    log('Merging results from different sources and finding earliest',
            'publication dates')
    start_time = time.time()
    merged_results = merge_identify_results(results, log)
    log('We have %d merged results, merging took: %.2f seconds' %
            (len(merged_results), time.time() - start_time))

def merge_identify_results(result_map, log):
    pass


