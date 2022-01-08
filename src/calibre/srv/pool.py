#!/usr/bin/env python


__license__ = 'GPL v3'
__copyright__ = '2015, Kovid Goyal <kovid at kovidgoyal.net>'

import sys
from threading import Thread

from calibre.utils.monotonic import monotonic
from polyglot.queue import Queue, Full


class Worker(Thread):

    daemon = True

    def __init__(self, log, notify_server, num, request_queue, result_queue):
        self.request_queue, self.result_queue = request_queue, result_queue
        self.notify_server = notify_server
        self.log = log
        self.working = False
        Thread.__init__(self, name='ServerWorker%d' % num)

    def run(self):
        while True:
            x = self.request_queue.get()
            if x is None:
                break
            job_id, func = x
            self.working = True
            try:
                result = func()
            except Exception:
                self.handle_error(job_id)  # must be a separate function to avoid reference cycles with sys.exc_info()
            else:
                self.result_queue.put((job_id, True, result))
            finally:
                self.working = False
            try:
                self.notify_server()
            except Exception:
                self.log.exception('ServerWorker failed to notify server on job completion')

    def handle_error(self, job_id):
        self.result_queue.put((job_id, False, sys.exc_info()))


class ThreadPool:

    def __init__(self, log, notify_server, count=10, queue_size=1000):
        self.request_queue, self.result_queue = Queue(queue_size), Queue(queue_size)
        self.workers = [Worker(log, notify_server, i, self.request_queue, self.result_queue) for i in range(count)]

    def start(self):
        for w in self.workers:
            w.start()

    def put_nowait(self, job_id, func):
        self.request_queue.put_nowait((job_id, func))

    def get_nowait(self):
        return self.result_queue.get_nowait()

    def stop(self, wait_till):
        for w in self.workers:
            try:
                self.request_queue.put_nowait(None)
            except Full:
                break
        for w in self.workers:
            now = monotonic()
            if now >= wait_till:
                break
            w.join(wait_till - now)
        self.workers = [w for w in self.workers if w.is_alive()]

    @property
    def busy(self):
        return sum(int(w.working) for w in self.workers)

    @property
    def idle(self):
        return sum(int(not w.working) for w in self.workers)


class PluginPool:

    def __init__(self, loop, plugins):
        self.workers = []
        self.loop = loop
        for plugin in plugins:
            w = Thread(target=self.run_plugin, args=(plugin,), name=self.plugin_name(plugin))
            w.daemon = True
            w.plugin = plugin
            self.workers.append(w)

    def plugin_name(self, plugin):
        return plugin.__class__.__name__

    def run_plugin(self, plugin):
        try:
            plugin.start(self.loop)
        except Exception:
            self.loop.log.exception('Failed to start plugin:', self.plugin_name(plugin))

    def start(self):
        for w in self.workers:
            w.start()

    def stop(self, wait_till):
        for w in self.workers:
            if w.is_alive():
                try:
                    w.plugin.stop()
                except Exception:
                    self.loop.log.exception('Failed to stop plugin:', self.plugin_name(w.plugin))
        for w in self.workers:
            left = wait_till - monotonic()
            if left > 0:
                w.join(left)
            else:
                break
        self.workers = [w for w in self.workers if w.is_alive()]
