# -*- coding: utf-8 -*-

from __future__ import (unicode_literals, division, absolute_import, print_function)

__license__ = 'GPL 3'
__copyright__ = '2011, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

import random
import re
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

class SmashwordsStore(BasicStoreConfig, StorePlugin):

    def open(self, parent=None, detail_item=None, external=False):
        url = 'http://www.smashwords.com/'

        aff_id = '?ref=usernone'
        # Use Kovid's affiliate id 30% of the time.
        if random.randint(1, 10) in (1, 2, 3):
            aff_id = '?ref=kovidgoyal'

        detail_url = None
        if detail_item:
            detail_url = url + detail_item + aff_id
        url = url + aff_id
            
        if external or self.config.get('open_external', False):
            open_url(QUrl(url_slash_cleaner(detail_url if detail_url else url)))
        else:
            d = WebStoreDialog(self.gui, url, parent, detail_url)
            d.setWindowTitle(self.name)
            d.set_tags(self.config.get('tags', ''))
            d.exec_()

    def search(self, query, max_results=10, timeout=60):
        url = 'http://www.smashwords.com/books/search?query=' + urllib2.quote(query)
        
        br = browser()
        
        counter = max_results
        with closing(br.open(url, timeout=timeout)) as f:
            doc = html.fromstring(f.read())
            for data in doc.xpath('//div[@id="pageCenterContent"]//div[@class="bookCoverImg"]'):
                if counter <= 0:
                    break
                data = html.fromstring(html.tostring(data))
                
                id = None
                id_a = data.xpath('//a[@class="bookTitle"]')
                if id_a:
                    id = id_a[0].get('href', None)
                    if id:
                        id = id.split('/')[-1]
                if not id:
                    continue
                
                cover_url = ''
                c_url = data.get('style', None)
                if c_url:
                    mo = re.search(r'http://[^\'"]+', c_url)
                    if mo:
                        cover_url = mo.group()
                
                title = ''.join(data.xpath('//a[@class="bookTitle"]/text()'))
                subnote = ''.join(data.xpath('//span[@class="subnote"]/text()'))
                author = ''.join(data.xpath('//span[@class="subnote"]/a/text()'))
                if '$' in subnote:
                    price = subnote.partition('$')[2]
                    price = price.split(u'\xa0')[0]
                    price = '$' + price
                else:
                    price = '$0.00'

                counter -= 1
                
                s = SearchResult()
                s.cover_url = cover_url
                s.title = title.strip()
                s.author = author.strip()
                s.price = price.strip()
                s.detail_item = '/books/view/' + id.strip()
                s.drm = SearchResult.DRM_UNLOCKED
                
                yield s

    def get_details(self, search_result, timeout):
        url = 'http://www.smashwords.com/'
        
        br = browser()
        with closing(br.open(url + search_result.detail_item, timeout=timeout)) as nf:
            idata = html.fromstring(nf.read())
            search_result.formats = ', '.join(list(set(idata.xpath('//td//b//text()'))))
        return True
