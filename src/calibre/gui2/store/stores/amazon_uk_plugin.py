# -*- coding: utf-8 -*-

from __future__ import (unicode_literals, division, absolute_import, print_function)

__license__ = 'GPL 3'
__copyright__ = '2011, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

from contextlib import closing

from lxml import html

from PyQt4.Qt import QUrl

from calibre import browser
from calibre.gui2 import open_url
from calibre.gui2.store import StorePlugin
from calibre.gui2.store.search_result import SearchResult

class AmazonUKKindleStore(StorePlugin):
    '''
    For comments on the implementation, please see amazon_plugin.py
    '''

    def open(self, parent=None, detail_item=None, external=False):
        aff_id = {'tag': 'calcharles-21'}
        store_link = 'http://www.amazon.co.uk/gp/redirect.html?ie=UTF8&location=http://www.amazon.co.uk/Kindle-eBooks/b?ie=UTF8&node=341689031&ref_=sa_menu_kbo2&tag=%(tag)s&linkCode=ur2&camp=1634&creative=19450' % aff_id

        if detail_item:
            aff_id['asin'] = detail_item
            store_link = 'http://www.amazon.co.uk/gp/redirect.html?ie=UTF8&location=http://www.amazon.co.uk/dp/%(asin)s&tag=%(tag)s&linkCode=ur2&camp=1634&creative=6738' % aff_id
        open_url(QUrl(store_link))

    def search(self, query, max_results=10, timeout=60):
        search_url = 'http://www.amazon.co.uk/s/?url=search-alias%3Ddigital-text&field-keywords='
        url = search_url + query.encode('ascii', 'backslashreplace').replace('%', '%25').replace('\\x', '%').replace(' ', '+')
        br = browser()

        counter = max_results
        with closing(br.open(url, timeout=timeout)) as f:
            # Apparently amazon Europe is responding in UTF-8 now
            doc = html.fromstring(f.read())

            data_xpath = '//div[contains(@class, "result") and contains(@class, "product")]'
            format_xpath = './/span[@class="format"]/text()'
            cover_xpath = './/img[@class="productImage"]/@src'

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

                title = ''.join(data.xpath('.//a[@class="title"]/text()'))
                price = ''.join(data.xpath('.//span[@class="price"]/text()'))

                author = ''.join(data.xpath('.//div[@class="title"]/span[@class="ptBrand"]/text()'))
                if author.startswith('by '):
                    author = author[3:]

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
        # We might already have been called.
        if search_result.drm:
            return

        url = 'http://amazon.co.uk/dp/'
        drm_search_text = u'Simultaneous Device Usage'
        drm_free_text = u'Unlimited'

        br = browser()
        with closing(br.open(url + search_result.detail_item, timeout=timeout)) as nf:
            idata = html.fromstring(nf.read())
            if not search_result.author:
                search_result.author = ''.join(idata.xpath('//div[@class="buying" and contains(., "Author")]/a/text()'))
                is_kindle = idata.xpath('boolean(//div[@class="buying"]/h1/span/span[contains(text(), "Kindle Edition")])')
                if is_kindle:
                    search_result.formats = 'Kindle'
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


