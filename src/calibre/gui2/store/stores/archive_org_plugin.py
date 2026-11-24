# License: GPLv3 Copyright: 2011, John Schember <john@nachtimwald.com>


store_version = 4  # Needed for dynamic plugin loading

from typing import TYPE_CHECKING

from calibre.gui2.store.basic_config import BasicStoreConfig
from calibre.gui2.store.opensearch_store import OpenSearchOPDSStore, open_search
from calibre.gui2.store.search_result import SearchResult

SEARCH_URL = 'http://bookserver.archive.org/catalog/opensearch.xml'


if TYPE_CHECKING:
    from collections.abc import Iterator


def search(query: bytes | str, max_results: int = 10, timeout: int = 60) -> Iterator[SearchResult]:
    yield from open_search(SEARCH_URL, query, max_results=max_results, timeout=timeout)


class ArchiveOrgStore(BasicStoreConfig, OpenSearchOPDSStore):
    open_search_url = SEARCH_URL
    web_url = 'http://www.archive.org/details/texts'

    # http://bookserver.archive.org/catalog/

    def search(self, query: bytes | str, max_results: int = 10, timeout: int = 60) -> Iterator[SearchResult]:
        for s in search(query, max_results, timeout):
            s.detail_item = 'http://www.archive.org/details/' + s.detail_item.split(':')[-1]
            s.price = '$0.00'
            s.drm = SearchResult.DRM_UNLOCKED
            yield s


if __name__ == '__main__':
    import sys

    for s in search(' '.join(sys.argv[1:])):
        print(s)
