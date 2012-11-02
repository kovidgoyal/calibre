# -*- coding: utf-8 -*-

from __future__ import (unicode_literals, division, absolute_import, print_function)

__license__ = 'GPL 3'
__copyright__ = '2011, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

import random
import urllib2
from contextlib import closing

from lxml import html

from PyQt4.Qt import QUrl

from calibre import browser, url_slash_cleaner
from calibre.gui2 import open_url
from calibre.gui2.store import StorePlugin
from calibre.gui2.store.basic_config import BasicStoreConfig
from calibre.gui2.store.search_result import SearchResult
from calibre.gui2.store.web_store_dialog import WebStoreDialog

class KoboStore(BasicStoreConfig, StorePlugin):

    def open(self, parent=None, detail_item=None, external=False):
        pub_id = 'sHa5EXvYOwA'
        # Use Kovid's affiliate id 30% of the time.
        if random.randint(1, 10) in (1, 2, 3):
            pub_id = '0dsO3kDu/AU'

        murl = 'http://click.linksynergy.com/fs-bin/click?id=%s&offerid=268429.4&type=3&subid=0' % pub_id

        if detail_item:
            purl = 'http://click.linksynergy.com/fs-bin/click?id=%s&subid=&offerid=268429.1&type=10&tmpid=9310&RD_PARM1=%s' % urllib.quote_plus(pub_id, detail_item) url = purl
        else:
            purl = None
            url = murl

        print(url)

        if external or self.config.get('open_external', False):
            open_url(QUrl(url_slash_cleaner(detail_url if detail_url else url)))
        else:
            d = WebStoreDialog(self.gui, url, parent, detail_url)
             d.setWindowTitle(self.name)
             d.set_tags(self.config.get('tags', ''))
             d.exec_()

    def search(self, query, max_results=10, timeout=60):
        url = 'http://www.kobobooks.com/search/search.html?q=' + urllib2.quote(query)

        br = browser()

        counter = max_results
        with closing(br.open(url, timeout=timeout)) as f:
            doc = html.fromstring(f.read())
            for data in doc.xpath('//ul[@class="SCShortCoverList"]/li'):
                if counter <= 0:
                    break

                id = ''.join(data.xpath('.//div[@class="SearchImageContainer"]/a[1]/@href'))
                if not id:
                    continue

                price = ''.join(data.xpath('.//span[@class="OurPrice"]/strong/text()'))
                if not price:
                    price = '$0.00'

                cover_url = ''.join(data.xpath('.//div[@class="SearchImageContainer"]//img[1]/@src'))

                title = ''.join(data.xpath('.//div[@class="SCItemHeader"]/h1/a[1]/text()'))
                author = ', '.join(data.xpath('.//div[@class="SCItemSummary"]//span//a/text()'))
                drm = data.xpath('boolean(.//span[@class="SCAvailibilityFormatsText" and not(contains(text(), "DRM-Free"))])')

                counter -= 1

                s = SearchResult()
                s.cover_url = cover_url
                s.title = title.strip()
                s.author = author.strip()
                s.price = price.strip()
                s.detail_item = 'http://www.kobobooks.com/' + id.strip()
                s.drm = SearchResult.DRM_LOCKED if drm else SearchResult.DRM_UNLOCKED
                s.formats = 'EPUB'

                yield s
