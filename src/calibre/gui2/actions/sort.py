#!/usr/bin/env python2
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

from PyQt5.Qt import QToolButton, QAction, pyqtSignal, QIcon

from calibre.gui2.actions import InterfaceAction
from calibre.utils.icu import sort_key


class SortAction(QAction):

    sort_requested = pyqtSignal(object, object)

    def __init__(self, text, key, ascending, parent):
        QAction.__init__(self, text, parent)
        self.key, self.ascending = key, ascending
        self.triggered.connect(self)

    def __call__(self):
        self.sort_requested.emit(self.key, self.ascending)


class SortByAction(InterfaceAction):

    name = 'Sort By'
    action_spec = (_('Sort by'), 'sort.png', _('Sort the list of books'), None)
    action_type = 'current'
    popup_type = QToolButton.InstantPopup
    action_add_menu = True
    dont_add_to = frozenset([
        'toolbar-device', 'context-menu-device', 'menubar', 'menubar-device',
        'context-menu-cover-browser'])

    def genesis(self):
        self.sorted_icon = QIcon(I('ok.png'))
        self.qaction.menu().aboutToShow.connect(self.about_to_show)

    def location_selected(self, loc):
        self.qaction.setEnabled(loc == 'library')

    def about_to_show(self):
        self.update_menu()

    def update_menu(self, menu=None):
        menu = self.qaction.menu() if menu is None else menu
        for action in menu.actions():
            action.sort_requested.disconnect()
        menu.clear()
        lv = self.gui.library_view
        m = lv.model()
        db = m.db
        try:
            sort_col, order = m.sorted_on
        except TypeError:
            sort_col, order = 'date', True
        fm = db.field_metadata
        name_map = {v:k for k, v in fm.ui_sortable_field_keys().iteritems()}
        for name in sorted(name_map, key=sort_key):
            key = name_map[name]
            if key == 'ondevice' and self.gui.device_connected is None:
                continue
            ascending = None
            if key == sort_col:
                name = _('%s [reverse current sort]') % name
                ascending = not order
            sac = SortAction(name, key, ascending, menu)
            if key == sort_col:
                sac.setIcon(self.sorted_icon)
            sac.sort_requested.connect(self.sort_requested)
            menu.addAction(sac)

    def sort_requested(self, key, ascending):
        if ascending is None:
            self.gui.library_view.intelligent_sort(key, True)
        else:
            self.gui.library_view.sort_by_named_field(key, ascending)
