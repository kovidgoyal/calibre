#!/usr/bin/env python


__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import sys

from qt.core import QAbstractItemView, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QPushButton, Qt, QVBoxLayout, QWidget

from calibre.constants import ismacos
from calibre.gui2 import gprefs
from calibre.gui2.ui import get_gui


def get_saved_field_data(name, all_fields):
    db = get_gui().current_db
    val = db.new_api.pref('catalog-field-data-for-' + name)
    if val is None:
        sort_order = gprefs.get(name + '_db_fields_sort_order', {})
        fields = frozenset(gprefs.get(name+'_db_fields', all_fields))
    else:
        sort_order = val['sort_order']
        fields = frozenset(val['fields'])
    return sort_order, fields


def set_saved_field_data(name, fields, sort_order):
    db = get_gui().current_db
    db.new_api.set_pref('catalog-field-data-for-' + name, {'fields': fields, 'sort_order': sort_order})
    gprefs.set(name+'_db_fields', fields)
    gprefs.set(name + '_db_fields_sort_order', sort_order)


class ListWidgetItem(QListWidgetItem):

    def __init__(self, colname, human_name, position_in_booklist, parent):
        super().__init__(human_name, parent)
        self.setData(Qt.ItemDataRole.UserRole, colname)
        self.position_in_booklist = position_in_booklist

    def __lt__(self, other):
        try:
            return self.position_in_booklist < getattr(other, 'position_in_booklist', sys.maxsize)
        except TypeError:
            return False


class PluginWidget(QWidget):

    TITLE = _('CSV/XML options')
    HELP  = _('Options specific to')+' CSV/XML '+_('output')
    sync_enabled = False
    formats = {'csv', 'xml'}
    handles_scrolling = True

    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.l = l = QVBoxLayout(self)
        self.la = la = QLabel(_('Fields to include in output:'))
        la.setWordWrap(True)
        l.addWidget(la)
        self.db_fields = QListWidget(self)
        l.addWidget(self.db_fields)
        self.la2 = la = QLabel(_('Drag and drop to re-arrange fields'))
        self.db_fields.setDragEnabled(True)
        self.db_fields.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.db_fields.setDefaultDropAction(Qt.DropAction.CopyAction if ismacos else Qt.DropAction.MoveAction)
        self.db_fields.setAlternatingRowColors(True)
        self.db_fields.setObjectName("db_fields")
        h = QHBoxLayout()
        l.addLayout(h)
        h.addWidget(la), h.addStretch(10)
        self.select_all_button = b = QPushButton(_('Select &all'))
        b.clicked.connect(self.select_all)
        h.addWidget(b)
        self.select_all_button = b = QPushButton(_('Select &none'))
        b.clicked.connect(self.select_none)
        h.addWidget(b)
        self.select_visible_button = b = QPushButton(_('Select &visible'))
        b.clicked.connect(self.select_visible)
        b.setToolTip(_('Select the fields currently shown in the book list'))
        h.addWidget(b)
        self.order_button = b = QPushButton(_('&Sort by booklist'))
        b.clicked.connect(self.order_by_booklist)
        b.setToolTip(_('Sort the fields by their position in the book list'))
        h.addWidget(b)

    def select_all(self):
        for row in range(self.db_fields.count()):
            item = self.db_fields.item(row)
            item.setCheckState(Qt.CheckState.Checked)

    def select_none(self):
        for row in range(self.db_fields.count()):
            item = self.db_fields.item(row)
            item.setCheckState(Qt.CheckState.Unchecked)

    def select_visible(self):
        state = get_gui().library_view.get_state()
        hidden = frozenset(state['hidden_columns'])
        for row in range(self.db_fields.count()):
            item = self.db_fields.item(row)
            field = item.data(Qt.ItemDataRole.UserRole)
            item.setCheckState(Qt.CheckState.Unchecked if field in hidden else Qt.CheckState.Checked)

    def order_by_booklist(self):
        self.db_fields.sortItems()

    def initialize(self, catalog_name, db):
        self.name = catalog_name
        from calibre.library.catalogs import FIELDS
        db = get_gui().current_db
        self.all_fields = {x for x in FIELDS if x != 'all'} | set(db.custom_field_keys())
        sort_order, fields = get_saved_field_data(self.name, self.all_fields)
        fm = db.field_metadata

        def name(x):
            if x == 'isbn':
                return 'ISBN'
            if x == 'library_name':
                return _('Library name')
            if x.endswith('_index'):
                return name(x[:-len('_index')]) + ' ' + _('Number')
            return fm[x].get('name') or x

        state = get_gui().library_view.get_state()
        cpos = state['column_positions']

        def key(x):
            return (sort_order.get(x, 10000), name(x))

        self.db_fields.clear()
        for x in sorted(self.all_fields, key=key):
            pos = cpos.get(x, sys.maxsize)
            if x == 'series_index':
                pos = cpos.get('series', sys.maxsize)
            ListWidgetItem(x, name(x) + ' (%s)' % x, pos, self.db_fields)
            if x.startswith('#') and fm[x]['datatype'] == 'series':
                x += '_index'
                ListWidgetItem(x, name(x) + ' (%s)' % x, pos, self.db_fields)

        # Restore the activated fields from last use
        for x in range(self.db_fields.count()):
            item = self.db_fields.item(x)
            item.setCheckState(Qt.CheckState.Checked if str(item.data(Qt.ItemDataRole.UserRole)) in fields else Qt.CheckState.Unchecked)

    def options(self):
        # Save the currently activated fields
        fields, all_fields = [], []
        for x in range(self.db_fields.count()):
            item = self.db_fields.item(x)
            all_fields.append(str(item.data(Qt.ItemDataRole.UserRole)))
            if item.checkState() == Qt.CheckState.Checked:
                fields.append(str(item.data(Qt.ItemDataRole.UserRole)))
        set_saved_field_data(self.name, fields, {x:i for i, x in enumerate(all_fields)})

        # Return a dictionary with current options for this widget
        if len(fields):
            return {'fields':fields}
        else:
            return {'fields':['all']}
