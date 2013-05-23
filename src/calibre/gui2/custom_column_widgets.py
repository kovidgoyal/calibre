#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from functools import partial

from PyQt4.Qt import (QComboBox, QLabel, QSpinBox, QDoubleSpinBox, QDateTimeEdit,
        QDateTime, QGroupBox, QVBoxLayout, QSizePolicy, QGridLayout,
        QSpacerItem, QIcon, QCheckBox, QWidget, QHBoxLayout, SIGNAL,
        QPushButton, QMessageBox, QToolButton, Qt)

from calibre.utils.date import qt_to_dt, now
from calibre.gui2.complete2 import EditWithComplete
from calibre.gui2.comments_editor import Editor as CommentsEditor
from calibre.gui2 import UNDEFINED_QDATETIME, error_dialog
from calibre.gui2.dialogs.tag_editor import TagEditor
from calibre.utils.config import tweaks
from calibre.utils.icu import sort_key
from calibre.library.comments import comments_to_html

class Base(object):

    def __init__(self, db, col_id, parent=None):
        self.db, self.col_id = db, col_id
        self.col_metadata = db.custom_column_num_map[col_id]
        self.initial_val = self.widgets = None
        self.setup_ui(parent)

    def initialize(self, book_id):
        val = self.db.get_custom(book_id, num=self.col_id, index_is_id=True)
        self.initial_val = val
        val = self.normalize_db_val(val)
        self.setter(val)

    @property
    def gui_val(self):
        return self.getter()

    def commit(self, book_id, notify=False):
        val = self.gui_val
        val = self.normalize_ui_val(val)
        if val != self.initial_val:
            return self.db.set_custom(book_id, val, num=self.col_id,
                            notify=notify, commit=False, allow_case_change=True)
        else:
            return set()

    def normalize_db_val(self, val):
        return val

    def normalize_ui_val(self, val):
        return val

    def break_cycles(self):
        self.db = self.widgets = self.initial_val = None

class Bool(Base):

    def setup_ui(self, parent):
        self.widgets = [QLabel('&'+self.col_metadata['name']+':', parent),
                QComboBox(parent)]
        w = self.widgets[1]
        items = [_('Yes'), _('No'), _('Undefined')]
        icons = [I('ok.png'), I('list_remove.png'), I('blank.png')]
        if not self.db.prefs.get('bools_are_tristate'):
            items = items[:-1]
            icons = icons[:-1]
        for icon, text in zip(icons, items):
            w.addItem(QIcon(icon), text)

    def setter(self, val):
        val = {None: 2, False: 1, True: 0}[val]
        if not self.db.prefs.get('bools_are_tristate') and val == 2:
            val = 1
        self.widgets[1].setCurrentIndex(val)

    def getter(self):
        val = self.widgets[1].currentIndex()
        return {2: None, 1: False, 0: True}[val]

class Int(Base):

    def setup_ui(self, parent):
        self.widgets = [QLabel('&'+self.col_metadata['name']+':', parent),
                QSpinBox(parent)]
        w = self.widgets[1]
        w.setRange(-1000000, 100000000)
        w.setSpecialValueText(_('Undefined'))
        w.setSingleStep(1)

    def setter(self, val):
        if val is None:
            val = self.widgets[1].minimum()
        else:
            val = int(val)
        self.widgets[1].setValue(val)

    def getter(self):
        val = self.widgets[1].value()
        if val == self.widgets[1].minimum():
            val = None
        return val

class Float(Int):

    def setup_ui(self, parent):
        self.widgets = [QLabel('&'+self.col_metadata['name']+':', parent),
                QDoubleSpinBox(parent)]
        w = self.widgets[1]
        w.setRange(-1000000., float(100000000))
        w.setDecimals(2)
        w.setSpecialValueText(_('Undefined'))
        w.setSingleStep(1)

    def setter(self, val):
        if val is None:
            val = self.widgets[1].minimum()
        self.widgets[1].setValue(val)

class Rating(Int):

    def setup_ui(self, parent):
        Int.setup_ui(self, parent)
        w = self.widgets[1]
        w.setRange(0, 5)
        w.setSuffix(' '+_('star(s)'))
        w.setSpecialValueText(_('Unrated'))

    def setter(self, val):
        if val is None:
            val = 0
        self.widgets[1].setValue(int(round(val/2.)))

    def getter(self):
        val = self.widgets[1].value()
        if val == 0:
            val = None
        else:
            val *= 2
        return val

class DateTimeEdit(QDateTimeEdit):

    def focusInEvent(self, x):
        self.setSpecialValueText('')
        QDateTimeEdit.focusInEvent(self, x)

    def focusOutEvent(self, x):
        self.setSpecialValueText(_('Undefined'))
        QDateTimeEdit.focusOutEvent(self, x)

    def set_to_today(self):
        self.setDateTime(now())

    def set_to_clear(self):
        self.setDateTime(UNDEFINED_QDATETIME)

    def keyPressEvent(self, ev):
        if ev.key() == Qt.Key_Minus:
            ev.accept()
            self.setDateTime(self.minimumDateTime())
        elif ev.key() == Qt.Key_Equal:
            ev.accept()
            self.setDateTime(QDateTime.currentDateTime())
        else:
            return QDateTimeEdit.keyPressEvent(self, ev)


class DateTime(Base):

    def setup_ui(self, parent):
        cm = self.col_metadata
        self.widgets = [QLabel('&'+cm['name']+':', parent), DateTimeEdit(parent)]
        self.widgets.append(QLabel(''))
        w = QWidget(parent)
        self.widgets.append(w)
        l = QHBoxLayout()
        l.setContentsMargins(0, 0, 0, 0)
        w.setLayout(l)
        l.addStretch(1)
        self.today_button = QPushButton(_('Set \'%s\' to today')%cm['name'], parent)
        l.addWidget(self.today_button)
        self.clear_button = QPushButton(_('Clear \'%s\'')%cm['name'], parent)
        l.addWidget(self.clear_button)
        l.addStretch(2)

        w = self.widgets[1]
        format = cm['display'].get('date_format','')
        if not format:
            format = 'dd MMM yyyy hh:mm'
        w.setDisplayFormat(format)
        w.setCalendarPopup(True)
        w.setMinimumDateTime(UNDEFINED_QDATETIME)
        w.setSpecialValueText(_('Undefined'))
        self.today_button.clicked.connect(w.set_to_today)
        self.clear_button.clicked.connect(w.set_to_clear)

    def setter(self, val):
        if val is None:
            val = self.widgets[1].minimumDateTime()
        else:
            val = QDateTime(val)
        self.widgets[1].setDateTime(val)

    def getter(self):
        val = self.widgets[1].dateTime()
        if val <= UNDEFINED_QDATETIME:
            val = None
        else:
            val = qt_to_dt(val)
        return val

class Comments(Base):

    def setup_ui(self, parent):
        self._box = QGroupBox(parent)
        self._box.setTitle('&'+self.col_metadata['name'])
        self._layout = QVBoxLayout()
        self._tb = CommentsEditor(self._box)
        self._tb.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        # self._tb.setTabChangesFocus(True)
        self._layout.addWidget(self._tb)
        self._box.setLayout(self._layout)
        self.widgets = [self._box]

    def setter(self, val):
        if val is None:
            val = ''
        self._tb.html = comments_to_html(val)

    def getter(self):
        val = unicode(self._tb.html).strip()
        if not val:
            val = None
        return val

class MultipleWidget(QWidget):

    def __init__(self, parent):
        QWidget.__init__(self, parent)
        layout = QHBoxLayout()
        layout.setSpacing(5)
        layout.setContentsMargins(0, 0, 0, 0)

        self.tags_box = EditWithComplete(parent)
        layout.addWidget(self.tags_box, stretch=1000)
        self.editor_button = QToolButton(self)
        self.editor_button.setToolTip(_('Open Item Editor'))
        self.editor_button.setIcon(QIcon(I('chapters.png')))
        layout.addWidget(self.editor_button)
        self.setLayout(layout)

    def get_editor_button(self):
        return self.editor_button

    def update_items_cache(self, values):
        self.tags_box.update_items_cache(values)

    def clear(self):
        self.tags_box.clear()

    def setEditText(self):
        self.tags_box.setEditText()

    def addItem(self, itm):
        self.tags_box.addItem(itm)

    def set_separator(self, sep):
        self.tags_box.set_separator(sep)

    def set_add_separator(self, sep):
        self.tags_box.set_add_separator(sep)

    def set_space_before_sep(self, v):
        self.tags_box.set_space_before_sep(v)

    def setSizePolicy(self, v1, v2):
        self.tags_box.setSizePolicy(v1, v2)

    def setText(self, v):
        self.tags_box.setText(v)

    def text(self):
        return self.tags_box.text()

class Text(Base):

    def setup_ui(self, parent):
        self.sep = self.col_metadata['multiple_seps']
        self.key = self.db.field_metadata.label_to_key(self.col_metadata['label'],
                                                       prefer_custom=True)
        self.parent = parent

        if self.col_metadata['is_multiple']:
            w = MultipleWidget(parent)
            w.set_separator(self.sep['ui_to_list'])
            if self.sep['ui_to_list'] == '&':
                w.set_space_before_sep(True)
                w.set_add_separator(tweaks['authors_completer_append_separator'])
            w.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Preferred)
            w.get_editor_button().clicked.connect(self.edit)
        else:
            w = EditWithComplete(parent)
            w.set_separator(None)
            w.setSizeAdjustPolicy(w.AdjustToMinimumContentsLengthWithIcon)
            w.setMinimumContentsLength(25)
        self.widgets = [QLabel('&'+self.col_metadata['name']+':', parent), w]

    def initialize(self, book_id):
        values = list(self.db.all_custom(num=self.col_id))
        values.sort(key=sort_key)
        self.book_id = book_id
        self.widgets[1].clear()
        self.widgets[1].update_items_cache(values)
        val = self.db.get_custom(book_id, num=self.col_id, index_is_id=True)
        if isinstance(val, list):
            val.sort(key=sort_key)
        self.initial_val = val
        val = self.normalize_db_val(val)

        if self.col_metadata['is_multiple']:
            self.setter(val)
        else:
            self.widgets[1].show_initial_value(val)

    def setter(self, val):
        if self.col_metadata['is_multiple']:
            if not val:
                val = []
            self.widgets[1].setText(self.sep['list_to_ui'].join(val))

    def getter(self):
        if self.col_metadata['is_multiple']:
            val = unicode(self.widgets[1].text()).strip()
            ans = [x.strip() for x in val.split(self.sep['ui_to_list']) if x.strip()]
            if not ans:
                ans = None
            return ans
        val = unicode(self.widgets[1].currentText()).strip()
        if not val:
            val = None
        return val

    def _save_dialog(self, parent, title, msg, det_msg=''):
        d = QMessageBox(parent)
        d.setWindowTitle(title)
        d.setText(msg)
        d.setStandardButtons(QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel)
        return d.exec_()

    def edit(self):
        if (self.getter() != self.initial_val and (self.getter() or
            self.initial_val)):
            d = self._save_dialog(self.parent, _('Values changed'),
                    _('You have changed the values. In order to use this '
                       'editor, you must either discard or apply these '
                       'changes. Apply changes?'))
            if d == QMessageBox.Cancel:
                return
            if d == QMessageBox.Yes:
                self.commit(self.book_id)
                self.db.commit()
                self.initial_val = self.getter()
            else:
                self.setter(self.initial_val)
        d = TagEditor(self.parent, self.db, self.book_id, self.key)
        if d.exec_() == TagEditor.Accepted:
            self.setter(d.tags)

class Series(Base):

    def setup_ui(self, parent):
        w = EditWithComplete(parent)
        w.set_separator(None)
        w.setSizeAdjustPolicy(w.AdjustToMinimumContentsLengthWithIcon)
        w.setMinimumContentsLength(25)
        self.name_widget = w
        self.widgets = [QLabel('&'+self.col_metadata['name']+':', parent), w]
        w.editTextChanged.connect(self.series_changed)

        self.widgets.append(QLabel('&'+self.col_metadata['name']+_(' index:'), parent))
        w = QDoubleSpinBox(parent)
        w.setRange(-10000., float(100000000))
        w.setDecimals(2)
        w.setSingleStep(1)
        self.idx_widget=w
        self.widgets.append(w)

    def initialize(self, book_id):
        values = list(self.db.all_custom(num=self.col_id))
        values.sort(key=sort_key)
        val = self.db.get_custom(book_id, num=self.col_id, index_is_id=True)
        self.initial_val = val
        s_index = self.db.get_custom_extra(book_id, num=self.col_id, index_is_id=True)
        self.initial_index = s_index
        try:
            s_index = float(s_index)
        except (ValueError, TypeError):
            s_index = 1.0
        self.idx_widget.setValue(s_index)
        val = self.normalize_db_val(val)
        self.name_widget.blockSignals(True)
        self.name_widget.update_items_cache(values)
        self.name_widget.show_initial_value(val)
        self.name_widget.blockSignals(False)

    def getter(self):
        n = unicode(self.name_widget.currentText()).strip()
        i = self.idx_widget.value()
        return n, i

    def series_changed(self, val):
        val, s_index = self.gui_val
        if tweaks['series_index_auto_increment'] == 'no_change':
            pass
        elif tweaks['series_index_auto_increment'] == 'const':
            s_index = 1.0
        else:
            s_index = self.db.get_next_cc_series_num_for(val,
                                                     num=self.col_id)
        self.idx_widget.setValue(s_index)

    def commit(self, book_id, notify=False):
        val, s_index = self.gui_val
        val = self.normalize_ui_val(val)
        if val != self.initial_val or s_index != self.initial_index:
            if val == '':
                val = s_index = None
            return self.db.set_custom(book_id, val, extra=s_index, num=self.col_id,
                               notify=notify, commit=False, allow_case_change=True)
        else:
            return set()

class Enumeration(Base):

    def setup_ui(self, parent):
        self.parent = parent
        self.widgets = [QLabel('&'+self.col_metadata['name']+':', parent),
                QComboBox(parent)]
        w = self.widgets[1]
        vals = self.col_metadata['display']['enum_values']
        w.addItem('')
        for v in vals:
            w.addItem(v)

    def initialize(self, book_id):
        val = self.db.get_custom(book_id, num=self.col_id, index_is_id=True)
        val = self.normalize_db_val(val)
        self.initial_val = val
        idx = self.widgets[1].findText(val)
        if idx < 0:
            error_dialog(self.parent, '',
                    _('The enumeration "{0}" contains an invalid value '
                      'that will be set to the default').format(
                                            self.col_metadata['name']),
                    show=True, show_copy_button=False)

            idx = 0
        self.widgets[1].setCurrentIndex(idx)

    def setter(self, val):
        self.widgets[1].setCurrentIndex(self.widgets[1].findText(val))

    def getter(self):
        return unicode(self.widgets[1].currentText())

    def normalize_db_val(self, val):
        if val is None:
            val = ''
        return val

    def normalize_ui_val(self, val):
        if not val:
            val = None
        return val

widgets = {
        'bool' : Bool,
        'rating' : Rating,
        'int': Int,
        'float': Float,
        'datetime': DateTime,
        'text' : Text,
        'comments': Comments,
        'series': Series,
        'enumeration': Enumeration
}

def field_sort_key(y, fm=None):
    m1 = fm[y]
    name = icu_lower(m1['name'])
    n1 = 'zzzzz' + name if m1['datatype'] == 'comments' else name
    return sort_key(n1)

def populate_metadata_page(layout, db, book_id, bulk=False, two_column=False, parent=None):
    def widget_factory(typ, key):
        if bulk:
            w = bulk_widgets[typ](db, key, parent)
        else:
            w = widgets[typ](db, key, parent)
        if book_id is not None:
            w.initialize(book_id)
        return w
    fm = db.field_metadata

    # Get list of all non-composite custom fields. We must make widgets for these
    fields = fm.custom_field_keys(include_composites=False)
    cols_to_display = fields
    cols_to_display.sort(key=partial(field_sort_key, fm=fm))

    # This will contain the fields in the order to display them
    cols = []

    # The fields named here must be first in the widget list
    tweak_cols = tweaks['metadata_edit_custom_column_order']
    comments_in_tweak = 0
    for key in (tweak_cols or ()):
        # Add the key if it really exists in the database
        if key in cols_to_display:
            cols.append(key)
            if fm[key]['datatype'] == 'comments':
                comments_in_tweak += 1

    # Add all the remaining fields
    comments_not_in_tweak = 0
    for key in cols_to_display:
        if key not in cols:
            cols.append(key)
            if fm[key]['datatype'] == 'comments':
                comments_not_in_tweak += 1

    count = len(cols)
    layout_rows_for_comments = 9
    if two_column:
        turnover_point = ((count-comments_not_in_tweak+1) +
                          comments_in_tweak*(layout_rows_for_comments-1))/2
    else:
        # Avoid problems with multi-line widgets
        turnover_point = count + 1000
    ans = []
    column = row = base_row = max_row = 0
    for key in cols:
        if not fm[key]['is_editable']:
            continue  # this almost never happens
        dt = fm[key]['datatype']
        if dt == 'composite' or (bulk and dt == 'comments'):
            continue
        w = widget_factory(dt, fm[key]['colnum'])
        ans.append(w)
        if two_column and dt == 'comments':
            # Here for compatibility with old layout. Comments always started
            # in the left column
            comments_in_tweak -= 1
            # no special processing if the comment field was named in the tweak
            if comments_in_tweak < 0 and comments_not_in_tweak > 0:
                # Force a turnover, adding comments widgets below max_row.
                # Save the row to return to if we turn over again
                column = 0
                row = max_row
                base_row = row
                turnover_point = row + (comments_not_in_tweak * layout_rows_for_comments)/2
                comments_not_in_tweak = 0

        l = QGridLayout()
        if dt == 'comments':
            layout.addLayout(l, row, column, layout_rows_for_comments, 1)
            layout.setColumnStretch(column, 100)
            row += layout_rows_for_comments
        else:
            layout.addLayout(l, row, column, 1, 1)
            layout.setColumnStretch(column, 100)
            row += 1
        for c in range(0, len(w.widgets), 2):
            if dt != 'comments':
                w.widgets[c].setWordWrap(True)
                w.widgets[c].setBuddy(w.widgets[c+1])
                l.addWidget(w.widgets[c], c, 0)
                l.addWidget(w.widgets[c+1], c, 1)
                l.setColumnStretch(1, 10000)
            else:
                l.addWidget(w.widgets[0], 0, 0, 1, 2)
        l.addItem(QSpacerItem(0, 0, vPolicy=QSizePolicy.Expanding), c, 0, 1, 1)
        max_row = max(max_row, row)
        if row >= turnover_point:
            column = 1
            turnover_point = count + 1000
            row = base_row

    items = []
    if len(ans) > 0:
        items.append(QSpacerItem(10, 10, QSizePolicy.Minimum,
            QSizePolicy.Expanding))
        layout.addItem(items[-1], layout.rowCount(), 0, 1, 1)
        layout.setRowStretch(layout.rowCount()-1, 100)
    return ans, items

class BulkBase(Base):

    @property
    def gui_val(self):
        if not hasattr(self, '_cached_gui_val_'):
            self._cached_gui_val_ = self.getter()
        return self._cached_gui_val_

    def get_initial_value(self, book_ids):
        values = set([])
        for book_id in book_ids:
            val = self.db.get_custom(book_id, num=self.col_id, index_is_id=True)
            if isinstance(val, list):
                val = frozenset(val)
            values.add(val)
            if len(values) > 1:
                break
        ans = None
        if len(values) == 1:
            ans = iter(values).next()
        if isinstance(ans, frozenset):
            ans = list(ans)
        return ans

    def initialize(self, book_ids):
        self.initial_val = val = self.get_initial_value(book_ids)
        val = self.normalize_db_val(val)
        self.setter(val)

    def commit(self, book_ids, notify=False):
        if not self.a_c_checkbox.isChecked():
            return
        val = self.gui_val
        val = self.normalize_ui_val(val)
        self.db.set_custom_bulk(book_ids, val, num=self.col_id, notify=notify)

    def make_widgets(self, parent, main_widget_class, extra_label_text=''):
        w = QWidget(parent)
        self.widgets = [QLabel('&'+self.col_metadata['name']+':', w), w]
        l = QHBoxLayout()
        l.setContentsMargins(0, 0, 0, 0)
        w.setLayout(l)
        self.main_widget = main_widget_class(w)
        l.addWidget(self.main_widget)
        l.setStretchFactor(self.main_widget, 10)
        self.a_c_checkbox = QCheckBox(_('Apply changes'), w)
        l.addWidget(self.a_c_checkbox)
        self.ignore_change_signals = True

        # connect to the various changed signals so we can auto-update the
        # apply changes checkbox
        if hasattr(self.main_widget, 'editTextChanged'):
            # editable combobox widgets
            self.main_widget.editTextChanged.connect(self.a_c_checkbox_changed)
        if hasattr(self.main_widget, 'textChanged'):
            # lineEdit widgets
            self.main_widget.textChanged.connect(self.a_c_checkbox_changed)
        if hasattr(self.main_widget, 'currentIndexChanged'):
            # combobox widgets
            self.main_widget.currentIndexChanged[int].connect(self.a_c_checkbox_changed)
        if hasattr(self.main_widget, 'valueChanged'):
            # spinbox widgets
            self.main_widget.valueChanged.connect(self.a_c_checkbox_changed)
        if hasattr(self.main_widget, 'dateTimeChanged'):
            # dateEdit widgets
            self.main_widget.dateTimeChanged.connect(self.a_c_checkbox_changed)

    def a_c_checkbox_changed(self):
        if not self.ignore_change_signals:
            self.a_c_checkbox.setChecked(True)

class BulkBool(BulkBase, Bool):

    def get_initial_value(self, book_ids):
        value = None
        for book_id in book_ids:
            val = self.db.get_custom(book_id, num=self.col_id, index_is_id=True)
            if not self.db.prefs.get('bools_are_tristate') and val is None:
                val = False
            if value is not None and value != val:
                return None
            value = val
        return value

    def setup_ui(self, parent):
        self.make_widgets(parent, QComboBox)
        items = [_('Yes'), _('No')]
        if not self.db.prefs.get('bools_are_tristate'):
            items.append('')
        else:
            items.append(_('Undefined'))
        icons = [I('ok.png'), I('list_remove.png'), I('blank.png')]
        self.main_widget.blockSignals(True)
        for icon, text in zip(icons, items):
            self.main_widget.addItem(QIcon(icon), text)
        self.main_widget.blockSignals(False)

    def getter(self):
        val = self.main_widget.currentIndex()
        if not self.db.prefs.get('bools_are_tristate'):
            return {2: False, 1: False, 0: True}[val]
        else:
            return {2: None, 1: False, 0: True}[val]

    def setter(self, val):
        val = {None: 2, False: 1, True: 0}[val]
        self.main_widget.setCurrentIndex(val)
        self.ignore_change_signals = False

    def commit(self, book_ids, notify=False):
        if not self.a_c_checkbox.isChecked():
            return
        val = self.gui_val
        val = self.normalize_ui_val(val)
        if not self.db.prefs.get('bools_are_tristate') and val is None:
            val = False
        self.db.set_custom_bulk(book_ids, val, num=self.col_id, notify=notify)

    def a_c_checkbox_changed(self):
        if not self.ignore_change_signals:
            if not self.db.prefs.get('bools_are_tristate') and \
                                    self.main_widget.currentIndex() == 2:
                self.a_c_checkbox.setChecked(False)
            else:
                self.a_c_checkbox.setChecked(True)

class BulkInt(BulkBase):

    def setup_ui(self, parent):
        self.make_widgets(parent, QSpinBox)
        self.main_widget.setRange(-1000000, 100000000)
        self.main_widget.setSpecialValueText(_('Undefined'))
        self.main_widget.setSingleStep(1)

    def setter(self, val):
        if val is None:
            val = self.main_widget.minimum()
        else:
            val = int(val)
        self.main_widget.setValue(val)
        self.ignore_change_signals = False

    def getter(self):
        val = self.main_widget.value()
        if val == self.main_widget.minimum():
            val = None
        return val

class BulkFloat(BulkInt):

    def setup_ui(self, parent):
        self.make_widgets(parent, QDoubleSpinBox)
        self.main_widget.setRange(-1000000., float(100000000))
        self.main_widget.setDecimals(2)
        self.main_widget.setSpecialValueText(_('Undefined'))
        self.main_widget.setSingleStep(1)

class BulkRating(BulkBase):

    def setup_ui(self, parent):
        self.make_widgets(parent, QSpinBox)
        self.main_widget.setRange(0, 5)
        self.main_widget.setSuffix(' '+_('star(s)'))
        self.main_widget.setSpecialValueText(_('Unrated'))
        self.main_widget.setSingleStep(1)

    def setter(self, val):
        if val is None:
            val = 0
        self.main_widget.setValue(int(round(val/2.)))
        self.ignore_change_signals = False

    def getter(self):
        val = self.main_widget.value()
        if val == 0:
            val = None
        else:
            val *= 2
        return val

class BulkDateTime(BulkBase):

    def setup_ui(self, parent):
        cm = self.col_metadata
        self.make_widgets(parent, DateTimeEdit)
        self.widgets.append(QLabel(''))
        w = QWidget(parent)
        self.widgets.append(w)
        l = QHBoxLayout()
        l.setContentsMargins(0, 0, 0, 0)
        w.setLayout(l)
        l.addStretch(1)
        self.today_button = QPushButton(_('Set \'%s\' to today')%cm['name'], parent)
        l.addWidget(self.today_button)
        self.clear_button = QPushButton(_('Clear \'%s\'')%cm['name'], parent)
        l.addWidget(self.clear_button)
        l.addStretch(2)

        w = self.main_widget
        format = cm['display'].get('date_format','')
        if not format:
            format = 'dd MMM yyyy'
        w.setDisplayFormat(format)
        w.setCalendarPopup(True)
        w.setMinimumDateTime(UNDEFINED_QDATETIME)
        w.setSpecialValueText(_('Undefined'))
        self.today_button.clicked.connect(w.set_to_today)
        self.clear_button.clicked.connect(w.set_to_clear)

    def setter(self, val):
        if val is None:
            val = self.main_widget.minimumDateTime()
        else:
            val = QDateTime(val)
        self.main_widget.setDateTime(val)
        self.ignore_change_signals = False

    def getter(self):
        val = self.main_widget.dateTime()
        if val <= UNDEFINED_QDATETIME:
            val = None
        else:
            val = qt_to_dt(val)
        return val

class BulkSeries(BulkBase):

    def setup_ui(self, parent):
        self.make_widgets(parent, EditWithComplete)
        values = self.all_values = list(self.db.all_custom(num=self.col_id))
        values.sort(key=sort_key)
        self.main_widget.setSizeAdjustPolicy(self.main_widget.AdjustToMinimumContentsLengthWithIcon)
        self.main_widget.setMinimumContentsLength(25)
        self.widgets.append(QLabel('', parent))
        w = QWidget(parent)
        layout = QHBoxLayout(w)
        layout.setContentsMargins(0, 0, 0, 0)
        self.remove_series = QCheckBox(parent)
        self.remove_series.setText(_('Remove series'))
        layout.addWidget(self.remove_series)
        self.idx_widget = QCheckBox(parent)
        self.idx_widget.setText(_('Automatically number books'))
        layout.addWidget(self.idx_widget)
        self.force_number = QCheckBox(parent)
        self.force_number.setText(_('Force numbers to start with '))
        layout.addWidget(self.force_number)
        self.series_start_number = QSpinBox(parent)
        self.series_start_number.setMinimum(1)
        self.series_start_number.setMaximum(9999999)
        self.series_start_number.setProperty("value", 1)
        layout.addWidget(self.series_start_number)
        layout.addItem(QSpacerItem(20, 10, QSizePolicy.Expanding, QSizePolicy.Minimum))
        self.widgets.append(w)
        self.idx_widget.stateChanged.connect(self.check_changed_checkbox)
        self.force_number.stateChanged.connect(self.check_changed_checkbox)
        self.series_start_number.valueChanged.connect(self.check_changed_checkbox)
        self.remove_series.stateChanged.connect(self.check_changed_checkbox)
        self.ignore_change_signals = False

    def check_changed_checkbox(self):
        self.a_c_checkbox.setChecked(True)

    def initialize(self, book_id):
        self.idx_widget.setChecked(False)
        self.main_widget.set_separator(None)
        self.main_widget.update_items_cache(self.all_values)
        self.main_widget.setEditText('')
        self.a_c_checkbox.setChecked(False)

    def getter(self):
        n = unicode(self.main_widget.currentText()).strip()
        i = self.idx_widget.checkState()
        f = self.force_number.checkState()
        s = self.series_start_number.value()
        r = self.remove_series.checkState()
        return n, i, f, s, r

    def commit(self, book_ids, notify=False):
        if not self.a_c_checkbox.isChecked():
            return
        val, update_indices, force_start, at_value, clear = self.gui_val
        val = None if clear else self.normalize_ui_val(val)
        if clear or val != '':
            extras = []
            for book_id in book_ids:
                if clear:
                    extras.append(None)
                    continue
                if update_indices:
                    if force_start:
                        s_index = at_value
                        at_value += 1
                    elif tweaks['series_index_auto_increment'] != 'const':
                        s_index = self.db.get_next_cc_series_num_for(val, num=self.col_id)
                    else:
                        s_index = 1.0
                else:
                    s_index = self.db.get_custom_extra(book_id, num=self.col_id,
                                                       index_is_id=True)
                extras.append(s_index)
            self.db.set_custom_bulk(book_ids, val, extras=extras,
                                   num=self.col_id, notify=notify)

class BulkEnumeration(BulkBase, Enumeration):

    def get_initial_value(self, book_ids):
        value = None
        first = True
        dialog_shown = False
        for book_id in book_ids:
            val = self.db.get_custom(book_id, num=self.col_id, index_is_id=True)
            if val and val not in self.col_metadata['display']['enum_values']:
                if not dialog_shown:
                    error_dialog(self.parent, '',
                            _('The enumeration "{0}" contains invalid values '
                              'that will not appear in the list').format(
                                                    self.col_metadata['name']),
                            show=True, show_copy_button=False)
                    dialog_shown = True
            if first:
                value = val
                first = False
            elif value != val:
                value = None
        if not value:
            self.ignore_change_signals = False
        return value

    def setup_ui(self, parent):
        self.parent = parent
        self.make_widgets(parent, QComboBox)
        vals = self.col_metadata['display']['enum_values']
        self.main_widget.blockSignals(True)
        self.main_widget.addItem('')
        self.main_widget.addItems(vals)
        self.main_widget.blockSignals(False)

    def getter(self):
        return unicode(self.main_widget.currentText())

    def setter(self, val):
        if val is None:
            self.main_widget.setCurrentIndex(0)
        else:
            self.main_widget.setCurrentIndex(self.main_widget.findText(val))
        self.ignore_change_signals = False

class RemoveTags(QWidget):

    def __init__(self, parent, values):
        QWidget.__init__(self, parent)
        layout = QHBoxLayout()
        layout.setSpacing(5)
        layout.setContentsMargins(0, 0, 0, 0)

        self.tags_box = EditWithComplete(parent)
        self.tags_box.update_items_cache(values)
        layout.addWidget(self.tags_box, stretch=3)
        self.checkbox = QCheckBox(_('Remove all tags'), parent)
        layout.addWidget(self.checkbox)
        layout.addStretch(1)
        self.setLayout(layout)
        self.connect(self.checkbox, SIGNAL('stateChanged(int)'), self.box_touched)

    def box_touched(self, state):
        if state:
            self.tags_box.setText('')
            self.tags_box.setEnabled(False)
        else:
            self.tags_box.setEnabled(True)

class BulkText(BulkBase):

    def setup_ui(self, parent):
        values = self.all_values = list(self.db.all_custom(num=self.col_id))
        values.sort(key=sort_key)
        if self.col_metadata['is_multiple']:
            self.make_widgets(parent, EditWithComplete,
                              extra_label_text=_('tags to add'))
            self.main_widget.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Preferred)
            self.adding_widget = self.main_widget

            if not self.col_metadata['display'].get('is_names', False):
                w = RemoveTags(parent, values)
                self.widgets.append(QLabel('&'+self.col_metadata['name']+': ' +
                                           _('tags to remove'), parent))
                self.widgets.append(w)
                self.removing_widget = w
                self.main_widget.set_separator(',')
                w.tags_box.textChanged.connect(self.a_c_checkbox_changed)
                w.checkbox.stateChanged.connect(self.a_c_checkbox_changed)
            else:
                self.main_widget.set_separator('&')
                self.main_widget.set_space_before_sep(True)
                self.main_widget.set_add_separator(
                                tweaks['authors_completer_append_separator'])
        else:
            self.make_widgets(parent, EditWithComplete)
            self.main_widget.set_separator(None)
            self.main_widget.setSizeAdjustPolicy(
                        self.main_widget.AdjustToMinimumContentsLengthWithIcon)
            self.main_widget.setMinimumContentsLength(25)
        self.ignore_change_signals = False

    def initialize(self, book_ids):
        self.main_widget.update_items_cache(self.all_values)
        if not self.col_metadata['is_multiple']:
            val = self.get_initial_value(book_ids)
            self.initial_val = val = self.normalize_db_val(val)
            self.main_widget.blockSignals(True)
            self.main_widget.show_initial_value(val)
            self.main_widget.blockSignals(False)

    def commit(self, book_ids, notify=False):
        if not self.a_c_checkbox.isChecked():
            return
        if self.col_metadata['is_multiple']:
            ism = self.col_metadata['multiple_seps']
            if self.col_metadata['display'].get('is_names', False):
                val = self.gui_val
                add = [v.strip() for v in val.split(ism['ui_to_list']) if v.strip()]
                self.db.set_custom_bulk(book_ids, add, num=self.col_id)
            else:
                remove_all, adding, rtext = self.gui_val
                remove = set()
                if remove_all:
                    remove = set(self.db.all_custom(num=self.col_id))
                else:
                    txt = rtext
                    if txt:
                        remove = set([v.strip() for v in txt.split(ism['ui_to_list'])])
                txt = adding
                if txt:
                    add = set([v.strip() for v in txt.split(ism['ui_to_list'])])
                else:
                    add = set()
                self.db.set_custom_bulk_multiple(book_ids, add=add,
                                            remove=remove, num=self.col_id)
        else:
            val = self.gui_val
            val = self.normalize_ui_val(val)
            self.db.set_custom_bulk(book_ids, val, num=self.col_id, notify=notify)

    def getter(self):
        if self.col_metadata['is_multiple']:
            if not self.col_metadata['display'].get('is_names', False):
                return self.removing_widget.checkbox.isChecked(), \
                        unicode(self.adding_widget.text()), \
                        unicode(self.removing_widget.tags_box.text())
            return unicode(self.adding_widget.text())
        val = unicode(self.main_widget.currentText()).strip()
        if not val:
            val = None
        return val


bulk_widgets = {
        'bool' : BulkBool,
        'rating' : BulkRating,
        'int': BulkInt,
        'float': BulkFloat,
        'datetime': BulkDateTime,
        'text' : BulkText,
        'series': BulkSeries,
        'enumeration': BulkEnumeration,
}


