# -*- coding: utf-8 -*-

from __future__ import (unicode_literals, division, absolute_import, print_function)

__license__ = 'GPL 3'
__copyright__ = '2011, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

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

class BeWriteStore(BasicStoreConfig, StorePlugin):

    def open(self, parent=None, detail_item=None, external=False):
        settings = self.get_settings()
        url = 'http://www.bewrite.net/mm5/merchant.mvc?Screen=SFNT'

        if external or settings.get(self.name + '_open_external', False):
            if detail_item:
                url = url + detail_item
            open_url(QUrl(url_slash_cleaner(url)))
        else:
            detail_url = None
            if detail_item:
                detail_url = url + detail_item
            d = WebStoreDialog(self.gui, url, parent, detail_url)
            d.setWindowTitle(self.name)
            d.set_tags(settings.get(self.name + '_tags', ''))
            d.exec_()

    def search(self, query, max_results=10, timeout=60):
        url = 'http://www.bewrite.net/mm5/merchant.mvc?Search_Code=B&Screen=SRCH&Search=' + urllib2.quote(query)

        br = browser()

        counter = max_results
        with closing(br.open(url, timeout=timeout)) as f:
            doc = html.fromstring(f.read())
            for data in doc.xpath('//div[@id="content"]//table/tr[position() > 1]'):
                if counter <= 0:
                    break

                id = ''.join(data.xpath('.//a/@href'))
                if not id:
                    continue

                heading = ''.join(data.xpath('./td[2]//text()'))
                title, q, author = heading.partition('by ')
                cover_url = ''
                price = ''

                with closing(br.open(id.strip(), timeout=timeout/4)) as nf:
                    idata = html.fromstring(nf.read())
                    price = ''.join(idata.xpath('//div[@id="content"]//td[contains(text(), "ePub")]/text()'))
                    price = '$' + price.split('$')[-1]
                    cover_img = idata.xpath('//div[@id="content"]//img[1]/@src')
                    if cover_img:
                        cover_url = 'http://www.bewrite.net/mm5/' + cover_img[0]

                counter -= 1

                s = SearchResult()
                s.cover_url = cover_url.strip()
                s.title = title.strip()
                s.author = author.strip()
                s.price = price.strip()
                s.detail_item = id.strip()
                s.drm = False

                yield s
