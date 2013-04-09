# -*- coding: utf-8 -*-

from __future__ import (unicode_literals, division, absolute_import, print_function)
store_version = 2 # Needed for dynamic plugin loading

__license__ = 'GPL 3'
__copyright__ = '2011, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

import mimetypes
import urllib
from contextlib import closing

from lxml import html

from PyQt4.Qt import QUrl

from calibre import browser, random_user_agent, url_slash_cleaner
from calibre.gui2 import open_url
from calibre.gui2.store import StorePlugin
from calibre.gui2.store.basic_config import BasicStoreConfig
from calibre.gui2.store.search_result import SearchResult
from calibre.gui2.store.web_store_dialog import WebStoreDialog

class GutenbergStore(BasicStoreConfig, StorePlugin):

    def open(self, parent=None, detail_item=None, external=False):
        url = 'http://gutenberg.org/'

        if detail_item:
            detail_item = url_slash_cleaner(url + detail_item)

        if external or self.config.get('open_external', False):
            open_url(QUrl(detail_item if detail_item else url))
        else:
            d = WebStoreDialog(self.gui, url, parent, detail_item)
            d.setWindowTitle(self.name)
            d.set_tags(self.config.get('tags', ''))
            d.exec_()

    def search(self, query, max_results=10, timeout=60):
        url = 'http://m.gutenberg.org/ebooks/search.mobile/?default_prefix=all&sort_order=title&query=' + urllib.quote_plus(query)

        br = browser(user_agent=random_user_agent())

        counter = max_results
        with closing(br.open(url, timeout=timeout)) as f:
            doc = html.fromstring(f.read())
            for data in doc.xpath('//ol[@class="results"]/li[@class="booklink"]'):
                if counter <= 0:
                    break

                id = ''.join(data.xpath('./a/@href'))
                id = id.split('.mobile')[0]

                title = ''.join(data.xpath('.//span[@class="title"]/text()'))
                author = ''.join(data.xpath('.//span[@class="subtitle"]/text()'))

                counter -= 1

                s = SearchResult()
                s.cover_url = ''

                s.detail_item = id.strip()
                s.title = title.strip()
                s.author = author.strip()
                s.price = '$0.00'
                s.drm = SearchResult.DRM_UNLOCKED

                yield s

    def get_details(self, search_result, timeout):
        url = url_slash_cleaner('http://m.gutenberg.org/' + search_result.detail_item)

        br = browser(user_agent=random_user_agent())
        with closing(br.open(url, timeout=timeout)) as nf:
            doc = html.fromstring(nf.read())

            for save_item in doc.xpath('//li[contains(@class, "icon_save")]/a'):
                type = save_item.get('type')
                href = save_item.get('href')

                if type:
                    ext = mimetypes.guess_extension(type)
                    if ext:
                        ext = ext[1:].upper().strip()
                        search_result.downloads[ext] = href

                search_result.formats = ', '.join(search_result.downloads.keys())

        return True
