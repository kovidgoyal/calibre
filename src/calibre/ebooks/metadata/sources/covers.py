#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import time
from Queue import Queue, Empty
from threading import Thread, Event
from io import BytesIO

from calibre.customize.ui import metadata_plugins
from calibre.ebooks.metadata.sources.base import msprefs, create_log
from calibre.utils.magick.draw import Image, save_cover_data_to

class Worker(Thread):

    def __init__(self, plugin, abort, title, authors, identifiers, timeout, rq, get_best_cover=False):
        Thread.__init__(self)
        self.daemon = True

        self.plugin = plugin
        self.abort = abort
        self.get_best_cover = get_best_cover
        self.buf = BytesIO()
        self.log = create_log(self.buf)
        self.title, self.authors, self.identifiers = (title, authors,
                identifiers)
        self.timeout, self.rq = timeout, rq
        self.time_spent = None

    def run(self):
        start_time = time.time()
        if not self.abort.is_set():
            try:
                if self.plugin.can_get_multiple_covers:
                    self.plugin.download_cover(self.log, self.rq, self.abort,
                        title=self.title, authors=self.authors, get_best_cover=self.get_best_cover,
                        identifiers=self.identifiers, timeout=self.timeout)
                else:
                    self.plugin.download_cover(self.log, self.rq, self.abort,
                        title=self.title, authors=self.authors,
                        identifiers=self.identifiers, timeout=self.timeout)
            except:
                self.log.exception('Failed to download cover from',
                        self.plugin.name)
        self.time_spent = time.time() - start_time

def is_worker_alive(workers):
    for w in workers:
        if w.is_alive():
            return True
    return False

def process_result(log, result):
    plugin, data = result
    try:
        im = Image()
        im.load(data)
        im.trim(10)
        width, height = im.size
        fmt = im.format

        if width < 50 or height < 50:
            raise ValueError('Image too small')
        data = save_cover_data_to(im, '/cover.jpg', return_data=True)
    except:
        log.exception('Invalid cover from', plugin.name)
        return None
    return (plugin, width, height, fmt, data)

def run_download(log, results, abort,
        title=None, authors=None, identifiers={}, timeout=30, get_best_cover=False):
    '''
    Run the cover download, putting results into the queue :param:`results`.

    Each result is a tuple of the form:

        (plugin, width, height, fmt, bytes)

    '''
    if title == _('Unknown'):
        title = None
    if authors == [_('Unknown')]:
        authors = None

    plugins = [p for p in metadata_plugins(['cover']) if p.is_configured()]

    rq = Queue()
    workers = [Worker(p, abort, title, authors, identifiers, timeout, rq, get_best_cover=get_best_cover) for p
            in plugins]
    for w in workers:
        w.start()

    first_result_at = None
    wait_time = msprefs['wait_after_first_cover_result']
    found_results = {}

    while True:
        time.sleep(0.1)
        try:
            x = rq.get_nowait()
            result = process_result(log, x)
            if result is not None:
                results.put(result)
                found_results[result[0]] = result
                if first_result_at is not None:
                    first_result_at = time.time()
        except Empty:
            pass

        if not is_worker_alive(workers):
            break

        if first_result_at is not None and time.time() - first_result_at > wait_time:
            log('Not waiting for any more results')
            abort.set()

        if abort.is_set():
            break

    while True:
        try:
            x = rq.get_nowait()
            result = process_result(log, x)
            if result is not None:
                results.put(result)
                found_results[result[0]] = result
        except Empty:
            break

    for w in workers:
        wlog = w.buf.getvalue().strip()
        log('\n'+'*'*30, w.plugin.name, 'Covers', '*'*30)
        log('Request extra headers:', w.plugin.browser.addheaders)
        if w.plugin in found_results:
            result = found_results[w.plugin]
            log('Downloaded cover:', '%dx%d'%(result[1], result[2]))
        else:
            log('Failed to download valid cover')
        if w.time_spent is None:
            log('Download aborted')
        else:
            log('Took', w.time_spent, 'seconds')
        if wlog:
            log(wlog)
        log('\n'+'*'*80)


def download_cover(log,
        title=None, authors=None, identifiers={}, timeout=30):
    '''
    Synchronous cover download. Returns the "best" cover as per user
    prefs/cover resolution.

    Returned cover is a tuple: (plugin, width, height, fmt, data)

    Returns None if no cover is found.
    '''
    rq = Queue()
    abort = Event()

    run_download(log, rq, abort, title=title, authors=authors,
            identifiers=identifiers, timeout=timeout, get_best_cover=True)

    results = []

    while True:
        try:
            results.append(rq.get_nowait())
        except Empty:
            break

    cp = msprefs['cover_priorities']

    def keygen(result):
        plugin, width, height, fmt, data = result
        return (cp.get(plugin.name, 1), 1/(width*height))

    results.sort(key=keygen)

    return results[0] if results else None




