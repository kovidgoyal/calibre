#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from calibre.gui2.complete2 import EditWithComplete
from calibre.utils.localization import lang_map
from calibre.utils.icu import sort_key, lower

class LanguagesEdit(EditWithComplete):

    def __init__(self, parent=None, db=None):
        EditWithComplete.__init__(self, parent)

        self.setSizeAdjustPolicy(self.AdjustToMinimumContentsLengthWithIcon)
        self.setMinimumContentsLength(20)
        self._lang_map = lang_map()
        self.names_with_commas = [x for x in self._lang_map.itervalues() if ',' in x]
        self.comma_map = {k:k.replace(',', '|') for k in self.names_with_commas}
        self.comma_rmap = {v:k for k, v in self.comma_map.iteritems()}
        self._rmap = {lower(v):k for k,v in self._lang_map.iteritems()}
        self.init_langs(db)

    def init_langs(self, db):
        if db is not None:
            pmap = {self._lang_map.get(x[1], x[1]):1 for x in
                    db.get_languages_with_ids()}
            all_items = sorted(self._lang_map.itervalues(),
                key=lambda x: (-pmap.get(x, 0), sort_key(x)))
        else:
            all_items = sorted(self._lang_map.itervalues(),
                key=lambda x: sort_key(x))
        self.update_items_cache(all_items)

    @property
    def vals(self):
        raw = unicode(self.lineEdit().text())
        for k, v in self.comma_map.iteritems():
            raw = raw.replace(k, v)
        parts = [x.strip() for x in raw.split(',')]
        return [self.comma_rmap.get(x, x) for x in parts]

    @dynamic_property
    def lang_codes(self):

        def fget(self):
            vals = self.vals
            ans = []
            for name in vals:
                if name:
                    code = self._rmap.get(lower(name), None)
                    if code is not None:
                        ans.append(code)
            return ans

        def fset(self, lang_codes):
            ans = []
            for lc in lang_codes:
                name = self._lang_map.get(lc, None)
                if name is not None:
                    ans.append(name)
            self.setEditText(', '.join(ans))

        return property(fget=fget, fset=fset)

    def validate(self):
        vals = self.vals
        bad = []
        for name in vals:
            if name:
                code = self._rmap.get(lower(name), None)
                if code is None:
                    bad.append(name)
        return bad

