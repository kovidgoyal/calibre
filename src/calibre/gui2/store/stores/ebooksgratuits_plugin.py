
# -*- coding: utf-8 -*-
from __future__ import (unicode_literals, division, absolute_import, print_function)
store_version = 1 # Needed for dynamic plugin loading

__license__ = 'GPL 3'
__copyright__ = '2012, Florent FAYOLLE <florent.fayolle69@gmail.com>'
__docformat__ = 'restructuredtext en'

from calibre.gui2.store.basic_config import BasicStoreConfig
from calibre.gui2.store.opensearch_store import OpenSearchOPDSStore
from calibre.gui2.store.search_result import SearchResult
from calibre.utils.filenames import ascii_text

class EbooksGratuitsStore(BasicStoreConfig, OpenSearchOPDSStore):

    open_search_url = 'http://www.ebooksgratuits.com/opds/opensearch.xml'
    web_url = 'http://www.ebooksgratuits.com/'

    def strip_accents(self, s):
        return ascii_text(s)

    def search(self, query, max_results=10, timeout=60):
        query = self.strip_accents(unicode(query))
        for s in OpenSearchOPDSStore.search(self, query, max_results, timeout):
            if s.downloads:
                s.drm = SearchResult.DRM_UNLOCKED
                s.price = '$0.00'
                yield s

