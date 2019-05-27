# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function, unicode_literals


__license__ = 'GPL 3'
__copyright__ = '2011, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

import os
from threading import Lock

from PyQt5.Qt import (QUrl, QCoreApplication)

from calibre.constants import cache_dir
from calibre.gui2 import open_url
from calibre.gui2.store import StorePlugin
from calibre.gui2.store.basic_config import BasicStoreConfig
from calibre.gui2.store.search_result import SearchResult
from calibre.gui2.store.web_store_dialog import WebStoreDialog
from calibre.gui2.store.stores.mobileread.models import SearchFilter
from calibre.gui2.store.stores.mobileread.cache_progress_dialog import CacheProgressDialog
from calibre.gui2.store.stores.mobileread.cache_update_thread import CacheUpdateThread
from calibre.gui2.store.stores.mobileread.store_dialog import MobileReadStoreDialog


class MobileReadStore(BasicStoreConfig, StorePlugin):

    def __init__(self, *args, **kwargs):
        StorePlugin.__init__(self, *args, **kwargs)
        self.lock = Lock()

    @property
    def cache(self):
        if not hasattr(self, '_mr_cache'):
            from calibre.utils.config import JSONConfig
            self._mr_cache = JSONConfig('mobileread_get_books')
            self._mr_cache.file_path = os.path.join(cache_dir(),
                                                 'mobileread_get_books.json')
            self._mr_cache.refresh()
        return self._mr_cache

    def open(self, parent=None, detail_item=None, external=False):
        url = 'https://www.mobileread.com/'

        if external or self.config.get('open_external', False):
            open_url(QUrl(detail_item if detail_item else url))
        else:
            if detail_item:
                d = WebStoreDialog(self.gui, url, parent, detail_item)
                d.setWindowTitle(self.name)
                d.set_tags(self.config.get('tags', ''))
                d.exec_()
            else:
                self.update_cache(parent, 30)
                d = MobileReadStoreDialog(self, parent)
                d.setWindowTitle(self.name)
                d.exec_()

    def search(self, query, max_results=10, timeout=60):
        books = self.get_book_list()

        if not books:
            return

        sf = SearchFilter(books)
        matches = sf.parse(query.decode('utf-8', 'replace'))

        for book in matches:
            book.price = '$0.00'
            book.drm = SearchResult.DRM_UNLOCKED
            yield book

    def update_cache(self, parent=None, timeout=10, force=False,
            suppress_progress=False):
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

    def get_book_list(self):
        return self.deseralize_books(self.cache.get('book_list', []))

    def seralize_books(self, books):
        sbooks = []
        for b in books:
            data = {}
            data['author'] = b.author
            data['title'] = b.title
            data['detail_item'] = b.detail_item
            data['formats'] = b.formats
            sbooks.append(data)
        return sbooks

    def deseralize_books(self, sbooks):
        books = []
        for s in sbooks:
            b = SearchResult()
            b.author = s.get('author', '')
            b.title = s.get('title', '')
            b.detail_item = s.get('detail_item', '')
            b.formats = s.get('formats', '')
            books.append(b)
        return books
