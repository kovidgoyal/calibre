# -*- coding: utf-8 -*-

from __future__ import (unicode_literals, division, absolute_import, print_function)

__license__ = 'GPL 3'
__copyright__ = '2011, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

import urllib
from contextlib import closing

from lxml import html

from PyQt4.Qt import QUrl

from calibre import browser, url_slash_cleaner
from calibre.gui2 import open_url
from calibre.gui2.store import StorePlugin
from calibre.gui2.store.basic_config import BasicStoreConfig
from calibre.gui2.store.search_result import SearchResult
from calibre.gui2.store.web_store_dialog import WebStoreDialog

class OReillyStore(BasicStoreConfig, StorePlugin):

    def open(self, parent=None, detail_item=None, external=False):
        url = 'http://oreilly.com/ebooks/'

        if external or self.config.get('open_external', False):
            open_url(QUrl(url_slash_cleaner(detail_item if detail_item else url)))
        else:
            d = WebStoreDialog(self.gui, url, parent, detail_item)
            d.setWindowTitle(self.name)
            d.set_tags(self.config.get('tags', ''))
            d.exec_()

    def search(self, query, max_results=10, timeout=60):
        url = 'http://search.oreilly.com/?t1=Books&t2=Format&t3=Ebook&q=' + urllib.quote_plus(query)

        br = browser()

        counter = max_results
        with closing(br.open(url, timeout=timeout)) as f:
            doc = html.fromstring(f.read())
            for data in doc.xpath('//div[@class="result"]'):
                if counter <= 0:
                    break

                ebook = ' '.join(data.xpath('.//p[@class="note"]/text()'))
                if 'ebook' not in ebook.lower():
                    continue

                id = ''.join(data.xpath('./div[@class="book_text"]//p[@class="title"]/a/@href'))

                cover_url = ''.join(data.xpath('./a/img[1]/@src'))

                title = ''.join(data.xpath('./div[@class="book_text"]/p[@class="title"]/a/text()'))
                author = ''.join(data.xpath('./div[@class="book_text"]/p[@class="note"][1]/text()'))
                author = author.split('By ')[-1].strip()

                # Get the detail here because we need to get the ebook id for the detail_item.
                with closing(br.open(id, timeout=timeout)) as nf:
                    idoc = html.fromstring(nf.read())

                    for td in idoc.xpath('//td[@class="optionsTd"]'):
                        if 'ebook' in ''.join(td.xpath('.//text()')).lower():
                            price = ''.join(td.xpath('.//span[@class="price"]/text()')).strip()
                            formats = ''.join(td.xpath('.//a[@id="availableFormats"]/text()')).strip()
                            break

                counter -= 1

                s = SearchResult()
                s.cover_url = cover_url.strip()
                s.title = title.strip()
                s.author = author.strip()
                s.detail_item = id.strip()
                s.price = price.strip()
                s.drm = SearchResult.DRM_UNLOCKED
                s.formats = formats.upper()

                yield s
