# -*- coding: utf-8 -*-

from __future__ import (unicode_literals, division, absolute_import, print_function)

__license__ = 'GPL 3'
__copyright__ = '2011, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

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

class GutenbergStore(BasicStoreConfig, StorePlugin):
        
    def open(self, parent=None, detail_item=None, external=False):
        url = 'http://m.gutenberg.org/'
        ext_url = 'http://gutenberg.org/'

        if external or self.config.get('open_external', False):
            if detail_item:
                ext_url = ext_url + detail_item
            open_url(QUrl(url_slash_cleaner(ext_url)))
        else:
            detail_url = None
            if detail_item:
                detail_url = url + detail_item
            d = WebStoreDialog(self.gui, url, parent, detail_url)
            d.setWindowTitle(self.name)
            d.set_tags(self.config.get('tags', ''))
            d.exec_()

    def search(self, query, max_results=10, timeout=60):
        # Gutenberg's website does not allow searching both author and title.
        # Using a google search so we can search on both fields at once.
        url = 'http://www.google.com/xhtml?q=site:gutenberg.org+' + urllib.quote_plus(query)
        
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
                
                url_a = html.fromstring(html.tostring(url_a))
                heading = ''.join(url_a.xpath('//text()'))
                title, _, author = heading.rpartition('by ')
                author = author.split('-')[0]
                price = '$0.00'
                
                counter -= 1
                
                s = SearchResult()
                s.cover_url = ''
                s.title = title.strip()
                s.author = author.strip()
                s.price = price.strip()
                s.detail_item = '/ebooks/' + id.strip()
                s.drm = SearchResult.DRM_UNLOCKED
                
                yield s

    def get_details(self, search_result, timeout):
        url = 'http://m.gutenberg.org/'
        
        br = browser()
        with closing(br.open(url + search_result.detail_item, timeout=timeout)) as nf:
            idata = html.fromstring(nf.read())
            search_result.formats = ', '.join(idata.xpath('//a[@type!="application/atom+xml"]//span[@class="title"]/text()'))
        return True