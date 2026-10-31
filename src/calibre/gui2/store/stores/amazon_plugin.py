#!/usr/bin/env python
# License: GPLv3 Copyright: 2015, Kovid Goyal <kovid at kovidgoyal.net>

store_version = 20  # Needed for dynamic plugin loading

from calibre.gui2.store import StorePlugin
from calibre.gui2.store.amazon_base import AmazonStore


class Base(AmazonStore):
    scraper_storage = []


class AmazonKindleStore(Base, StorePlugin):
    pass


if __name__ == '__main__':
    Base().develop_plugin()
