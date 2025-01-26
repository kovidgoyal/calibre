#!/usr/bin/env python


__license__   = 'GPL v3'
__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import json

from qt.core import QAbstractListModel, QIcon, QItemSelectionModel, Qt

from calibre.gui2 import (
    choose_files,
    choose_save_file,
    config,
    error_dialog,
    gprefs,
)
from calibre.gui2.book_details import get_field_list


class DisplayedFields(QAbstractListModel):  # {{{

    def __init__(self, db, parent=None, pref_name=None, category_icons=None):
        self.pref_name = pref_name or 'book_display_fields'
        QAbstractListModel.__init__(self, parent)

        self.fields = []
        self.db = db
        self.changed = False
        self.category_icons = category_icons

    def get_field_list(self, use_defaults=False):
        return get_field_list(self.db.field_metadata, use_defaults=use_defaults, pref_name=self.pref_name)

    def initialize(self, use_defaults=False):
        self.beginResetModel()
        self.fields = [[x[0], x[1]] for x in self.get_field_list(use_defaults=use_defaults)]
        self.endResetModel()
        self.changed = True

    def rowCount(self, *args):
        return len(self.fields)

    def data(self, index, role):
        try:
            field, visible = self.fields[index.row()]
        except:
            return None
        if role == Qt.ItemDataRole.DisplayRole:
            name = field
            try:
                name = self.db.field_metadata[field]['name']
            except:
                pass
            if field == 'path':
                name = _('Folders/path')
            name = field.partition('.')[0][1:] if field.startswith('@') else name
            if not name:
                return field
            return f'{name} ({field})'
        if role == Qt.ItemDataRole.CheckStateRole:
            return Qt.CheckState.Checked if visible else Qt.CheckState.Unchecked
        if role == Qt.ItemDataRole.DecorationRole:
            if self.category_icons:
                icon = self.category_icons.get(field, None)
                if icon is not None:
                    return icon
            if field.startswith('#'):
                return QIcon.ic('column.png')
        return None

    def toggle_all(self, show=True):
        for i in range(self.rowCount()):
            idx = self.index(i)
            if idx.isValid():
                self.setData(idx, Qt.CheckState.Checked if show else Qt.CheckState.Unchecked, Qt.ItemDataRole.CheckStateRole)

    def flags(self, index):
        ans = QAbstractListModel.flags(self, index)
        return ans | Qt.ItemFlag.ItemIsUserCheckable

    def setData(self, index, val, role):
        ret = False
        if role == Qt.ItemDataRole.CheckStateRole:
            self.fields[index.row()][1] = val in (Qt.CheckState.Checked, Qt.CheckState.Checked.value)
            self.changed = True
            ret = True
            self.dataChanged.emit(index, index)
        return ret

    def restore_defaults(self):
        self.initialize(use_defaults=True)

    def commit(self):
        if self.changed:
            self.db.new_api.set_pref(self.pref_name, self.fields)

    def move(self, idx, delta):
        row = idx.row() + delta
        if row >= 0 and row < len(self.fields):
            t = self.fields[row]
            self.fields[row] = self.fields[row-delta]
            self.fields[row-delta] = t
            self.dataChanged.emit(idx, idx)
            idx = self.index(row)
            self.dataChanged.emit(idx, idx)
            self.changed = True
            return idx

def export_layout(in_widget, model=None):
    filename = choose_save_file(in_widget, 'look_feel_prefs_import_export_field_list',
            _('Save column list to file'),
            filters=[(_('Column list'), ['json'])])
    if filename:
        try:
            with open(filename, 'w') as f:
                json.dump(model.fields, f, indent=1)
        except Exception as err:
            error_dialog(in_widget, _('Export field layout'),
                         _('<p>Could not write field list. Error:<br>%s')%err, show=True)

def import_layout(in_widget, model=None):
    filename = choose_files(in_widget, 'look_feel_prefs_import_export_field_list',
            _('Load column list from file'),
            filters=[(_('Column list'), ['json'])])
    if filename:
        try:
            with open(filename[0]) as f:
                fields = json.load(f)
            model.initialize(pref_data_override=fields)
            in_widget.changed_signal.emit()
        except Exception as err:
            error_dialog(in_widget, _('Import layout'),
                         _('<p>Could not read field list. Error:<br>%s')%err, show=True)

def reset_layout(in_widget, model=None):
    model.initialize(use_defaults=True)
    in_widget.changed_signal.emit()


def move_field_up(widget, model):
    idx = widget.currentIndex()
    if idx.isValid():
        idx = model.move(idx, -1)
        if idx is not None:
            sm = widget.selectionModel()
            sm.select(idx, QItemSelectionModel.SelectionFlag.ClearAndSelect)
            widget.setCurrentIndex(idx)


def move_field_down(widget, model):
    idx = widget.currentIndex()
    if idx.isValid():
        idx = model.move(idx, 1)
        if idx is not None:
            sm = widget.selectionModel()
            sm.select(idx, QItemSelectionModel.SelectionFlag.ClearAndSelect)
            widget.setCurrentIndex(idx)

# }}}
