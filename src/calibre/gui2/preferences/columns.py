#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import copy, sys

from PyQt4.Qt import Qt, QVariant, QListWidgetItem, QIcon

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
        model = self.gui.library_view.model()
        colmap = list(model.column_map)
        state = self.columns_state(defaults)
        hidden_cols = state['hidden_columns']
        positions = state['column_positions']
        colmap.sort(cmp=lambda x,y: cmp(positions[x], positions[y]))
        self.opt_columns.clear()
        for col in colmap:
            item = QListWidgetItem(model.headers[col], self.opt_columns)
            item.setData(Qt.UserRole, QVariant(col))
            if col.startswith('#'):
                item.setData(Qt.DecorationRole, QVariant(QIcon(I('column.png'))))
            flags = Qt.ItemIsEnabled|Qt.ItemIsSelectable
            if col != 'ondevice':
                flags |= Qt.ItemIsUserCheckable
            item.setFlags(flags)
            if col != 'ondevice':
                item.setCheckState(Qt.Unchecked if col in hidden_cols else
                        Qt.Checked)
        self.opt_columns.blockSignals(False)

    def up_column(self):
        idx = self.opt_columns.currentRow()
        if idx > 0:
            self.opt_columns.insertItem(idx-1, self.opt_columns.takeItem(idx))
            self.opt_columns.setCurrentRow(idx-1)
            self.changed_signal.emit()

    def down_column(self):
        idx = self.opt_columns.currentRow()
        if idx < self.opt_columns.count()-1:
            self.opt_columns.insertItem(idx+1, self.opt_columns.takeItem(idx))
            self.opt_columns.setCurrentRow(idx+1)
            self.changed_signal.emit()

    def del_custcol(self):
        idx = self.opt_columns.currentRow()
        if idx < 0:
            return error_dialog(self, '', _('You must select a column to delete it'),
                    show=True)
        col = unicode(self.opt_columns.item(idx).data(Qt.UserRole).toString())
        if col not in self.custcols:
            return error_dialog(self, '',
                    _('The selected column is not a custom column'), show=True)
        if not question_dialog(self, _('Are you sure?'),
            _('Do you really want to delete column %s and all its data?') %
            self.custcols[col]['name'], show_copy_button=False):
            return
        self.opt_columns.item(idx).setCheckState(False)
        self.opt_columns.takeItem(idx)
        if self.custcols[col]['colnum'] is None:
            del self.custcols[col] # A newly-added column was deleted
        else:
            self.custcols[col]['*deleteme'] = True
        self.changed_signal.emit()

    def add_custcol(self):
        model = self.gui.library_view.model()
        CreateCustomColumn(self, False, model.orig_headers, ALL_COLUMNS)
        self.changed_signal.emit()

    def edit_custcol(self):
        model = self.gui.library_view.model()
        CreateCustomColumn(self, True, model.orig_headers, ALL_COLUMNS)
        self.changed_signal.emit()

    def apply_custom_column_changes(self):
        model = self.gui.library_view.model()
        db = model.db
        config_cols = [unicode(self.opt_columns.item(i).data(Qt.UserRole).toString())\
                 for i in range(self.opt_columns.count())]
        if not config_cols:
            config_cols = ['title']
        removed_cols = set(model.column_map) - set(config_cols)
        hidden_cols = set([unicode(self.opt_columns.item(i).data(Qt.UserRole).toString())\
                 for i in range(self.opt_columns.count()) \
                 if self.opt_columns.item(i).checkState()==Qt.Unchecked])
        hidden_cols = hidden_cols.union(removed_cols) # Hide removed cols
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
                                display = self.custcols[c]['display'])
                must_restart = True
            elif '*deleteme' in self.custcols[c]:
                db.delete_custom_column(label=self.custcols[c]['label'])
                must_restart = True
            elif '*edited' in self.custcols[c]:
                cc = self.custcols[c]
                db.set_custom_column_metadata(cc['colnum'], name=cc['name'],
                                              label=cc['label'],
                                              display = self.custcols[c]['display'],
                                              notify=False)
                if '*must_restart' in self.custcols[c]:
                    must_restart = True
        return must_restart


if __name__ == '__main__':
    from PyQt4.Qt import QApplication
    app = QApplication([])
    test_widget('Interface', 'Custom Columns')

