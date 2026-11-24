# License: GPLv3 Copyright: 2011, John Schember <john@nachtimwald.com>

import traceback
from contextlib import closing
from queue import Queue
from threading import Thread
from typing import TYPE_CHECKING, Any

from calibre import browser
from calibre.constants import DEBUG
from calibre.utils.img import scale_image
from polyglot.binary import from_base64_bytes

if TYPE_CHECKING:
    from collections.abc import Callable
    from typing import Protocol

    from calibre.gui2.store import StorePlugin
    from calibre.gui2.store.search_result import SearchResult

    class WorkerThread(Protocol):
        def start(self) -> None: ...
        def abort(self) -> None: ...
        def is_alive(self) -> bool: ...

    SearchTask = tuple[str | bytes | None, str | None, StorePlugin | None, int | None, int | None]
    SearchThreadResult = tuple[SearchResult, StorePlugin]
    CoverTask = tuple[SearchResult | None, Callable[[], object] | None, int]
    DetailsTask = tuple[SearchResult | None, StorePlugin | None, Callable[[SearchResult], object] | None, int]
    CacheUpdateTask = tuple[StorePlugin | None, int]


class GenericDownloadThreadPool[T, R]:
    """
    add_task must be implemented in a subclass and must
    GenericDownloadThreadPool.add_task must be called
    at the end of the function.
    """

    def __init__(self, thread_type: Callable[[Queue[T], Queue[R]], WorkerThread], thread_count: int = 1) -> None:
        self.thread_type = thread_type
        self.thread_count = thread_count

        self.tasks: Queue[T] = Queue()
        self.results: Queue[R] = Queue()
        self.threads: list[WorkerThread] = []

    def set_thread_count(self, thread_count: int) -> None:
        self.thread_count = thread_count

    # Any so that subclasses (including third party ones) can override with their own signatures
    def add_task(self, *args: Any, **kwargs: Any) -> None:  # ruff: ignore[any-type]
        """
        This must be implemented in a sub class and this function
        must be called at the end of the add_task function in
        the sub class.

        The implementation of this function (in this base class)
        starts any threads necessary to fill the pool if it is
        not already full.
        """
        for i in range(self.thread_count - self.running_threads_count()):
            t = self.thread_type(self.tasks, self.results)
            self.threads.append(t)
            t.start()

    def abort(self) -> None:
        self.tasks = Queue()
        self.results = Queue()
        for t in self.threads:
            t.abort()
        self.threads = []

    def has_tasks(self) -> bool:
        return not self.tasks.empty()

    def get_result(self) -> R:
        return self.results.get()

    def get_result_no_wait(self) -> R:
        return self.results.get_nowait()

    def result_count(self) -> int:
        return self.results.qsize()

    def has_results(self) -> bool:
        return not self.results.empty()

    def threads_running(self) -> bool:
        return self.running_threads_count() > 0

    def running_threads_count(self) -> int:
        count = 0
        for t in self.threads:
            if t.is_alive():
                count += 1
        return count


class SearchThreadPool(GenericDownloadThreadPool['SearchTask', 'SearchThreadResult']):
    """
    Threads will run until there is no work or
    abort is called. Create and start new threads
    using start_threads(). Reset by calling abort().

    Example:
    sp = SearchThreadPool(3)
    sp.add_task(...)
    """

    def __init__(self, thread_count: int) -> None:
        GenericDownloadThreadPool.__init__(self, SearchThread, thread_count)

    def add_task(
        self,
        query: str | bytes | None = None,
        store_name: str | None = None,
        store_plugin: StorePlugin | None = None,
        max_results: int | None = None,
        timeout: int | None = None,
    ) -> None:
        self.tasks.put((query, store_name, store_plugin, max_results, timeout))
        GenericDownloadThreadPool.add_task(self)


class SearchThread(Thread):
    def __init__(self, tasks: Queue[SearchTask], results: Queue[SearchThreadResult]) -> None:
        Thread.__init__(self)
        self.daemon = True
        self.tasks = tasks
        self.results = results
        self._run = True

    def abort(self) -> None:
        self._run = False

    def run(self) -> None:
        while self._run and not self.tasks.empty():
            try:
                query, store_name, store_plugin, max_results, timeout = self.tasks.get()
                assert query is not None and store_name is not None and store_plugin is not None
                assert max_results is not None and timeout is not None
                assert store_plugin.base_plugin is not None
                for res in store_plugin.search(query, max_results=max_results, timeout=timeout):
                    if not self._run:
                        return
                    res.store_name = store_name
                    res.affiliate = store_plugin.base_plugin.affiliate
                    res.plugin_author = store_plugin.base_plugin.author
                    res.create_browser = store_plugin.create_browser
                    self.results.put((res, store_plugin))
                self.tasks.task_done()
            except Exception:
                if DEBUG:
                    traceback.print_exc()


class CoverThreadPool(GenericDownloadThreadPool['CoverTask', object]):
    def __init__(self, thread_count: int) -> None:
        GenericDownloadThreadPool.__init__(self, CoverThread, thread_count)

    def add_task(self, search_result: SearchResult | None = None, update_callback: Callable[[], object] | None = None, timeout: int = 5) -> None:
        self.tasks.put((search_result, update_callback, timeout))
        GenericDownloadThreadPool.add_task(self)


def decode_data_url(url: str) -> bytes:
    return from_base64_bytes(url.partition(',')[2])


class CoverThread(Thread):
    def __init__(self, tasks: Queue[CoverTask], results: Queue[object]) -> None:
        Thread.__init__(self)
        self.daemon = True
        self.tasks = tasks
        self.results = results
        self._run = True

        self.br = browser()

    def abort(self) -> None:
        self._run = False

    def run(self) -> None:
        while self._run and not self.tasks.empty():
            try:
                result, callback, timeout = self.tasks.get()
                if result and result.cover_url:
                    if result.cover_url.startswith('data:'):
                        result.cover_data = decode_data_url(result.cover_url)
                    else:
                        with closing(self.br.open(result.cover_url, timeout=timeout)) as f:
                            result.cover_data = f.read()
                    assert result.cover_data is not None and callback is not None
                    result.cover_data = scale_image(result.cover_data, 256, 256)[2]
                    callback()
                self.tasks.task_done()
            except Exception:
                if DEBUG:
                    traceback.print_exc()


class DetailsThreadPool(GenericDownloadThreadPool['DetailsTask', object]):
    def __init__(self, thread_count: int) -> None:
        GenericDownloadThreadPool.__init__(self, DetailsThread, thread_count)

    def add_task(
        self,
        search_result: SearchResult | None = None,
        store_plugin: StorePlugin | None = None,
        update_callback: Callable[[SearchResult], object] | None = None,
        timeout: int = 10,
    ) -> None:
        self.tasks.put((search_result, store_plugin, update_callback, timeout))
        GenericDownloadThreadPool.add_task(self)


class DetailsThread(Thread):
    def __init__(self, tasks: Queue[DetailsTask], results: Queue[object]) -> None:
        Thread.__init__(self)
        self.daemon = True
        self.tasks = tasks
        self.results = results
        self._run = True

    def abort(self) -> None:
        self._run = False

    def run(self) -> None:
        while self._run and not self.tasks.empty():
            try:
                result, store_plugin, callback, timeout = self.tasks.get()
                if result:
                    assert store_plugin is not None and callback is not None
                    store_plugin.get_details(result, timeout)
                    callback(result)
                self.tasks.task_done()
            except Exception:
                if DEBUG:
                    traceback.print_exc()


class CacheUpdateThreadPool(GenericDownloadThreadPool['CacheUpdateTask', object]):
    def __init__(self, thread_count: int) -> None:
        GenericDownloadThreadPool.__init__(self, CacheUpdateThread, thread_count)

    def add_task(self, store_plugin: StorePlugin | None = None, timeout: int = 10) -> None:
        self.tasks.put((store_plugin, timeout))
        GenericDownloadThreadPool.add_task(self)


class CacheUpdateThread(Thread):
    def __init__(self, tasks: Queue[CacheUpdateTask], results: Queue[object]) -> None:
        Thread.__init__(self)
        self.daemon = True
        self.tasks = tasks
        self._run = True

    def abort(self) -> None:
        self._run = False

    def run(self) -> None:
        while self._run and not self.tasks.empty():
            try:
                store_plugin, timeout = self.tasks.get()
                assert store_plugin is not None
                store_plugin.update_cache(timeout=timeout, suppress_progress=True)
            except Exception:
                if DEBUG:
                    traceback.print_exc()
