__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'

from PyQt4.Qt import (Qt, QDialog, QTableWidgetItem, QIcon, QByteArray,
        QString, QSize)

from calibre.gui2.dialogs.tag_list_editor_ui import Ui_TagListEditor
from calibre.gui2 import question_dialog, error_dialog, info_dialog, gprefs
from calibre.utils.icu import sort_key

class NameTableWidgetItem(QTableWidgetItem):

    def __init__(self, txt):
        QTableWidgetItem.__init__(self, txt)
        self.initial_value = QString(txt)
        self.current_value = QString(txt)
        self.previous_value = QString(txt)

    def data(self, role):
        if role == Qt.DisplayRole:
            return self.current_value
        elif role == Qt.EditRole:
            return self.current_value
        else:
            return QTableWidgetItem.data(self, role)

    def setData(self, role, data):
        if role == Qt.EditRole:
            self.previous_value = self.current_value
            self.current_value = data.toString()
        QTableWidgetItem.setData(self, role, data)

    def text(self):
        return self.current_value

    def initial_text(self):
        return self.initial_value

    def previous_text(self):
        return self.previous_value

    def setText(self, txt):
        self.current_value = txt
        QTableWidgetItem.setText(txt)

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


class TagListEditor(QDialog, Ui_TagListEditor):

    def __init__(self, window, cat_name, tag_to_match, data, sorter):
        QDialog.__init__(self, window)
        Ui_TagListEditor.__init__(self)
        self.setupUi(self)

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
        self.original_names = {}
        self.all_tags = {}
        self.counts = {}

        for k,v,count in data:
            self.all_tags[v] = k
            self.counts[v] = count
            self.original_names[k] = v

        # Set up the column headings
        self.down_arrow_icon = QIcon(I('arrow-down.png'))
        self.up_arrow_icon = QIcon(I('arrow-up.png'))
        self.blank_icon = QIcon(I('blank.png'))

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

        # Capture clicks on the horizontal header to sort the table columns
        hh = self.table.horizontalHeader();
        hh.setClickable(True)
        hh.sectionClicked.connect(self.header_clicked)
        hh.sectionResized.connect(self.table_column_resized)
        self.name_order = 0
        self.count_order = 1
        self.was_order = 1

        # Add the data
        select_item = None
        self.table.setRowCount(len(self.all_tags))
        for row,tag in enumerate(sorted(self.all_tags.keys(), key=sorter)):
            item = NameTableWidgetItem(tag)
            item.setData(Qt.UserRole, self.all_tags[tag])
            item.setFlags (item.flags() | Qt.ItemIsSelectable | Qt.ItemIsEditable)
            self.table.setItem(row, 0, item)
            if tag == tag_to_match:
                select_item = item
            item = CountTableWidgetItem(self.counts[tag])
            # only the name column can be selected
            item.setFlags (item.flags() & ~Qt.ItemIsSelectable)
            self.table.setItem(row, 1, item)
            item = QTableWidgetItem('')
            item.setFlags (item.flags() & ~Qt.ItemIsSelectable)
            self.table.setItem(row, 2, item)

        # Scroll to the selected item if there is one
        if select_item is not None:
            self.table.setCurrentItem(select_item)

        self.delete_button.clicked.connect(self.delete_tags)
        self.rename_button.clicked.connect(self.rename_tag)
        self.table.itemDoubleClicked.connect(self._rename_tag)
        self.table.itemChanged.connect(self.finish_editing)
        self.buttonBox.accepted.connect(self.accepted)

        self.search_box.initialize('tag_list_search_box_' + cat_name)
        self.search_button.clicked.connect(self.search_clicked)

        try:
            geom = gprefs.get('tag_list_editor_dialog_geometry', None)
            if geom is not None:
                self.restoreGeometry(QByteArray(geom))
            else:
                self.resize(self.sizeHint()+QSize(150, 100))
        except:
            pass

    def search_clicked(self):
        search_for = icu_lower(unicode(self.search_box.text()))
        if not search_for:
            error_dialog(self, _('Find'), _('You must enter some text to search for'),
                         show=True, show_copy_button=False)
            return
        row = self.table.currentRow()
        if row < 0:
            row = 0
        rows = self.table.rowCount()
        for i in range(0, rows):
            row += 1
            if row >= rows:
                row = 0
            item = self.table.item(row, 0)
            if search_for in icu_lower(unicode(item.text())):
                self.table.setCurrentItem(item)
                return
        info_dialog(self, _('Find'), _('No tag found'), show=True, show_copy_button=False)

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
                item.setText(item.previous_text())
                return
        if item.text() != item.initial_text():
            id_ = item.data(Qt.UserRole).toInt()[0]
            self.to_rename[id_] = unicode(item.text())
            orig = self.table.item(item.row(), 2)
            self.table.blockSignals(True)
            orig.setData(Qt.DisplayRole, item.initial_text())
            self.table.blockSignals(False)

    def rename_tag(self):
        item = self.table.item(self.table.currentRow(), 0)
        self._rename_tag(item)

    def _rename_tag(self, item):
        if item is None:
            error_dialog(self, _('No item selected'),
                         _('You must select one item from the list of Available items.')).exec_()
            return
        self.table.editItem(item)

    def delete_tags(self):
        deletes = self.table.selectedItems()
        if not deletes:
            error_dialog(self, _('No items selected'),
                         _('You must select at least one item from the list.')).exec_()
            return
        ct = ', '.join([unicode(item.text()) for item in deletes])
        if not question_dialog(self, _('Are you sure?'),
            '<p>'+_('Are you sure you want to delete the following items?')+'<br>'+ct):
            return
        row = self.table.row(deletes[0])
        for item in deletes:
            (id,ign) = item.data(Qt.UserRole).toInt()
            self.to_delete.add(id)
            self.table.removeRow(self.table.row(item))

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

    def do_sort_by_count (self):
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
