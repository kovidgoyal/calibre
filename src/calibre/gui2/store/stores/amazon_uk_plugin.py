# -*- coding: utf-8 -*-

from __future__ import (unicode_literals, division, absolute_import, print_function)

__license__ = 'GPL 3'
__copyright__ = '2011, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

import re

from contextlib import closing
from lxml import html

from PyQt4.Qt import QUrl

from calibre import browser
from calibre.gui2 import open_url
from calibre.gui2.store import StorePlugin
from calibre.gui2.store.search_result import SearchResult

class AmazonUKKindleStore(StorePlugin):
    aff_id = {'tag': 'calcharles-21'}
    store_link = ('http://www.amazon.co.uk/gp/redirect.html?ie=UTF8&'
                  'location=http://www.amazon.co.uk/Kindle-eBooks/b?'
                  'ie=UTF8&node=341689031&ref_=sa_menu_kbo2&tag=%(tag)s&'
                  'linkCode=ur2&camp=1634&creative=19450')
    store_link_details = ('http://www.amazon.co.uk/gp/redirect.html?ie=UTF8&'
                          'location=http://www.amazon.co.uk/dp/%(asin)s&tag=%(tag)s&'
                          'linkCode=ur2&camp=1634&creative=6738')
    search_url = 'http://www.amazon.co.uk/s/?url=search-alias%3Ddigital-text&field-keywords='

    author_article = 'by '

    '''
    For comments on the implementation, please see amazon_plugin.py
    '''

    def open(self, parent=None, detail_item=None, external=False):

        store_link = self.store_link % self.aff_id
        if detail_item:
            self.aff_id['asin'] = detail_item
            store_link = self.store_link_details % self.aff_id
        open_url(QUrl(store_link))

    def search(self, query, max_results=10, timeout=60):
        url = self.search_url + query.encode('ascii', 'backslashreplace').replace('%', '%25').replace('\\x', '%').replace(' ', '+')
        br = browser()

        counter = max_results
        with closing(br.open(url, timeout=timeout)) as f:
            doc = html.fromstring(f.read())#.decode('latin-1', 'replace'))

            data_xpath = '//div[contains(@class, "prod")]'
            format_xpath = './/ul[contains(@class, "rsltL")]//span[contains(@class, "lrg") and not(contains(@class, "bld"))]/text()'
            asin_xpath = './/div[@class="image"]/a[1]'
            cover_xpath = './/img[@class="productImage"]/@src'
            title_xpath = './/h3[@class="newaps"]/a//text()'
            author_xpath = './/h3[@class="newaps"]//span[contains(@class, "reg")]/text()'
            price_xpath = './/ul[contains(@class, "rsltL")]//span[contains(@class, "lrg") and contains(@class, "bld")]/text()'

            for data in doc.xpath(data_xpath):
                if counter <= 0:
                    break

                # Even though we are searching digital-text only Amazon will still
                # put in results for non Kindle books (author pages). Se we need
                # to explicitly check if the item is a Kindle book and ignore it
                # if it isn't.
                format_ = ''.join(data.xpath(format_xpath))
                if 'kindle' not in format_.lower():
                    continue

                # We must have an asin otherwise we can't easily reference the
                # book later.
                asin_href = None
                asin_a = data.xpath(asin_xpath)
                if asin_a:
                    asin_href = asin_a[0].get('href', '')
                    m = re.search(r'/dp/(?P<asin>.+?)(/|$)', asin_href)
                    if m:
                        asin = m.group('asin')
                    else:
                        continue
                else:
                    continue

                cover_url = ''.join(data.xpath(cover_xpath))

                title = ''.join(data.xpath(title_xpath))
                author = ''.join(data.xpath(author_xpath))
                try:
                    if self.author_article:
                        author = author.split(self.author_article, 1)[1].split(" (")[0]
                except:
                    pass

                price = ''.join(data.xpath(price_xpath))

                counter -= 1

                s = SearchResult()
                s.cover_url = cover_url.strip()
                s.title = title.strip()
                s.author = author.strip()
                s.price = price.strip()
                s.detail_item = asin.strip()
                s.drm = SearchResult.DRM_UNKNOWN
                s.formats = 'Kindle'

                yield s

    def get_details(self, search_result, timeout):
        pass
