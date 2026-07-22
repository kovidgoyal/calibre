# -*- coding: utf-8 -*-
# License: GPLv3 Copyright: 2011, John Schember <john@nachtimwald.com>

from __future__ import absolute_import, division, print_function, unicode_literals

store_version = 1  # Needed for dynamic plugin loading

from calibre.gui2.store.basic_config import BasicStoreConfig
from calibre.gui2.store.opensearch_store import OpenSearchOPDSStore
from calibre.gui2.store.search_result import SearchResult


class FeedbooksStore(BasicStoreConfig, OpenSearchOPDSStore):
    open_search_url = 'http://assets0.feedbooks.net/opensearch.xml?t=1253087147'
    web_url = 'http://feedbooks.com/'

    # http://www.feedbooks.com/catalog

    def search(self, query, max_results=10, timeout=60):
        for s in OpenSearchOPDSStore.search(self, query, max_results, timeout):
            if s.downloads:
                s.drm = SearchResult.DRM_UNLOCKED
                s.price = '$0.00'
            else:
                s.drm = SearchResult.DRM_LOCKED
                s.formats = 'EPUB'
            yield s
