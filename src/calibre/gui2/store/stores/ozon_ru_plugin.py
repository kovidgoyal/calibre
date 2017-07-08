# -*- coding: utf-8 -*-

from __future__ import (unicode_literals, division, absolute_import, print_function)
store_version = 3  # Needed for dynamic plugin loading

__license__ = 'GPL 3'
__copyright__ = '2011-2013, Roman Mukhin <ramses_ru at hotmail.com>'
__docformat__ = 'restructuredtext en'

import urllib
from contextlib import closing

from PyQt5.Qt import QUrl

from calibre import browser, url_slash_cleaner
from calibre.ebooks.chardet import xml_to_unicode
from calibre.gui2 import open_url
from calibre.gui2.store import StorePlugin
from calibre.gui2.store.search_result import SearchResult
from calibre.gui2.store.web_store_dialog import WebStoreDialog

shop_url = 'http://www.ozon.ru'


def parse_html(raw):
    try:
        from html5_parser import parse
    except ImportError:
        # Old versions of calibre
        import html5lib
        return html5lib.parse(raw, treebuilder='lxml', namespaceHTMLElements=False)
    else:
        return parse(raw)


def search(query, max_results=15, timeout=60):
    url = 'http://www.ozon.ru/?context=search&text=%s&store=1,0&group=div_book' % urllib.quote_plus(query)

    counter = max_results
    br = browser()

    with closing(br.open(url, timeout=timeout)) as f:
        raw = xml_to_unicode(f.read(), strip_encoding_pats=True, assume_utf8=True)[0]
        root = parse_html(raw)
        for tile in root.xpath('//*[@class="bShelfTile inline"]'):
            if counter <= 0:
                break
            counter -= 1

            s = SearchResult(store_name='OZON.ru')
            s.detail_item = shop_url + tile.xpath('descendant::a[@class="eShelfTile_Link"]/@href')[0]
            s.title = tile.xpath('descendant::span[@class="eShelfTile_ItemNameText"]/@title')[0]
            s.author = tile.xpath('descendant::span[@class="eShelfTile_ItemPerson"]/@title')[0]
            s.price = ''.join(tile.xpath('descendant::div[contains(@class, "eShelfTile_Price")]/text()'))
            s.cover_url = 'http:' + tile.xpath('descendant::img/@data-original')[0]
            s.price = format_price_in_RUR(s.price)
            yield s


class OzonRUStore(StorePlugin):

    def open(self, parent=None, detail_item=None, external=False):
        url = detail_item or shop_url
        if external or self.config.get('open_external', False):
            open_url(QUrl(url_slash_cleaner(url)))
        else:
            d = WebStoreDialog(self.gui, shop_url, parent, url)
            d.setWindowTitle(self.name)
            d.set_tags(self.config.get('tags', ''))
            d.exec_()

    def search(self, query, max_results=15, timeout=60):
        for s in search(query, max_results=max_results, timeout=timeout):
            yield s


def format_price_in_RUR(price):
    '''
    Try to format price according ru locale: '12 212,34 руб.'
    @param price: price in format like 25.99
    @return: formatted price if possible otherwise original value
    @rtype: unicode
    '''
    price = price.replace('\xa0', '').replace(',', '.').strip() + ' py6'
    return price


if __name__ == '__main__':
    import sys
    for r in search(sys.argv[-1]):
        print(r)
