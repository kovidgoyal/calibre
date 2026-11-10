#!/usr/bin/env python
# License: GPLv3 Copyright: 2015, Kovid Goyal <kovid at kovidgoyal.net>

store_version = 18  # Needed for dynamic plugin loading

from calibre.gui2.store import StorePlugin
from calibre.gui2.store.amazon_base import AmazonStore


class Base(AmazonStore):
    scraper_storage = []
    SEARCH_BASE_URL = 'https://www.amazon.fr/s/'
    BY = 'de'
    KINDLE_EDITION = 'Format Kindle'
    DETAILS_URL = 'https://amazon.fr/dp/'
    STORE_LINK = 'https://www.amazon.fr'


class AmazonKindleStore(Base, StorePlugin):
    pass


if __name__ == '__main__':
    Base().develop_plugin()
