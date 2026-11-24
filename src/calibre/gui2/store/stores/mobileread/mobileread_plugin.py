# License: GPLv3 Copyright: 2011, John Schember <john@nachtimwald.com>


import os
from threading import Lock
from typing import TYPE_CHECKING

from qt.core import QCoreApplication, QUrl

from calibre.constants import cache_dir
from calibre.gui2 import open_url
from calibre.gui2.store import StorePlugin
from calibre.gui2.store.basic_config import BasicStoreConfig
from calibre.gui2.store.search_result import SearchResult
from calibre.gui2.store.stores.mobileread.cache_progress_dialog import CacheProgressDialog
from calibre.gui2.store.stores.mobileread.cache_update_thread import CacheUpdateThread
from calibre.gui2.store.stores.mobileread.models import SearchFilter
from calibre.gui2.store.stores.mobileread.store_dialog import MobileReadStoreDialog
from calibre.gui2.store.web_store_dialog import WebStoreDialog
from calibre.utils.localization import _

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator

    from qt.core import QWidget

    from calibre.customize import StoreBase
    from calibre.gui2.ui import Main
    from calibre.utils.config import JSONConfig


class MobileReadStore(BasicStoreConfig, StorePlugin):
    _mr_cache: JSONConfig

    def __init__(self, gui: Main, name: str, config: JSONConfig | None = None, base_plugin: StoreBase | None = None) -> None:
        StorePlugin.__init__(self, gui, name, config=config, base_plugin=base_plugin)
        self.lock = Lock()

    @property
    def cache(self) -> JSONConfig:
        if not hasattr(self, '_mr_cache'):
            from calibre.utils.config import JSONConfig

            self._mr_cache = JSONConfig('mobileread_get_books')
            self._mr_cache.file_path = os.path.join(cache_dir(), 'mobileread_get_books.json')
            self._mr_cache.refresh()
        return self._mr_cache

    def open(self, gui: Main | None = None, parent: QWidget | None = None, detail_item: str | None = None, external: bool = False) -> None:
        url = 'https://www.mobileread.com/'

        if external or self.config.get('open_external', False):
            open_url(QUrl(detail_item or url))
        elif detail_item:
            d = WebStoreDialog(self.gui, url, parent, detail_item)
            d.setWindowTitle(self.name)
            d.set_tags(self.config.get('tags', ''))
            d.exec()
        else:
            self.update_cache(parent, 30)
            d = MobileReadStoreDialog(self, parent)
            d.setWindowTitle(self.name)
            d.exec()

    def search(self, query: str | bytes, max_results: int = 10, timeout: int = 60) -> Iterator[SearchResult]:
        books = self.get_book_list()

        if not books:
            return

        sf = SearchFilter(books)
        matches = sf.parse(query.decode('utf-8', 'replace') if isinstance(query, bytes) else query)

        for book in matches:
            book.price = '$0.00'
            book.drm = SearchResult.DRM_UNLOCKED
            yield book

    def update_cache(self, parent: QWidget | None = None, timeout: int = 10, force: bool = False, suppress_progress: bool = False) -> bool:
        if self.lock.acquire(False):
            try:
                update_thread = CacheUpdateThread(self.cache, self.seralize_books, timeout)
                if not suppress_progress:
                    progress = CacheProgressDialog(parent)
                    progress.set_message(_('Updating MobileRead book cache...'))

                    update_thread.total_changed.connect(progress.set_total)
                    update_thread.update_progress.connect(progress.set_progress)
                    update_thread.update_details.connect(progress.set_details)
                    progress.rejected.connect(update_thread.abort)

                    progress.open()
                    update_thread.start()
                    while update_thread.is_alive() and not progress.canceled:
                        QCoreApplication.processEvents()

                    if progress.isVisible():
                        progress.accept()
                    return not progress.canceled
                else:
                    update_thread.start()
            finally:
                self.lock.release()
        return False

    def get_book_list(self) -> list[SearchResult]:
        return self.deseralize_books(self.cache.get('book_list', []))

    def seralize_books(self, books: Iterable[SearchResult]) -> list[dict[str, str]]:
        sbooks = []
        for b in books:
            data: dict[str, str] = {}
            data['author'] = b.author
            data['title'] = b.title
            data['detail_item'] = b.detail_item
            data['formats'] = b.formats
            sbooks.append(data)
        return sbooks

    def deseralize_books(self, sbooks: Iterable[dict[str, str]]) -> list[SearchResult]:
        books = []
        for s in sbooks:
            b = SearchResult()
            b.author = s.get('author', '')
            b.title = s.get('title', '')
            b.detail_item = s.get('detail_item', '')
            b.formats = s.get('formats', '')
            books.append(b)
        return books
