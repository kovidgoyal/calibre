# -*- coding: utf-8 -*-

from __future__ import (unicode_literals, division, absolute_import, print_function)
store_version = 1 # Needed for dynamic plugin loading

__license__ = 'GPL 3'
__copyright__ = '2011, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

import urllib2
from contextlib import closing

from lxml import html

from PyQt4.Qt import QUrl

from calibre import browser
from calibre.gui2 import open_url
from calibre.gui2.store import StorePlugin
from calibre.gui2.store.basic_config import BasicStoreConfig
from calibre.gui2.store.search_result import SearchResult
from calibre.gui2.store.web_store_dialog import WebStoreDialog

class EBookNLStore(BasicStoreConfig, StorePlugin):

    def open(self, parent=None, detail_item=None, external=False):
        url = 'http://www.ebook.nl/'
        url_details = ('http://www.ebook.nl/store/{0}')

        if external or self.config.get('open_external', False):
            if detail_item:
                url = url_details.format(detail_item)
            open_url(QUrl(url))
        else:
            detail_url = None
            if detail_item:
                detail_url = url_details.format(detail_item)
            d = WebStoreDialog(self.gui, url, parent, detail_url)
            d.setWindowTitle(self.name)
            d.set_tags(self.config.get('tags', ''))
            d.exec_()

    def search(self, query, max_results=10, timeout=60):
        url = ('http://www.ebook.nl/store/advanced_search_result.php?keywords='
               + urllib2.quote(query))
        br = browser()

        counter = max_results
        with closing(br.open(url, timeout=timeout)) as f:
            doc = html.fromstring(f.read())
            for data in doc.xpath('//table[contains(@class, "productListing")]/tr'):
                if counter <= 0:
                    break

                details = data.xpath('./td/div[@class="prodImage"]/a')
                if not details:
                    continue
                details = details[0]
                id = ''.join(details.xpath('./@href')).strip()
                id = id[id.rfind('/')+1:]
                i = id.rfind('?')
                if i > 0:
                    id = id[:i]
                if not id:
                    continue
                cover_url = 'http://www.ebook.nl/store/' + ''.join(details.xpath('./img/@src'))
                title = ''.join(details.xpath('./img/@title')).strip()
                author = ''.join(data.xpath('./td/div[@class="prodTitle"]/h3/a/text()')).strip()
                price = ''.join(data.xpath('./td/div[@class="prodTitle"]/b/text()'))
                pdf = data.xpath('boolean(./td/div[@class="prodTitle"]/'
                                   'p[contains(text(), "Bestandsformaat: Pdf")])')
                epub = data.xpath('boolean(./td/div[@class="prodTitle"]/'
                                   'p[contains(text(), "Bestandsformaat: ePub")])')
                nodrm = data.xpath('boolean(./td/div[@class="prodTitle"]/'
                                   'p[contains(text(), "zonder DRM") or'
                                   '  contains(text(), "watermerk")])')
                counter -= 1

                s = SearchResult()
                s.cover_url = cover_url
                s.title = title.strip()
                s.author = author.strip()
                s.price = price
                if nodrm:
                    s.drm = SearchResult.DRM_UNLOCKED
                else:
                    s.drm = SearchResult.DRM_LOCKED
                s.detail_item = id
                formats = []
                if epub:
                    formats.append('ePub')
                if pdf:
                    formats.append('PDF')
                s.formats = ','.join(formats)

                yield s
