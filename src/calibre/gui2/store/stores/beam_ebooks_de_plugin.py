# -*- coding: utf-8 -*-

from __future__ import (unicode_literals, division, absolute_import, print_function)
store_version = 3  # Needed for dynamic plugin loading

__license__ = 'GPL 3'
__copyright__ = '2011, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

import urllib2
from contextlib import closing

from lxml import html

from PyQt5.Qt import QUrl

from calibre import browser
from calibre.gui2 import open_url
from calibre.gui2.store import StorePlugin
from calibre.gui2.store.basic_config import BasicStoreConfig
from calibre.gui2.store.search_result import SearchResult
from calibre.gui2.store.web_store_dialog import WebStoreDialog


class BeamEBooksDEStore(BasicStoreConfig, StorePlugin):

    def open(self, parent=None, detail_item=None, external=False):
        url = 'http://klick.affiliwelt.net/klick.php?bannerid=10072&pid=32307&prid=908'
        url_details = ('http://klick.affiliwelt.net/klick.php?'
                       'bannerid=66830&pid=32307&prid=908&'
                       'url={0}')

        if external or self.config.get('open_external', False):
            if detail_item:
                url = url_details.format(detail_item)
            open_url(QUrl(url))
        else:
            detail_url = None
            if detail_item:
                detail_url = url_details.format(detail_item)
            d = WebStoreDialog(self.gui, url, parent, detail_url)
            d.setWindowTitle(self.name)
            d.set_tags(self.config.get('tags', ''))
            d.exec_()

    def search(self, query, max_results=10, timeout=60):
        url = 'https://www.beam-shop.de/search?saltFieldLimitation=all&sSearch=' + urllib2.quote(query)
        print(url)
        br = browser()

        counter = max_results
        with closing(br.open(url, timeout=timeout)) as f:
            doc = html.fromstring(f.read())
            for data in doc.xpath('//div[contains(@class, "product--box")]'):
                if counter <= 0:
                    break

                id_ = ''.join(data.xpath('./div/div[contains(@class, "product--info")]/a/@href')).strip()
                if not id_:
                    continue
                cover_url = ''.join(data.xpath('./div/div[contains(@class, "product--info")]/a//img/@srcset'))
                if cover_url:
                    cover_url = cover_url.split(',')[0].strip()
                author = data.xpath('.//a[@class="product--author"]/text()')[0].strip()
                title = data.xpath('.//a[@class="product--title"]/text()')[0].strip()
                price = data.xpath('.//div[@class="product--price"]/span/text()')[0].strip()
                counter -= 1

                s = SearchResult()
                s.cover_url = cover_url
                s.title = title.strip()
                s.author = author.strip()
                s.price = price
                s.drm = SearchResult.DRM_UNLOCKED
                s.detail_item = id_
#                 s.formats = None
                yield s

