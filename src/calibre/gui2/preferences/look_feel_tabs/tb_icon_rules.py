#!/usr/bin/env python


__license__   = 'GPL v3'
__copyright__ = '2025, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import copy
import os
from functools import partial

from qt.core import QAbstractItemView, QApplication, QDialog, QIcon, QMenu, QSize, QStyledItemDelegate, Qt, QTableWidgetItem

from calibre.constants import config_dir
from calibre.db.constants import TEMPLATE_ICON_INDICATOR
from calibre.gui2 import choose_files, gprefs, pixmap_to_data
from calibre.gui2.dialogs.template_dialog import TemplateDialog
from calibre.gui2.library.delegates import DelegateCB
from calibre.gui2.preferences import LazyConfigWidgetBase
from calibre.gui2.preferences.look_feel_tabs.tb_icon_rules_ui import Ui_Form
from calibre.utils.formatter import EvalFormatter

DELETED_COLUMN = 0
CATEGORY_COLUMN = 1
VALUE_COLUMN = 2
ICON_MODIFIED_COLUMN = 3
ICON_COLUMN = 4
FOR_CHILDREN_MODIFIED_COLUMN = 5
FOR_CHILDREN_COLUMN = 6
HEADER_SECTION_COUNT = 7


class StateTableWidgetItem(QTableWidgetItem):

    def __init__(self, txt):
        super().__init__(txt)
        self.setIcon(QIcon.cached_icon('blank.png'))
        self.setFlags(Qt.ItemFlag.NoItemFlags)

    def setText(self, txt):
        if txt:
            super().setText(_('Yes') if txt else '')
            if self.column() == DELETED_COLUMN:
                self.setIcon(QIcon.cached_icon('trash.png'))
            else:
                self.setIcon(QIcon.cached_icon('modified.png'))
        else:
            super().setText('')
            self.setIcon(QIcon.cached_icon('blank.png'))


class CategoryTableWidgetItem(QTableWidgetItem):

    def __init__(self, lookup_name, category_icons, display_name, table):
        txt = display_name + f' ({lookup_name})'
        super().__init__(txt)
        self._lookup_name = lookup_name
        self._table = table
        self._is_modified = False
        self.setIcon(category_icons.get(lookup_name) or QIcon.cached_icon('column.png'))
        self._txt = txt
        self.setFlags(self.flags() & ~Qt.ItemFlag.ItemIsEditable)

    @property
    def is_modified(self):
        return self._is_modified

    @is_modified.setter
    def is_modified(self, to_what):
        self._is_modified = to_what
        deleted_item = self._table.item(self.row(), DELETED_COLUMN)
        deleted_item.setText(to_what)

    @property
    def lookup_name(self):
        return self._lookup_name

    def undo(self):
        self.is_modified = False


class ValueTableWidgetItem(QTableWidgetItem):

    def __init__(self, txt, table):
        self._original_text = txt
        self._table = table
        self._is_template = is_template = txt == TEMPLATE_ICON_INDICATOR
        super().__init__(('{' + _('template') + '}') if is_template else txt)
        self.setIcon(QIcon.cached_icon('debug.png' if is_template else 'icon_choose.png'))
        self.setFlags(self.flags() & ~Qt.ItemFlag.ItemIsEditable)

    @property
    def original_text(self):
        return self._original_text

    @property
    def is_template(self):
        return self._is_template

    @property
    def is_modified(self):
        return self._table.item(self.row(), CATEGORY_COLUMN).is_modified


class IconFileTableWidgetItem(QTableWidgetItem):

    def __init__(self, icon_file, value_text, table):
        super().__init__(icon_file)
        self._new_icon = None
        self._table = table
        self._is_modified = False
        self._original_text = icon_file
        self.setToolTip(icon_file)
        if value_text == TEMPLATE_ICON_INDICATOR:
            icon = QIcon.cached_icon('blank.png')
        else:
            p = os.path.join(config_dir, 'tb_icons', icon_file)
            if os.path.exists(p):
                icon = QIcon.ic(p)
            else:
                icon = QIcon.cached_icon('dialog_error.png')
                self.setToolTip(icon_file + '\n' + _("This icon file doesn't exist"))
        self.setIcon(icon)
        self._original_icon = icon

    @property
    def original_text(self):
        return self._original_text

    @property
    def new_icon(self):
        return self._new_icon

    @new_icon.setter
    def new_icon(self, to_what):
        # to_what is the new icon pixmap in bytes
        self._new_icon = to_what

    @property
    def is_modified(self):
        return self._is_modified

    @is_modified.setter
    def is_modified(self, to_what):
        self._is_modified = to_what
        del_item = self._table.item(self.row(), ICON_MODIFIED_COLUMN)
        del_item.setText(to_what)

    def set_text(self, txt):
        self.setText(txt)
        self.setToolTip(txt)

    def undo(self):
        self.is_modified = False
        self.set_text(self._original_text)
        self.setIcon(self._original_icon)


class IconColumnDelegate(QStyledItemDelegate):

    def __init__(self, parent, table, changed_signal):
        super().__init__(parent)
        self._table = table
        self._changed_signal = changed_signal

    def createEditor(self, parent, option, index):
        row = index.row()
        value_item = self._table.item(row, VALUE_COLUMN)
        icon_item = self._table.item(row, ICON_COLUMN)
        if value_item.is_template:
            v = {'title': 'Template Rule', 'category': self._table.item(row, CATEGORY_COLUMN).text(),
                  'value': 'abcd', 'count': str(5), 'avg_rating': str(2.5)}
            d = TemplateDialog(parent=self.parent(), text=self._table.item(row, ICON_COLUMN).text(),
                           mi=v, doing_emblem=True, formatter=EvalFormatter, icon_dir='tb_icons/template_icons')
            if d.exec() == QDialog.DialogCode.Accepted:
                icon_item.set_text(d.rule[2])
                icon_item.is_modified = True
                self._changed_signal.emit()
            return

        path = choose_files(self.parent(), 'choose_category_icon',
                    _('Change icon for: %s')%value_item.text(), filters=[
                    ('Images', ['png', 'gif', 'jpg', 'jpeg'])],
                all_files=False, select_only_single_file=True)
        if not path:
            return
        new_icon = QIcon(path[0])
        icon_item.new_icon = pixmap_to_data(new_icon.pixmap(QSize(128, 128)), format='PNG')
        icon_item.setIcon(new_icon)
        icon_item.is_modified = True
        self._changed_signal.emit()


class ChildrenTableWidgetItem(QTableWidgetItem):

    def __init__(self, value, item_value, table):
        super().__init__('')
        self._is_modified = False
        self._original_value = self._value = value
        self._item_value = item_value
        self._table = table
        self._set_text_and_icon(value)

    def _set_text_and_icon(self, value):
        if self._item_value == TEMPLATE_ICON_INDICATOR:
            txt = ''
        else:
            txt = _('Yes') if value else _('No')
            if value is None:
                icon = QIcon()
            elif value:
                icon = QIcon.cached_icon('ok.png')
            else:
                icon = QIcon.cached_icon('list_remove.png')
            self.setIcon(icon)
        self.setText(txt)
        self._value = value

    @property
    def original_value(self):
        return self._original_value

    @property
    def value(self):
        return self._value

    @property
    def is_modified(self):
        return self._is_modified

    @is_modified.setter
    def is_modified(self, to_what):
        del_item = self._table.item(self.row(), FOR_CHILDREN_MODIFIED_COLUMN)
        if to_what:
            del_item.setText(to_what)
            self._is_modified = True
        else:
            del_item.setText(False)
            self._is_modified = False

    def set_value(self, val):
        self._set_text_and_icon(val)
        self.is_modified = val != self.original_value

    def undo(self):
        self.is_modified = False
        self._set_text_and_icon(self._original_value)


class ChildrenColumnDelegate(QStyledItemDelegate):

    def __init__(self, parent, table, changed_signal):
        super().__init__(parent)
        self._table = table
        self._changed_signal = changed_signal

    def createEditor(self, parent, option, index):
        item = self._table.item(index.row(), VALUE_COLUMN)
        if item.is_template:
            return None
        editor = DelegateCB(parent)
        items = [_('Yes'), _('No'), ]
        icons = ['ok.png', 'list_remove.png']
        self.longest_text = ''
        for icon, text in zip(icons, items):
            editor.addItem(QIcon.cached_icon(icon), text)
            if len(text) > len(self.longest_text):
                self.longest_text = text
        return editor

    def setModelData(self, editor, model, index):
        val = {0:True, 1:False}[editor.currentIndex()]
        self._table.item(index.row(), index.column()).set_value(val)
        self._changed_signal.emit()

    def setEditorData(self, editor, index):
        item = self._table.item(index.row(), index.column())
        val = item.original_value
        val = 0 if val else 1
        editor.setCurrentIndex(val)


class TbIconRulesTab(LazyConfigWidgetBase, Ui_Form):

    def genesis(self, gui):
        self.gui = gui
        r = self.register
        r('tag_browser_show_category_icons', gprefs)
        r('tag_browser_show_value_icons', gprefs)

        self.show_only_current_library.setChecked(gprefs.get('tag_browser_rules_show_only_current_library', False))

        self.rules_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)
        self.rules_table.setColumnCount(HEADER_SECTION_COUNT)
        self.rules_table.setHorizontalHeaderLabels(('', _('Category'), _('Value'), '',
                                                    _('Icon file or template'), '', _('For children')))
        self.rules_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.rules_table.customContextMenuRequested.connect(self.show_context_menu)
        self.rules_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)

        # Make the minimum section size smaller so the icon column icons don't
        # have a lot of space on the right
        self.rules_table.horizontalHeader().setMinimumSectionSize(20)

        for i in range(HEADER_SECTION_COUNT):
            item = self.rules_table.horizontalHeaderItem(i)
            if i == DELETED_COLUMN:
                item.setIcon(QIcon.cached_icon('trash.png'))
                item.setToolTip(_('This icon shows in the row if the rule is deleted'))
            elif i == CATEGORY_COLUMN:
                item.setToolTip(_('The name of the category'))
            elif i == VALUE_COLUMN:
                item.setToolTip(_('The value in the category the rule is applied to'))
            elif i == ICON_MODIFIED_COLUMN:
                item.setIcon(QIcon.cached_icon('modified.png'))
                item.setToolTip(_('This icon shows in the row if the icon or template is modified'))
            elif i == ICON_COLUMN:
                item.setToolTip(_('The file name of the icon or the text of the template'))
            elif i == FOR_CHILDREN_MODIFIED_COLUMN:
                item.setIcon(QIcon.cached_icon('modified.png'))
                item.setToolTip(_('This icon shows in the row if the "for children" setting is modified'))
            elif i == FOR_CHILDREN_COLUMN:
                item.setToolTip(_('Indicates whether the rule applies to child values'))

        # Capture clicks on the horizontal header to sort the table columns
        hh = self.rules_table.horizontalHeader()
        hh.sectionResized.connect(self.table_column_resized)
        hh.setSectionsClickable(True)
        hh.sectionClicked.connect(self.do_sort)
        hh.setSortIndicatorShown(True)

        self.delete_button.clicked.connect(self.delete_rule)
        self.edit_button.clicked.connect(self.edit_column)
        self.undo_button.clicked.connect(self.undo_changes)
        self.show_only_current_library.stateChanged.connect(self.change_filter_library)

        self.tb_icon_rules_groupbox.setContentsMargins(0, 0, 0, 0)
        self.tb_icon_rules_gridlayout.setContentsMargins(2, 2, 2, 2)

        try:
            self.table_column_widths = gprefs.get('tag_browser_rules_dialog_table_widths', None)
        except Exception:
            pass

    def lazy_initialize(self):
        self.rules_table.setItemDelegateForColumn(ICON_COLUMN, IconColumnDelegate(self, self.rules_table, self.changed_signal))
        self.rules_table.setItemDelegateForColumn(FOR_CHILDREN_COLUMN,
                                   ChildrenColumnDelegate(self, self.rules_table, self.changed_signal))
        self.populate_content()
        self.section_order = [0, 1, 1, 0, 0, 0, 0]
        self.last_section_sorted = 0
        self.do_sort(VALUE_COLUMN)
        self.do_sort(CATEGORY_COLUMN)

    def populate_content(self):
        field_metadata = self.gui.current_db.field_metadata
        category_icons = self.gui.tags_view.model().category_custom_icons
        only_current_library = self.show_only_current_library.isChecked()
        v = gprefs['tags_browser_value_icons']
        row = 0

        t = self.rules_table
        t.clearContents()

        for category,vdict in v.items():
            if category in field_metadata:
                display_name = field_metadata[category]['name']
                all_values = self.gui.current_db.new_api.all_field_names(category)
            elif only_current_library:
                continue
            else:
                display_name = category.removeprefix('#')
                all_values = ()
            for item_value in vdict:
                if only_current_library and item_value != TEMPLATE_ICON_INDICATOR and item_value not in all_values:
                    continue
                t.setRowCount(row + 1)
                d = v[category][item_value]
                t.setItem(row, DELETED_COLUMN, StateTableWidgetItem(''))
                t.setItem(row, CATEGORY_COLUMN,
                          CategoryTableWidgetItem(category, category_icons, display_name, t))
                t.setItem(row, ICON_MODIFIED_COLUMN, StateTableWidgetItem(''))
                t.setItem(row, VALUE_COLUMN, ValueTableWidgetItem(item_value, t))
                t.setItem(row, ICON_COLUMN, IconFileTableWidgetItem(d[0], item_value, t))
                t.setItem(row, FOR_CHILDREN_MODIFIED_COLUMN, StateTableWidgetItem(''))
                item = ChildrenTableWidgetItem(d[1], item_value, t)
                t.setItem(row, FOR_CHILDREN_COLUMN, item)
                row += 1

    def show_context_menu(self, point):
        item = self.rules_table.itemAt(point)
        if item is None:
            return
        column = item.column()
        if column in (DELETED_COLUMN, ICON_MODIFIED_COLUMN, FOR_CHILDREN_MODIFIED_COLUMN):
            return
        m = QMenu(self)
        if column in (CATEGORY_COLUMN, VALUE_COLUMN):
            ac = m.addAction(_('Delete this rule'), partial(self.context_menu_handler, 'delete', item))
            ac.setEnabled(not item.is_modified)
            ac = m.addAction(_('Undo delete'), partial(self.context_menu_handler, 'undo_delete', item))
            ac.setEnabled(item.is_modified)
        elif column in (ICON_COLUMN, FOR_CHILDREN_COLUMN):
            ac = m.addAction(_('Modify this value'), partial(self.context_menu_handler, 'modify', item))
            ac.setEnabled(not item.is_modified)
            ac = m.addAction(_('Undo modification'), partial(self.context_menu_handler, 'undo_modification', item))
            ac.setEnabled(item.is_modified)
        m.addSeparator()
        m.addAction(_('Copy'), partial(self.context_menu_handler, 'copy', item))
        m.exec(self.rules_table.viewport().mapToGlobal(point))

    def context_menu_handler(self, action, item):
        if action == 'copy':
            QApplication.clipboard().setText(item.text())
            return
        if action == 'delete':
            self.delete_rule()
        elif action == 'undo_delete':
            self.undo_delete()
        elif action == 'modify':
            self.edit_column()
        elif action == 'undo_modification':
            self.undo_modification()
        self.changed_signal.emit()

    def keyPressEvent(self, ev):
        if ev.key() == Qt.Key.Key_Delete:
            self.delete_rule()
            ev.accept()
            return
        return super().keyPressEvent(ev)

    def change_filter_library(self, state):
        gprefs['tag_browser_rules_show_only_current_library'] = self.show_only_current_library.isChecked()
        self.populate_content()
        self.rules_table.sortByColumn(self.last_section_sorted, Qt.SortOrder(self.section_order[self.last_section_sorted]))

    def undo_changes(self):
        idx = self.rules_table.currentIndex()
        if idx.isValid():
            column = idx.column()
            if column == DELETED_COLUMN:
                column = CATEGORY_COLUMN
            elif column == ICON_MODIFIED_COLUMN:
                column = ICON_COLUMN
            elif column == FOR_CHILDREN_MODIFIED_COLUMN:
                column = FOR_CHILDREN_COLUMN

            if column in (CATEGORY_COLUMN, VALUE_COLUMN):
                self.undo_delete()
            elif column in (ICON_COLUMN, FOR_CHILDREN_COLUMN):
                self.undo_modification()

    def edit_column(self):
        idx = self.rules_table.currentIndex()
        if idx.isValid():
            column = idx.column()
            if column in (ICON_COLUMN, FOR_CHILDREN_COLUMN):
                self.rules_table.edit(idx)

    def delete_rule(self):
        idx = self.rules_table.currentIndex()
        if idx.isValid():
            item = self.rules_table.item(idx.row(), CATEGORY_COLUMN)
            item.is_modified = True
            self.changed_signal.emit()

    def undo_delete(self):
        idx = self.rules_table.currentIndex()
        if idx.isValid():
            self.rules_table.item(idx.row(), CATEGORY_COLUMN).undo()
            self.changed_signal.emit()

    def undo_modification(self):
        idx = self.rules_table.currentIndex()
        if idx.isValid():
            item = self.rules_table.item(idx.row(), idx.column())
            item.undo()
            self.changed_signal.emit()

    def table_column_resized(self, col, old, new):
        self.table_column_widths = []
        for c in range(self.rules_table.columnCount()):
            self.table_column_widths.append(self.rules_table.columnWidth(c))
        gprefs['tag_browser_rules_dialog_table_widths'] = self.table_column_widths

    def resizeEvent(self, *args):
        super().resizeEvent(*args)
        if self.table_column_widths is not None:
            for c,w in enumerate(self.table_column_widths):
                self.rules_table.setColumnWidth(c, w)
        else:
            # Calculate a reasonable initial sizing. The vertical scroll bar
            # might not be rendered, so might not yet have a width, assume 25.
            # Assume that a button is 60 wide. Assume that the 3 icon columns
            # are 25 wide. None of this really matters because user-changed
            # column widths will be remembered.
            w = self.tb_icon_rules_groupbox.width() - (4*25) - 60 - self.rules_table.verticalHeader().width()
            w //= (self.rules_table.columnCount() - 3)
            for c in range(self.rules_table.columnCount()):
                if c in (DELETED_COLUMN, ICON_MODIFIED_COLUMN, FOR_CHILDREN_MODIFIED_COLUMN):
                    self.rules_table.setColumnWidth(c, 20)
                else:
                    self.rules_table.setColumnWidth(c, w)
                self.table_column_widths.append(self.rules_table.columnWidth(c))

        gprefs['tag_browser_rules_dialog_table_widths'] = self.table_column_widths

    def do_sort(self, section):
        order = 1 - self.section_order[section]
        self.section_order[section] = order
        self.last_section_sorted = section
        self.rules_table.sortByColumn(section, Qt.SortOrder(order))

    def commit(self):
        v = copy.deepcopy(gprefs['tags_browser_value_icons'])
        for r in range(self.rules_table.rowCount()):
            cat_item = self.rules_table.item(r, CATEGORY_COLUMN)
            value_item = self.rules_table.item(r, VALUE_COLUMN)
            value_text = value_item._original_text

            if cat_item.is_modified:  # deleted
                if not value_item.is_template:
                    # Need to delete the icon file to clean up
                    icon_file = self.rules_table.item(r, ICON_COLUMN).text()
                    path = os.path.join(config_dir, 'tb_icons', icon_file)
                    try:
                        os.remove(path)
                    except:
                        pass
                v[cat_item.lookup_name].pop(value_text, None)
                continue

            icon_item = self.rules_table.item(r, ICON_COLUMN)
            d = v[cat_item.lookup_name][value_text]

            if icon_item.is_modified:
                if value_item.is_template:
                    d[0] = icon_item.text()
                    v[cat_item.lookup_name][TEMPLATE_ICON_INDICATOR] = d
                elif icon_item.new_icon is not None:
                    # No need to delete anything. The file name stays the same.
                    p = os.path.join(config_dir, 'tb_icons')
                    if not os.path.exists(p):
                        os.makedirs(p)
                    p = os.path.join(p, icon_item.text())
                    with open(p, 'wb') as f:
                        f.write(icon_item.new_icon)

            child_item = self.rules_table.item(r, FOR_CHILDREN_COLUMN)
            if child_item.is_modified:
                d[1] = child_item.value
                v[cat_item.lookup_name][value_text] = d

        # Remove categories with no rules
        for category in list(v.keys()):
            if len(v[category]) == 0:
                v.pop(category, None)
        gprefs['tags_browser_value_icons'] = v

        return LazyConfigWidgetBase.commit(self)
