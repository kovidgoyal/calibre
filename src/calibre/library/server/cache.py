#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from collections import OrderedDict

from calibre.utils.date import utcnow

class Cache(object):

    def __init__(self):
        self.reset_caches()

    def reset_caches(self):
        self._category_cache = OrderedDict()
        self._search_cache = OrderedDict()

    def search_cache(self, search):
        old = self._search_cache.pop(search, None)
        if old is None or old[0] <= self.db.last_modified():
            matches = self.search_for_books(search) or []
            self._search_cache[search] = (utcnow(), frozenset(matches))
            if len(self._search_cache) > 50:
                self._search_cache.popitem(last=False)
        else:
            self._search_cache[search] = old
        return self._search_cache[search][1]

    def categories_cache(self, restrict_to=frozenset([])):
        base_restriction = self.search_cache('')
        if restrict_to:
            restrict_to = frozenset(restrict_to).intersection(base_restriction)
        else:
            restrict_to = base_restriction
        old = self._category_cache.pop(frozenset(restrict_to), None)
        if old is None or old[0] <= self.db.last_modified():
            categories = self.db.get_categories(ids=restrict_to)
            self._category_cache[restrict_to] = (utcnow(), categories)
            if len(self._category_cache) > 20:
                self._category_cache.popitem(last=False)
        else:
            self._category_cache[frozenset(restrict_to)] = old
        return self._category_cache[restrict_to][1]
