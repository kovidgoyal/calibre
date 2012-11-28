# -*- coding: utf-8 -*-

from __future__ import (unicode_literals, division, absolute_import, print_function)

__license__ = 'GPL 3'
__copyright__ = '2012, Tomasz Długosz <tomek3d@gmail.com>'
__docformat__ = 'restructuredtext en'

import re
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

class PublioStore(BasicStoreConfig, StorePlugin):

    def open(self, parent=None, detail_item=None, external=False):
        google_analytics = '?utm_source=tdcalibre&utm_medium=calibre'
        url = 'http://www.publio.pl/e-booki.html' + google_analytics

        if external or self.config.get('open_external', False):
            open_url(QUrl(url_slash_cleaner((detail_item + google_analytics) if detail_item else url)))
        else:
            d = WebStoreDialog(self.gui, url, parent, detail_item)
            d.setWindowTitle(self.name)
            d.set_tags(self.config.get('tags', ''))
            d.exec_()

    def search(self, query, max_results=20, timeout=60):

        br = browser()

        counter = max_results
        page = 1
        while counter:
            with closing(br.open('http://www.publio.pl/e-booki,strona' + str(page) + '.html?q=' + urllib.quote(query), timeout=timeout)) as f:
                doc = html.fromstring(f.read())
                for data in doc.xpath('//div[@class="item"]'):
                    if counter <= 0:
                        break

                    id = ''.join(data.xpath('.//div[@class="img"]/a/@href'))
                    if not id:
                        continue

                    cover_url = ''.join(data.xpath('.//div[@class="img"]/a/img/@data-original'))
                    # TODO: fix highlight handling
                    title = ''.join(data.xpath('.//div[@class="desc"]/h4/a/text()'))
                    title2 = ''.join(data.xpath('.//div[@class="desc"]/h5/a/text()'))
                    if title2:
                        title = title + '. ' + title2
                    if (''.join(data.xpath('./div[@class="desc"]/div[@class="detailShortList"]/div[last()]/span/text()')).strip() == "Seria:"):
                        # TODO: fix highlight handling
                        series = ''.join(data.xpath('./div[@class="desc"]/div[@class="detailShortList"]/div[last()]/a/@title'))
                        title = title + ' (seria ' + series + ')'
                    author = ', '.join(data.xpath('./div[@class="desc"]/div[@class="detailShortList"]/div[@class="row"][1]/a/@title'))
                    price = ''.join(data.xpath('.//div[@class="priceBoxContener "]/div/ins/text()'))
                    if not price:
                        price = ''.join(data.xpath('.//div[@class="priceBoxContener "]/div/text()'))
                    formats = ', '.join(data.xpath('.//div[@class="formats"]/a/img/@alt'))

                    counter -= 1

                    s = SearchResult()
                    s.cover_url = 'http://www.publio.pl' + cover_url 
                    s.title = title.strip()
                    s.author = author
                    s.price = price
                    s.detail_item = 'http://www.publio.pl' + id.strip()
                    s.drm = SearchResult.DRM_LOCKED if 'DRM' in formats else SearchResult.DRM_UNLOCKED
                    s.formats = formats.replace(' DRM','').strip()

                    yield s
                if not doc.xpath('boolean(//a[@class="next"])'):
                    break
                page+=1
