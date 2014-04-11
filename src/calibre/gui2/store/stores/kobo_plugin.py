# -*- coding: utf-8 -*-

from __future__ import (unicode_literals, division, absolute_import, print_function)
store_version = 3 # Needed for dynamic plugin loading

__license__ = 'GPL 3'
__copyright__ = '2011, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

import random
import urllib
from contextlib import closing

from lxml import html

from PyQt5.Qt import QUrl

from calibre import browser, url_slash_cleaner
from calibre.gui2 import open_url
from calibre.gui2.store import StorePlugin
from calibre.gui2.store.basic_config import BasicStoreConfig
from calibre.gui2.store.search_result import SearchResult
from calibre.gui2.store.web_store_dialog import WebStoreDialog

class KoboStore(BasicStoreConfig, StorePlugin):

    def open(self, parent=None, detail_item=None, external=False):
        pub_id = 'sHa5EXvYOwA'
        # Use Kovid's affiliate id 30% of the time.
        if random.randint(1, 10) in (1, 2, 3):
            pub_id = '0dsO3kDu/AU'

        murl = 'http://click.linksynergy.com/fs-bin/click?id=%s&subid=&offerid=280046.1&type=10&tmpid=9310&RD_PARM1=http%%3A%%2F%%2Fkobo.com' % pub_id

        if detail_item:
            purl = 'http://click.linksynergy.com/link?id=%s&offerid=280046&type=2&murl=%s' % (pub_id, urllib.quote_plus(detail_item))
            url = purl
        else:
            purl = None
            url = murl

        if external or self.config.get('open_external', False):
            open_url(QUrl(url_slash_cleaner(url)))
        else:
            d = WebStoreDialog(self.gui, murl, parent, purl)
            d.setWindowTitle(self.name)
            d.set_tags(self.config.get('tags', ''))
            d.exec_()

    def search(self, query, max_results=10, timeout=60):
        url = 'http://www.kobobooks.com/search/search.html?q=' + urllib.quote_plus(query)

        br = browser()

        counter = max_results
        with closing(br.open(url, timeout=timeout)) as f:
            doc = html.fromstring(f.read())
            for data in doc.xpath('//ul[contains(@class, "flowview-items")]/li'):
                if counter <= 0:
                    break

                id = ''.join(data.xpath('./a[contains(@class, "block-link")]/@href'))
                if not id:
                    continue
                id = id[1:]

                price = ''.join(data.xpath('.//a[contains(@class, "primary-button")]//text()'))

                cover_url = ''.join(data.xpath('.//img[1]/@src'))
                cover_url = 'http:%s' % cover_url

                title = ''.join(data.xpath('.//p[contains(@class, "flowview-item-title")]//text()'))

                counter -= 1

                s = SearchResult()
                s.cover_url = cover_url
                s.title = title.strip()
                s.price = price.strip()
                s.detail_item = 'http://store.kobobooks.com/' + id.strip()
                s.formats = 'EPUB'
                s.drm = SearchResult.DRM_UNKNOWN

                yield s

    def get_details(self, search_result, timeout):
        br = browser()
        with closing(br.open(search_result.detail_item, timeout=timeout)) as nf:
            idata = html.fromstring(nf.read())
            search_result.author = ', '.join(idata.xpath('.//h2[contains(@class, "author")]//a/text()'))
        return True
