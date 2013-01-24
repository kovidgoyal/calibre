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

class BeamEBooksDEStore(BasicStoreConfig, StorePlugin):

    def open(self, parent=None, detail_item=None, external=False):
        url = 'http://klick.affiliwelt.net/klick.php?bannerid=10072&pid=32307&prid=908'
        url_details = ('http://klick.affiliwelt.net/klick.php?'
                       'bannerid=66820&pid=32307&prid=908&feedid=27&prdid={0}')

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
        url = 'http://www.beam-ebooks.de/suchergebnis.php?Type=&sw=' + urllib2.quote(query)
        br = browser()

        counter = max_results
        with closing(br.open(url, timeout=timeout)) as f:
            doc = html.fromstring(f.read())
            for data in doc.xpath('//table[tr/td/div[@class="stil2"]]'):
                if counter <= 0:
                    break

                id_ = ''.join(data.xpath('./tr/td[1]/a/@href')).strip()
                if not id_:
                    continue
                id_ = id_[7:]
                cover_url = ''.join(data.xpath('./tr/td[1]/a/img/@src'))
                if cover_url:
                    cover_url = 'http://www.beam-ebooks.de' + cover_url
                temp = ''.join(data.xpath('./tr/td[1]/a/img/@alt'))
                colon = temp.find(':')
                if not temp.startswith('eBook') or colon < 0:
                    continue
                author = temp[5:colon]
                title = temp[colon+1:]
                price = ''.join(data.xpath('./tr/td[3]/text()'))
                pdf = data.xpath(
                        'boolean(./tr/td[3]/a/img[contains(@alt, "PDF")]/@alt)')
                epub = data.xpath(
                        'boolean(./tr/td[3]/a/img[contains(@alt, "ePub")]/@alt)')
                mobi = data.xpath(
                        'boolean(./tr/td[3]/a/img[contains(@alt, "Mobipocket")]/@alt)')
                counter -= 1

                s = SearchResult()
                s.cover_url = cover_url
                s.title = title.strip()
                s.author = author.strip()
                s.price = price
                s.drm = SearchResult.DRM_UNLOCKED
                s.detail_item = id_
                formats = []
                if epub:
                    formats.append('ePub')
                if pdf:
                    formats.append('PDF')
                if mobi:
                    formats.append('MOBI')
                s.formats = ', '.join(formats)

                yield s

