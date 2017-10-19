#!/usr/bin/env python2
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from functools import partial

from PyQt5.Qt import QToolButton

from calibre.gui2.actions import InterfaceAction


class SimilarBooksAction(InterfaceAction):

    name = 'Similar Books'
    action_spec = (_('Similar books...'), 'similar.png', _('Show books similar to the current book'), None)
    popup_type = QToolButton.InstantPopup
    action_type = 'current'
    action_add_menu = True

    def genesis(self):
        m = self.qaction.menu()
        for text, icon, target, shortcut in [
        (_('Books by same author'), 'user_profile.png', 'authors', 'Alt+A'),
        (_('Books in this series'), 'books_in_series.png', 'series',
            'Alt+Shift+S'),
        (_('Books by this publisher'), 'publisher.png', 'publisher', 'Alt+P'),
        (_('Books with the same tags'), 'tags.png', 'tags', 'Alt+T'),]:
            ac = self.create_action(spec=(text, icon, None, shortcut),
                    attr=target)
            m.addAction(ac)
            ac.triggered.connect(partial(self.show_similar_books, target))
        self.qaction.setMenu(m)

    def show_similar_books(self, typ, *args):
        idx = self.gui.library_view.currentIndex()
        if not idx.isValid():
            return
        db = idx.model().db
        row = idx.row()

        # Get the parameters for this search
        col = db.prefs['similar_' + typ + '_search_key']
        match = db.prefs['similar_' + typ + '_match_kind']
        if match == 'match_all':
            join = ' and '
        else:
            join = ' or '

        # Get all the data for the current record
        mi = db.get_metadata(row)

        # Get the definitive field name to use for this search. If the field
        # is a grouped search term, the function returns the list of fields that
        # are to be searched, otherwise it returns the field name.
        loc = db.field_metadata.search_term_to_field_key(icu_lower(col))
        if isinstance(loc, list):
            # Grouped search terms are a list of fields. Get all the values,
            # pruning duplicates
            val = set()
            for f in loc:
                v = mi.get(f, None)
                if not v:
                    continue
                if isinstance(v, list):
                    val.update(v)
                else:
                    val.add(v)
        else:
            # Get the value of the requested field. Can be a list or a simple val
            val = mi.get(col, None)
        if not val:
            return

        if isinstance(val, basestring):
            val = [val]
        search = [col + ':"='+t.replace('"', '\\"')+'"' for t in val]
        if search:
            self.gui.search.set_search_string(join.join(search),
                    store_in_history=True)
