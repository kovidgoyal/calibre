#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

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

    def open(self, parent=None, detail_item=None, external=False):
        if detail_item:
            if external or self.config.get('open_external', False):
                open_url(QUrl(url_slash_cleaner(detail_item)))
            else:
                d = WebStoreDialog(self.gui, 'http://ebookstore.sony.com', parent, detail_item)
                d.setWindowTitle(self.name)
                d.set_tags(self.config.get('tags', ''))
                d.exec_()
        else:
            open_url(QUrl('http://ebookstore.sony.com'))

    def search(self, query, max_results=10, timeout=60):
        url = 'http://ebookstore.sony.com/search?keyword=%s'%urllib.quote_plus(
                query)

        br = browser()

        counter = max_results
        with closing(br.open(url, timeout=timeout)) as f:
            doc = html.fromstring(f.read())
            for item in doc.xpath('//div[contains(@class, "searchResult")]/'
                    'descendant::li[contains(@class, "hreview")]'):
                if counter <= 0:
                    break

                curr = ''.join(item.xpath('descendant::div[@class="pricing"]/descendant::*[@class="currency"]/@title')).strip()
                amt = ''.join(item.xpath('descendant::div[@class="pricing"]/descendant::*[@class="amount"]/text()')).strip()
                s = SearchResult()
                s.price = (curr+' '+amt) if (curr and amt) else _('Not Available')
                title = item.xpath('descendant::h3[@class="item"]')
                if not title: continue
                title = etree.tostring(title[0], method='text',
                        encoding=unicode)
                if not title: continue
                s.title = title.strip()
                s.author = ''.join(item.xpath(
                        'descendant::li[contains(@class, "author")]/'
                        'a[@class="fn"]/text()')).strip()
                if not s.author: continue
                detail_url = ''.join(item.xpath('descendant::h3[@class="item"]'
                    '/descendant::a[@class="fn" and @href]/@href'))
                if not detail_url: continue
                if detail_url.startswith('/'):
                    detail_url = 'http:'+detail_url
                s.detail_item = detail_url

                counter -= 1

                cover_url = ''.join(item.xpath(
                    'descendant::li[@class="coverart"]/'
                    'descendant::img[@src]/@src'))
                if cover_url:
                    if cover_url.startswith('//'):
                        cover_url = 'http:' + cover_url
                    elif cover_url.startswith('/'):
                        cover_url = 'http://ebookstore.sony.com'+cover_url
                    s.cover_url = url_slash_cleaner(cover_url)

                s.drm = SearchResult.DRM_UNKNOWN
                s.formats = 'Sony'

                yield s
