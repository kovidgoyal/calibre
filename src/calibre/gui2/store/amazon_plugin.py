# -*- coding: utf-8 -*-

__license__ = 'GPL 3'
__copyright__ = '2011, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

import re
import urllib2
from contextlib import closing

from lxml import html

from calibre import browser
from calibre.customize import StorePlugin
from calibre.gui2.store.search_result import SearchResult

class AmazonKindleStore(StorePlugin):
    
    name           = 'Amazon Kindle'
    description    = _('Buy Kindle books from Amazon')
    
    ASTORE_URL = 'http://astore.amazon.com/josbl0e-20/'
    
    def open(self, gui, parent=None, detail_item=None):
        from calibre.gui2.store.web_store_dialog import WebStoreDialog
        d = WebStoreDialog(gui, self.ASTORE_URL, parent, detail_item)
        d.setWindowTitle(self.name)
        d = d.exec_()

    def search(self, query, max_results=10, timeout=60):
        url = 'http://www.amazon.com/s/url=search-alias%3Ddigital-text&field-keywords=' + urllib2.quote(query)
        br = browser()
        
        counter = max_results
        with closing(br.open(url, timeout=timeout)) as f:
            doc = html.fromstring(f.read())
            for data in doc.xpath('//div[@class="productData"]'):
                if counter <= 0:
                    break
                
                # Even though we are searching digital-text only Amazon will still
                # put in results for non Kindle books (author pages). Se we need
                # to explicitly check if the item is a Kindle book and ignore it
                # if it isn't.
                type = ''.join(data.xpath('//span[@class="format"]/text()'))
                if 'kindle' not in type.lower():
                    continue
                
                title = ''.join(data.xpath('div[@class="productTitle"]/a/text()'))
                author = ''.join(data.xpath('div[@class="productTitle"]/span[@class="ptBrand"]/text()'))
                author = author.split('by')[-1]
                price = ''.join(data.xpath('div[@class="newPrice"]/span/text()'))
                
                # We must have an asin otherwise we can't easily reference the
                # book later.
                asin = data.xpath('div[@class="productTitle"]/a[1]')
                if asin:
                    asin = asin[0].get('href', '')
                    m = re.search(r'/dp/(?P<asin>.+?)(/|$)', asin)
                    if m:
                        asin = m.group('asin')
                    else:
                        continue
                    
                    counter -= 1
                    
                    s = SearchResult()
                    s.cover_url = ''
                    s.title = title.strip()
                    s.author = author.strip()
                    s.price = price.strip()
                    s.detail_item = '/detail/' + asin.strip()
                    
                    yield s
