# -*- coding: utf-8 -*-

from __future__ import (unicode_literals, division, absolute_import, print_function)

__license__ = 'GPL 3'
__copyright__ = '2011, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

import urllib
from contextlib import closing

from lxml import html

from PyQt4.Qt import QUrl

from calibre import browser
from calibre.gui2 import open_url
from calibre.gui2.store.amazon_plugin import AmazonKindleStore
from calibre.gui2.store.search_result import SearchResult

class AmazonUKKindleStore(AmazonKindleStore):
    '''
    For comments on the implementation, please see amazon_plugin.py
    '''

    search_url = 'http://www.amazon.co.uk/s/?url=search-alias%3Ddigital-text&field-keywords='
    details_url = 'http://amazon.co.uk/dp/'

    def open(self, parent=None, detail_item=None, external=False):
        aff_id = {'tag': 'calcharles-21'}
        store_link = 'http://www.amazon.co.uk/gp/redirect.html?ie=UTF8&location=http://www.amazon.co.uk/Kindle-eBooks/b?ie=UTF8&node=341689031&ref_=sa_menu_kbo2&tag=%(tag)s&linkCode=ur2&camp=1634&creative=19450' % aff_id

        if detail_item:
            aff_id['asin'] = detail_item
            store_link = 'http://www.amazon.co.uk/gp/redirect.html?ie=UTF8&location=http://www.amazon.co.uk/dp/%(asin)s&tag=%(tag)s&linkCode=ur2&camp=1634&creative=6738' % aff_id
        open_url(QUrl(store_link))

    def search(self, query, max_results=10, timeout=60):
        url =  self.search_url + urllib.quote_plus(query)
        br = browser()

        counter = max_results
        with closing(br.open(url, timeout=timeout)) as f:
            doc = html.fromstring(f.read())

            # Amazon has two results pages.
            is_shot = doc.xpath('boolean(//div[@id="shotgunMainResults"])')
            # Horizontal grid of books.
            if is_shot:
                data_xpath = '//div[contains(@class, "result")]'
                cover_xpath = './/div[@class="productTitle"]//img/@src'
            # Vertical list of books.
            else:
                data_xpath = '//div[contains(@class, "product")]'
                cover_xpath = './div[@class="productImage"]/a/img/@src'

            for data in doc.xpath(data_xpath):
                if counter <= 0:
                    break

                # We must have an asin otherwise we can't easily reference the
                # book later.
                asin = ''.join(data.xpath('./@name'))
                if not asin:
                    continue
                cover_url = ''.join(data.xpath(cover_xpath))

                title = ''.join(data.xpath('.//div[@class="productTitle"]/a/text()'))
                price = ''.join(data.xpath('.//div[@class="newPrice"]/span/text()'))

                counter -= 1

                s = SearchResult()
                s.cover_url = cover_url.strip()
                s.title = title.strip()
                s.price = price.strip()
                s.detail_item = asin.strip()
                s.formats = ''

                print('is_shot', is_shot)
                if is_shot:
                    # Amazon UK does not include the author on the grid layout
                    s.author = ''
                    self.get_details(s, timeout)
                    if s.formats != 'Kindle':
                        continue
                else:
                    author = ''.join(data.xpath('.//div[@class="productTitle"]/span[@class="ptBrand"]/text()'))
                    s.author = author.split(' by ')[-1].strip()
                    s.formats = 'Kindle'

                yield s

    def get_details(self, search_result, timeout):
        # We might already have been called.
        if search_result.drm:
            return

        url = self.details_url

        br = browser()
        with closing(br.open(url + search_result.detail_item, timeout=timeout)) as nf:
            idata = html.fromstring(nf.read())
            if not search_result.author:
                search_result.author = ''.join(idata.xpath('//div[@class="buying" and contains(., "Author")]/a/text()'))
                is_kindle = idata.xpath('boolean(//div[@class="buying"]/h1/span/span[contains(text(), "Kindle Edition")])')
                if is_kindle:
                    search_result.formats = 'Kindle'
                print('az uk', is_kindle)
            if idata.xpath('boolean(//div[@class="content"]//li/b[contains(text(), "' +
                           self.drm_search_text + '")])'):
                if idata.xpath('boolean(//div[@class="content"]//li[contains(., "' +
                               self.drm_free_text + '") and contains(b, "' +
                               self.drm_search_text + '")])'):
                    search_result.drm = SearchResult.DRM_UNLOCKED
                else:
                    search_result.drm = SearchResult.DRM_UNKNOWN
            else:
                search_result.drm = SearchResult.DRM_LOCKED
        return True


