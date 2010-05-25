#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from calibre.utils.date import utcnow
from calibre.utils.ordered_dict import OrderedDict

class Cache(object):

    def add_routes(self, c):
        self._category_cache = OrderedDict()
        self._search_cache = OrderedDict()

    def search_cache(self, search):
        old = self._search_cache.get(search, None)
        if old is None or old[0] <= self.db.last_modified():
            matches = self.db.data.search(search, return_matches=True,
                    ignore_search_restriction=True)
            if not matches:
                matches = []
            self._search_cache[search] = (utcnow(), frozenset(matches))
            if len(self._search_cache) > 10:
                self._search_cache.popitem(last=False)
        return self._search_cache[search][1]


    def categories_cache(self, restrict_to=frozenset([])):
        old = self._category_cache.get(frozenset(restrict_to), None)
        if old is None or old[0] <= self.db.last_modified():
            categories = self.db.get_categories(ids=restrict_to)
            self._category_cache[restrict_to] = (utcnow(), categories)
            if len(self._category_cache) > 10:
                self._category_cache.popitem(last=False)
        return self._category_cache[restrict_to][1]
