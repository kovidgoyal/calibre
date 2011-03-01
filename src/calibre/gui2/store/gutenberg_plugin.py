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

class GutenbergStore(StorePlugin):
    
    name           = 'Project Gutenberg'
    description    = _('The first producer of free ebooks.')
        
    def open(self, gui, parent=None, detail_item=None):
        settings = self.get_settings()
        from calibre.gui2.store.web_store_dialog import WebStoreDialog
        d = WebStoreDialog(gui, 'http://m.gutenberg.org/', parent, detail_item)
        d.setWindowTitle(self.name)
        d.set_tags(settings.get(self.name + '_tags', ''))
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
                title, _, author = heading.partition('by ')
                author = author.split('-')[0]
                price = '$0.00'
                
                counter -= 1
                
                s = SearchResult()
                s.cover_url = ''
                s.title = title.strip()
                s.author = author.strip()
                s.price = price.strip()
                s.detail_item = '/ebooks/' + id.strip()
                
                yield s

    def customization_help(self, gui=False):
        return 'Customize the behavior of this store.'

    def config_widget(self):
        from calibre.gui2.store.basic_config_widget import BasicStoreConfigWidget
        return BasicStoreConfigWidget(self)

    def save_settings(self, config_widget):
        from calibre.gui2.store.basic_config_widget import save_settings
        save_settings(config_widget)

    def get_settings(self):
        from calibre.gui2 import gprefs
        settings = {}
        
        settings[self.name + '_tags'] = gprefs.get(self.name + '_tags', self.name + ', store, download')
        
        return settings
