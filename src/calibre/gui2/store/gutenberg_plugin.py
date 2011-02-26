# -*- coding: utf-8 -*-

__license__ = 'GPL 3'
__copyright__ = '2011, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

import urllib2
from contextlib import closing

from lxml import html

from calibre import browser
from calibre.customize import StorePlugin

class GutenbergStore(StorePlugin):
    
    name           = 'Project Gutenberg'
    description    = _('The first producer of free ebooks.')
    
        
    def open(self, gui, parent=None, start_item=None):
        from calibre.gui2.store.web_store_dialog import WebStoreDialog
        d = WebStoreDialog(gui, 'http://m.gutenberg.org/', parent, start_item)
        d.setWindowTitle('Free eBooks by Project Gutenberg')
        d = d.exec_()

    def search(self, query, max_results=10, timeout=60):
        # Gutenberg's website does not allow searching both author and title.
        # Using a google search so we can search on both fields at once.
        url = 'http://www.google.com/xhtml?q=site:gutenberg.org+' + urllib2.quote(query)
        
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
                    url = url.split('u=')[-1].split('&')[0]
                if '/ebooks/' not in url:
                    continue
                id = url.split('/')[-1]
                
                heading = ''.join(url_a.xpath('text()'))
                title, _, author = heading.partition('by')
                author = author.split('-')[0]
                price = '$0.00'
                
                counter -= 1
                yield ('', title.strip(), author.strip(), price.strip(), '/ebooks/' + id.strip())
