# License: GPLv3 Copyright: 2014, Rafael Vega <rafavega@gmail.com>


store_version = 3  # Needed for dynamic plugin loading

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


class BubokPublishingStore(BasicStoreConfig, StorePlugin):
    def open(self, gui: Main | None = None, parent: QWidget | None = None, detail_item: str | None = None, external: bool = False) -> None:
        url = 'https://www.bubok.es/tienda'
        if external or self.config.get('open_external', False):
            open_url(QUrl(url_slash_cleaner(detail_item or url)))
        else:
            d = WebStoreDialog(self.gui, url, parent, detail_item)
            d.setWindowTitle(self.name)
            d.set_tags(self.config.get('tags', ''))
            d.exec()

    def search(self, query: bytes | str, max_results: int = 10, timeout: int = 60) -> Iterator[SearchResult]:
        url = 'http://www.bubok.es/resellers/calibre_search/' + quote_plus(query)

        br = browser()

        counter = max_results
        with closing(br.open(url, timeout=timeout)) as f:
            doc = safe_html_fromstring(f.read())
            for data in doc.xpath('//div[contains(@class, "libro")]'):
                if counter <= 0:
                    break

                id = ''.join(data.xpath('.//div[@class="url"]/text()'))

                title = ''.join(data.xpath('.//div[@class="titulo"]/text()'))

                author = ''.join(data.xpath('.//div[@class="autor"]/text()'))

                price = ''.join(data.xpath('.//div[@class="precio"]/text()'))

                formats = ''.join(data.xpath('.//div[@class="formatos"]/text()'))

                cover = ''.join(data.xpath('.//div[@class="portada"]/text()'))

                counter -= 1

                s = SearchResult()
                s.title = title.strip()
                s.author = author.strip()
                s.detail_item = id.strip()
                s.price = price.strip()
                s.drm = SearchResult.DRM_UNLOCKED
                s.formats = formats.strip()
                s.cover_url = cover.strip()
                yield s

    def get_details(self, search_result: SearchResult, timeout: int = 60) -> bool:
        return True
