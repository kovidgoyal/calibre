#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from calibre.utils.date import utcnow

class Cache(object):

    @property
    def categories_cache(self):
        old = getattr(self, '_category_cache', None)
        if old is None or old[0] <= self.db.last_modified():
            categories = self.db.get_categories()
            self._category_cache = (utcnow(), categories)
        return self._category_cache[1]
