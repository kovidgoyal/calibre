# -*- coding: utf-8 -*-

from __future__ import (unicode_literals, division, absolute_import, print_function)

__license__ = 'GPL 3'
__copyright__ = '2011, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

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
        
class ManyBooksStore(BasicStoreConfig, StorePlugin):

    def open(self, parent=None, detail_item=None, external=False):
        url = 'http://manybooks.net/'

        detail_url = None
        if detail_item:
            detail_url = url + detail_item
        
        if external or self.config.get('open_external', False):
            open_url(QUrl(url_slash_cleaner(detail_url if detail_url else url)))
        else:
            d = WebStoreDialog(self.gui, url, parent, detail_url)
            d.setWindowTitle(self.name)
            d.set_tags(self.config.get('tags', ''))
            d.exec_()

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
                id = id.strip()
                
                url_a = html.fromstring(html.tostring(url_a))
                heading = ''.join(url_a.xpath('//text()'))
                title, _, author = heading.rpartition('by ')
                author = author.split('-')[0]
                price = '$0.00'
                
                cover_url = ''
                mo = re.match('^\D+', id)
                if mo:
                    cover_name = mo.group()
                    cover_name = cover_name.replace('etext', '')
                    cover_id = id.split('.')[0]
                    cover_url = 'http://manybooks_images.s3.amazonaws.com/original_covers/' + id[0] + '/' + cover_name + '/' + cover_id + '-thumb.jpg' 

                counter -= 1
                
                s = SearchResult()
                s.cover_url = cover_url
                s.title = title.strip()
                s.author = author.strip()
                s.price = price.strip()
                s.detail_item = '/titles/' + id
                s.drm = SearchResult.DRM_UNLOCKED
                s.formts = 'EPUB, PDB (eReader, PalmDoc, zTXT, Plucker, iSilo), FB2, ZIP, AZW, MOBI, PRC, LIT, PKG, PDF, TXT, RB, RTF, LRF, TCR, JAR'
                
                yield s
