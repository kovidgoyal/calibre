# -*- coding: utf-8 -*-

from __future__ import (unicode_literals, division, absolute_import, print_function)
store_version = 1 # Needed for dynamic plugin loading

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

class BaenWebScriptionStore(BasicStoreConfig, StorePlugin):

    def open(self, parent=None, detail_item=None, external=False):
        url = 'http://www.baenebooks.com/'

        if external or self.config.get('open_external', False):
            if detail_item:
                url = url + detail_item
            open_url(QUrl(url_slash_cleaner(url)))
        else:
            detail_url = None
            if detail_item:
                detail_url = url + detail_item
            d = WebStoreDialog(self.gui, url, parent, detail_url)
            d.setWindowTitle(self.name)
            d.set_tags(self.config.get('tags', ''))
            d.exec_()

    def search(self, query, max_results=10, timeout=60):
        url = 'http://www.baenebooks.com/searchadv.aspx?IsSubmit=true&SearchTerm=' + urllib2.quote(query)

        br = browser()

        counter = max_results
        with closing(br.open(url, timeout=timeout)) as f:
            doc = html.fromstring(f.read())
            for data in doc.xpath('//table//table//table//table//tr'):
                if counter <= 0:
                    break

                id = ''.join(data.xpath('./td[1]/a/@href'))
                if not id or not id.startswith('p-'):
                    continue

                title = ''.join(data.xpath('./td[1]/a/text()'))

                author = ''
                cover_url = ''
                price = ''

                with closing(br.open('http://www.baenebooks.com/' + id.strip(), timeout=timeout/4)) as nf:
                    idata = html.fromstring(nf.read())
                    author = ''.join(idata.xpath('//span[@class="ProductNameText"]/../b/text()'))
                    author = author.split('by ')[-1]
                    price = ''.join(idata.xpath('//span[@class="variantprice"]/text()'))
                    a, b, price = price.partition('$')
                    price = b + price

                    pnum = ''
                    mo = re.search(r'p-(?P<num>\d+)-', id.strip())
                    if mo:
                        pnum = mo.group('num')
                    if pnum:
                        cover_url = 'http://www.baenebooks.com/' + ''.join(idata.xpath('//img[@id="ProductPic%s"]/@src' % pnum))

                counter -= 1

                s = SearchResult()
                s.cover_url = cover_url
                s.title = title.strip()
                s.author = author.strip()
                s.price = price
                s.detail_item = id.strip()
                s.drm = SearchResult.DRM_UNLOCKED
                s.formats = 'RB, MOBI, EPUB, LIT, LRF, RTF, HTML'

                yield s
