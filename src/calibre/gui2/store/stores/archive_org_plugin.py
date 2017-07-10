# -*- coding: utf-8 -*-

from __future__ import (unicode_literals, division, absolute_import, print_function)
store_version = 4  # Needed for dynamic plugin loading

__license__ = 'GPL 3'
__copyright__ = '2011, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

from calibre.gui2.store.basic_config import BasicStoreConfig
from calibre.gui2.store.opensearch_store import OpenSearchOPDSStore, open_search
from calibre.gui2.store.search_result import SearchResult

SEARCH_URL =  'http://bookserver.archive.org/catalog/opensearch.xml'


def search(query, max_results=10, timeout=60):
    for result in open_search(SEARCH_URL, query, max_results=max_results, timeout=timeout):
        yield result


class ArchiveOrgStore(BasicStoreConfig, OpenSearchOPDSStore):

    open_search_url = SEARCH_URL
    web_url = 'http://www.archive.org/details/texts'

    # http://bookserver.archive.org/catalog/

    def search(self, query, max_results=10, timeout=60):
        for s in search(query, max_results, timeout):
            s.detail_item = 'http://www.archive.org/details/' + s.detail_item.split(':')[-1]
            s.price = '$0.00'
            s.drm = SearchResult.DRM_UNLOCKED
            yield s


if __name__ == '__main__':
    import sys
    for s in search(' '.join(sys.argv[1:])):
        print(s)
