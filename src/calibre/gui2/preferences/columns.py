#!/usr/bin/env python2
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import copy, sys

from PyQt5.Qt import Qt, QTableWidgetItem, QIcon

from calibre.gui2 import gprefs, Application
from calibre.gui2.preferences import ConfigWidgetBase, test_widget
from calibre.gui2.preferences.columns_ui import Ui_Form
from calibre.gui2.preferences.create_custom_column import CreateCustomColumn
from calibre.gui2 import error_dialog, question_dialog, ALL_COLUMNS


class ConfigWidget(ConfigWidgetBase, Ui_Form):

    restart_critical = True

    def genesis(self, gui):
        self.gui = gui
        db = self.gui.library_view.model().db
        self.custcols = copy.deepcopy(db.field_metadata.custom_field_metadata())

        self.column_up.clicked.connect(self.up_column)
        self.column_down.clicked.connect(self.down_column)
        self.del_custcol_button.clicked.connect(self.del_custcol)
        self.add_custcol_button.clicked.connect(self.add_custcol)
        self.add_col_button.clicked.connect(self.add_custcol)
        self.edit_custcol_button.clicked.connect(self.edit_custcol)
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

    def columns_changed(self, *args):
        self.changed_signal.emit()

    def columns_state(self, defaults=False):
        if defaults:
            return self.gui.library_view.get_default_state()
        return self.gui.library_view.get_state()

    def init_columns(self, defaults=False):
        # Set up columns
        self.opt_columns.blockSignals(True)
        self.model = model = self.gui.library_view.model()
        colmap = list(model.column_map)
        state = self.columns_state(defaults)
        self.hidden_cols = state['hidden_columns']
        positions = state['column_positions']
        colmap.sort(cmp=lambda x,y: cmp(positions[x], positions[y]))
        self.opt_columns.clear()

        db = model.db
        self.field_metadata = db.field_metadata

        self.opt_columns.setColumnCount(4)
        item = QTableWidgetItem(_('Column header'))
        self.opt_columns.setHorizontalHeaderItem(0, item)
        item = QTableWidgetItem(_('Lookup name'))
        self.opt_columns.setHorizontalHeaderItem(1, item)
        item = QTableWidgetItem(_('Type'))
        self.opt_columns.setHorizontalHeaderItem(2, item)
        item = QTableWidgetItem(_('Description'))
        self.opt_columns.setHorizontalHeaderItem(3, item)

        self.opt_columns.setRowCount(len(colmap))
        self.column_desc = dict(map(lambda x:(CreateCustomColumn.column_types[x]['datatype'],
                                         CreateCustomColumn.column_types[x]['text']),
                                  CreateCustomColumn.column_types))

        for row, col in enumerate(colmap):
            self.setup_row(self.field_metadata, row, col)

        self.restore_geometry()
        self.opt_columns.cellDoubleClicked.connect(self.row_double_clicked)
        self.opt_columns.blockSignals(False)

    def row_double_clicked(self, r, c):
        self.edit_custcol()

    def restore_geometry(self):
        geom = gprefs.get('custcol-prefs-table-geometry', None)
        if geom is not None and len(geom) == self.opt_columns.columnCount():
            try:
                for i in range(0, self.opt_columns.columnCount()):
                    self.opt_columns.setColumnWidth(i, geom[i])
            except:
                self.set_default_geometry()
        else:
            self.set_default_geometry()

    def set_default_geometry(self):
        self.opt_columns.resizeColumnsToContents()
        self.opt_columns.resizeRowsToContents()

    def setup_row(self, field_metadata, row, col, oldkey=None):
        flags = Qt.ItemIsEnabled | Qt.ItemIsSelectable

        item = QTableWidgetItem(col)
        item.setFlags(flags)
        self.opt_columns.setItem(row, 1, item)

        if col.startswith('#'):
            fm = self.custcols[oldkey if oldkey is not None else col]
        else:
            fm = field_metadata[col]

        if col == 'title':
            coltype = _('Text')
        elif col == 'ondevice':
            coltype = _('Yes/No with text')
        else:
            dt = fm['datatype']
            if fm['is_multiple']:
                if col == 'authors' or fm.get('display', {}).get('is_names', False):
                    coltype = _('Ampersand separated text, shown in the Tag browser')
                else:
                    coltype = self.column_desc['*' + dt]
            else:
                coltype = self.column_desc[dt]
        coltype_info = (coltype if oldkey is None else
                          ' ' + _('(lookup name was {0}) {1}'.format(oldkey, coltype)))

        item = QTableWidgetItem(coltype_info)
        item.setFlags(flags)
        self.opt_columns.setItem(row, 2, item)

        desc = fm['display'].get('description', "")
        item = QTableWidgetItem(desc)
        item.setFlags(flags)
        self.opt_columns.setItem(row, 3, item)

        item = QTableWidgetItem(fm['name'])
        item.setData(Qt.UserRole, (col))
        item.setFlags(flags)
        self.opt_columns.setItem(row, 0, item)

        if col.startswith('#'):
            item.setData(Qt.DecorationRole, (QIcon(I('column.png'))))
        if col != 'ondevice':
            flags |= Qt.ItemIsUserCheckable
        item.setFlags(flags)
        if col != 'ondevice':
            item.setCheckState(Qt.Unchecked if col in self.hidden_cols else
                    Qt.Checked)

    def up_column(self):
        idx = self.opt_columns.currentRow()
        if idx > 0:
            for i in range(0, self.opt_columns.columnCount()):
                lower = self.opt_columns.takeItem(idx-1, i)
                upper = self.opt_columns.takeItem(idx, i)
                self.opt_columns.setItem(idx, i, lower)
                self.opt_columns.setItem(idx-1, i, upper)
            self.opt_columns.setCurrentCell(idx-1, 0)
            self.changed_signal.emit()

    def down_column(self):
        idx = self.opt_columns.currentRow()
        if idx < self.opt_columns.rowCount()-1:
            for i in range(0, self.opt_columns.columnCount()):
                lower = self.opt_columns.takeItem(idx, i)
                upper = self.opt_columns.takeItem(idx+1, i)
                self.opt_columns.setItem(idx+1, i, lower)
                self.opt_columns.setItem(idx, i, upper)
            self.opt_columns.setCurrentCell(idx+1, 0)
            self.changed_signal.emit()

    def del_custcol(self):
        idx = self.opt_columns.currentRow()
        if idx < 0:
            return error_dialog(self, '', _('You must select a column to delete it'),
                    show=True)
        col = unicode(self.opt_columns.item(idx, 0).data(Qt.UserRole) or '')
        if col not in self.custcols:
            return error_dialog(self, '',
                    _('The selected column is not a custom column'), show=True)
        if not question_dialog(self, _('Are you sure?'),
            _('Do you really want to delete column %s and all its data?') %
            self.custcols[col]['name'], show_copy_button=False):
            return
        self.opt_columns.removeRow(idx)
        if self.custcols[col]['colnum'] is None:
            del self.custcols[col]  # A newly-added column was deleted
        else:
            self.custcols[col]['*deleteme'] = True
        self.changed_signal.emit()

    def add_custcol(self):
        model = self.gui.library_view.model()
        CreateCustomColumn(self, None, None, model.orig_headers, ALL_COLUMNS)
        if self.cc_column_key is None:
            return
        row = self.opt_columns.rowCount()
        self.opt_columns.setRowCount(row + 1)
        self.setup_row(self.field_metadata, row, self.cc_column_key)
        self.changed_signal.emit()

    def edit_custcol(self):
        model = self.gui.library_view.model()
        row = self.opt_columns.currentRow()
        try:
            key = unicode(self.opt_columns.item(row, 0).data(Qt.UserRole))
        except:
            key = ''
        CreateCustomColumn(self, row, key, model.orig_headers, ALL_COLUMNS)
        if self.cc_column_key is None:
            return
        self.setup_row(self.field_metadata, row, self.cc_column_key,
                       None if self.cc_column_key == key else key)
        self.changed_signal.emit()

    def apply_custom_column_changes(self):
        model = self.gui.library_view.model()
        db = model.db
        config_cols = [unicode(self.opt_columns.item(i, 0).data(Qt.UserRole) or '')
                 for i in range(self.opt_columns.rowCount())]
        if not config_cols:
            config_cols = ['title']
        removed_cols = set(model.column_map) - set(config_cols)
        hidden_cols = set([unicode(self.opt_columns.item(i, 0).data(Qt.UserRole) or '')
                 for i in range(self.opt_columns.rowCount())
                 if self.opt_columns.item(i, 0).checkState()==Qt.Unchecked])
        hidden_cols = hidden_cols.union(removed_cols)  # Hide removed cols
        hidden_cols = list(hidden_cols.intersection(set(model.column_map)))
        if 'ondevice' in hidden_cols:
            hidden_cols.remove('ondevice')

        def col_pos(x, y):
            xidx = config_cols.index(x) if x in config_cols else sys.maxint
            yidx = config_cols.index(y) if y in config_cols else sys.maxint
            return cmp(xidx, yidx)
        positions = {}
        for i, col in enumerate((sorted(model.column_map, cmp=col_pos))):
            positions[col] = i
        state = {'hidden_columns': hidden_cols, 'column_positions':positions}
        self.gui.library_view.apply_state(state)
        self.gui.library_view.save_state()

        must_restart = False
        for c in self.custcols:
            if self.custcols[c]['colnum'] is None:
                db.create_custom_column(
                                label=self.custcols[c]['label'],
                                name=self.custcols[c]['name'],
                                datatype=self.custcols[c]['datatype'],
                                is_multiple=self.custcols[c]['is_multiple'],
                                display=self.custcols[c]['display'])
                must_restart = True
            elif '*deleteme' in self.custcols[c]:
                db.delete_custom_column(label=self.custcols[c]['label'])
                must_restart = True
            elif '*edited' in self.custcols[c]:
                cc = self.custcols[c]
                db.set_custom_column_metadata(cc['colnum'], name=cc['name'],
                                              label=cc['label'],
                                              display=self.custcols[c]['display'],
                                              notify=False)
                if '*must_restart' in self.custcols[c]:
                    must_restart = True
        return must_restart


if __name__ == '__main__':
    app = Application([])
    test_widget('Interface', 'Custom Columns')
