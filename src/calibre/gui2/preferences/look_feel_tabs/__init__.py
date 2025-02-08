#!/usr/bin/env python


__license__   = 'GPL v3'
__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import json

from qt.core import (
    QAbstractListModel,
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QIcon,
    QItemSelectionModel,
    QLineEdit,
    Qt,
    QToolButton,
    QVBoxLayout,
    QWidget,
    pyqtSignal,
)

from calibre.ebooks.metadata.book.render import DEFAULT_AUTHOR_LINK
from calibre.ebooks.metadata.search_internet import qquote
from calibre.gui2 import choose_files, choose_save_file, error_dialog
from calibre.gui2.book_details import get_field_list
from calibre.gui2.dialogs.template_dialog import TemplateDialog
from calibre.gui2.preferences import LazyConfigWidgetBase
from calibre.gui2.preferences.coloring import EditRules
from calibre.gui2.ui import get_gui
from calibre.utils.formatter import EvalFormatter


class DefaultAuthorLink(QWidget):

    changed_signal = pyqtSignal()

    def __init__(self, parent):
        QWidget.__init__(self, parent)
        l = QVBoxLayout()
        l.addWidget(self)
        l.setContentsMargins(0, 0, 0, 0)
        l = QFormLayout(self)
        l.setContentsMargins(0, 0, 0, 0)
        l.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self.choices = c = QComboBox()
        c.setMinimumContentsLength(30)
        for text, data in [
                (_('Search for the author on Goodreads'), 'search-goodreads'),
                (_('Search for the author on Amazon'), 'search-amzn'),
                (_('Search for the author in your calibre library'), 'search-calibre'),
                (_('Search for the author on Wikipedia'), 'search-wikipedia'),
                (_('Search for the author on Google Books'), 'search-google'),
                (_('Search for the book on Goodreads'), 'search-goodreads-book'),
                (_('Search for the book on Amazon'), 'search-amzn-book'),
                (_('Search for the book on Google Books'), 'search-google-book'),
                (_('Use a custom search URL'), 'url'),
        ]:
            c.addItem(text, data)
        l.addRow(_('Clicking on &author names should:'), c)
        ul = QHBoxLayout()
        self.custom_url = u = QLineEdit(self)
        u.setToolTip(_(
            'Enter the URL to search. It should contain the string {0}'
            '\nwhich will be replaced by the author name. For example,'
            '\n{1}').format('{author}', 'https://en.wikipedia.org/w/index.php?search={author}'))
        u.textChanged.connect(self.changed_signal)
        u.setPlaceholderText(_('Enter the URL'))
        ul.addWidget(u)
        u = self.custom_url_button = QToolButton()
        u.setIcon(QIcon.ic('edit_input.png'))
        u.setToolTip(_('Click this button to open the template tester'))
        u.clicked.connect(self.open_template_tester)
        ul.addWidget(u)
        c.currentIndexChanged.connect(self.current_changed)
        l.addRow(ul)
        self.current_changed()
        c.currentIndexChanged.connect(self.changed_signal)

    @property
    def value(self):
        k = self.choices.currentData()
        if k == 'url':
            return self.custom_url.text()
        return k if k != DEFAULT_AUTHOR_LINK else None

    @value.setter
    def value(self, val):
        i = self.choices.findData(val)
        if i < 0:
            i = self.choices.findData('url')
            self.custom_url.setText(val)
        self.choices.setCurrentIndex(i)

    def open_template_tester(self):
        gui = get_gui()
        db = gui.current_db.new_api
        lv = gui.library_view
        rows = lv.selectionModel().selectedRows()
        if not rows:
            vals = [{'author': qquote(_('Author')), 'title': _('Title'), 'author_sort': _('Author sort')}]
        else:
            vals = []
            for row in rows:
                book_id = lv.model().id(row)
                mi = db.new_api.get_proxy_metadata(book_id)
                vals.append({'author': qquote(mi.authors[0]),
                             'title': qquote(mi.title),
                             'author_sort': qquote(mi.author_sort_map.get(mi.authors[0]))})
        d = TemplateDialog(parent=self, text=self.custom_url.text(), mi=vals, formatter=EvalFormatter)
        if d.exec() == QDialog.DialogCode.Accepted:
            self.custom_url.setText(d.rule[1])

    def current_changed(self):
        k = self.choices.currentData()
        self.custom_url.setVisible(k == 'url')
        self.custom_url_button.setVisible(k == 'url')

    def restore_defaults(self):
        self.value = DEFAULT_AUTHOR_LINK


class DisplayedFields(QAbstractListModel):

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


class LazyEditRulesBase(LazyConfigWidgetBase):

    rule_set_name = None

    def __init__(self, parent=None):
        super().__init__(parent)
        self.rules_editor = EditRules(parent)
        self.setLayout(self.rules_editor.layout())

    def genesis(self, gui):
        self.gui = gui
        self.rules_editor.changed.connect(self.changed_signal)

    def lazy_initialize(self):
        if not self.rule_set_name:
            raise NotImplementedError('You must define the attribut "rule_set_name" in LazyEditRulesBase subclasses')
        self.load_rule_set(self.rule_set_name)

    def load_rule_set(self, name):
        db = self.gui.current_db
        mi = selected_rows_metadatas()
        self.rules_editor.initialize(db.field_metadata, db.prefs, mi, name)

    def commit(self):
        self.rules_editor.commit(self.gui.current_db.prefs)
        return LazyConfigWidgetBase.commit(self)

    def restore_defaults(self):
        LazyConfigWidgetBase.restore_defaults(self)
        self.rules_editor.clear()
        self.changed_signal.emit()


class ColumnColorRules(LazyEditRulesBase):
    rule_set_name = 'column_color_rules'


class ColumnIconRules(LazyEditRulesBase):
    rule_set_name = 'column_icon_rules'


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


def selected_rows_metadatas():
    rslt = []
    try:
        db = get_gui().current_db
        rows = get_gui().current_view().selectionModel().selectedRows()
        for row in rows:
            if row.isValid():
                rslt.append(db.new_api.get_proxy_metadata(db.data.index_to_id(row.row())))
    except:
        pass
    return rslt
