#!/usr/bin/env python


__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

from contextlib import suppress
from functools import partial
from qt.core import QAction, QDialog, QIcon, QToolButton, pyqtSignal

from calibre.gui2.actions import InterfaceAction
from calibre.utils.icu import primary_sort_key
from calibre.library.field_metadata import category_icon_map
from polyglot.builtins import iteritems

SORT_HIDDEN_PREF = 'sort-action-hidden-fields'


def change_hidden(key, visible):
    from calibre.gui2.ui import get_gui
    gui = get_gui()
    if gui is not None:
        db = gui.current_db.new_api
        val = set(db.pref(SORT_HIDDEN_PREF) or ())
        if visible:
            val.discard(key)
        else:
            val.add(key)
        db.set_pref(SORT_HIDDEN_PREF, tuple(val))


class SortAction(QAction):

    sort_requested = pyqtSignal(object, object)

    def __init__(self, text, key, ascending, parent):
        QAction.__init__(self, text, parent)
        self.key, self.ascending = key, ascending
        self.triggered.connect(self)
        ic = category_icon_map['custom:'] if self.key.startswith('#') else category_icon_map.get(key)
        if ic:
            self.setIcon(QIcon.ic(ic))

    def __call__(self):
        self.sort_requested.emit(self.key, self.ascending)


class SortByAction(InterfaceAction):

    name = 'Sort By'
    action_spec = (_('Sort by'), 'sort.png', _('Sort the list of books'), None)
    action_type = 'current'
    popup_type = QToolButton.ToolButtonPopupMode.InstantPopup
    action_add_menu = True
    dont_add_to = frozenset(('context-menu-cover-browser', ))

    def genesis(self):
        self.sorted_icon = QIcon.ic('ok.png')
        self.qaction.menu().aboutToShow.connect(self.about_to_show)

        def c(attr, title, tooltip, callback, keys=()):
            ac = self.create_action(spec=(title, None, tooltip, keys), attr=attr)
            ac.triggered.connect(callback)
            self.gui.addAction(ac)
            return ac

        c('reverse_sort_action', _('Reverse current sort'), _('Reverse the current sort order'), self.reverse_sort, 'shift+f5')
        c('reapply_sort_action', _('Re-apply current sort'), _('Re-apply the current sort'), self.reapply_sort, 'f5')

    def reverse_sort(self):
        self.gui.current_view().reverse_sort()

    def reapply_sort(self):
        self.gui.current_view().resort()

    def location_selected(self, loc):
        enabled = loc == 'library'
        self.qaction.setEnabled(enabled)
        self.menuless_qaction.setEnabled(enabled)

    def about_to_show(self):
        self.update_menu()

    def update_menu(self, menu=None):
        menu = self.qaction.menu() if menu is None else menu
        for action in menu.actions():
            if hasattr(action, 'sort_requested'):
                action.sort_requested.disconnect()
                with suppress(TypeError):
                    action.toggled.disconnect()

        menu.clear()
        lv = self.gui.library_view
        m = lv.model()
        db = m.db
        try:
            sort_col, order = m.sorted_on
        except TypeError:
            sort_col, order = 'date', True
        fm = db.field_metadata
        name_map = {v:k for k, v in iteritems(fm.ui_sortable_field_keys())}
        hidden = frozenset(db.new_api.pref(SORT_HIDDEN_PREF, default=()) or ())
        hidden_items_menu = menu.addMenu(_('Select sortable columns'))
        menu.addAction(_('Sort on multiple columns'), self.choose_multisort)
        menu.addSeparator()
        all_names = sorted(name_map, key=primary_sort_key)
        for name in all_names:
            key = name_map[name]
            ac = hidden_items_menu.addAction(name)
            ac.setCheckable(True)
            ac.setChecked(key not in hidden)
            ac.setObjectName(key)
            ac.toggled.connect(partial(change_hidden, key))

        for name in all_names:
            key = name_map[name]
            if key == 'ondevice' and self.gui.device_connected is None:
                continue
            if key in hidden:
                continue
            ascending = None
            if key == sort_col:
                name = _('%s [reverse current sort]') % name
                ascending = not order
            sac = SortAction(name, key, ascending, menu)
            if key == sort_col:
                sac.setIcon(self.sorted_icon)
            sac.sort_requested.connect(self.sort_requested)
            if key == sort_col:
                before = menu.actions()[0] if menu.actions() else None
                menu.insertAction(before, sac)
                menu.insertSeparator(before)
            else:
                menu.addAction(sac)

    def choose_multisort(self):
        from calibre.gui2.dialogs.multisort import ChooseMultiSort
        d = ChooseMultiSort(self.gui.current_db, parent=self.gui, is_device_connected=self.gui.device_connected)
        if d.exec() == QDialog.DialogCode.Accepted:
            self.gui.library_view.multisort(d.current_sort_spec)

    def sort_requested(self, key, ascending):
        if ascending is None:
            self.gui.library_view.intelligent_sort(key, True)
        else:
            self.gui.library_view.sort_by_named_field(key, ascending)
