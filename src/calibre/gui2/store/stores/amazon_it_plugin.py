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

class AmazonITKindleStore(StorePlugin):
    '''
    For comments on the implementation, please see amazon_plugin.py
    '''

    def open(self, parent=None, detail_item=None, external=False):
        aff_id = {'tag': 'httpcharles07-21'}
        store_link = 'http://www.amazon.it/ebooks-kindle/b?_encoding=UTF8&node=827182031&tag=%(tag)s&ie=UTF8&linkCode=ur2&camp=3370&creative=23322' % aff_id
        if detail_item:
            aff_id['asin'] = detail_item
            store_link = 'http://www.amazon.it/gp/redirect.html?ie=UTF8&location=http://www.amazon.it/dp/%(asin)s&tag=%(tag)s&linkCode=ur2&camp=3370&creative=23322' % aff_id
        open_url(QUrl(store_link))

    def search(self, query, max_results=10, timeout=60):
        search_url = 'http://www.amazon.it/s/?url=search-alias%3Ddigital-text&field-keywords='
        url = search_url + query.encode('ascii', 'backslashreplace').replace('%', '%25').replace('\\x', '%').replace(' ', '+')
        br = browser()

        counter = max_results
        with closing(br.open(url, timeout=timeout)) as f:
            # doc = html.fromstring(f.read().decode('latin-1', 'replace'))
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
                author = unicode(''.join(data.xpath('.//div[@class="title"]/span[@class="ptBrand"]/text()')))
                if author.startswith('di '):
                    author = author[3:]

                counter -= 1

                s = SearchResult()
                s.cover_url = cover_url.strip()
                s.title = title.strip()
                s.author = author.strip()
                s.price = price.strip()
                s.detail_item = asin.strip()
                s.formats = 'Kindle'
                s.drm = SearchResult.DRM_UNKNOWN

                yield s
