# License: GPLv3 Copyright: 2012, Florent FAYOLLE <florent.fayolle69@gmail.com>


store_version = 1  # Needed for dynamic plugin loading

from typing import TYPE_CHECKING

from calibre.gui2.store.basic_config import BasicStoreConfig
from calibre.gui2.store.opensearch_store import OpenSearchOPDSStore
from calibre.gui2.store.search_result import SearchResult
from calibre.utils.filenames import ascii_text

if TYPE_CHECKING:
    from collections.abc import Iterator


class EbooksGratuitsStore(BasicStoreConfig, OpenSearchOPDSStore):
    open_search_url = 'http://www.ebooksgratuits.com/opds/opensearch.xml'
    web_url = 'http://www.ebooksgratuits.com/'

    def strip_accents(self, s: str | bytes) -> str:
        return ascii_text(s)

    def search(self, query: bytes | str, max_results: int = 10, timeout: int = 60) -> Iterator[SearchResult]:
        query = self.strip_accents(str(query))
        for s in OpenSearchOPDSStore.search(self, query, max_results, timeout):
            if s.downloads:
                s.drm = SearchResult.DRM_UNLOCKED
                s.price = '$0.00'
                yield s
