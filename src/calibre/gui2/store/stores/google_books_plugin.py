# -*- coding: utf-8 -*-

from __future__ import (unicode_literals, division, absolute_import, print_function)

__license__ = 'GPL 3'
__copyright__ = '2011, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

import random
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

class GoogleBooksStore(BasicStoreConfig, StorePlugin):

    def open(self, parent=None, detail_item=None, external=False):
        aff_id = {
            'lid': '41000000033185143',
            'pubid': '21000000000352219',
            'ganpub': 'k352219',
            'ganclk': 'GOOG_1335334761',
        }
        # Use Kovid's affiliate id 30% of the time.
        if random.randint(1, 10) in (1, 2, 3):
            aff_id = {
                'lid': '41000000031855266',
                'pubid': '21000000000352583',
                'ganpub': 'k352583',
                'ganclk': 'GOOG_1335335464',
            }
            
        url = 'http://gan.doubleclick.net/gan_click?lid=%(lid)s&pubid=%(pubid)s' % aff_id
        if detail_item:
            detail_item += '&ganpub=%(ganpub)s&ganclk=%(ganclk)s' % aff_id

        if external or self.config.get('open_external', False):
            open_url(QUrl(url_slash_cleaner(detail_item if detail_item else url)))
        else:
            d = WebStoreDialog(self.gui, url, parent, detail_item)
            d.setWindowTitle(self.name)
            d.set_tags(self.config.get('tags', ''))
            d.exec_()

    def search(self, query, max_results=10, timeout=60):
        url = 'http://www.google.com/search?tbm=bks&q=' + urllib.quote_plus(query)
        
        br = browser()
        
        counter = max_results
        with closing(br.open(url, timeout=timeout)) as f:
            doc = html.fromstring(f.read())
            for data in doc.xpath('//ol/li'):
                if counter <= 0:
                    break

                id = ''.join(data.xpath('.//h3/a/@href'))
                if not id:
                    continue

                title = ''.join(data.xpath('.//h3/a//text()'))
                authors = data.xpath('.//span[contains(@class, "f")]//a//text()')
                while authors and authors[-1].strip().lower() in ('preview', 'read', 'more editions'):
                    authors = authors[:-1]
                if not authors:
                    continue
                author = ', '.join(authors)

                counter -= 1
                
                s = SearchResult()
                s.title = title.strip()
                s.author = author.strip()
                s.detail_item = id.strip()
                s.drm = SearchResult.DRM_UNKNOWN
                
                yield s
                
    def get_details(self, search_result, timeout):
        br = browser()
        with closing(br.open(search_result.detail_item, timeout=timeout)) as nf:
            doc = html.fromstring(nf.read())
            
            search_result.cover_url = ''.join(doc.xpath('//div[@class="sidebarcover"]//img/@src'))
            
            # Try to get the set price.
            price = ''.join(doc.xpath('//div[@id="gb-get-book-container"]//a/text()'))
            if 'read' in price.lower():
                price = 'Unknown'
            elif 'free' in price.lower() or not price.strip():
                price = '$0.00'
            elif '-' in price:
                a, b, price = price.partition(' - ')
            search_result.price = price.strip()
            
            search_result.formats = ', '.join(doc.xpath('//div[contains(@class, "download-panel-div")]//a/text()')).upper()
            if not search_result.formats:
                search_result.formats = _('Unknown')
            
        return True

