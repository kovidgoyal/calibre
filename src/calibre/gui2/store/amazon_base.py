#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2022, Kovid Goyal <kovid at kovidgoyal.net>

from qt.core import QUrl
from threading import Lock
from time import monotonic

from calibre.gui2 import open_url


lock = Lock()
cached_mod = None
cached_time = -10000000


def live_module():
    global cached_time, cached_mod
    with lock:
        now = monotonic()
        if now - cached_time > 3600:
            cached_mod = None
        if cached_mod is None:
            from calibre.live import load_module, Strategy
            cached_mod = load_module('calibre.gui2.store.amazon_live', strategy=Strategy.fast)
        return cached_mod


def get_method(name):
    return getattr(live_module(), name)


class AmazonStore:

    minimum_calibre_version = (5, 40, 1)
    SEARCH_BASE_URL = 'https://www.amazon.com/s/'
    SEARCH_BASE_QUERY = {'i': 'digital-text'}
    BY = 'by'
    KINDLE_EDITION = 'Kindle Edition'
    DETAILS_URL = 'https://amazon.com/dp/'
    STORE_LINK =  'https://www.amazon.com/Kindle-eBooks'
    DRM_SEARCH_TEXT = 'Simultaneous Device Usage'
    DRM_FREE_TEXT = 'Unlimited'
    FIELD_KEYWORDS = 'k'

    def open(self, parent=None, detail_item=None, external=False):
        store_link = get_method('get_store_link_amazon')(self, detail_item)
        open_url(QUrl(store_link))

    def search(self, query, max_results=10, timeout=60):
        for result in get_method('search_amazon')(self, query, max_results=max_results, timeout=timeout):
            yield result

    def get_details(self, search_result, timeout):
        return get_method('get_details_amazon')(self, search_result, timeout)

    def develop_plugin(self):
        import sys
        for result in get_method('search_amazon')(self, ' '.join(sys.argv[1:]), write_html_to='/t/amazon.html'):
            print(result)
