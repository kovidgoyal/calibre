#!/usr/bin/env python


__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import copy, sys
from contextlib import suppress

from qt.core import Qt, QTableWidgetItem, QIcon

from calibre.gui2 import gprefs, Application
from calibre.gui2.preferences import ConfigWidgetBase, test_widget
from calibre.gui2.preferences.columns_ui import Ui_Form
from calibre.gui2.preferences.create_custom_column import CreateCustomColumn
from calibre.gui2 import error_dialog, question_dialog


class ConfigWidget(ConfigWidgetBase, Ui_Form):

    restart_critical = True

    def genesis(self, gui):
        self.gui = gui
        db = self.gui.library_view.model().db
        self.custcols = copy.deepcopy(db.field_metadata.custom_field_metadata())
        for k, cc in self.custcols.items():
            cc['original_key'] = k
        # Using max() in this way requires python 3.4+
        self.initial_created_count = max((x['colnum'] for x in self.custcols.values()),
                                         default=0) + 1
        self.created_count = self.initial_created_count

        self.column_up.clicked.connect(self.up_column)
        self.column_down.clicked.connect(self.down_column)
        self.del_custcol_button.clicked.connect(self.del_custcol)
        self.add_custcol_button.clicked.connect(self.add_custcol)
        self.add_col_button.clicked.connect(self.add_custcol)
        self.edit_custcol_button.clicked.connect(self.edit_custcol)
        self.opt_columns.currentItemChanged.connect(self.set_up_down_enabled)
        for signal in ('Activated', 'Changed', 'DoubleClicked', 'Clicked'):
            signal = getattr(self.opt_columns, 'item'+signal)
            signal.connect(self.columns_changed)

    def initialize(self):
        ConfigWidgetBase.initialize(self)
        self.init_columns()

    def restore_defaults(self):
        ConfigWidgetBase.restore_defaults(self)
        self.init_columns(defaults=True)
        self.changed_signal.emit()

    def commit(self):
        widths = []
        for i in range(0, self.opt_columns.columnCount()):
            widths.append(self.opt_columns.columnWidth(i))
        gprefs.set('custcol-prefs-table-geometry', widths)
        rr = ConfigWidgetBase.commit(self)
        return self.apply_custom_column_changes() or rr

    def init_columns(self, defaults=False):
        # Set up columns
        self.opt_columns.blockSignals(True)
        self.model = model = self.gui.library_view.model()
        colmap = list(model.column_map)
        state = self.columns_state(defaults)
        self.hidden_cols = state['hidden_columns']
        positions = state['column_positions']
        colmap.sort(key=lambda x: positions[x])
        self.opt_columns.clear()

        db = model.db
        self.field_metadata = db.field_metadata

        self.opt_columns.setColumnCount(6)
        self.opt_columns.setHorizontalHeaderItem(0, QTableWidgetItem(_('Order')))
        self.opt_columns.setHorizontalHeaderItem(1, QTableWidgetItem(_('Column header')))
        self.opt_columns.setHorizontalHeaderItem(2, QTableWidgetItem(_('Lookup name')))
        self.opt_columns.setHorizontalHeaderItem(3, QTableWidgetItem(_('Type')))
        self.opt_columns.setHorizontalHeaderItem(4, QTableWidgetItem(_('Description')))
        self.opt_columns.setHorizontalHeaderItem(5, QTableWidgetItem(_('Status')))
        self.opt_columns.horizontalHeader().sectionClicked.connect(self.table_sorted)
        self.opt_columns.verticalHeader().hide()

        self.opt_columns.setRowCount(len(colmap))
        self.column_desc = dict(map(lambda x:(CreateCustomColumn.column_types[x]['datatype'],
                                         CreateCustomColumn.column_types[x]['text']),
                                  CreateCustomColumn.column_types))

        for row, key in enumerate(colmap):
            self.setup_row(row, key, row)
        self.initial_row_count = row
        self.opt_columns.setSortingEnabled(True)
        self.opt_columns.horizontalHeader().setSortIndicator(0, Qt.SortOrder.AscendingOrder)
        self.restore_geometry()
        self.opt_columns.cellDoubleClicked.connect(self.row_double_clicked)
        self.opt_columns.setCurrentCell(0, 1)
        self.set_up_down_enabled(self.opt_columns.currentItem(), None)
        self.opt_columns.blockSignals(False)

    def set_up_down_enabled(self, current_item, _):
        h = self.opt_columns.horizontalHeader()
        row = current_item.row()
        if h.sortIndicatorSection() == 0 and h.sortIndicatorOrder() == Qt.SortOrder.AscendingOrder:
            self.column_up.setEnabled(row > 0 and row <= self.initial_row_count)
            self.column_down.setEnabled(row < self.initial_row_count)

    def columns_changed(self, *args):
        self.changed_signal.emit()

    def columns_state(self, defaults=False):
        if defaults:
            return self.gui.library_view.get_default_state()
        return self.gui.library_view.get_state()

    def table_sorted(self, column):
        h = self.opt_columns.horizontalHeader()
        enabled = column == 0 and h.sortIndicatorOrder() == Qt.SortOrder.AscendingOrder
        self.column_up.setEnabled(enabled)
        self.column_down.setEnabled(enabled)
        self.opt_columns.scrollTo(self.opt_columns.currentIndex())
        self.set_up_down_enabled(self.opt_columns.currentItem(), _)

    def row_double_clicked(self, r, c):
        self.edit_custcol()

    def restore_geometry(self):
        geom = gprefs.get('custcol-prefs-table-geometry', None)
        if geom is not None and len(geom) == self.opt_columns.columnCount():
            with suppress(Exception):
                for i in range(0, self.opt_columns.columnCount()):
                    self.opt_columns.setColumnWidth(i, geom[i])
                return
        self.opt_columns.resizeColumnsToContents()

    def setup_row(self, row, key, order):
        flags = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable

        if self.is_custom_key(key):
            cc = self.custcols[key]
            original_key = cc['original_key']
        else:
            cc = self.field_metadata[key]
            original_key = key

        self.opt_columns.setSortingEnabled(False)
        item = QTableWidgetItem()
        item.setData(Qt.ItemDataRole.DisplayRole, order)
        item.setToolTip(str(order))
        item.setData(Qt.ItemDataRole.UserRole, key)
        item.setFlags(flags)
        self.opt_columns.setItem(row, 0, item)

        flags |= Qt.ItemFlag.ItemIsUserCheckable
        if key == 'ondevice':
            item.setFlags(flags & ~Qt.ItemFlag.ItemIsEnabled)
            item.setCheckState(Qt.CheckState.PartiallyChecked)
        else:
            item.setFlags(flags)
            item.setCheckState(Qt.CheckState.Unchecked if key in self.hidden_cols else
                    Qt.CheckState.Checked)

        item = QTableWidgetItem(cc['name'])
        item.setToolTip(cc['name'])
        item.setFlags(flags)
        if self.is_custom_key(key):
            item.setData(Qt.ItemDataRole.DecorationRole, (QIcon.ic('column.png')))
        self.opt_columns.setItem(row, 1, item)

        item = QTableWidgetItem(key)
        item.setToolTip(key)
        item.setFlags(flags)
        self.opt_columns.setItem(row, 2, item)

        if key == 'title':
            coltype = _('Text')
        elif key == 'ondevice':
            coltype = _('Yes/No with text')
        else:
            dt = cc['datatype']
            if cc['is_multiple']:
                if key == 'authors' or cc.get('display', {}).get('is_names', False):
                    coltype = _('Ampersand separated text, shown in the Tag browser')
                else:
                    coltype = self.column_desc['*' + dt]
            else:
                coltype = self.column_desc[dt]
        item = QTableWidgetItem(coltype)
        item.setToolTip(coltype)
        item.setFlags(flags)
        self.opt_columns.setItem(row, 3, item)

        desc = cc['display'].get('description', "")
        item = QTableWidgetItem(desc)
        item.setToolTip(desc)
        item.setFlags(flags)
        self.opt_columns.setItem(row, 4, item)

        if '*deleted' in cc:
            col_status = _('Deleted column. Double-click to undelete it')
        elif self.is_new_custom_column(cc):
            col_status = _('New column')
        elif original_key != key:
            col_status = _('Edited. Lookup name was {}').format(original_key)
        elif '*edited' in cc:
            col_status = _('Edited')
        else:
            col_status = ''
        item = QTableWidgetItem(col_status)
        item.setToolTip(col_status)
        item.setFlags(flags)
        self.opt_columns.setItem(row, 5, item)
        self.opt_columns.setSortingEnabled(True)

    def up_column(self):
        self.opt_columns.setSortingEnabled(False)
        row = self.opt_columns.currentRow()
        if row > 0:
            for i in range(0, self.opt_columns.columnCount()):
                lower = self.opt_columns.takeItem(row-1, i)
                upper = self.opt_columns.takeItem(row, i)
                self.opt_columns.setItem(row, i, lower)
                self.opt_columns.setItem(row-1, i, upper)
            self.setup_row(row-1, self.opt_columns.item(row-1, 2).text(), row-1)
            self.setup_row(row, self.opt_columns.item(row, 2).text(), row)
            self.opt_columns.setCurrentCell(row-1, 1)
            self.changed_signal.emit()
        self.opt_columns.setSortingEnabled(True)

    def down_column(self):
        self.opt_columns.setSortingEnabled(False)
        row = self.opt_columns.currentRow()
        if row < self.opt_columns.rowCount()-1:
            for i in range(0, self.opt_columns.columnCount()):
                lower = self.opt_columns.takeItem(row, i)
                upper = self.opt_columns.takeItem(row+1, i)
                self.opt_columns.setItem(row+1, i, lower)
                self.opt_columns.setItem(row, i, upper)
            self.setup_row(row+1, self.opt_columns.item(row+1, 2).text(), row+1)
            self.setup_row(row, self.opt_columns.item(row, 2).text(), row)
            self.opt_columns.setCurrentCell(row+1, 1)
            self.changed_signal.emit()
        self.opt_columns.setSortingEnabled(True)

    def is_new_custom_column(self, cc):
        return 'colnum' in cc and cc['colnum'] >= self.initial_created_count

    def set_new_custom_column(self, cc):
        self.created_count += 1
        cc['colnum'] = self.created_count

    def del_custcol(self):
        row = self.opt_columns.currentRow()
        if row < 0:
            return error_dialog(self, '', _('You must select a column to delete it'),
                    show=True)
        key = str(self.opt_columns.item(row, 0).data(Qt.ItemDataRole.UserRole) or '')
        if key not in self.custcols:
            return error_dialog(self, '',
                    _('The selected column is not a custom column'), show=True)
        if not question_dialog(self, _('Are you sure?'),
            _('Do you really want to delete column %s and all its data?') %
            self.custcols[key]['name'], show_copy_button=False):
            return
        if self.is_new_custom_column(self.custcols[key]):
            del self.custcols[key]  # A newly-added column was deleted
            self.opt_columns.removeRow(row)
        else:
            self.custcols[key]['*deleted'] = True
            self.setup_row(row, key, self.column_order_val(row))
        self.changed_signal.emit()

    def add_custcol(self):
        model = self.gui.library_view.model()
        CreateCustomColumn(self.gui, self, None, model.orig_headers)
        if self.cc_column_key is None:
            return
        cc = self.custcols[self.cc_column_key]
        self.set_new_custom_column(cc)
        cc['original_key'] = self.cc_column_key
        row = self.opt_columns.rowCount()
        o = self.opt_columns
        o.setRowCount(row + 1)
        self.setup_row(row, self.cc_column_key, row)
        # We need to find the new item after sorting
        for i in range(0, o.rowCount()):
            if self.column_order_val(i) == row:
                o.setCurrentCell(i, 1)
                o.scrollTo(o.currentIndex())
                break
        self.changed_signal.emit()

    def label_to_lookup_name(self, label):
        return '#' + label

    def is_custom_key(self, key):
        return key.startswith('#')

    def column_order_val(self, row):
        return int(self.opt_columns.item(row, 0).text())

    def edit_custcol(self):
        model = self.gui.library_view.model()
        row = self.opt_columns.currentRow()
        try:
            key = str(self.opt_columns.item(row, 0).data(Qt.ItemDataRole.UserRole))
            if key not in self.custcols:
                return error_dialog(self, '',
                            _('The selected column is not a user-defined column'),
                            show=True)
            cc = self.custcols[key]
            if '*deleted' in cc:
                if question_dialog(self, _('Undelete the column?'),
                           _('The column is to be deleted. Do you want to undelete it?'),
                           show_copy_button=False):
                    cc.pop('*deleted', None)
                    self.setup_row(row, key, self.column_order_val(row))
                return
            CreateCustomColumn(self.gui, self,
                               self.label_to_lookup_name(self.custcols[key]['label']),
                               model.orig_headers)
            new_key = self.cc_column_key
            if new_key is None:
                return
            if key != new_key:
                self.custcols[new_key] = self.custcols[key]
                self.custcols.pop(key, None)
            cc = self.custcols[new_key]
            if self.is_new_custom_column(cc):
                cc.pop('*edited', None)
            self.setup_row(row, new_key, self.column_order_val(row))
            self.opt_columns.scrollTo(self.opt_columns.currentIndex())
            self.changed_signal.emit()
        except:
            import traceback
            traceback.print_exc()

    def apply_custom_column_changes(self):
        model = self.gui.library_view.model()
        db = model.db
        self.opt_columns.sortItems(0, Qt.SortOrder.AscendingOrder)
        config_cols = [str(self.opt_columns.item(i, 0).data(Qt.ItemDataRole.UserRole) or '')
                 for i in range(self.opt_columns.rowCount())]
        if not config_cols:
            config_cols = ['title']
        removed_cols = set(model.column_map) - set(config_cols)
        hidden_cols = {str(self.opt_columns.item(i, 0).data(Qt.ItemDataRole.UserRole) or '')
                 for i in range(self.opt_columns.rowCount())
                 if self.opt_columns.item(i, 0).checkState()==Qt.CheckState.Unchecked}
        hidden_cols = hidden_cols.union(removed_cols)  # Hide removed cols
        hidden_cols = list(hidden_cols.intersection(set(model.column_map)))
        if 'ondevice' in hidden_cols:
            hidden_cols.remove('ondevice')

        def col_pos(x):
            return config_cols.index(x) if x in config_cols else sys.maxsize
        positions = {}
        for i, col in enumerate(sorted(model.column_map, key=col_pos)):
            positions[col] = i
        state = {'hidden_columns': hidden_cols, 'column_positions':positions}
        self.gui.library_view.apply_state(state)
        self.gui.library_view.save_state()

        must_restart = False
        for cc in self.custcols.values():
            if '*deleted' in cc:
                db.delete_custom_column(label=cc['label'])
                must_restart = True
            elif '*edited' in cc:
                db.set_custom_column_metadata(cc['colnum'], name=cc['name'],
                                              label=cc['label'],
                                              display=cc['display'],
                                              notify=False)
                if '*must_restart' in cc:
                    must_restart = True
            elif self.is_new_custom_column(cc):
                db.create_custom_column(label=cc['label'], name=cc['name'],
                                        datatype=cc['datatype'], is_multiple=cc['is_multiple'],
                                        display=cc['display'])
                must_restart = True
        return must_restart


if __name__ == '__main__':
    app = Application([])
    test_widget('Interface', 'Custom Columns')
