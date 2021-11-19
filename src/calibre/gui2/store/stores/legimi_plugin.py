# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function, unicode_literals

store_version = 10  # Needed for dynamic plugin loading

__license__ = 'GPL 3'
__copyright__ = '2011-2019, Tomasz Długosz <tomek3d@gmail.com>'
__docformat__ = 'restructuredtext en'

from base64 import b64encode
from contextlib import closing
try:
    from urllib.parse import quote_plus
except ImportError:
    from urllib import quote_plus

from lxml import html

from qt.core import QUrl

from calibre import browser, url_slash_cleaner
from calibre.gui2 import open_url
from calibre.gui2.store import StorePlugin
from calibre.gui2.store.basic_config import BasicStoreConfig
from calibre.gui2.store.search_result import SearchResult
from calibre.gui2.store.web_store_dialog import WebStoreDialog


def as_base64(data):
    if not isinstance(data, bytes):
        data = data.encode('utf-8')
    ans = b64encode(data)
    if isinstance(ans, bytes):
        ans = ans.decode('ascii')
    return ans


class LegimiStore(BasicStoreConfig, StorePlugin):

    def open(self, parent=None, detail_item=None, external=False):
        aff_root = 'https://www.a4b-tracking.com/pl/stat-click-text-link/9/58/'

        url = 'https://www.legimi.pl/ebooki/'

        aff_url = aff_root + as_base64(url)

        detail_url = None
        if detail_item:
            detail_url = aff_root + as_base64(detail_item)

        if external or self.config.get('open_external', False):
            open_url(QUrl(url_slash_cleaner(detail_url if detail_url else aff_url)))
        else:
            d = WebStoreDialog(self.gui, url, parent, detail_url if detail_url else aff_url)
            d.setWindowTitle(self.name)
            d.set_tags(self.config.get('tags', ''))
            d.exec()

    def search(self, query, max_results=10, timeout=60):
        url = 'https://www.legimi.pl/ebooki/?sort=score&searchphrase=' + quote_plus(query)

        br = browser()

        counter = max_results
        with closing(br.open(url, timeout=timeout)) as f:
            doc = html.fromstring(f.read())
            for data in doc.xpath('//div[@class="book-search row auto-clear"]/div'):
                if counter <= 0:
                    break

                id = ''.join(data.xpath('.//div[@class="panel-body"]/a/@href'))
                if not id:
                    continue

                cover_url = ''.join(data.xpath('.//div[@class="img-content"]/img/@data-src'))
                title = ''.join(data.xpath('.//a[@class="book-title clampBookTitle"]/text()'))
                author = ' '.join(data.xpath('.//div[@class="authors-container clampBookAuthors"]/a/text()'))
                counter -= 1

                s = SearchResult()
                s.cover_url = cover_url
                s.title = title.strip()
                s.author = author.strip()
                s.detail_item = 'https://www.legimi.pl' + id.strip()
                s.drm = SearchResult.DRM_UNLOCKED

                yield s

    def get_details(self, search_result, timeout):
        br = browser()
        with closing(br.open(search_result.detail_item, timeout=timeout/2)) as nf:
            idata = html.fromstring(nf.read())

            price = ''.join(idata.xpath('.//section[@class="book-sale-options"]//p[@class="light-text"]/text()'))
            search_result.price = price.split('bez abonamentu ')[-1]
        return True
