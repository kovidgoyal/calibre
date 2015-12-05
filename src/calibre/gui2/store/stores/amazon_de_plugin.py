# -*- coding: utf-8 -*-

from __future__ import (unicode_literals, division, absolute_import, print_function)
store_version = 9 # Needed for dynamic plugin loading

__license__ = 'GPL 3'
__copyright__ = '2011, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

from calibre.gui2.store import StorePlugin
from calibre.gui2.store.search_result import SearchResult

class AmazonDEKindleStore(StorePlugin):
    '''
    Amazon forcibly closed the affiliate account, requesting that "all links
    toward Amazon content be removed".
    '''

    def genesis(self):
        StorePlugin.genesis(self)
        from calibre.customize.ui import find_plugin
        pi = find_plugin('Amazon DE Kindle')
        pi.affiliate = False

    def open(self, parent=None, detail_item=None, external=False):
        pass

    def search(self, query, max_results=10, timeout=60):
        s = SearchResult()
        s.title = 'Amazon demanded that this<br>store be permanently closed.'
        s.author = None
        yield s

    def get_details(self, search_result, timeout):
        pass