'''
Created on 17 Jan 2025

@author: Charles Haley
'''

import copy
from functools import partial
import os

from qt.core import QAbstractItemView, QDialog, QDialogButtonBox, QIcon, QMenu, QSize, Qt, QTableWidget, QTableWidgetItem, QVBoxLayout

from calibre.constants import config_dir
from calibre.db.constants import TEMPLATE_ICON_INDICATOR
from calibre.gui2 import gprefs

CATEGORY_COLUMN = 0
VALUE_COLUMN = 1
ICON_COLUMN = 2
FOR_CHILDREN_COLUMN = 3
DELECTED_COLUMN = 4


class CategoryTableWidgetItem(QTableWidgetItem):

    def __init__(self, txt):
        super().__init__(txt)
        self._is_deleted = False

    @property
    def is_deleted(self):
        return self._is_deleted

    @is_deleted.setter
    def is_deleted(self, to_what):
        self._is_deleted = to_what


class TagBrowserRulesDisplay(QDialog):

    def __init__(self, parent):
        super().__init__(parent)

        self.setWindowTitle(_('View tag browser value icon rules'))
        l = QVBoxLayout()
        self.setLayout(l)
        table = self.table = QTableWidget()
        table.resize(800, 800)
        l.addWidget(table)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setColumnCount(4)
        table.setHorizontalHeaderLabels((_('category'), _('value'), _('icon'), _('for children')))
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_context_menu)

        # Capture clicks on the horizontal header to sort the table columns
        hh = self.table.horizontalHeader()
        hh.sectionResized.connect(self.table_column_resized)
        hh.setSectionsClickable(True)
        hh.sectionClicked.connect(self.do_sort)
        hh.setSortIndicatorShown(True)

        self.bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel)
        self.bb.accepted.connect(self.accept)
        self.bb.rejected.connect(self.reject)
        l.addWidget(self.bb)

        v = gprefs['tags_browser_value_icons']
        row = 0
        for category,vdict in v.items():
            for value in vdict:
                table.setRowCount(row + 1)
                d = v[category][value]
                table.setItem(row, 0, CategoryTableWidgetItem(category))
                table.setItem(row, 1, QTableWidgetItem(value))
                table.setItem(row, 2, QTableWidgetItem(d[0]))
                table.setItem(row, 3, QTableWidgetItem('' if value == TEMPLATE_ICON_INDICATOR else str(d[1])))
                row += 1

        self.category_order = 1
        self.value_order = 1
        self.icon_order = 0
        self.for_children_order = 0
        self.do_sort(VALUE_COLUMN)
        self.do_sort(CATEGORY_COLUMN)

        self.table.resizeColumnsToContents()
        try:
            self.table_column_widths = gprefs.get('tag_browser_rules_dialog_table_widths', None)
            self.restore_geometry(gprefs, 'tag_browser_rules_dialog_geometry')
        except Exception:
            pass

    def sizeHint(self):
        return QSize(800, 400)

    def show_context_menu(self, point):
        clicked_item = self.table.itemAt(point)
        item = self.table.item(clicked_item.row(), CATEGORY_COLUMN)
        m = QMenu(self)
        ac = m.addAction(_('Delete this rule'), partial(self.context_menu_handler, 'delete', item))
        ac.setEnabled(not item.is_deleted)
        ac = m.addAction(_('Undo delete'), partial(self.context_menu_handler, 'undelete', item))
        ac.setEnabled(item.is_deleted)
        m.exec(self.table.viewport().mapToGlobal(point))

    def context_menu_handler(self, action, item):
        item.setIcon(QIcon.ic('trash.png') if action == 'delete' else QIcon())
        item.is_deleted = action == 'delete'

    def save_state(self):
        self.table_column_widths = []
        for c in range(0, self.table.columnCount()):
            self.table_column_widths.append(self.table.columnWidth(c))
        gprefs['tag_browser_rules_dialog_table_widths'] = self.table_column_widths
        self.save_geometry(gprefs, 'tag_browser_rules_dialog_geometry')

    def table_column_resized(self, col, old, new):
        self.table_column_widths = []
        for c in range(0, self.table.columnCount()):
            self.table_column_widths.append(self.table.columnWidth(c))

    def resizeEvent(self, *args):
        QDialog.resizeEvent(self, *args)
        if self.table_column_widths is not None:
            for c,w in enumerate(self.table_column_widths):
                self.table.setColumnWidth(c, w)
        else:
            # the vertical scroll bar might not be rendered, so might not yet
            # have a width. Assume 25. Not a problem because user-changed column
            # widths will be remembered
            w = self.table.width() - 25 - self.table.verticalHeader().width()
            w //= self.table.columnCount()
            for c in range(0, self.table.columnCount()):
                self.table.setColumnWidth(c, w)
        self.save_state()

    def do_sort(self, section):
        if section == CATEGORY_COLUMN:
            self.category_order = 1 - self.category_order
            self.table.sortByColumn(CATEGORY_COLUMN, Qt.SortOrder(self.category_order))
        elif section == VALUE_COLUMN:
            self.value_order = 1 - self.value_order
            self.table.sortByColumn(VALUE_COLUMN, Qt.SortOrder(self.value_order))
        elif section == ICON_COLUMN:
            self.icon_order = 1 - self.icon_order
            self.table.sortByColumn(ICON_COLUMN, Qt.SortOrder(self.icon_order))
        elif section == FOR_CHILDREN_COLUMN:
            self.for_children_order = 1 - self.for_children_order
            self.table.sortByColumn(FOR_CHILDREN_COLUMN, Qt.SortOrder(self.for_children_order))

    def accept(self):
        self.save_state()
        v = copy.deepcopy(gprefs['tags_browser_value_icons'])
        for r in range(0, self.table.rowCount()):
            cat_item = self.table.item(r, CATEGORY_COLUMN)
            if cat_item.is_deleted:
                val = self.table.item(r, VALUE_COLUMN).text()
                if val != TEMPLATE_ICON_INDICATOR:
                    icon_file = self.table.item(r, ICON_COLUMN).text()
                    path = os.path.join(config_dir, 'tb_icons', icon_file)
                    try:
                        os.remove(path)
                    except:
                        pass
                v[cat_item.text()].pop(val, None)
        # Remove categories with no rules
        for category in list(v.keys()):
            if len(v[category]) == 0:
                v.pop(category, None)
        gprefs['tags_browser_value_icons'] = v

        from calibre.gui2.ui import get_gui
        get_gui().tags_view.reset_value_icons()
        super().accept()

    def reject(self):
        self.save_state()
        super().reject()
