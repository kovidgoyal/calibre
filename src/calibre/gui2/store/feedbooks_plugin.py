# -*- coding: utf-8 -*-

__license__ = 'GPL 3'
__copyright__ = '2011, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

import urllib2
from contextlib import closing

from lxml import html

from calibre import browser
from calibre.customize import StorePlugin
from calibre.gui2.store.search_result import SearchResult

class FeedbooksStore(StorePlugin):
    
    name           = 'Feedbooks'
    description    = _('Read anywhere.')
    
        
    def open(self, gui, parent=None, detail_item=None):
        from calibre.gui2.store.web_store_dialog import WebStoreDialog
        d = WebStoreDialog(gui, 'http://m.feedbooks.com/', parent, detail_item)
        d.setWindowTitle(self.name)
        d.set_tags(self.name + ',' + _('store'))
        d = d.exec_()

    def search(self, query, max_results=10, timeout=60):
        url = 'http://m.feedbooks.com/search?query=' + urllib2.quote(query)
        
        br = browser()
        
        counter = max_results
        with closing(br.open(url, timeout=timeout)) as f:
            doc = html.fromstring(f.read())
            for data in doc.xpath('//ul[@class="m-list"]//li'):
                if counter <= 0:
                    break
                data = html.fromstring(html.tostring(data))
                
                id = ''
                id_a = data.xpath('//a[@class="buy"]')
                if id_a:
                    id = id_a[0].get('href', None)
                    id = id.split('/')[-2]
                    id = '/item/' + id
                else:
                    id_a = data.xpath('//a[@class="download"]')
                    if id_a:
                        id = id_a[0].get('href', None)
                        id = id.split('/')[-1]
                        id = id.split('.')[0]
                        id = '/book/' + id
                if not id:
                    continue
                
                title = ''.join(data.xpath('//h5/a/text()'))
                author = ''.join(data.xpath('//h6/a/text()'))
                price = ''.join(data.xpath('//a[@class="buy"]/text()'))
                if not price:
                    price = '$0.00'
                cover_url = ''
                cover_url_img =  data.xpath('//img')
                if cover_url_img:
                    cover_url = cover_url_img[0].get('src')
                    cover_url.split('?')[0]
                
                counter -= 1
                
                s = SearchResult()
                s.cover_url = cover_url
                s.title = title.strip()
                s.author = author.strip()
                s.price = price.replace(' ', '').strip()
                s.detail_item = id.strip()
                
                yield s
