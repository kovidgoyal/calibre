# -*- coding: utf-8 -*-

from __future__ import (unicode_literals, division, absolute_import, print_function)

__license__ = 'GPL 3'
__copyright__ = '2011, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

from calibre.gui2.store.basic_config import BasicStoreConfig
from calibre.gui2.store.opensearch_store import OpenSearchStore
from calibre.gui2.store.search_result import SearchResult

class EpubBudStore(BasicStoreConfig, OpenSearchStore):

    open_search_url = 'http://www.epubbud.com/feeds/opensearch.xml'
    web_url = 'http://www.epubbud.com/'
    
    # http://www.epubbud.com/feeds/catalog.atom

    def search(self, query, max_results=10, timeout=60):
        for s in OpenSearchStore.search(self, query, max_results, timeout):
            s.price = '$0.00'
            s.drm = SearchResult.DRM_UNLOCKED
            s.formats = 'EPUB'
            # Download links are broken for this store.
            s.downloads = {}
            yield s
