#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

import json, copy
from functools import partial
from collections import OrderedDict

from PyQt4.Qt import (
    QWidget, QToolBar, Qt, QHBoxLayout, QSize, QIcon, QGridLayout, QLabel, QTimer,
    QPushButton, pyqtSignal, QComboBox, QCheckBox, QSizePolicy, QVBoxLayout, QFont,
    QLineEdit, QToolButton, QListView, QFrame, QApplication, QStyledItemDelegate,
    QAbstractListModel, QVariant, QFormLayout, QModelIndex, QMenu, QItemSelection)

import regex

from calibre import prepare_string_for_xml
from calibre.gui2 import NONE, error_dialog, info_dialog, choose_files, choose_save_file
from calibre.gui2.dialogs.message_box import MessageBox
from calibre.gui2.widgets2 import HistoryComboBox
from calibre.gui2.tweak_book import tprefs, editors, current_container
from calibre.gui2.tweak_book.widgets import Dialog, BusyCursor

from calibre.utils.icu import primary_contains

REGEX_FLAGS = regex.VERSION1 | regex.WORD | regex.FULLCASE | regex.MULTILINE | regex.UNICODE

# The search panel {{{

class PushButton(QPushButton):

    def __init__(self, text, action, parent):
        QPushButton.__init__(self, text, parent)
        self.clicked.connect(lambda : parent.search_triggered.emit(action))

class HistoryBox(HistoryComboBox):

    max_history_items = 100
    save_search = pyqtSignal()
    show_saved_searches = pyqtSignal()

    def __init__(self, parent, clear_msg):
        HistoryComboBox.__init__(self, parent)
        self.disable_popup = tprefs['disable_completion_popup_for_search']
        self.clear_msg = clear_msg

    def contextMenuEvent(self, event):
        menu = self.lineEdit().createStandardContextMenu()
        menu.addSeparator()
        menu.addAction(self.clear_msg, self.clear_history)
        menu.addAction((_('Enable completion based on search history') if self.disable_popup else _(
            'Disable completion based on search history')), self.toggle_popups)
        menu.addSeparator()
        menu.addAction(_('Save current search'), self.save_search.emit)
        menu.addAction(_('Show saved searches'), self.show_saved_searches.emit)
        menu.exec_(event.globalPos())

    def toggle_popups(self):
        self.disable_popup = not bool(self.disable_popup)
        tprefs['disable_completion_popup_for_search'] = self.disable_popup

class WhereBox(QComboBox):

    def __init__(self, parent, emphasize=False):
        QComboBox.__init__(self)
        self.addItems([_('Current file'), _('All text files'), _('All style files'), _('Selected files'), _('Marked text')])
        self.setToolTip('<style>dd {margin-bottom: 1.5ex}</style>' + _(
            '''
            Where to search/replace:
            <dl>
            <dt><b>Current file</b></dt>
            <dd>Search only inside the currently opened file</dd>
            <dt><b>All text files</b></dt>
            <dd>Search in all text (HTML) files</dd>
            <dt><b>All style files</b></dt>
            <dd>Search in all style (CSS) files</dd>
            <dt><b>Selected files</b></dt>
            <dd>Search in the files currently selected in the Files Browser</dd>
            <dt><b>Marked text</b></dt>
            <dd>Search only within the marked text in the currently opened file. You can mark text using the Search menu.</dd>
            </dl>'''))
        self.emphasize = emphasize
        self.ofont = QFont(self.font())
        if emphasize:
            f = self.emph_font = QFont(self.ofont)
            f.setBold(True), f.setItalic(True)
            self.setFont(f)

    @dynamic_property
    def where(self):
        wm = {0:'current', 1:'text', 2:'styles', 3:'selected', 4:'selected-text'}
        def fget(self):
            return wm[self.currentIndex()]
        def fset(self, val):
            self.setCurrentIndex({v:k for k, v in wm.iteritems()}[val])
        return property(fget=fget, fset=fset)

    def showPopup(self):
        # We do it like this so that the popup uses a normal font
        if self.emphasize:
            self.setFont(self.ofont)
        QComboBox.showPopup(self)

    def hidePopup(self):
        if self.emphasize:
            self.setFont(self.emph_font)
        QComboBox.hidePopup(self)

class DirectionBox(QComboBox):

    def __init__(self, parent):
        QComboBox.__init__(self, parent)
        self.addItems([_('Down'), _('Up')])
        self.setToolTip('<style>dd {margin-bottom: 1.5ex}</style>' + _(
            '''
            Direction to search:
            <dl>
            <dt><b>Down</b></dt>
            <dd>Search for the next match from your current position</dd>
            <dt><b>Up</b></dt>
            <dd>Search for the previous match from your current position</dd>
            </dl>'''))

    @dynamic_property
    def direction(self):
        def fget(self):
            return 'down' if self.currentIndex() == 0 else 'up'
        def fset(self, val):
            self.setCurrentIndex(1 if val == 'up' else 0)
        return property(fget=fget, fset=fset)

class ModeBox(QComboBox):

    def __init__(self, parent):
        QComboBox.__init__(self, parent)
        self.addItems([_('Normal'), _('Regex')])
        self.setToolTip('<style>dd {margin-bottom: 1.5ex}</style>' + _(
            '''Select how the search expression is interpreted
            <dl>
            <dt><b>Normal</b></dt>
            <dd>The search expression is treated as normal text, calibre will look for the exact text.</dd>
            <dt><b>Regex</b></dt>
            <dd>The search expression is interpreted as a regular expression. See the User Manual for more help on using regular expressions.</dd>
            </dl>'''))

    @dynamic_property
    def mode(self):
        def fget(self):
            return 'normal' if self.currentIndex() == 0 else 'regex'
        def fset(self, val):
            self.setCurrentIndex({'regex':1}.get(val, 0))
        return property(fget=fget, fset=fset)


class SearchWidget(QWidget):

    DEFAULT_STATE = {
        'mode': 'normal',
        'where': 'current',
        'case_sensitive': False,
        'direction': 'down',
        'wrap': True,
        'dot_all': False,
    }

    search_triggered = pyqtSignal(object)
    save_search = pyqtSignal()
    show_saved_searches = pyqtSignal()

    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.l = l = QGridLayout(self)
        l.setContentsMargins(0, 0, 0, 0)
        self.setLayout(l)

        self.fl = fl = QLabel(_('&Find:'))
        fl.setAlignment(Qt.AlignRight | Qt.AlignCenter)
        self.find_text = ft = HistoryBox(self, _('Clear search history'))
        ft.save_search.connect(self.save_search)
        ft.show_saved_searches.connect(self.show_saved_searches)
        ft.initialize('tweak_book_find_edit')
        ft.lineEdit().returnPressed.connect(lambda : self.search_triggered.emit('find'))
        fl.setBuddy(ft)
        l.addWidget(fl, 0, 0)
        l.addWidget(ft, 0, 1)

        self.rl = rl = QLabel(_('&Replace:'))
        rl.setAlignment(Qt.AlignRight | Qt.AlignCenter)
        self.replace_text = rt = HistoryBox(self, _('Clear replace history'))
        rt.save_search.connect(self.save_search)
        rt.show_saved_searches.connect(self.show_saved_searches)
        rt.initialize('tweak_book_replace_edit')
        rl.setBuddy(rt)
        l.addWidget(rl, 1, 0)
        l.addWidget(rt, 1, 1)
        l.setColumnStretch(1, 10)

        self.fb = fb = PushButton(_('&Find'), 'find', self)
        self.rfb = rfb = PushButton(_('Replace a&nd Find'), 'replace-find', self)
        self.rb = rb = PushButton(_('&Replace'), 'replace', self)
        self.rab = rab = PushButton(_('Replace &all'), 'replace-all', self)
        l.addWidget(fb, 0, 2)
        l.addWidget(rfb, 0, 3)
        l.addWidget(rb, 1, 2)
        l.addWidget(rab, 1, 3)

        self.ml = ml = QLabel(_('&Mode:'))
        self.ol = ol = QHBoxLayout()
        ml.setAlignment(Qt.AlignRight | Qt.AlignCenter)
        l.addWidget(ml, 2, 0)
        l.addLayout(ol, 2, 1, 1, 3)
        self.mode_box = mb = ModeBox(self)
        mb.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Maximum)
        ml.setBuddy(mb)
        ol.addWidget(mb)

        self.where_box = wb = WhereBox(self)
        wb.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
        ol.addWidget(wb)

        self.direction_box = db = DirectionBox(self)
        db.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Maximum)
        ol.addWidget(db)

        self.cs = cs = QCheckBox(_('&Case sensitive'))
        cs.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Maximum)
        ol.addWidget(cs)

        self.wr = wr = QCheckBox(_('&Wrap'))
        wr.setToolTip('<p>'+_('When searching reaches the end, wrap around to the beginning and continue the search'))
        wr.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Maximum)
        ol.addWidget(wr)

        self.da = da = QCheckBox(_('&Dot all'))
        da.setToolTip('<p>'+_("Make the '.' special character match any character at all, including a newline"))
        da.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Maximum)
        ol.addWidget(da)

        self.mode_box.currentIndexChanged[int].connect(self.da.setVisible)

        ol.addStretch(10)

    @dynamic_property
    def mode(self):
        def fget(self):
            return self.mode_box.mode
        def fset(self, val):
            self.mode_box.mode = val
            self.da.setVisible(self.mode == 'regex')
        return property(fget=fget, fset=fset)

    @dynamic_property
    def find(self):
        def fget(self):
            return unicode(self.find_text.text())
        def fset(self, val):
            self.find_text.setText(val)
        return property(fget=fget, fset=fset)

    @dynamic_property
    def replace(self):
        def fget(self):
            return unicode(self.replace_text.text())
        def fset(self, val):
            self.replace_text.setText(val)
        return property(fget=fget, fset=fset)

    @dynamic_property
    def where(self):
        def fget(self):
            return self.where_box.where
        def fset(self, val):
            self.where_box.where = val
        return property(fget=fget, fset=fset)

    @dynamic_property
    def case_sensitive(self):
        def fget(self):
            return self.cs.isChecked()
        def fset(self, val):
            self.cs.setChecked(bool(val))
        return property(fget=fget, fset=fset)

    @dynamic_property
    def direction(self):
        def fget(self):
            return self.direction_box.direction
        def fset(self, val):
            self.direction_box.direction = val
        return property(fget=fget, fset=fset)

    @dynamic_property
    def wrap(self):
        def fget(self):
            return self.wr.isChecked()
        def fset(self, val):
            self.wr.setChecked(bool(val))
        return property(fget=fget, fset=fset)

    @dynamic_property
    def dot_all(self):
        def fget(self):
            return self.da.isChecked()
        def fset(self, val):
            self.da.setChecked(bool(val))
        return property(fget=fget, fset=fset)

    @dynamic_property
    def state(self):
        def fget(self):
            return {x:getattr(self, x) for x in self.DEFAULT_STATE}
        def fset(self, val):
            for x in self.DEFAULT_STATE:
                if x in val:
                    setattr(self, x, val[x])
        return property(fget=fget, fset=fset)

    def restore_state(self):
        self.state = tprefs.get('find-widget-state', self.DEFAULT_STATE)
        if self.where == 'selected-text':
            self.where = self.DEFAULT_STATE['where']

    def save_state(self):
        tprefs.set('find-widget-state', self.state)

    def pre_fill(self, text):
        if self.mode == 'regex':
            text = regex.escape(text, special_only=True)
        self.find = text
        self.find_text.lineEdit().setSelection(0, len(text)+10)

# }}}

regex_cache = {}

class SearchPanel(QWidget):  # {{{

    search_triggered = pyqtSignal(object)
    save_search = pyqtSignal()
    show_saved_searches = pyqtSignal()

    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.l = l = QHBoxLayout()
        self.setLayout(l)
        l.setContentsMargins(0, 0, 0, 0)
        self.t = t = QToolBar(self)
        l.addWidget(t)
        t.setOrientation(Qt.Vertical)
        t.setIconSize(QSize(12, 12))
        t.setMovable(False)
        t.setFloatable(False)
        t.cl = ac = t.addAction(QIcon(I('window-close.png')), _('Close search panel'))
        ac.triggered.connect(self.hide_panel)
        self.widget = SearchWidget(self)
        l.addWidget(self.widget)
        self.restore_state, self.save_state = self.widget.restore_state, self.widget.save_state
        self.widget.search_triggered.connect(self.search_triggered)
        self.widget.save_search.connect(self.save_search)
        self.widget.show_saved_searches.connect(self.show_saved_searches)
        self.pre_fill = self.widget.pre_fill

    def hide_panel(self):
        self.setVisible(False)

    def show_panel(self):
        self.setVisible(True)
        self.widget.find_text.setFocus(Qt.OtherFocusReason)

    @property
    def state(self):
        ans = self.widget.state
        ans['find'] = self.widget.find
        ans['replace'] = self.widget.replace
        return ans

    def set_where(self, val):
        self.widget.where = val

    def keyPressEvent(self, ev):
        if ev.key() == Qt.Key_Escape:
            self.hide_panel()
            ev.accept()
        else:
            return QWidget.keyPressEvent(self, ev)
# }}}

class SearchesModel(QAbstractListModel):

    def __init__(self, parent):
        QAbstractListModel.__init__(self, parent)
        self.searches = tprefs['saved_searches']
        self.filtered_searches = list(xrange(len(self.searches)))

    def rowCount(self, parent=QModelIndex()):
        return len(self.filtered_searches)

    def data(self, index, role):
        try:
            if role == Qt.DisplayRole:
                search = self.searches[self.filtered_searches[index.row()]]
                return QVariant(search['name'])
            if role == Qt.ToolTipRole:
                search = self.searches[self.filtered_searches[index.row()]]
                tt = '\n'.join((search['find'], search['replace']))
                return QVariant(tt)
            if role == Qt.UserRole:
                search = self.searches[self.filtered_searches[index.row()]]
                return QVariant((self.filtered_searches[index.row()], search))
        except IndexError:
            pass
        return NONE

    def do_filter(self, text):
        text = unicode(text)
        self.filtered_searches = []
        for i, search in enumerate(self.searches):
            if primary_contains(text, search['name']):
                self.filtered_searches.append(i)
        self.reset()

    def move_entry(self, row, delta):
        a, b = row, row + delta
        if 0 <= b < len(self.filtered_searches):
            ai, bi = self.filtered_searches[a], self.filtered_searches[b]
            self.searches[ai], self.searches[bi] = self.searches[bi], self.searches[ai]
            self.dataChanged.emit(self.index(a), self.index(a))
            self.dataChanged.emit(self.index(b), self.index(b))
            tprefs['saved_searches'] = self.searches

    def add_searches(self, count=1):
        self.searches = tprefs['saved_searches']
        self.filtered_searches.extend(xrange(len(self.searches) - 1, len(self.searches) - 1 - count, -1))
        self.reset()

    def remove_searches(self, rows):
        rows = sorted(set(rows), reverse=True)
        indices = [self.filtered_searches[row] for row in rows]
        for row in rows:
            self.beginRemoveRows(QModelIndex(), row, row)
            del self.filtered_searches[row]
            self.endRemoveRows()
        for idx in sorted(indices, reverse=True):
            del self.searches[idx]
        tprefs['saved_searches'] = self.searches

class EditSearch(Dialog):  # {{{

    def __init__(self, search=None, search_index=-1, parent=None, state=None):
        self.search = search or {}
        self.original_name = self.search.get('name', None)
        self.search_index = search_index
        Dialog.__init__(self, _('Edit search'), 'edit-saved-search', parent=parent)
        if state is not None:
            self.find.setText(state['find'])
            self.replace.setText(state['replace'])
            self.case_sensitive.setChecked(state['case_sensitive'])
            self.dot_all.setChecked(state['dot_all'])
            self.mode_box.mode = state.get('mode')

    def sizeHint(self):
        ans = Dialog.sizeHint(self)
        ans.setWidth(600)
        return ans

    def setup_ui(self):
        self.l = l = QFormLayout(self)
        self.setLayout(l)

        self.search_name = n = QLineEdit(self.search.get('name', ''), self)
        n.setPlaceholderText(_('The name with which to save this search'))
        l.addRow(_('&Name:'), n)

        self.find = f = QLineEdit(self.search.get('find', ''), self)
        f.setPlaceholderText(_('The expression to search for'))
        l.addRow(_('&Find:'), f)

        self.replace = r = QLineEdit(self.search.get('replace', ''), self)
        r.setPlaceholderText(_('The replace expression'))
        l.addRow(_('&Replace:'), r)

        self.case_sensitive = c = QCheckBox(_('Case sensitive'))
        c.setChecked(self.search.get('case_sensitive', SearchWidget.DEFAULT_STATE['case_sensitive']))
        l.addRow(c)

        self.dot_all = d = QCheckBox(_('Dot matches all'))
        d.setChecked(self.search.get('dot_all', SearchWidget.DEFAULT_STATE['dot_all']))
        l.addRow(d)

        self.mode_box = m = ModeBox(self)
        self.mode_box.mode = self.search.get('mode', 'regex')
        l.addRow(_('&Mode:'), m)

        l.addRow(self.bb)

    def accept(self):
        searches = tprefs['saved_searches']
        all_names = {x['name'] for x in searches} - {self.original_name}
        n = unicode(self.search_name.text()).strip()
        search = self.search
        if not n:
            return error_dialog(self, _('Must specify name'), _(
                'You must specify a search name'), show=True)
        if n in all_names:
            return error_dialog(self, _('Name exists'), _(
                'Another search with the name %s already exists') % n, show=True)
        search['name'] = n

        f = unicode(self.find.text())
        if not f:
            return error_dialog(self, _('Must specify find'), _(
                'You must specify a find expression'), show=True)
        search['find'] = f

        r = unicode(self.replace.text())
        search['replace'] = r

        search['dot_all'] = bool(self.dot_all.isChecked())
        search['case_sensitive'] = bool(self.case_sensitive.isChecked())
        search['mode'] = self.mode_box.mode

        if self.search_index == -1:
            searches.append(search)
        else:
            searches[self.search_index] = search
        tprefs.set('saved_searches', searches)

        Dialog.accept(self)
# }}}

class SearchDelegate(QStyledItemDelegate):

    def sizeHint(self, *args):
        ans = QStyledItemDelegate.sizeHint(self, *args)
        ans.setHeight(ans.height() + 4)
        return ans

class SavedSearches(Dialog):

    run_saved_searches = pyqtSignal(object, object)

    def __init__(self, parent=None):
        Dialog.__init__(self, _('Saved Searches'), 'saved-searches', parent=parent)

    def sizeHint(self):
        return QSize(800, 675)

    def setup_ui(self):
        self.l = l = QVBoxLayout(self)
        self.setLayout(l)

        self.h = h = QHBoxLayout()
        self.filter_text = ft = QLineEdit(self)
        ft.textChanged.connect(self.do_filter)
        ft.setPlaceholderText(_('Filter displayed searches'))
        h.addWidget(ft)
        self.cft = cft = QToolButton(self)
        cft.setToolTip(_('Clear filter')), cft.setIcon(QIcon(I('clear_left.png')))
        cft.clicked.connect(ft.clear)
        h.addWidget(cft)
        l.addLayout(h)

        self.h2 = h = QHBoxLayout()
        self.searches = searches = QListView(self)
        searches.doubleClicked.connect(self.edit_search)
        self.model = SearchesModel(self.searches)
        self.model.dataChanged.connect(self.show_details)
        searches.setModel(self.model)
        searches.selectionModel().currentChanged.connect(self.show_details)
        searches.setSelectionMode(searches.ExtendedSelection)
        self.delegate = SearchDelegate(searches)
        searches.setItemDelegate(self.delegate)
        searches.setAlternatingRowColors(True)
        h.addWidget(searches, stretch=10)
        self.v = v = QVBoxLayout()
        h.addLayout(v)
        l.addLayout(h)

        def pb(text, tooltip=None):
            b = QPushButton(text, self)
            b.setToolTip(tooltip or '')
            b.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
            return b

        mulmsg = '\n\n' + _('The entries are tried in order until the first one matches.')

        for text, action, tooltip in [
                (_('&Find'), 'find', _('Run the search using the selected entries.') + mulmsg),
                (_('&Replace'), 'replace', _('Run replace using the selected entries.') + mulmsg),
                (_('Replace a&nd Find'), 'replace-find', _('Run replace and then find using the selected entries.') + mulmsg),
                (_('Replace &all'), 'replace-all', _('Run Replace All for all selected entries in the order selected')),
                (_('&Count all'), 'count', _('Run Count All for all selected entries')),
        ]:
            b = pb(text, tooltip)
            v.addWidget(b)
            b.clicked.connect(partial(self.run_search, action))

        self.d1 = d = QFrame(self)
        d.setFrameStyle(QFrame.HLine)
        v.addWidget(d)

        self.h3 = h = QHBoxLayout()
        self.upb = b = QToolButton(self)
        b.setIcon(QIcon(I('arrow-up.png'))), b.setToolTip(_('Move selected entries up'))
        b.clicked.connect(partial(self.move_entry, -1))
        self.dnb = b = QToolButton(self)
        b.setIcon(QIcon(I('arrow-down.png'))), b.setToolTip(_('Move selected entries down'))
        b.clicked.connect(partial(self.move_entry, 1))
        h.addWidget(self.upb), h.addWidget(self.dnb)
        v.addLayout(h)

        self.eb = b = pb(_('&Edit search'), _('Edit the currently selected search'))
        b.clicked.connect(self.edit_search)
        v.addWidget(b)

        self.eb = b = pb(_('Re&move search'), _('Remove the currently selected searches'))
        b.clicked.connect(self.remove_search)
        v.addWidget(b)

        self.eb = b = pb(_('&Add search'), _('Add a new saved search'))
        b.clicked.connect(self.add_search)
        v.addWidget(b)

        self.d2 = d = QFrame(self)
        d.setFrameStyle(QFrame.HLine)
        v.addWidget(d)

        self.where_box = wb = WhereBox(self, emphasize=True)
        self.where = SearchWidget.DEFAULT_STATE['where']
        v.addWidget(wb)
        self.direction_box = db = DirectionBox(self)
        self.direction = SearchWidget.DEFAULT_STATE['direction']
        v.addWidget(db)

        self.wr = wr = QCheckBox(_('&Wrap'))
        wr.setToolTip('<p>'+_('When searching reaches the end, wrap around to the beginning and continue the search'))
        self.wr.setChecked(SearchWidget.DEFAULT_STATE['wrap'])
        v.addWidget(wr)

        self.description = d = QLabel(' \n \n ')
        d.setTextFormat(Qt.PlainText)
        l.addWidget(d)

        l.addWidget(self.bb)
        self.bb.clear()
        self.bb.addButton(self.bb.Close)
        self.ib = b = self.bb.addButton(_('&Import'), self.bb.ActionRole)
        b.clicked.connect(self.import_searches)
        self.eb = b = self.bb.addButton(_('E&xport'), self.bb.ActionRole)
        self.em = m = QMenu(_('Export'))
        m.addAction(_('Export All'), lambda : QTimer.singleShot(0, partial(self.export_searches, all=True)))
        m.addAction(_('Export Selected'), lambda : QTimer.singleShot(0, partial(self.export_searches, all=False)))
        b.setMenu(m)

        self.searches.setFocus(Qt.OtherFocusReason)

    @dynamic_property
    def where(self):
        def fget(self):
            return self.where_box.where
        def fset(self, val):
            self.where_box.where = val
        return property(fget=fget, fset=fset)

    @dynamic_property
    def direction(self):
        def fget(self):
            return self.direction_box.direction
        def fset(self, val):
            self.direction_box.direction = val
        return property(fget=fget, fset=fset)

    @dynamic_property
    def wrap(self):
        def fget(self):
            return self.wr.isChecked()
        def fset(self, val):
            self.wr.setChecked(bool(val))
        return property(fget=fget, fset=fset)

    def do_filter(self, text):
        self.model.do_filter(text)
        self.searches.scrollTo(self.model.index(0))

    def run_search(self, action):
        searches, seen = [], set()
        for index in self.searches.selectionModel().selectedIndexes():
            if index.row() in seen:
                continue
            seen.add(index.row())
            search = SearchWidget.DEFAULT_STATE.copy()
            del search['mode']
            search_index, s = index.data(Qt.UserRole).toPyObject()
            search.update(s)
            search['wrap'] = self.wrap
            search['direction'] = self.direction
            search['where'] = self.where
            search['mode'] = search.get('mode', 'regex')
            searches.append(search)
        if not searches:
            return
        self.run_saved_searches.emit(searches, action)

    def move_entry(self, delta):
        rows = {index.row() for index in self.searches.selectionModel().selectedIndexes()} - {-1}
        if rows:
            with tprefs:
                for row in sorted(rows, reverse=delta > 0):
                    self.model.move_entry(row, delta)
            nrow = row + delta
            index = self.model.index(nrow)
            if index.isValid():
                sm = self.searches.selectionModel()
                sm.setCurrentIndex(index, sm.ClearAndSelect)

    def edit_search(self):
        index = self.searches.currentIndex()
        if index.isValid():
            search_index, search = index.data(Qt.UserRole).toPyObject()
            d = EditSearch(search=search, search_index=search_index, parent=self)
            if d.exec_() == d.Accepted:
                self.model.dataChanged.emit(index, index)

    def remove_search(self):
        rows = {index.row() for index in self.searches.selectionModel().selectedIndexes()} - {-1}
        self.model.remove_searches(rows)
        self.show_details()

    def add_search(self):
        d = EditSearch(parent=self)
        self._add_search(d)

    def _add_search(self, d):
        if d.exec_() == d.Accepted:
            self.model.add_searches()
            index = self.model.index(self.model.rowCount() - 1)
            self.searches.scrollTo(index)
            sm = self.searches.selectionModel()
            sm.setCurrentIndex(index, sm.ClearAndSelect)
            self.show_details()

    def add_predefined_search(self, state):
        d = EditSearch(parent=self, state=state)
        self._add_search(d)

    def show_details(self):
        self.description.setText(' \n \n ')
        i = self.searches.currentIndex()
        if i.isValid():
            search_index, search = i.data(Qt.UserRole).toPyObject()
            cs = '✓' if search.get('case_sensitive', SearchWidget.DEFAULT_STATE['case_sensitive']) else '✗'
            da = '✓' if search.get('dot_all', SearchWidget.DEFAULT_STATE['dot_all']) else '✗'
            if search.get('mode', SearchWidget.DEFAULT_STATE['mode']) == 'regex':
                ts = _('(Case sensitive: {0} Dot All: {1})').format(cs, da)
            else:
                ts = _('(Case sensitive: {0} [Normal search])').format(cs)
            self.description.setText(_('{2} {3}\nFind: {0}\nReplace: {1}').format(
                search.get('find', ''), search.get('replace', ''), search.get('name', ''), ts))

    def import_searches(self):
        path = choose_files(self, 'import_saved_searches', _('Choose file'), filters=[
            (_('Saved Searches'), ['json'])], all_files=False, select_only_single_file=True)
        if path:
            with open(path[0], 'rb') as f:
                obj = json.loads(f.read())
            needed_keys = {'name', 'find', 'replace', 'case_sensitive', 'dot_all', 'mode'}
            def err():
                error_dialog(self, _('Invalid data'), _(
                    'The file %s does not contain valid saved searches') % path, show=True)
            if not isinstance(obj, dict) or 'version' not in obj or 'searches' not in obj or obj['version'] not in (1,):
                return err()
            searches = []
            for item in obj['searches']:
                if not isinstance(item, dict) or not set(item.iterkeys()).issuperset(needed_keys):
                    return err
                searches.append({k:item[k] for k in needed_keys})

            if searches:
                tprefs['saved_searches'] = tprefs['saved_searches'] + searches
                count = len(searches)
                self.model.add_searches(count=count)
                sm = self.searches.selectionModel()
                top, bottom = self.model.index(self.model.rowCount() - count), self.model.index(self.model.rowCount() - 1)
                sm.select(QItemSelection(top, bottom), sm.ClearAndSelect)
                self.searches.scrollTo(bottom)

    def export_searches(self, all=True):
        if all:
            searches = copy.deepcopy(tprefs['saved_searches'])
            if not searches:
                return error_dialog(self, _('No searches'), _(
                    'No searches available to be saved'), show=True)
        else:
            searches = []
            for index in self.searches.selectionModel().selectedIndexes():
                search = index.data(Qt.UserRole).toPyObject()[-1]
                searches.append(search.copy())
            if not searches:
                return error_dialog(self, _('No searches'), _(
                    'No searches selected'), show=True)
        [s.__setitem__('mode', s.get('mode', 'regex')) for s in searches]
        path = choose_save_file(self, 'export-saved-searches', _('Choose file'), filters=[
            (_('Saved Searches'), ['json'])], all_files=False)
        if path:
            if not path.lower().endswith('.json'):
                path += '.json'
            raw = json.dumps({'version':1, 'searches':searches}, ensure_ascii=False, indent=2, sort_keys=True)
            with open(path, 'wb') as f:
                f.write(raw.encode('utf-8'))

def validate_search_request(name, searchable_names, has_marked_text, state, gui_parent):
    err = None
    where = state['where']
    if name is None and where in {'current', 'selected-text'}:
        err = _('No file is being edited.')
    elif where == 'selected' and not searchable_names['selected']:
        err = _('No files are selected in the Files Browser')
    elif where == 'selected-text' and not has_marked_text:
        err = _('No text is marked. First select some text, and then use'
                ' The "Mark selected text" action in the Search menu to mark it.')
    if not err and not state['find']:
        err = _('No search query specified')
    if err:
        error_dialog(gui_parent, _('Cannot search'), err, show=True)
        return False
    return True

class InvalidRegex(regex.error):

    def __init__(self, raw, e):
        regex.error.__init__(self, e.message)
        self.regex = raw

def get_search_regex(state):
    raw = state['find']
    if state['mode'] != 'regex':
        raw = regex.escape(raw, special_only=True)
    flags = REGEX_FLAGS
    if not state['case_sensitive']:
        flags |= regex.IGNORECASE
    if state['mode'] == 'regex' and state['dot_all']:
        flags |= regex.DOTALL
    if state['direction'] == 'up':
        flags |= regex.REVERSE
    ans = regex_cache.get((flags, raw), None)
    if ans is None:
        try:
            ans = regex_cache[(flags, raw)] = regex.compile(raw, flags=flags)
        except regex.error as e:
            raise InvalidRegex(raw, e)

    return ans

def initialize_search_request(state, action, current_editor, current_editor_name, searchable_names):
    editor = None
    where = state['where']
    files = OrderedDict()
    do_all = state['wrap'] or action in {'replace-all', 'count'}
    marked = False
    if where == 'current':
        editor = current_editor
    elif where in {'styles', 'text', 'selected'}:
        files = searchable_names[where]
        if current_editor_name in files:
            # Start searching in the current editor
            editor = current_editor
            # Re-order the list of other files so that we search in the same
            # order every time. Depending on direction, search the files
            # that come after the current file, or before the current file,
            # first.
            lfiles = list(files)
            idx = lfiles.index(current_editor_name)
            before, after = lfiles[:idx], lfiles[idx+1:]
            if state['direction'] == 'up':
                lfiles = list(reversed(before))
                if do_all:
                    lfiles += list(reversed(after)) + [current_editor_name]
            else:
                lfiles = after
                if do_all:
                    lfiles += before + [current_editor_name]
            files = OrderedDict((m, files[m]) for m in lfiles)
    else:
        editor = current_editor
        marked = True

    return editor, where, files, do_all, marked

def run_search(
    searches, action, current_editor, current_editor_name, searchable_names,
    gui_parent, show_editor, edit_file, show_current_diff, add_savepoint, rewind_savepoint, set_modified):

    if isinstance(searches, dict):
        searches = [searches]

    editor, where, files, do_all, marked = initialize_search_request(searches[0], action, current_editor, current_editor_name, searchable_names)
    wrap = searches[0]['wrap']

    errfind = searches[0]['find']
    if len(searches) > 1:
        errfind = _('the selected searches')

    try:
        searches = [(get_search_regex(search), search['replace']) for search in searches]
    except InvalidRegex as e:
        return error_dialog(gui_parent, _('Invalid regex'), '<p>' + _(
            'The regular expression you entered is invalid: <pre>{0}</pre>With error: {1}').format(
                prepare_string_for_xml(e.regex), e.message), show=True)

    def no_match():
        QApplication.restoreOverrideCursor()
        msg = '<p>' + _('No matches were found for %s') % ('<pre style="font-style:italic">' + prepare_string_for_xml(errfind) + '</pre>')
        if not wrap:
            msg += '<p>' + _('You have turned off search wrapping, so all text might not have been searched.'
                ' Try the search again, with wrapping enabled. Wrapping is enabled via the'
                ' "Wrap" checkbox at the bottom of the search panel.')
        return error_dialog(
            gui_parent, _('Not found'), msg, show=True)

    def do_find():
        for p, __ in searches:
            if editor is not None:
                if editor.find(p, marked=marked, save_match='gui'):
                    return
                if wrap and not files and editor.find(p, wrap=True, marked=marked, save_match='gui'):
                    return
            for fname, syntax in files.iteritems():
                ed = editors.get(fname, None)
                if ed is not None:
                    if not wrap and ed is editor:
                        continue
                    if ed.find(p, complete=True, save_match='gui'):
                        return show_editor(fname)
                else:
                    raw = current_container().raw_data(fname)
                    if p.search(raw) is not None:
                        edit_file(fname, syntax)
                        if editors[fname].find(p, complete=True, save_match='gui'):
                            return
        return no_match()

    def no_replace(prefix=''):
        QApplication.restoreOverrideCursor()
        if prefix:
            prefix += ' '
        error_dialog(
            gui_parent, _('Cannot replace'), prefix + _(
            'You must first click Find, before trying to replace'), show=True)
        return False

    def do_replace():
        if editor is None:
            return no_replace()
        for p, repl in searches:
            if editor.replace(p, repl, saved_match='gui'):
                return True
        return no_replace(_(
                'Currently selected text does not match the search query.'))

    def count_message(action, count, show_diff=False):
        msg = _('%(action)s %(num)s occurrences of %(query)s' % dict(num=count, query=errfind, action=action))
        if show_diff and count > 0:
            d = MessageBox(MessageBox.INFO, _('Searching done'), prepare_string_for_xml(msg), parent=gui_parent, show_copy_button=False)
            d.diffb = b = d.bb.addButton(_('See what &changed'), d.bb.ActionRole)
            b.setIcon(QIcon(I('diff.png'))), d.set_details(None), b.clicked.connect(d.accept)
            b.clicked.connect(partial(show_current_diff, allow_revert=True))
            d.exec_()
        else:
            info_dialog(gui_parent, _('Searching done'), prepare_string_for_xml(msg), show=True)

    def do_all(replace=True):
        count = 0
        if not files and editor is None:
            return 0
        lfiles = files or {current_editor_name:editor.syntax}
        updates = set()
        raw_data = {}
        for n, syntax in lfiles.iteritems():
            if n in editors:
                raw = editors[n].get_raw_data()
            else:
                raw = current_container().raw_data(n)
            raw_data[n] = raw

        for p, repl in searches:
            for n, syntax in lfiles.iteritems():
                raw = raw_data[n]
                if replace:
                    raw, num = p.subn(repl, raw)
                    if num > 0:
                        updates.add(n)
                        raw_data[n] = raw
                else:
                    num = len(p.findall(raw))
                count += num

        for n in updates:
            raw = raw_data[n]
            if n in editors:
                editors[n].replace_data(raw)
            else:
                with current_container().open(n, 'wb') as f:
                    f.write(raw.encode('utf-8'))
        QApplication.restoreOverrideCursor()
        count_message(_('Replaced') if replace else _('Found'), count, show_diff=replace)
        return count

    with BusyCursor():
        if action == 'find':
            return do_find()
        if action == 'replace':
            return do_replace()
        if action == 'replace-find' and do_replace():
            return do_find()
        if action == 'replace-all':
            if marked:
                return count_message(_('Replaced'), sum(editor.all_in_marked(p, repl) for p, repl in searches))
            add_savepoint(_('Before: Replace all'))
            count = do_all()
            if count == 0:
                rewind_savepoint()
            else:
                set_modified()
            return
        if action == 'count':
            if marked:
                return count_message(_('Found'), sum(editor.all_in_marked(p) for p, __ in searches))
            return do_all(replace=False)

if __name__ == '__main__':
    app = QApplication([])
    d = SavedSearches()
    d.exec_()
