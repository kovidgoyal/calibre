# -*- coding: utf-8 -*-

from __future__ import (unicode_literals, division, absolute_import, print_function)

__license__ = 'GPL 3'
__copyright__ = '2011, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

import re, urllib
from contextlib import closing

from lxml import html

from PyQt4.Qt import QUrl

from calibre import browser
from calibre.gui2 import open_url
from calibre.gui2.store import StorePlugin
from calibre.gui2.store.search_result import SearchResult

class AmazonDEKindleStore(StorePlugin):
    '''
    For comments on the implementation, please see amazon_plugin.py
    '''

    def open(self, parent=None, detail_item=None, external=False):
        aff_id = {'tag': 'charhale0a-21'}
        store_link = ('http://www.amazon.de/gp/redirect.html?ie=UTF8&site-redirect=de'
                     '&tag=%(tag)s&linkCode=ur2&camp=1638&creative=19454'
                     '&location=http://www.amazon.de/ebooks-kindle/b?node=530886031') % aff_id
        if detail_item:
            aff_id['asin'] = detail_item
            store_link = ('http://www.amazon.de/gp/redirect.html?ie=UTF8'
                          '&location=http://www.amazon.de/dp/%(asin)s&site-redirect=de'
                          '&tag=%(tag)s&linkCode=ur2&camp=1638&creative=6742') % aff_id
        open_url(QUrl(store_link))

    def search(self, query, max_results=10, timeout=60):
        search_url = 'http://www.amazon.de/s/?url=search-alias%3Ddigital-text&field-keywords='
        url =  search_url + urllib.quote_plus(query)
        br = browser()

        counter = max_results
        with closing(br.open(url, timeout=timeout)) as f:
            doc = html.fromstring(f.read())

            # Amazon has two results pages.
            # 20110725: seems that is_shot is gone.
#            is_shot = doc.xpath('boolean(//div[@id="shotgunMainResults"])')
#            # Horizontal grid of books.
#            if is_shot:
#                data_xpath = '//div[contains(@class, "result")]'
#                format_xpath = './/div[@class="productTitle"]/text()'
#                cover_xpath = './/div[@class="productTitle"]//img/@src'
#            # Vertical list of books.
#            else:
            data_xpath = '//div[contains(@class, "result") and contains(@class, "product")]'
            format_xpath = './/span[@class="format"]/text()'
            cover_xpath = './/img[@class="productImage"]/@src'
# end is_shot else

            for data in doc.xpath(data_xpath):
                if counter <= 0:
                    break

                # Even though we are searching digital-text only Amazon will still
                # put in results for non Kindle books (author pages). So we need
                # to explicitly check if the item is a Kindle book and ignore it
                # if it isn't.
                format = ''.join(data.xpath(format_xpath))
                if 'kindle' not in format.lower():
                    continue

                # We must have an asin otherwise we can't easily reference the
                # book later.
                asin = ''.join(data.xpath("@name"))

                cover_url = ''.join(data.xpath(cover_xpath))

                title = ''.join(data.xpath('.//div[@class="title"]/a/text()'))
                price = ''.join(data.xpath('.//div[@class="newPrice"]/span/text()'))

#                if is_shot:
#                    author = format.split(' von ')[-1]
#                else:
                author = ''.join(data.xpath('.//div[@class="title"]/span[@class="ptBrand"]/text()'))
                author = author.split('von ')[-1]

                counter -= 1

                s = SearchResult()
                s.cover_url = cover_url.strip()
                s.title = title.strip()
                s.author = author.strip()
                s.price = price.strip()
                s.detail_item = asin.strip()
                s.formats = 'Kindle'

                yield s

    def get_details(self, search_result, timeout):
        drm_search_text = u'Gleichzeitige Verwendung von Geräten'
        drm_free_text = u'Keine Einschränkung'
        url = 'http://amazon.de/dp/'

        br = browser()
        with closing(br.open(url + search_result.detail_item, timeout=timeout)) as nf:
            idata = html.fromstring(nf.read())
            if idata.xpath('boolean(//div[@class="content"]//li/b[contains(text(), "' +
                           drm_search_text + '")])'):
                if idata.xpath('boolean(//div[@class="content"]//li[contains(., "' +
                               drm_free_text + '") and contains(b, "' +
                               drm_search_text + '")])'):
                    search_result.drm = SearchResult.DRM_UNLOCKED
                else:
                    search_result.drm = SearchResult.DRM_UNKNOWN
            else:
                search_result.drm = SearchResult.DRM_LOCKED
        return True
