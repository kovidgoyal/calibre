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

class ManyBooksStore(StorePlugin):
    
    name           = 'ManyBooks'
    description    = _('The best ebooks at the best price: free!.')
    
        
    def open(self, gui, parent=None, detail_item=None):
        from calibre.gui2.store.web_store_dialog import WebStoreDialog
        d = WebStoreDialog(gui, 'http://manybooks.net/', parent, detail_item)
        d.setWindowTitle('ManyBooks')
        d = d.exec_()

    def search(self, query, max_results=10, timeout=60):
        # ManyBooks website separates results for title and author.
        # It also doesn't do a clear job of references authors and
        # secondary titles. Google is also faster.
        # Using a google search so we can search on both fields at once.
        url = 'http://www.google.com/xhtml?q=site:manybooks.net+' + urllib2.quote(query)
        
        br = browser()
        
        counter = max_results
        with closing(br.open(url, timeout=timeout)) as f:
            doc = html.fromstring(f.read())
            for data in doc.xpath('//div[@class="edewpi"]//div[@class="r ld"]'):
                if counter <= 0:
                    break
                
                url = ''
                url_a = data.xpath('div[@class="jd"]/a')
                if url_a:
                    url_a = url_a[0]
                    url = url_a.get('href', None)
                if url:
                    url = url.split('u=')[-1][:-2]
                if '/titles/' not in url:
                    continue
                id = url.split('/')[-1]
                
                heading = ''.join(url_a.xpath('text()'))
                title, _, author = heading.partition('by')
                author = author.split('-')[0]
                price = '$0.00'
                
                counter -= 1
                
                s = SearchResult()
                s.cover_url = ''
                s.title = title.strip()
                s.author = author.strip()
                s.price = price.strip()
                s.detail_item = '/titles/' + id.strip()
                
                yield s
