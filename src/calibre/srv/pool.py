#!/usr/bin/env python
# License: GPLv3 Copyright: 2015, Kovid Goyal <kovid at kovidgoyal.net>

import sys
from queue import Full, Queue
from threading import Thread
from typing import TYPE_CHECKING, Protocol

from calibre.utils.monotonic import monotonic

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable

    from calibre.srv.loop import ServerLoop
    from calibre.utils.logging import Log

    # job_id, func
    type Job = tuple[int, Callable[[], object]]
    # job_id, ok, result. When ok is False result is the sys.exc_info() tuple
    type JobResult = tuple[int, bool, object]


class ServerPlugin(Protocol):
    def start(self, loop: ServerLoop) -> None: ...
    def stop(self) -> None: ...


class Worker(Thread):
    daemon = True

    def __init__(
        self,
        log: Log,
        notify_server: Callable[[], None],
        num: int,
        request_queue: Queue[Job | None],
        result_queue: Queue[JobResult],
    ) -> None:
        self.request_queue, self.result_queue = request_queue, result_queue
        self.notify_server = notify_server
        self.log = log
        self.working = False
        Thread.__init__(self, name=f'ServerWorker{num}')

    def run(self) -> None:
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

    def handle_error(self, job_id: int) -> None:
        self.result_queue.put((job_id, False, sys.exc_info()))


class ThreadPool:
    def __init__(self, log: Log, notify_server: Callable[[], None], count: int = 10, queue_size: int = 1000) -> None:
        self.request_queue: Queue[Job | None] = Queue(queue_size)
        self.result_queue: Queue[JobResult] = Queue(queue_size)
        self.workers = [Worker(log, notify_server, i, self.request_queue, self.result_queue) for i in range(count)]

    def start(self) -> None:
        for w in self.workers:
            w.start()

    def put_nowait(self, job_id: int, func: Callable[[], object]) -> None:
        self.request_queue.put_nowait((job_id, func))

    def get_nowait(self) -> JobResult:
        return self.result_queue.get_nowait()

    def stop(self, wait_till: float) -> None:
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
    def busy(self) -> int:
        return sum(int(w.working) for w in self.workers)

    @property
    def idle(self) -> int:
        return sum(int(not w.working) for w in self.workers)


class PluginThread(Thread):
    def __init__(self, plugin: ServerPlugin, target: Callable[[ServerPlugin], None], name: str) -> None:
        super().__init__(target=target, args=(plugin,), name=name, daemon=True)
        self.plugin = plugin


class PluginPool:
    def __init__(self, loop: ServerLoop, plugins: Iterable[ServerPlugin]) -> None:
        self.workers: list[PluginThread] = []
        self.loop = loop
        for plugin in plugins:
            w = PluginThread(plugin, target=self.run_plugin, name=self.plugin_name(plugin))
            self.workers.append(w)

    def plugin_name(self, plugin: ServerPlugin) -> str:
        return plugin.__class__.__name__

    def run_plugin(self, plugin: ServerPlugin) -> None:
        try:
            plugin.start(self.loop)
        except Exception:
            self.loop.log.exception('Failed to start plugin:', self.plugin_name(plugin))

    def start(self) -> None:
        for w in self.workers:
            w.start()

    def stop(self, wait_till: float) -> None:
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
