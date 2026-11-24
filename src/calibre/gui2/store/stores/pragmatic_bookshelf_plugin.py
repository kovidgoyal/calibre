# License: GPLv3 Copyright: 2011, John Schember <john@nachtimwald.com>


store_version = 1  # Needed for dynamic plugin loading

from typing import TYPE_CHECKING

from calibre.gui2.store.basic_config import BasicStoreConfig
from calibre.gui2.store.opensearch_store import OpenSearchOPDSStore
from calibre.gui2.store.search_result import SearchResult

if TYPE_CHECKING:
    from collections.abc import Iterator


class PragmaticBookshelfStore(BasicStoreConfig, OpenSearchOPDSStore):
    open_search_url = 'http://pragprog.com/catalog/search-description'
    web_url = 'http://pragprog.com/'

    # http://pragprog.com/catalog.opds

    def search(self, query: bytes | str, max_results: int = 10, timeout: int = 60) -> Iterator[SearchResult]:
        for s in OpenSearchOPDSStore.search(self, query, max_results, timeout):
            s.drm = SearchResult.DRM_UNLOCKED
            s.formats = 'EPUB, PDF, MOBI'
            yield s
