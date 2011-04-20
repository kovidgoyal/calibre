# -*- coding: utf-8 -*-

from __future__ import (unicode_literals, division, absolute_import, print_function)

__license__ = 'GPL 3'
__copyright__ = '2011, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

import random
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

class EHarlequinStore(BasicStoreConfig, StorePlugin):

    def open(self, parent=None, detail_item=None, external=False):
        settings = self.get_settings()

        m_url = 'http://www.dpbolvw.net/'
        h_click = 'click-4879827-534091'
        d_click = 'click-4879827-10375439'
        # Use Kovid's affiliate id 30% of the time.
        if random.randint(1, 10) in (1, 2, 3):
            h_click = 'click-4913808-534091'
            d_click = 'click-4913808-10375439'

        url = m_url + h_click
        detail_url = None
        if detail_item:
            detail_url = m_url + d_click + detail_item

        if external or settings.get(self.name + '_open_external', False):
            open_url(QUrl(url_slash_cleaner(detail_url if detail_url else url)))
        else:
            d = WebStoreDialog(self.gui, url, parent, detail_url)
            d.setWindowTitle(self.name)
            d.set_tags(settings.get(self.name + '_tags', ''))
            d.exec_()

    def search(self, query, max_results=10, timeout=60):
        url = 'http://ebooks.eharlequin.com/BANGSearch.dll?Type=FullText&FullTextField=All&FullTextCriteria=' + urllib2.quote(query)
        
        br = browser()
        
        counter = max_results
        with closing(br.open(url, timeout=timeout)) as f:
            doc = html.fromstring(f.read())
            for data in doc.xpath('//table[not(.//@class="sidelink")]/tr[.//ul[@id="details"]]'):
                if counter <= 0:
                    break

                id = ''.join(data.xpath('.//ul[@id="details"]/li[@id="title-results"]/a/@href'))
                if not id:
                    continue

                title = ''.join(data.xpath('.//ul[@id="details"]/li[@id="title-results"]/a/text()'))
                author = ''.join(data.xpath('.//ul[@id="details"]/li[@id="author"][1]//a/text()'))
                price = ''.join(data.xpath('.//div[@class="ourprice"]/font/text()'))
                cover_url = ''.join(data.xpath('.//a[@href="%s"]/img/@src' % id))

                with closing(br.open('http://ebooks.eharlequin.com/' + id.strip(), timeout=timeout/4)) as nf:
                    idata = html.fromstring(nf.read())
                    drm = None
                    if idata.xpath('boolean(//div[@class="drm_head"])'):
                        drm = idata.xpath('boolean(//td[contains(., "Copy") and contains(., "not")])')

                counter -= 1

                s = SearchResult()
                s.cover_url = cover_url
                s.title = title.strip()
                s.author = author.strip()
                s.price = price.strip()
                s.detail_item = '?url=http://ebooks.eharlequin.com/' + id.strip()
                s.drm = drm
                
                yield s
