#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from functools import partial

from PyQt4.Qt import QMenu, QToolButton

from calibre.gui2.actions import InterfaceAction

class SimilarBooksAction(InterfaceAction):

    name = 'Similar Books'
    action_spec = (_('Similar books...'), None, None, None)
    popup_type = QToolButton.InstantPopup
    action_type = 'current'

    def genesis(self):
        m = QMenu(self.gui)
        for text, icon, target, shortcut in [
        (_('Books by same author'), 'user_profile.png', 'authors', _('Alt+A')),
        (_('Books in this series'), 'books_in_series.png', 'series',
            _('Alt+Shift+S')),
        (_('Books by this publisher'), 'publisher.png', 'publisher', _('Alt+P')),
        (_('Books with the same tags'), 'tags.png', 'tag', _('Alt+T')),]:
            ac = self.create_action(spec=(text, icon, None, shortcut),
                    attr=target)
            m.addAction(ac)
            ac.triggered.connect(partial(self.show_similar_books, target))
        self.qaction.setMenu(m)
        self.similar_menu = m

    def show_similar_books(self, type, *args):
        search, join = [], ' '
        idx = self.gui.library_view.currentIndex()
        if not idx.isValid():
            return
        row = idx.row()
        if type == 'series':
            series = idx.model().db.series(row)
            if series:
                search = ['series:"'+series+'"']
        elif type == 'publisher':
            publisher = idx.model().db.publisher(row)
            if publisher:
                search = ['publisher:"'+publisher+'"']
        elif type == 'tag':
            tags = idx.model().db.tags(row)
            if tags:
                search = ['tag:"='+t+'"' for t in tags.split(',')]
        elif type in ('author', 'authors'):
            authors = idx.model().db.authors(row)
            if authors:
                search = ['author:"='+a.strip().replace('|', ',')+'"' \
                                for a in authors.split(',')]
                join = ' or '
        if search:
            self.gui.search.set_search_string(join.join(search))


