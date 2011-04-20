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

class EbookscomStore(BasicStoreConfig, StorePlugin):

    def open(self, parent=None, detail_item=None, external=False):
        settings = self.get_settings()

        m_url = 'http://www.dpbolvw.net/'
        h_click = 'click-4879827-10364500'
        d_click = 'click-4879827-10281551'
        # Use Kovid's affiliate id 30% of the time.
        if random.randint(1, 10) in (1, 2, 3):
            h_click = 'click-4913808-10364500'
            d_click = 'click-4913808-10281551'
        
        url = m_url + h_click
        detail_url = None
        if detail_item:
            detail_url = m_url + d_click + detail_item

        if external or settings.get(self.name + '_open_external', False):
            open_url(QUrl(url_slash_cleaner(detail_url if detail_url else url)))
        else:
            d = WebStoreDialog(self.gui, url, parent, detail_url)
            d.setWindowTitle(self.name)
            d.set_tags(settings.get(self.name + '_tags', ''))
            d.exec_()

    def search(self, query, max_results=10, timeout=60):
        url = 'http://www.ebooks.com/SearchApp/SearchResults.net?term=' + urllib2.quote(query)
        
        br = browser()
        
        counter = max_results
        with closing(br.open(url, timeout=timeout)) as f:
            doc = html.fromstring(f.read())
            for data in doc.xpath('//div[@class="book_a" or @class="book_b"]'):
                if counter <= 0:
                    break

                id = ''.join(data.xpath('.//a[1]/@href'))
                id = id.split('=')[-1]
                if not id:
                    continue

                price = ''
                with closing(br.open('http://www.ebooks.com/ebooks/book_display.asp?IID=' + id.strip(), timeout=timeout)) as fp:
                    pdoc = html.fromstring(fp.read())
                    pdata = pdoc.xpath('//table[@class="price"]/tr/td/text()')
                    if len(pdata) >= 2:
                        price = pdata[1]
                    drm = False
                    for sec in ('Printing', 'Copying', 'Lending'):
                        if pdoc.xpath('boolean(//div[@class="formatTableInner"]//table//tr[contains(th, "%s") and contains(td, "Off")])' % sec):
                            drm = True
                            break
                if not price:
                    continue
                
                cover_url = ''.join(data.xpath('.//img[1]/@src'))
                
                title = ''
                author = ''
                heading_a = data.xpath('.//a[1]/text()')
                if heading_a:
                    title = heading_a[0]
                if len(heading_a) >= 2:
                    author = heading_a[1]

                counter -= 1
                
                s = SearchResult()
                s.cover_url = cover_url
                s.title = title.strip()
                s.author = author.strip()
                s.price = price.strip()
                s.detail_item = '?url=http://www.ebooks.com/cj.asp?IID=' + id.strip() + '&cjsku=' + id.strip()
                s.drm = drm
                
                yield s
