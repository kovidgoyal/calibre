# -*- coding: utf-8 -*-

from __future__ import (unicode_literals, division, absolute_import, print_function)

__license__ = 'GPL 3'
__copyright__ = '2011, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

import time
import traceback
from contextlib import closing
from threading import Thread
from Queue import Queue

from calibre import browser
from calibre.utils.magick.draw import thumbnail

class GenericDownloadThreadPool(object):
    '''
    add_task must be implemented in a subclass.
    '''

    def __init__(self, thread_type, thread_count):
        self.thread_type = thread_type
        self.thread_count = thread_count

        self.tasks = Queue()
        self.results = Queue()
        self.threads = []

    def add_task(self):
        raise NotImplementedError()

    def start_threads(self):
        for i in range(self.thread_count):
            t = self.thread_type(self.tasks, self.results)
            self.threads.append(t)
            t.start()

    def abort(self):
        self.tasks = Queue()
        self.results = Queue()
        for t in self.threads:
            t.abort()
        self.threads = []

    def has_tasks(self):
        return not self.tasks.empty()

    def get_result(self):
        return self.results.get()

    def get_result_no_wait(self):
        return self.results.get_nowait()

    def result_count(self):
        return len(self.results)

    def has_results(self):
        return not self.results.empty()

    def threads_running(self):
        for t in self.threads:
            if t.is_alive():
                return True
        return False


class SearchThreadPool(GenericDownloadThreadPool):
    '''
    Threads will run until there is no work or
    abort is called. Create and start new threads
    using start_threads(). Reset by calling abort().

    Example:
    sp = SearchThreadPool(SearchThread, 3)
    add tasks using add_task(...)
    sp.start_threads()
    all threads have finished.
    sp.abort()
    add tasks using add_task(...)
    sp.start_threads()
    '''

    def add_task(self, query, store_name, store_plugin, timeout):
        self.tasks.put((query, store_name, store_plugin, timeout))


class SearchThread(Thread):

    def __init__(self, tasks, results):
        Thread.__init__(self)
        self.daemon = True
        self.tasks = tasks
        self.results = results
        self._run = True

    def abort(self):
        self._run = False

    def run(self):
        while self._run and not self.tasks.empty():
            try:
                query, store_name, store_plugin, timeout = self.tasks.get()
                for res in store_plugin.search(query, timeout=timeout):
                    if not self._run:
                        return
                    res.store_name = store_name
                    self.results.put((res, store_plugin))
                self.tasks.task_done()
            except:
                traceback.print_exc()


class CoverThreadPool(GenericDownloadThreadPool):
    '''
    Once started all threads run until abort is called.
    '''

    def add_task(self, search_result, update_callback, timeout=5):
        self.tasks.put((search_result, update_callback, timeout))


class CoverThread(Thread):

    def __init__(self, tasks, results):
        Thread.__init__(self)
        self.daemon = True
        self.tasks = tasks
        self.results = results
        self._run = True

        self.br = browser()

    def abort(self):
        self._run = False

    def run(self):
        while self._run:
            try:
                time.sleep(.1)
                while not self.tasks.empty():
                    if not self._run:
                        break
                    result, callback, timeout = self.tasks.get()
                    if result and result.cover_url:
                        with closing(self.br.open(result.cover_url, timeout=timeout)) as f:
                            result.cover_data = f.read()
                        result.cover_data = thumbnail(result.cover_data, 64, 64)[2]
                        callback()
                    self.tasks.task_done()
            except:
                continue


class DetailsThreadPool(GenericDownloadThreadPool):
    '''
    Once started all threads run until abort is called.
    '''

    def add_task(self, search_result, store_plugin, update_callback, timeout=10):
        self.tasks.put((search_result, store_plugin, update_callback, timeout))


class DetailsThread(Thread):

    def __init__(self, tasks, results):
        Thread.__init__(self)
        self.daemon = True
        self.tasks = tasks
        self.results = results
        self._run = True

    def abort(self):
        self._run = False

    def run(self):
        while self._run:
            try:
                time.sleep(.1)
                while not self.tasks.empty():
                    if not self._run:
                        break
                    result, store_plugin, callback, timeout = self.tasks.get()
                    if result:
                        store_plugin.get_details(result, timeout)
                        callback(result)
                    self.tasks.task_done()
            except:
                continue
