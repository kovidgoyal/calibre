#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2015, Kovid Goyal <kovid at kovidgoyal.net>
from __future__ import absolute_import, division, print_function, unicode_literals

store_version = 20  # Needed for dynamic plugin loading

from calibre.gui2.store import StorePlugin
try:
    from calibre.gui2.store.amazon_base import AmazonStore
except ImportError:
    class AmazonStore:
        minimum_calibre_version = 9999, 0, 0


class Base(AmazonStore):
    scraper_storage = []
    SEARCH_BASE_URL = 'https://www.amazon.ca/s/'
    SEARCH_BASE_QUERY = {'url': 'search-alias=digital-text'}
    DETAILS_URL = 'https://amazon.ca/dp/'
    STORE_LINK =  'https://www.amazon.ca'


class AmazonKindleStore(Base, StorePlugin):
    pass


if __name__ == '__main__':
    Base().develop_plugin()
