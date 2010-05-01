__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid at kovidgoyal.net>'

'''Dialog to create a new custom column'''

from PyQt4.QtCore import SIGNAL, QObject
from PyQt4.Qt import QDialog, Qt, QMessageBox, QListWidgetItem, QVariant
from calibre.gui2.dialogs.config.create_custom_column_ui import Ui_QCreateCustomColumn
from calibre.gui2 import ALL_COLUMNS, qstring_to_unicode

class CreateCustomColumn(QDialog, Ui_QCreateCustomColumn):
    column_types = {
                    0:{'datatype':'text', 'text':_('Text, column shown in tags browser'), 'is_multiple':False},
                    1:{'datatype':'*text', 'text':_('Comma separated text, shown in tags browser'), 'is_multiple':True},
                    2:{'datatype':'comments', 'text':_('Text, column not shown in tags browser'), 'is_multiple':False},
                    3:{'datatype':'datetime', 'text':_('Date'), 'is_multiple':False},
                    4:{'datatype':'float', 'text':_('Float'), 'is_multiple':False},
                    5:{'datatype':'int', 'text':_('Integer'), 'is_multiple':False},
                    6:{'datatype':'rating', 'text':_('Rating (stars)'), 'is_multiple':False},
                    7:{'datatype':'bool', 'text':_('Yes/No'), 'is_multiple':False},
                }
    def __init__(self, parent, editing, standard_colheads, standard_colnames):
        QDialog.__init__(self, parent)
        Ui_QCreateCustomColumn.__init__(self)
        self.setupUi(self)
        self.connect(self.button_box, SIGNAL("accepted()"), self.accept)
        self.connect(self.button_box, SIGNAL("rejected()"), self.reject)
        self.parent = parent
        self.editing_col = editing
        self.standard_colheads = standard_colheads
        self.standard_colnames = standard_colnames
        if not self.editing_col:
            for t in self.column_types:
                self.column_type_box.addItem(self.column_types[t]['text'])
            self.exec_()
            return
        idx = parent.columns.currentRow()
        if idx < 0:
            self.parent.messagebox(_('No column has been selected'))
            return
        col = qstring_to_unicode(parent.columns.item(idx).data(Qt.UserRole).toString())
        if col not in parent.custcols:
            self.parent.messagebox(_('Selected column is not a user-defined column'))
            return

        c = parent.custcols[col]
        self.column_name_box.setText(c['label'])
        self.column_heading_box.setText(c['name'])
        ct = c['datatype'] if not c['is_multiple'] else '*text'
        self.orig_column_number = c['num']
        self.orig_column_name = col
        column_numbers = dict(map(lambda x:(self.column_types[x]['datatype'], x), self.column_types))
        self.column_type_box.addItem(self.column_types[column_numbers[ct]]['text'])
        self.exec_()

    def accept(self):
        col = qstring_to_unicode(self.column_name_box.text())
        col_heading = qstring_to_unicode(self.column_heading_box.text())
        col_type = self.column_types[self.column_type_box.currentIndex()]['datatype']
        if col_type == '*text':
            col_type='text'
            is_multiple = True
        else:
            is_multiple = False
        if not col:
            self.parent.messagebox(_('No lookup name was provided'))
            return
        if not col_heading:
            self.parent.messagebox(_('No column heading was provided'))
            return
        bad_col = False
        if col in self.parent.custcols:
            if not self.editing_col or self.parent.custcols[col]['num'] != self.orig_column_number:
                bad_col = True
        if col in self.standard_colnames:
            bad_col = True
        if bad_col:
            self.parent.messagebox(_('The lookup name %s is already used')%col)
            return
        bad_head = False
        for t in self.parent.custcols:
            if self.parent.custcols[t]['name'] == col_heading:
                if not self.editing_col or self.parent.custcols[t]['num'] != self.orig_column_number:
                    bad_head = True
        for t in self.standard_colheads:
            if self.standard_colheads[t] == col_heading:
                bad_head = True
        if bad_head:
            self.parent.messagebox(_('The heading %s is already used')%col_heading)
            return
        if col.find(':') >= 0 or col.find(' ') >= 0 and \
                (not is_alpha(col) or is_lower(col)):
            self.parent.messagebox(_('The lookup name must be lower case and cannot contain ":"s or spaces'))
            return

        if not self.editing_col:
            self.parent.custcols[col] = {
                    'label':col,
                    'name':col_heading,
                    'datatype':col_type,
                    'editable':True,
                    'display':None,
                    'normalized':None,
                    'num':None,
                    'is_multiple':is_multiple,
                }
            item = QListWidgetItem(col_heading, self.parent.columns)
            item.setData(Qt.UserRole, QVariant(col))
            item.setFlags(Qt.ItemIsEnabled|Qt.ItemIsUserCheckable|Qt.ItemIsSelectable)
            item.setCheckState(Qt.Checked)
        else:
            idx = self.parent.columns.currentRow()
            item = self.parent.columns.item(idx)
            item.setData(Qt.UserRole, QVariant(col))
            item.setText(col_heading)
            self.parent.custcols[self.orig_column_name]['label'] = col
            self.parent.custcols[self.orig_column_name]['name'] = col_heading
            self.parent.custcols[self.orig_column_name]['*edited'] = True
            self.parent.custcols[self.orig_column_name]['*must_restart'] = True
        QDialog.accept(self)

    def reject(self):
        QDialog.reject(self)