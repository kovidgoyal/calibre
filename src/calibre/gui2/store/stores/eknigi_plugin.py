# -*- coding: utf-8 -*-

from __future__ import (unicode_literals, division, absolute_import, print_function)
store_version = 1 # Needed for dynamic plugin loading

__license__ = 'GPL 3'
__copyright__ = '2011, Alex Stanev <alex@stanev.org>'
__docformat__ = 'restructuredtext en'

import re
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

class eKnigiStore(BasicStoreConfig, StorePlugin):

    def open(self, parent=None, detail_item=None, external=False):
        # Use Kovid's affiliate id 30% of the time
        if random.randint(1, 10) in (1, 2, 3):
            aff_suffix = '&amigosid=23'
        else:
            aff_suffix = '&amigosid=22'
        url = 'http://e-knigi.net/?' + aff_suffix[1:]

        if external or self.config.get('open_external', False):
            if detail_item:
                url = detail_item + aff_suffix
            open_url(QUrl(url_slash_cleaner(url)))
        else:
            detail_url = None
            if detail_item:
                url = detail_item + aff_suffix
            d = WebStoreDialog(self.gui, url, parent, detail_url)
            d.setWindowTitle(self.name)
            d.set_tags(self.config.get('tags', ''))
            d.exec_()

    def search(self, query, max_results=10, timeout=60):
        # check for cyrillic symbols before performing search
        uquery = unicode(query.strip(), 'utf-8')
        reObj = re.search(u'^[а-яА-Я\\d\\s]{2,}$', uquery)
        if not reObj:
            return

        base_url = 'http://e-knigi.net'
        url = base_url + '/virtuemart?page=shop.browse&search_category=0&search_limiter=anywhere&keyword=' + urllib2.quote(query)

        br = browser()

        counter = max_results
        with closing(br.open(url, timeout=timeout)) as f:
            doc = html.fromstring(f.read())

            # if the store finds only one product, it opens directly detail view
            for data in doc.xpath('//div[@class="prod_details"]'):
                s = SearchResult()
                s.cover_url = ''.join(data.xpath('.//div[@class="vm_main_info clearfix"]/div[@class="lf"]/a/img/@src')).strip()
                s.title = ''.join(data.xpath('.//div[@class="vm_main_info clearfix"]/div[@class="lf"]/a/img/@alt')).strip()
                s.author = ''.join(data.xpath('.//div[@class="td_bg clearfix"]/div[@class="gk_product_tab"]/div/table/tr[3]/td[2]/text()')).strip()
                s.price = ''.join(data.xpath('.//span[@class="productPrice"]/text()')).strip()
                s.detail_item = url
                s.drm = SearchResult.DRM_UNLOCKED

                yield s
                return

            # search in store results
            for data in doc.xpath('//div[@class="browseProductContainer"]'):
                if counter <= 0:
                    break
                id = ''.join(data.xpath('.//a[1]/@href')).strip()
                if not id:
                    continue

                title = ''.join(data.xpath('.//a[@class="gk_vm_product_image"]/img/@title')).strip()
                author = ''.join(data.xpath('.//div[@style="float:left;width:90%"]/b/text()')).strip().replace('Автор: ', '')

                if title.lower().find(query.lower()) == -1 and author.lower().find(query.lower()) == -1:
                    continue

                counter -= 1

                s = SearchResult()
                s.cover_url = ''.join(data.xpath('.//a[@class="gk_vm_product_image"]/img/@src')).strip()
                s.title = title
                s.author = author
                s.price = ''.join(data.xpath('.//span[@class="productPrice"]/text()')).strip()
                s.detail_item = base_url + id
                s.drm = SearchResult.DRM_UNLOCKED

                yield s
