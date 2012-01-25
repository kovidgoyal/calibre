# -*- coding: utf-8 -*-

from __future__ import (unicode_literals, division, absolute_import, print_function)

__license__ = 'GPL 3'
__copyright__ = '2011, Tomasz Długosz <tomek3d@gmail.com>'
__docformat__ = 'restructuredtext en'

import re
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

class GandalfStore(BasicStoreConfig, StorePlugin):

    def open(self, parent=None, detail_item=None, external=False):
        url = 'http://www.gandalf.com.pl/ebooks/'

        if external or self.config.get('open_external', False):
            open_url(QUrl(url_slash_cleaner(detail_item if detail_item else url)))
        else:
            d = WebStoreDialog(self.gui, url, parent, detail_item)
            d.setWindowTitle(self.name)
            d.set_tags(self.config.get('tags', ''))
            d.exec_()

    def search(self, query, max_results=10, timeout=60):
        url = 'http://www.gandalf.com.pl/s/'
        values={
            'search': query.decode('utf-8').encode('iso8859_2'),
            'dzialx':'11'
            }

        br = browser()

        counter = max_results
        with closing(br.open(url, data=urllib.urlencode(values), timeout=timeout)) as f:
            doc = html.fromstring(f.read())
            for data in doc.xpath('//div[@class="box"]'):
                if counter <= 0:
                    break

                id = ''.join(data.xpath('.//div[@class="info"]/h3/a/@href'))
                if not id:
                    continue

                cover_url = ''.join(data.xpath('.//div[@class="info"]/h3/a/@id'))
                title = ''.join(data.xpath('.//div[@class="info"]/h3/a/@title'))
                formats = ''.join(data.xpath('.//div[@class="info"]/p[1]/text()'))
                formats = re.findall(r'\((.*?)\)',formats)[0]
                author = ''.join(data.xpath('.//div[@class="info"]/h4/text() | .//div[@class="info"]/h4/span/text()'))
                price = ''.join(data.xpath('.//div[@class="options"]/h3/text()'))
                price = re.sub('PLN', 'zł', price)
                price = re.sub('\.', ',', price)
                drm = data.xpath('boolean(.//div[@class="info" and contains(., "Zabezpieczenie: DRM")])')

                counter -= 1

                s = SearchResult()
                s.cover_url = 'http://imguser.gandalf.com.pl/' + re.sub('p', 'p_', cover_url) + '.jpg'
                s.title = title.strip()
                s.author = author.strip()
                s.price = price
                s.detail_item = id.strip()
                if drm:
                    s.drm = SearchResult.DRM_LOCKED
                else:
                    s.drm = SearchResult.DRM_UNLOCKED
                s.formats = formats.upper().strip()

                yield s
