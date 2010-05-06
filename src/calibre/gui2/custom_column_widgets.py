#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import sys
from functools import partial

from PyQt4.Qt import QComboBox, QLabel, QSpinBox, QDoubleSpinBox, QDateEdit, \
        QDate, QGroupBox, QVBoxLayout, QPlainTextEdit, QSizePolicy, \
        QSpacerItem, QIcon

from calibre.utils.date import qt_to_dt
from calibre.gui2.widgets import TagsLineEdit, EnComboBox
from calibre.gui2 import UNDEFINED_DATE
from calibre.utils.config import tweaks

class Base(object):

    def __init__(self, db, col_id, parent=None):
        self.db, self.col_id = db, col_id
        self.col_metadata = db.custom_column_num_map[col_id]
        self.initial_val = None
        self.setup_ui(parent)

    def initialize(self, book_id):
        val = self.db.get_custom(book_id, num=self.col_id, index_is_id=True)
        self.initial_val = val
        val = self.normalize_db_val(val)
        self.setter(val)

    def commit(self, book_id, notify=False):
        val = self.getter()
        val = self.normalize_ui_val(val)
        if val != self.initial_val:
            self.db.set_custom(book_id, val, num=self.col_id, notify=notify)

    def normalize_db_val(self, val):
        return val

    def normalize_ui_val(self, val):
        return val

class Bool(Base):

    def setup_ui(self, parent):
        self.widgets = [QLabel('&'+self.col_metadata['name'], parent),
                QComboBox(parent)]
        w = self.widgets[1]
        items = [_('Yes'), _('No'), _('Undefined')]
        icons = [I('ok.svg'), I('list_remove.svg'), I('blank.svg')]
        if tweaks['bool_custom_columns_are_tristate'] == 'no':
            items = items[:-1]
            icons = icons[:-1]
        for icon, text in zip(icons, items):
            w.addItem(QIcon(icon), text)


    def setter(self, val):
        val = {None: 2, False: 1, True: 0}[val]
        if tweaks['bool_custom_columns_are_tristate'] == 'no' and val == 2:
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
        w.setRange(-100, sys.maxint)
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
        w.setRange(-100., float(sys.maxint))
        w.setDecimals(2)
        w.setSpecialValueText(_('Undefined'))
        w.setSingleStep(1)

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

class DateTime(Base):

    def setup_ui(self, parent):
        self.widgets = [QLabel('&'+self.col_metadata['name']+':', parent),
                QDateEdit(parent)]
        w = self.widgets[1]
        w.setDisplayFormat('dd MMM yyyy')
        w.setCalendarPopup(True)
        w.setMinimumDate(UNDEFINED_DATE)
        w.setSpecialValueText(_('Undefined'))

    def setter(self, val):
        if val is None:
            val = self.widgets[1].minimumDate()
        else:
            val = QDate(val.year, val.month, val.day)
        self.widgets[1].setDate(val)

    def getter(self):
        val = self.widgets[1].date()
        if val == UNDEFINED_DATE:
            val = None
        else:
            val = qt_to_dt(val)
        return val


class Comments(Base):

    def setup_ui(self, parent):
        self._box = QGroupBox(parent)
        self._box.setTitle('&'+self.col_metadata['name'])
        self._layout = QVBoxLayout()
        self._tb = QPlainTextEdit(self._box)
        self._tb.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        self._tb.setTabChangesFocus(True)
        self._layout.addWidget(self._tb)
        self._box.setLayout(self._layout)
        self.widgets = [self._box]

    def setter(self, val):
        if val is None:
            val = ''
        self._tb.setPlainText(val)

    def getter(self):
        val = unicode(self._tb.toPlainText()).strip()
        if not val:
            val = None
        return val

class Text(Base):

    def setup_ui(self, parent):
        values = self.all_values = list(self.db.all_custom(num=self.col_id))
        values.sort(cmp = lambda x,y: cmp(x.lower(), y.lower()))
        if self.col_metadata['is_multiple']:
            w = TagsLineEdit(parent, values)
            w.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Preferred)
        else:
            w = EnComboBox(parent)
            w.setSizeAdjustPolicy(w.AdjustToMinimumContentsLengthWithIcon)
            w.setMinimumContentsLength(25)



        self.widgets = [QLabel('&'+self.col_metadata['name']+':', parent),
                w]

    def initialize(self, book_id):
        val = self.db.get_custom(book_id, num=self.col_id, index_is_id=True)
        self.initial_val = val
        val = self.normalize_db_val(val)
        if self.col_metadata['is_multiple']:
            self.setter(val)
            self.widgets[1].update_tags_cache(self.all_values)
        else:
            idx = None
            for i, c in enumerate(self.all_values):
                if c == val:
                    idx = i
                self.widgets[1].addItem(c)
            self.widgets[1].setEditText('')
            if idx is not None:
                self.widgets[1].setCurrentIndex(idx)


    def setter(self, val):
        if self.col_metadata['is_multiple']:
            if not val:
                val = []
            self.widgets[1].setText(u', '.join(val))

    def getter(self):
        if self.col_metadata['is_multiple']:
            val = unicode(self.widgets[1].text()).strip()
            ans = [x.strip() for x in val.split(',') if x.strip()]
            if not ans:
                ans = None
            return ans
        val = unicode(self.widgets[1].currentText()).strip()
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
}

def field_sort(y, z, x=None):
    m1, m2 = x[y], x[z]
    n1 = 'zzzzz' if m1['datatype'] == 'comments' else m1['name']
    n2 = 'zzzzz' if m2['datatype'] == 'comments' else m2['name']
    return cmp(n1.lower(), n2.lower())

def populate_single_metadata_page(left, right, db, book_id, parent=None):
    x = db.custom_column_num_map
    cols = list(x)
    cols.sort(cmp=partial(field_sort, x=x))
    ans = []
    for i, col in enumerate(cols):
        w = widgets[x[col]['datatype']](db, col, parent)
        ans.append(w)
        w.initialize(book_id)
        layout = left if i%2 == 0 else right
        row = layout.rowCount()
        if len(w.widgets) == 1:
            layout.addWidget(w.widgets[0], row, 0, 1, -1)
        else:
            w.widgets[0].setBuddy(w.widgets[1])
            for c, widget in enumerate(w.widgets):
                layout.addWidget(widget, row, c)
    items = []
    if len(ans) > 0:
        items.append(QSpacerItem(10, 10, QSizePolicy.Minimum,
            QSizePolicy.Expanding))
        left.addItem(items[-1], left.rowCount(), 0, 1, 1)
        left.setRowStretch(left.rowCount()-1, 100)
    if len(ans) > 1:
         items.append(QSpacerItem(10, 100, QSizePolicy.Minimum,
             QSizePolicy.Expanding))
         right.addItem(items[-1], left.rowCount(), 0, 1, 1)
         right.setRowStretch(right.rowCount()-1, 100)

    return ans, items

class BulkBase(Base):

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
        val = self.getter()
        val = self.normalize_ui_val(val)
        if val != self.initial_val:
            for book_id in book_ids:
                self.db.set_custom(book_id, val, num=self.col_id, notify=notify)

class BulkBool(BulkBase, Bool):
    pass

class BulkInt(BulkBase, Int):
    pass

class BulkFloat(BulkBase, Float):
    pass

class BulkRating(BulkBase, Rating):
    pass

class BulkDateTime(BulkBase, DateTime):
    pass

class BulkText(BulkBase, Text):

    def initialize(self, book_ids):
        val = self.get_initial_value(book_ids)
        self.initial_val = val = self.normalize_db_val(val)
        if self.col_metadata['is_multiple']:
            self.setter(val)
            self.widgets[1].update_tags_cache(self.all_values)
        else:
            idx = None
            for i, c in enumerate(self.all_values):
                if c == val:
                    idx = i
                self.widgets[1].addItem(c)
            self.widgets[1].setEditText('')
            if idx is not None:
                self.widgets[1].setCurrentIndex(idx)


bulk_widgets = {
        'bool' : BulkBool,
        'rating' : BulkRating,
        'int': BulkInt,
        'float': BulkFloat,
        'datetime': BulkDateTime,
        'text' : BulkText,
}

def populate_bulk_metadata_page(layout, db, book_ids, parent=None):
    x = db.custom_column_num_map
    cols = list(x)
    cols.sort(cmp=partial(field_sort, x=x))
    ans = []
    for i, col in enumerate(cols):
        dt = x[col]['datatype']
        if dt == 'comments':
            continue
        w = bulk_widgets[dt](db, col, parent)
        ans.append(w)
        w.initialize(book_ids)
        row = layout.rowCount()
        if len(w.widgets) == 1:
            layout.addWidget(w.widgets[0], row, 0, 1, -1)
        else:
            w.widgets[0].setBuddy(w.widgets[1])
            for c, widget in enumerate(w.widgets):
                layout.addWidget(widget, row, c)
    items = []
    if len(ans) > 0:
        items.append(QSpacerItem(10, 10, QSizePolicy.Minimum,
            QSizePolicy.Expanding))
        layout.addItem(items[-1], layout.rowCount(), 0, 1, 1)
        layout.setRowStretch(layout.rowCount()-1, 100)

    return ans, items

