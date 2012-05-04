# -*- coding: utf-8 -*-

from __future__ import (unicode_literals, division, absolute_import, print_function)

__license__ = 'GPL 3'
__copyright__ = '2012, Alex Stanev <alex@stanev.org>'
__docformat__ = 'restructuredtext en'

import re

from calibre.gui2.store.basic_config import BasicStoreConfig
from calibre.gui2.store.opensearch_store import OpenSearchOPDSStore
from calibre.gui2.store.search_result import SearchResult

class BiblioStore(BasicStoreConfig, OpenSearchOPDSStore):

    open_search_url = 'http://biblio.bg/feed.opds.php'
    web_url = 'http://biblio.bg/'

    def search(self, query, max_results=10, timeout=60):
        # check for cyrillic symbols before performing search
        uquery = unicode(query.strip(), 'utf-8')
        reObj = re.search(u'^[а-яА-Я\\d\\s]{3,}$', uquery)
        if not reObj:
            return

        for s in OpenSearchOPDSStore.search(self, query, max_results, timeout):
            yield s
            
    def get_details(self, search_result, timeout):
        # get format and DRM status
        from calibre import browser
        from contextlib import closing
        from lxml import html

        br = browser()
        with closing(br.open(search_result.detail_item, timeout=timeout)) as nf:
            idata = html.fromstring(nf.read())
            search_result.formats = ''
            if idata.xpath('.//span[@class="format epub"]'):
                search_result.formats = 'EPUB'
 
            if idata.xpath('.//span[@class="format pdf"]'):
                if search_result.formats == '':
                    search_result.formats = 'PDF'
                else:
                    search_result.formats.join(', PDF')
                
            if idata.xpath('.//span[@class="format nodrm-icon"]'):
                search_result.drm = SearchResult.DRM_UNLOCKED
            else:
                search_result.drm = SearchResult.DRM_LOCKED

        return True
