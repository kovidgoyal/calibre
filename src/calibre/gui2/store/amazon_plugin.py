# -*- coding: utf-8 -*-

__license__ = 'GPL 3'
__copyright__ = '2011, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

import re
import urllib2
from contextlib import closing

from lxml import html

from PyQt4.Qt import QUrl

from calibre import browser
from calibre.customize import StorePlugin
from calibre.gui2.store.search_result import SearchResult

class AmazonKindleStore(StorePlugin):
    
    name           = 'Amazon Kindle'
    description    = _('Buy Kindle books from Amazon')
    
    def open(self, gui, parent=None, detail_item=None):
        from calibre.gui2 import open_url
        aff_id = {'tag': 'josbl0e-cpb-20'}
        store_link = 'http://www.amazon.com/Kindle-eBooks/b/?ie=UTF&node=1286228011&ref_=%(tag)s&ref=%(tag)s&tag=%(tag)s&linkCode=ur2&camp=1789&creative=390957' % aff_id
        if detail_item:
            aff_id['asin'] = detail_item
            store_link = 'http://www.amazon.com/dp/%(asin)s/?tag=%(tag)s' % aff_id
        open_url(QUrl(store_link))

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
                
                # We must have an asin otherwise we can't easily reference the
                # book later.
                asin_href = None
                asin_a = data.xpath('div[@class="productTitle"]/a[1]')
                if asin_a:
                    asin_href = asin_a[0].get('href', '')
                    m = re.search(r'/dp/(?P<asin>.+?)(/|$)', asin_href)
                    if m:
                        asin = m.group('asin')
                    else:
                        continue
                else:
                    continue
                
                cover_url = ''
                if asin_href:
                    cover_img = data.xpath('//div[@class="productImage"]/a[@href="%s"]/img/@src' % asin_href)
                    if cover_img:
                        cover_url = cover_img[0]
                
                title = ''.join(data.xpath('div[@class="productTitle"]/a/text()'))
                author = ''.join(data.xpath('div[@class="productTitle"]/span[@class="ptBrand"]/text()'))
                author = author.split('by')[-1]
                price = ''.join(data.xpath('div[@class="newPrice"]/span/text()'))
                    
                counter -= 1
                
                s = SearchResult()
                s.cover_url = cover_url
                s.title = title.strip()
                s.author = author.strip()
                s.price = price.strip()
                s.detail_item = asin.strip()
                
                yield s
