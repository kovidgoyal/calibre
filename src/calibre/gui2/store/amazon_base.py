#!/usr/bin/env python
# License: GPL v3 Copyright: 2022, Kovid Goyal <kovid at kovidgoyal.net>

from threading import Lock
from time import monotonic
from typing import TYPE_CHECKING, Literal, overload

from qt.core import QUrl

from calibre.gui2 import open_url

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator
    from types import ModuleType

    from qt.core import QWidget

    from calibre.gui2.store.search_result import SearchResult
    from calibre.gui2.ui import Main
    from calibre.scraper.qt import WebEngineBrowser

lock = Lock()
cached_mod: ModuleType | None = None
cached_time = -10000000


def live_module() -> ModuleType:
    global cached_time, cached_mod
    with lock:
        now = monotonic()
        if now - cached_time > 3600:
            cached_mod = None
        if cached_mod is None:
            from calibre.live import Strategy, load_module

            cached_mod = load_module('calibre.gui2.store.amazon_live', strategy=Strategy.fast)
        return cached_mod


@overload
def get_method(name: Literal['search_amazon']) -> Callable[..., Iterator[SearchResult]]: ...
@overload
def get_method(name: Literal['get_store_link_amazon']) -> Callable[[AmazonStore, str | None], str]: ...
def get_method(name: str) -> Callable[..., object]:
    return getattr(live_module(), name)


class AmazonStore:
    minimum_calibre_version = (5, 40, 1)
    SEARCH_BASE_URL = 'https://www.amazon.com/s/'
    SEARCH_BASE_QUERY = {'i': 'digital-text'}
    BY = 'by'
    KINDLE_EDITION = 'Kindle Edition'
    DETAILS_URL = 'https://amazon.com/dp/'
    STORE_LINK = 'https://www.amazon.com/Kindle-eBooks'
    FIELD_KEYWORDS = 'k'
    scraper_storage: list[WebEngineBrowser]

    def open(self, gui: Main | None, parent: QWidget | None = None, detail_item: str | None = None, external: bool = False) -> None:
        store_link = get_method('get_store_link_amazon')(self, detail_item)
        open_url(QUrl(store_link))

    def search(self, query: bytes | str, max_results: int = 10, timeout: int = 60) -> Iterator[SearchResult]:
        yield from get_method('search_amazon')(self, query, max_results=max_results, timeout=timeout)

    def develop_plugin(self) -> None:
        import sys

        for result in get_method('search_amazon')(self, ' '.join(sys.argv[1:]), write_html_to='/t/amazon.html'):
            print(result)
