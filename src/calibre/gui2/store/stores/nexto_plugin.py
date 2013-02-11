# -*- coding: utf-8 -*-

from __future__ import (unicode_literals, division, absolute_import, print_function)
store_version = 1 # Needed for dynamic plugin loading

__license__ = 'GPL 3'
__copyright__ = '2011-2012, Tomasz Długosz <tomek3d@gmail.com>'
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

class NextoStore(BasicStoreConfig, StorePlugin):

    def open(self, parent=None, detail_item=None, external=False):
        pid = '155711'

        url = 'http://www.nexto.pl/ebooki_c1015.xml'
        detail_url = None

        if detail_item:
            book_id = re.search(r'p[0-9]*\.xml\Z', detail_item)
            book_id = book_id.group(0).replace('.xml','').replace('p','')
            if book_id:
                detail_url = 'http://www.nexto.pl/rf/pr?p=' + book_id + '&pid=' + pid

        if external or self.config.get('open_external', False):
            open_url(QUrl(url_slash_cleaner(detail_url if detail_url else url)))
        else:
            d = WebStoreDialog(self.gui, url, parent, detail_url)
            d.setWindowTitle(self.name)
            d.set_tags(self.config.get('tags', ''))
            d.exec_()

    def search(self, query, max_results=10, timeout=60):
        url = 'http://www.nexto.pl/szukaj.xml?search-clause=' + urllib.quote_plus(query) + '&scid=1015'

        br = browser()
        offset=0

        counter = max_results

        while counter:
            with closing(br.open(url + '&_offset=' + str(offset), timeout=timeout)) as f:
                doc = html.fromstring(f.read())
                for data in doc.xpath('//ul[@class="productslist"]/li'):
                    if counter <= 0:
                        break

                    id = ''.join(data.xpath('.//div[@class="cover_container"]/a[1]/@href'))
                    if not id:
                        continue

                    price = ''.join(data.xpath('.//strong[@class="nprice"]/text()'))

                    cover_url = ''.join(data.xpath('.//img[@class="cover"]/@src'))
                    cover_url = re.sub(r'%2F', '/', cover_url)
                    cover_url = re.sub(r'\widthMax=120&heightMax=200', 'widthMax=64&heightMax=64', cover_url)
                    title = ''.join(data.xpath('.//a[@class="title"]/text()'))
                    title = re.sub(r' - ebook$', '', title)
                    formats = ', '.join(data.xpath('.//ul[@class="formats_available"]/li//b/text()'))
                    DrmFree = re.search(r'znak', formats)
                    formats = re.sub(r'\ ?\(.+?\)', '', formats)

                    author = ''
                    with closing(br.open('http://www.nexto.pl/' + id.strip(), timeout=timeout/4)) as nf:
                        idata = html.fromstring(nf.read())
                        author = ', '.join(idata.xpath('//div[@class="basic_data"]/p[1]/b/a/text()'))

                    counter -= 1

                    s = SearchResult()
                    s.cover_url = 'http://www.nexto.pl' + cover_url
                    s.title = title.strip()
                    s.author = author.strip()
                    s.price = price
                    s.detail_item = id.strip()
                    s.drm = SearchResult.DRM_UNLOCKED if DrmFree else SearchResult.DRM_LOCKED
                    s.formats = formats.upper().strip()

                    yield s
                if not doc.xpath('//div[@class="listnavigator"]//a[@class="next"]'):
                    break
            offset+=10
