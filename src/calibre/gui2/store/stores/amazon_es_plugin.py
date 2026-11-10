#!/usr/bin/env python
# License: GPLv3 Copyright: 2015, Kovid Goyal <kovid at kovidgoyal.net>

store_version = 17  # Needed for dynamic plugin loading

from calibre.gui2.store import StorePlugin
from calibre.gui2.store.amazon_base import AmazonStore


class Base(AmazonStore):
    scraper_storage = []
    SEARCH_BASE_URL = 'https://www.amazon.es/s/'
    BY = 'de'
    KINDLE_EDITION = 'Versión Kindle'
    DETAILS_URL = 'https://amazon.es/dp/'
    STORE_LINK = 'https://www.amazon.es'


class AmazonKindleStore(Base, StorePlugin):
    pass


if __name__ == '__main__':
    Base().develop_plugin()
