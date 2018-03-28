__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'

from PyQt5.Qt import (Qt, QDialog, QTableWidgetItem, QIcon, QByteArray, QSize,
                      QDialogButtonBox, QTableWidget, QItemDelegate)

from calibre.gui2.dialogs.tag_list_editor_ui import Ui_TagListEditor
from calibre.gui2.dialogs.confirm_delete import confirm
from calibre.gui2 import question_dialog, error_dialog, gprefs
from calibre.utils.icu import sort_key


class NameTableWidgetItem(QTableWidgetItem):

    def __init__(self):
        QTableWidgetItem.__init__(self)
        self.initial_value = ''
        self.current_value = ''
        self.is_deleted = False

    def data(self, role):
        if role == Qt.DisplayRole:
            if self.is_deleted:
                return ''
            return self.current_value
        elif role == Qt.EditRole:
            return self.current_value
        else:
            return QTableWidgetItem.data(self, role)

    def set_is_deleted(self, to_what):
        if to_what:
            self.setIcon(QIcon(I('trash.png')))
        else:
            self.setIcon(QIcon(None))
            self.current_value = self.initial_value
        self.is_deleted = to_what

    def setData(self, role, data):
        if role == Qt.EditRole:
            self.current_value = data
        QTableWidgetItem.setData(self, role, data)

    def set_initial_text(self, txt):
        self.initial_value = txt

    def initial_text(self):
        return self.initial_value

    def text(self):
        return self.current_value

    def setText(self, txt):
        self.current_value = txt
        QTableWidgetItem.setText(self, txt)

    def __ge__(self, other):
        return sort_key(unicode(self.text())) >= sort_key(unicode(other.text()))

    def __lt__(self, other):
        return sort_key(unicode(self.text())) < sort_key(unicode(other.text()))


class CountTableWidgetItem(QTableWidgetItem):

    def __init__(self, count):
        QTableWidgetItem.__init__(self, str(count))
        self._count = count

    def __ge__(self, other):
        return self._count >= other._count

    def __lt__(self, other):
        return self._count < other._count


class EditColumnDelegate(QItemDelegate):

    def __init__(self, table):
        QItemDelegate.__init__(self)
        self.table = table

    def createEditor(self, parent, option, index):
        item = self.table.item(index.row(), 0)
        if index.column() == 0:
            item = self.table.item(index.row(), 0)
            if item.is_deleted:
                return None
            return QItemDelegate.createEditor(self, parent, option, index)


class TagListEditor(QDialog, Ui_TagListEditor):

    def __init__(self, window, cat_name, tag_to_match, data, sorter):
        QDialog.__init__(self, window)
        Ui_TagListEditor.__init__(self)
        self.setupUi(self)
        self.search_box.setMinimumContentsLength(25)

        # Put the category name into the title bar
        t = self.windowTitle()
        self.setWindowTitle(t + ' (' + cat_name + ')')
        # Remove help icon on title bar
        icon = self.windowIcon()
        self.setWindowFlags(self.windowFlags()&(~Qt.WindowContextHelpButtonHint))
        self.setWindowIcon(icon)

        # Get saved geometry info
        try:
            self.table_column_widths = \
                        gprefs.get('tag_list_editor_table_widths', None)
        except:
            pass

        # initialization
        self.to_rename = {}
        self.to_delete = set([])
        self.all_tags = {}
        self.original_names = {}

        for k,v,count in data:
            self.all_tags[v] = {'key': k, 'count': count, 'cur_name': v, 'is_deleted': False}
            self.original_names[k] = v
        self.ordered_tags = sorted(self.all_tags.keys(), key=sorter)

        # Set up the column headings
        self.down_arrow_icon = QIcon(I('arrow-down.png'))
        self.up_arrow_icon = QIcon(I('arrow-up.png'))
        self.blank_icon = QIcon(I('blank.png'))

        # Capture clicks on the horizontal header to sort the table columns
        hh = self.table.horizontalHeader()
        hh.setSectionsClickable(True)
        hh.sectionClicked.connect(self.header_clicked)
        hh.sectionResized.connect(self.table_column_resized)
        self.name_order = 0
        self.count_order = 1
        self.was_order = 1

        self.table.setItemDelegate(EditColumnDelegate(self.table))

        # Add the data
        select_item = self.fill_in_table(self.ordered_tags, tag_to_match)

        # Scroll to the selected item if there is one
        if select_item is not None:
            self.table.setCurrentItem(select_item)

        self.delete_button.clicked.connect(self.delete_tags)
        self.rename_button.clicked.connect(self.rename_tag)
        self.undo_button.clicked.connect(self.undo_edit)
        self.table.itemDoubleClicked.connect(self._rename_tag)
        self.table.itemChanged.connect(self.finish_editing)

        self.buttonBox.button(QDialogButtonBox.Ok).setText(_('&OK'))
        self.buttonBox.button(QDialogButtonBox.Cancel).setText(_('&Cancel'))
        self.buttonBox.accepted.connect(self.accepted)

        self.search_box.initialize('tag_list_search_box_' + cat_name)
        self.search_button.clicked.connect(self.all_matching_clicked)
        self.search_button.setDefault(True)

        self.table.setEditTriggers(QTableWidget.EditKeyPressed)

        try:
            geom = gprefs.get('tag_list_editor_dialog_geometry', None)
            if geom is not None:
                self.restoreGeometry(QByteArray(geom))
            else:
                self.resize(self.sizeHint()+QSize(150, 100))
        except:
            pass

    def fill_in_table(self, tags, tag_to_match):
        select_item = None
        self.table.blockSignals(True)
        self.table.clear()
        self.table.setColumnCount(3)
        self.name_col = QTableWidgetItem(_('Tag'))
        self.table.setHorizontalHeaderItem(0, self.name_col)
        self.name_col.setIcon(self.up_arrow_icon)
        self.count_col = QTableWidgetItem(_('Count'))
        self.table.setHorizontalHeaderItem(1, self.count_col)
        self.count_col.setIcon(self.blank_icon)
        self.was_col = QTableWidgetItem(_('Was'))
        self.table.setHorizontalHeaderItem(2, self.was_col)
        self.count_col.setIcon(self.blank_icon)

        self.table.setRowCount(len(tags))

        for row,tag in enumerate(tags):
            item = NameTableWidgetItem()
            item.set_is_deleted(self.all_tags[tag]['is_deleted'])
            item.setText(self.all_tags[tag]['cur_name'])
            item.set_initial_text(tag)
            item.setData(Qt.UserRole, self.all_tags[tag]['key'])
            item.setFlags(item.flags() | Qt.ItemIsSelectable | Qt.ItemIsEditable)
            self.table.setItem(row, 0, item)
            if tag == tag_to_match:
                select_item = item

            item = CountTableWidgetItem(self.all_tags[tag]['count'])
            # only the name column can be selected
            item.setFlags(item.flags() & ~(Qt.ItemIsSelectable|Qt.ItemIsEditable))
            self.table.setItem(row, 1, item)

            item = QTableWidgetItem()
            item.setFlags(item.flags() & ~(Qt.ItemIsSelectable|Qt.ItemIsEditable))
            if tag != self.all_tags[tag]['cur_name'] or self.all_tags[tag]['is_deleted']:
                item.setData(Qt.DisplayRole, tag)
            self.table.setItem(row, 2, item)
        self.table.blockSignals(False)
        return select_item

    def all_matching_clicked(self):
        for i in range(0, self.table.rowCount()):
            item = self.table.item(i, 0)
            tag = item.initial_text()
            self.all_tags[tag]['cur_name'] = item.text()
            self.all_tags[tag]['is_deleted'] = item.is_deleted
        search_for = icu_lower(unicode(self.search_box.text()))
        if len(search_for) == 0:
            self.fill_in_table(self.ordered_tags, None)
        result = []
        for k in self.ordered_tags:
            if search_for in icu_lower(unicode(self.all_tags[k]['cur_name'])):
                result.append(k)
        self.fill_in_table(result, None)

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
            w /= self.table.columnCount()
            for c in range(0, self.table.columnCount()):
                self.table.setColumnWidth(c, w)

    def save_geometry(self):
        gprefs['tag_list_editor_table_widths'] = self.table_column_widths
        gprefs['tag_list_editor_dialog_geometry'] = bytearray(self.saveGeometry())

    def finish_editing(self, item):
        if not item.text():
                error_dialog(self, _('Item is blank'),
                             _('An item cannot be set to nothing. Delete it instead.')).exec_()
                item.setText(item.initial_text())
                return
        if item.text() != item.initial_text():
            id_ = int(item.data(Qt.UserRole))
            self.to_rename[id_] = unicode(item.text())
            orig = self.table.item(item.row(), 2)
            self.table.blockSignals(True)
            orig.setData(Qt.DisplayRole, item.initial_text())
            self.table.blockSignals(False)

    def undo_edit(self):
        indexes = self.table.selectionModel().selectedRows()
        if not indexes:
            error_dialog(self, _('No item selected'),
                         _('You must select one item from the list of Available items.')).exec_()
            return

        if not confirm(
                _('Do you really want to undo your changes?'),
                'tag_list_editor_undo'):
                return
        self.table.blockSignals(True)
        for idx in indexes:
            row = idx.row()
            item = self.table.item(row, 0)
            item.setText(item.initial_text())
            item.set_is_deleted(False)
            self.to_delete.discard(int(item.data(Qt.UserRole)))
            self.to_rename.pop(int(item.data(Qt.UserRole)), None)
            self.table.item(row, 2).setData(Qt.DisplayRole, '')
        self.table.blockSignals(False)

    def rename_tag(self):
        item = self.table.item(self.table.currentRow(), 0)
        self._rename_tag(item)

    def _rename_tag(self, item):
        if item is None:
            error_dialog(self, _('No item selected'),
                         _('You must select one item from the list of Available items.')).exec_()
            return
        col_zero_item = self.table.item(item.row(), 0)
        if col_zero_item.is_deleted:
            if not question_dialog(self, _('Undelete item?'),
                   '<p>'+_('That item is deleted. Do you want to undelete it?')+'<br>'):
                return
            col_zero_item.set_is_deleted(False)
            self.to_delete.discard(int(col_zero_item.data(Qt.UserRole)))
            orig = self.table.item(col_zero_item.row(), 2)
            self.table.blockSignals(True)
            orig.setData(Qt.DisplayRole, '')
            self.table.blockSignals(False)
        else:
            self.table.editItem(item)

    def delete_tags(self):
        deletes = self.table.selectedItems()
        if not deletes:
            error_dialog(self, _('No items selected'),
                         _('You must select at least one item from the list.')).exec_()
            return

        to_del = []
        to_undel = []
        for item in deletes:
            if item.is_deleted:
                to_undel.append(item)
            else:
                to_del.append(item)
        if to_del:
            ct = ', '.join([unicode(item.text()) for item in to_del])
            if not confirm(
                '<p>'+_('Are you sure you want to delete the following items?')+'<br>'+ct,
                'tag_list_editor_delete'):
                return
        if to_undel:
            ct = ', '.join([unicode(item.text()) for item in to_undel])
            if not confirm(
                '<p>'+_('Are you sure you want to undelete the following items?')+'<br>'+ct,
                'tag_list_editor_undelete'):
                return
        row = self.table.row(deletes[0])
        for item in deletes:
            if item.is_deleted:
                item.set_is_deleted(False)
                self.to_delete.discard(int(item.data(Qt.UserRole)))
                orig = self.table.item(item.row(), 2)
                self.table.blockSignals(True)
                orig.setData(Qt.DisplayRole, '')
                self.table.blockSignals(False)
            else:
                id = int(item.data(Qt.UserRole))
                self.to_delete.add(id)
                item.set_is_deleted(True)
                orig = self.table.item(item.row(), 2)
                self.table.blockSignals(True)
                orig.setData(Qt.DisplayRole, item.initial_text())
                self.table.blockSignals(False)
        if row >= self.table.rowCount():
            row = self.table.rowCount() - 1
        if row >= 0:
            self.table.scrollToItem(self.table.item(row, 0))

    def header_clicked(self, idx):
        if idx == 0:
            self.do_sort_by_name()
        elif idx == 1:
            self.do_sort_by_count()
        else:
            self.do_sort_by_was()

    def do_sort_by_name(self):
        self.name_order = 1 if self.name_order == 0 else 0
        self.table.sortByColumn(0, self.name_order)
        self.name_col.setIcon(self.down_arrow_icon if self.name_order
                                                    else self.up_arrow_icon)
        self.count_col.setIcon(self.blank_icon)
        self.was_col.setIcon(self.blank_icon)

    def do_sort_by_count(self):
        self.count_order = 1 if self.count_order == 0 else 0
        self.table.sortByColumn(1, self.count_order)
        self.count_col.setIcon(self.down_arrow_icon if self.count_order
                                                    else self.up_arrow_icon)
        self.name_col.setIcon(self.blank_icon)
        self.was_col.setIcon(self.blank_icon)

    def do_sort_by_was(self):
        self.was_order = 1 if self.was_order == 0 else 0
        self.table.sortByColumn(2, self.was_order)
        self.was_col.setIcon(self.down_arrow_icon if self.was_order
                                                    else self.up_arrow_icon)
        self.name_col.setIcon(self.blank_icon)
        self.count_col.setIcon(self.blank_icon)

    def accepted(self):
        self.save_geometry()
