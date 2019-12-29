# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function, unicode_literals

store_version = 2  # Needed for dynamic plugin loading

__license__ = 'GPL 3'
__copyright__ = '2011, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

from contextlib import closing
try:
    from urllib.parse import quote_plus
except ImportError:
    from urllib import quote_plus

from lxml import etree

from calibre import browser
from calibre.gui2.store.basic_config import BasicStoreConfig
from calibre.gui2.store.opensearch_store import OpenSearchOPDSStore
from calibre.gui2.store.search_result import SearchResult


class XinXiiStore(BasicStoreConfig, OpenSearchOPDSStore):

    open_search_url = 'https://www.xinxii.com/catalog-search/'
    web_url = 'https://xinxii.com/'

    # https://www.xinxii.com/catalog/

    def search(self, query, max_results=10, timeout=60):
        '''
        XinXii's open search url is:
        http://www.xinxii.com/catalog-search/query/?keywords={searchTerms}&amp;pw={startPage?}&amp;doc_lang={docLang}&amp;ff={docFormat},{docFormat},{docFormat}

        This url requires the docLang and docFormat. However, the search itself
        sent to XinXii does not require them. They can be ignored. We cannot
        push this into the stanard OpenSearchOPDSStore search because of the
        required attributes.

        XinXii doesn't return all info supported by OpenSearchOPDSStore search
        function so this one is modified to remove parts that are used.
        '''

        url = 'https://www.xinxii.com/catalog-search/query/?keywords=' + quote_plus(query)

        counter = max_results
        br = browser()
        with closing(br.open(url, timeout=timeout)) as f:
            doc = etree.fromstring(f.read(), parser=etree.XMLParser(recover=True, no_network=True, resolve_entities=False))
            for data in doc.xpath('//*[local-name() = "entry"]'):
                if counter <= 0:
                    break

                counter -= 1

                s = SearchResult()

                s.detail_item = ''.join(data.xpath('./*[local-name() = "id"]/text()')).strip()

                for link in data.xpath('./*[local-name() = "link"]'):
                    rel = link.get('rel')
                    href = link.get('href')
                    type = link.get('type')

                    if rel and href and type:
                        if rel in ('http://opds-spec.org/thumbnail', 'http://opds-spec.org/image/thumbnail'):
                            s.cover_url = href
                        if rel == 'alternate':
                            s.detail_item = href

                s.formats = 'EPUB, PDF'

                s.title = ' '.join(data.xpath('./*[local-name() = "title"]//text()')).strip()
                s.author = ', '.join(data.xpath('./*[local-name() = "author"]//*[local-name() = "name"]//text()')).strip()

                price_e = data.xpath('.//*[local-name() = "price"][1]')
                if price_e:
                    price_e = price_e[0]
                    currency_code = price_e.get('currencycode', '')
                    price = ''.join(price_e.xpath('.//text()')).strip()
                    s.price = currency_code + ' ' + price
                    s.price = s.price.strip()

                yield s
