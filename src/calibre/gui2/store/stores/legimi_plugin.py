# -*- coding: utf-8 -*-

from __future__ import (unicode_literals, division, absolute_import, print_function)

__license__ = 'GPL 3'
__copyright__ = '2011, Tomasz Długosz <tomek3d@gmail.com>'
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

class LegimiStore(BasicStoreConfig, StorePlugin):

    def open(self, parent=None, detail_item=None, external=False):
        
        plain_url = 'http://www.legimi.com/pl/ebooki/'
        url = 'https://ssl.afiliant.com/affskrypt,,2f9de2,,11483,,,?u=(' + plain_url + ')'
        detail_url = None

        if detail_item:
            detail_url = 'https://ssl.afiliant.com/affskrypt,,2f9de2,,11483,,,?u=(' + detail_item + ')'

        if external or self.config.get('open_external', False):
            open_url(QUrl(url_slash_cleaner(detail_url if detail_url else url)))
        else:
            d = WebStoreDialog(self.gui, url, parent, detail_url)
            d.setWindowTitle(self.name)
            d.set_tags(self.config.get('tags', ''))
            d.exec_()

    def search(self, query, max_results=10, timeout=60):
        url = 'http://www.legimi.com/pl/ebooki/?szukaj=' + urllib.quote_plus(query)
        
        br = browser()
        drm_pattern = re.compile("zabezpieczona DRM")
        
        counter = max_results
        with closing(br.open(url, timeout=timeout)) as f:
            doc = html.fromstring(f.read())
            for data in doc.xpath('//div[@id="listBooks"]/div'):
                if counter <= 0:
                    break
                
                id = ''.join(data.xpath('.//a[@class="plainLink"]/@href'))
                if not id:
                    continue

                cover_url = ''.join(data.xpath('.//img[1]/@src'))
                title = ''.join(data.xpath('.//span[@class="bookListTitle ellipsis"]/text()'))
                author = ''.join(data.xpath('.//span[@class="bookListAuthor ellipsis"]/text()'))
                author = re.sub(',','',author)
                author = re.sub(';',',',author)
                price = ''.join(data.xpath('.//div[@class="bookListPrice"]/span/text()'))
                formats = []
                with closing(br.open(id.strip(), timeout=timeout/4)) as nf:
                    idata = html.fromstring(nf.read())
                    formatlist = idata.xpath('.//div[@id="fullBookFormats"]//span[@class="bookFormat"]/text()')
                    for x in formatlist:
                        if x.strip() not in formats:
                            formats.append(x.strip())
                    drm = drm_pattern.search(''.join(idata.xpath('.//div[@id="fullBookFormats"]/p/text()')))

                counter -= 1
                
                s = SearchResult()
                s.cover_url = 'http://www.legimi.com/' + cover_url
                s.title = title.strip()
                s.author = author.strip()
                s.price = price
                s.detail_item = 'http://www.legimi.com/' + id.strip()
                s.formats = ', '.join(formats)
                s.drm = SearchResult.DRM_LOCKED if drm else SearchResult.DRM_UNLOCKED
                
                yield s
