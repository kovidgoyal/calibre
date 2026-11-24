# License: GPLv3 Copyright: 2011, John Schember <john@nachtimwald.com>


store_version = 2  # Needed for dynamic plugin loading

from contextlib import closing
from typing import TYPE_CHECKING
from urllib.parse import quote_plus

from qt.core import QUrl

from calibre import browser, url_slash_cleaner
from calibre.gui2 import open_url
from calibre.gui2.store import StorePlugin
from calibre.gui2.store.basic_config import BasicStoreConfig
from calibre.gui2.store.search_result import SearchResult
from calibre.gui2.store.web_store_dialog import WebStoreDialog

try:
    from calibre.utils.xml_parse import safe_html_fromstring
except ImportError:
    from lxml.html import fromstring as safe_html_fromstring


if TYPE_CHECKING:
    from collections.abc import Iterator

    from qt.core import QWidget

    from calibre.gui2.ui import Main


class WeightlessBooksStore(BasicStoreConfig, StorePlugin):
    def open(self, gui: Main | None = None, parent: QWidget | None = None, detail_item: str | None = None, external: bool = False) -> None:
        url = 'http://weightlessbooks.com/'

        if external or self.config.get('open_external', False):
            open_url(QUrl(url_slash_cleaner(detail_item or url)))
        else:
            d = WebStoreDialog(self.gui, url, parent, detail_item)
            d.setWindowTitle(self.name)
            d.set_tags(self.config.get('tags', ''))
            d.exec()

    def search(self, query: bytes | str, max_results: int = 10, timeout: int = 60) -> Iterator[SearchResult]:
        url = 'http://weightlessbooks.com/?s=' + quote_plus(query)

        br = browser()

        counter = max_results
        with closing(br.open(url, timeout=timeout)) as f:
            doc = safe_html_fromstring(f.read())
            for data in doc.xpath('//li[@class="product"]'):
                if counter <= 0:
                    break

                id = ''.join(data.xpath('.//div[@class="cover"]/a/@href'))
                if not id:
                    continue

                cover_url = ''.join(data.xpath('.//div[@class="cover"]/a/img/@src'))

                price = ''.join(data.xpath('.//div[@class="buy_buttons"]/b[1]/text()'))
                if not price:
                    continue

                formats = ', '.join(data.xpath('.//select[@class="eStore_variation"]//option//text()'))
                formats = formats.upper()

                title = ''.join(data.xpath('.//h3/a/text()'))
                author = ''.join(data.xpath('.//h3//text()'))
                author = author.replace(title, '')

                counter -= 1

                s = SearchResult()
                s.cover_url = cover_url
                s.title = title.strip()
                s.author = author.strip()
                s.price = price.strip()
                s.detail_item = id.strip()
                s.drm = SearchResult.DRM_UNLOCKED
                s.formats = formats

                yield s
