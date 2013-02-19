# -*- coding: utf-8 -*-

from __future__ import (unicode_literals, division, absolute_import, print_function)
store_version = 1 # Needed for dynamic plugin loading

__license__ = 'GPL 3'
__copyright__ = '2011, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

from calibre.gui2.store.basic_config import BasicStoreConfig
from calibre.gui2.store.opensearch_store import OpenSearchOPDSStore
from calibre.gui2.store.search_result import SearchResult

class PragmaticBookshelfStore(BasicStoreConfig, OpenSearchOPDSStore):

    open_search_url = 'http://pragprog.com/catalog/search-description'
    web_url = 'http://pragprog.com/'

    # http://pragprog.com/catalog.opds

    def search(self, query, max_results=10, timeout=60):
        for s in OpenSearchOPDSStore.search(self, query, max_results, timeout):
            s.drm = SearchResult.DRM_UNLOCKED
            s.formats = 'EPUB, PDF, MOBI'
            yield s
