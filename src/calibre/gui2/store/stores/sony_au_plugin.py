#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)
store_version = 1  # Needed for dynamic plugin loading

__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import urllib
from contextlib import closing

from lxml import html, etree

from PyQt4.Qt import QUrl

from calibre import browser, url_slash_cleaner
from calibre.gui2 import open_url
from calibre.gui2.store import StorePlugin
from calibre.gui2.store.basic_config import BasicStoreConfig
from calibre.gui2.store.search_result import SearchResult
from calibre.gui2.store.web_store_dialog import WebStoreDialog

class SonyStore(BasicStoreConfig, StorePlugin):

    SEARCH_URL = 'https://au.readerstore.sony.com/catalog/search/?query=%s'
    STORE_URL = 'https://au.readerstore.sony.com/store/'

    def open(self, parent=None, detail_item=None, external=False):
        if detail_item:
            if external or self.config.get('open_external', False):
                open_url(QUrl(url_slash_cleaner(detail_item)))
            else:
                d = WebStoreDialog(self.gui, self.STORE_URL, parent, detail_item)
                d.setWindowTitle(self.name)
                d.set_tags(self.config.get('tags', ''))
                d.exec_()
        else:
            open_url(QUrl(self.STORE_URL))

    def search(self, query, max_results=10, timeout=60):
        url = self.SEARCH_URL % urllib.quote_plus(query)

        br = browser()

        counter = max_results
        with closing(br.open(url, timeout=timeout)) as f:
            doc = html.fromstring(f.read())
            for item in doc.xpath('//div[@id="searchresult-list"]/descendant::div[contains(@class, "doc-item")]'):
                if counter <= 0:
                    break

                s = SearchResult()
                s.price = _('Not Available')
                p = ''.join(item.xpath('descendant::p[@class="doc-price"]/descendant::span[@itemprop="price"]/text()')).strip()
                if p:
                    s.price = 'AUD ' + p.split('$')[-1]

                title = item.xpath('descendant::h3[@class="doc-title"]')
                if not title:
                    continue
                title = etree.tostring(title[0], method='text', encoding=unicode)
                if not title:
                    continue
                st = item.xpath('descendant::p[@class="doc-subtitle"]')
                if st:
                    st = etree.tostring(st[0], method='text', encoding=unicode)
                    if st and st.strip():
                        title = title.strip() + ': ' + st
                s.title = title.strip()
                aut = item.xpath('descendant::p[@class="doc-author"]')
                if not aut:
                    continue
                s.author = etree.tostring(aut[0], method='text', encoding=unicode).strip()
                if not s.author:
                    continue
                du = ''.join(item.xpath('descendant::h3[position() = 1 and @class="doc-title"]/descendant::a[position() = 1 and @href]/@href')).strip()
                if not du:
                    continue
                detail_url = 'https://au.readerstore.sony.com'+du
                s.detail_item = detail_url

                counter -= 1

                cover_url = ''.join(item.xpath(
                    'descendant::p[@class="doc-cover" and position() = 1]/'
                    'descendant::img[position() = 1 and @src]/@src'))
                if cover_url:
                    s.cover_url = url_slash_cleaner(cover_url)

                s.drm = SearchResult.DRM_UNKNOWN
                s.formats = 'Sony'

                yield s

