#!/usr/bin/env python2
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from calibre.gui2 import gui_prefs
from calibre.gui2.complete2 import EditWithComplete
from calibre.utils.localization import lang_map_for_ui
from calibre.utils.icu import sort_key, lower


class LanguagesEdit(EditWithComplete):

    def __init__(self, parent=None, db=None, prefs=None):
        self.prefs = prefs or gui_prefs()
        self.refresh_recently_used()
        EditWithComplete.__init__(self, parent, sort_func=self.sort_language_items_key)

        self.setSizeAdjustPolicy(self.AdjustToMinimumContentsLengthWithIcon)
        self.setMinimumContentsLength(20)
        self._lang_map = lang_map_for_ui()
        self.names_with_commas = [x for x in self._lang_map.itervalues() if ',' in x]
        self.comma_map = {k:k.replace(',', '|') for k in self.names_with_commas}
        self.comma_rmap = {v:k for k, v in self.comma_map.iteritems()}
        self._rmap = {lower(v):k for k,v in self._lang_map.iteritems()}
        self.init_langs(db)
        self.item_selected.connect(self.update_recently_used)

    def init_langs(self, db):
        self.update_items_cache(self._lang_map.itervalues())

    def refresh_recently_used(self):
        recently_used = self.prefs.get('recently_used_languages') or ()
        self.recently_used = {x:i for i, x in enumerate(recently_used) if x}

    def update_recently_used(self):
        recently_used = self.prefs.get('recently_used_languages') or []
        vals = self.vals
        for x in vals:
            if x:
                if x in recently_used:
                    recently_used.remove(x)
                recently_used.insert(0, x)
        self.prefs.set('recently_used_languages', recently_used[:5])

    def sort_language_items_key(self, val):
        idx = self.recently_used.get(val, 100000)
        return (idx, sort_key(val))

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
            self.set_lang_codes(lang_codes, allow_undo=False)

        return property(fget=fget, fset=fset)

    def set_lang_codes(self, lang_codes, allow_undo=True):
        ans = []
        for lc in lang_codes:
            name = self._lang_map.get(lc, None)
            if name is not None:
                ans.append(name)
        ans = ', '.join(ans)

        if allow_undo:
            orig, self.disable_popup = self.disable_popup, True
            try:
                self.lineEdit().selectAll(), self.lineEdit().insert(ans)
            finally:
                self.disable_popup = orig
        else:
            self.setEditText(ans)

    def validate(self):
        vals = self.vals
        bad = []
        for name in vals:
            if name:
                code = self._rmap.get(lower(name), None)
                if code is None:
                    bad.append(name)
        return bad
