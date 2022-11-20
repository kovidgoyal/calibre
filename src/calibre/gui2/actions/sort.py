#!/usr/bin/env python


__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

from contextlib import suppress
from qt.core import (
    QAbstractItemView, QAction, QDialog, QDialogButtonBox, QIcon, QListWidget,
    QListWidgetItem, QSize, Qt, QToolButton, QVBoxLayout, pyqtSignal,
)

from calibre.gui2.actions import InterfaceAction
from calibre.library.field_metadata import category_icon_map
from calibre.utils.icu import primary_sort_key
from polyglot.builtins import iteritems

SORT_HIDDEN_PREF = 'sort-action-hidden-fields'


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
        menu.addAction(_('Select sortable columns')).triggered.connect(self.select_sortable_columns)
        menu.addAction(_('Sort on multiple columns'), self.choose_multisort)
        menu.addSeparator()
        all_names = sorted(name_map, key=primary_sort_key)

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

    def select_sortable_columns(self):
        db = self.gui.current_db
        fm = db.field_metadata
        name_map = {v:k for k, v in iteritems(fm.ui_sortable_field_keys())}
        hidden = frozenset(db.new_api.pref(SORT_HIDDEN_PREF, default=()) or ())
        all_names = sorted(name_map, key=primary_sort_key)
        items = QListWidget()
        items.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)
        for display_name in all_names:
            key = name_map[display_name]
            i = QListWidgetItem(display_name, items)
            i.setData(Qt.ItemDataRole.UserRole, key)
            i.setSelected(key not in hidden)
        d = QDialog(self.gui)
        l = QVBoxLayout(d)
        l.addWidget(items)
        d.setWindowTitle(_('Select sortable columns'))
        d.bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        d.bb.accepted.connect(d.accept)
        d.bb.rejected.connect(d.reject)
        l.addWidget(d.bb)
        d.resize(d.sizeHint() + QSize(50, 100))
        if d.exec() == QDialog.DialogCode.Accepted:
            hidden = []
            for i in (items.item(x) for x in range(items.count())):
                if not i.isSelected():
                    hidden.append(i.data(Qt.ItemDataRole.UserRole))
            db.new_api.set_pref(SORT_HIDDEN_PREF, tuple(hidden))

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
