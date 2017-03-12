#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2013, Kovid Goyal <kovid at kovidgoyal.net>
from __future__ import absolute_import, division, print_function, unicode_literals

import copy
import json
from collections import OrderedDict
from functools import partial

from PyQt5.Qt import (
    QAbstractListModel, QApplication, QCheckBox, QComboBox, QFont, QFrame,
    QGridLayout, QHBoxLayout, QIcon, QItemSelection, QLabel, QLineEdit, QListView,
    QMenu, QMimeData, QModelIndex, QPushButton, QScrollArea, QSize, QSizePolicy,
    QStackedLayout, QStyledItemDelegate, Qt, QTimer, QToolBar, QToolButton,
    QVBoxLayout, QWidget, pyqtSignal, QAction, QKeySequence
)

import regex
from calibre import prepare_string_for_xml
from calibre.gui2 import choose_files, choose_save_file, error_dialog, info_dialog
from calibre.gui2.dialogs.confirm_delete import confirm
from calibre.gui2.dialogs.message_box import MessageBox
from calibre.gui2.tweak_book import current_container, editors, tprefs
from calibre.gui2.tweak_book.editor.snippets import (
    KEY, MODIFIER, SnippetTextEdit, find_matching_snip, parse_template,
    string_length
)
from calibre.gui2.tweak_book.function_replace import (
    Function, FunctionBox, FunctionEditor, functions as replace_functions,
    remove_function
)
from calibre.gui2.tweak_book.widgets import BusyCursor
from calibre.gui2.widgets2 import FlowLayout, HistoryComboBox
from calibre.utils.icu import primary_contains


REGEX_FLAGS = regex.VERSION1 | regex.WORD | regex.FULLCASE | regex.MULTILINE | regex.UNICODE

# The search panel {{{


class AnimatablePushButton(QPushButton):

    'A push button that can be animated without actually emitting a clicked signal'

    def __init__(self, *args, **kwargs):
        QPushButton.__init__(self, *args, **kwargs)
        self.timer = t = QTimer(self)
        t.setSingleShot(True), t.timeout.connect(self.animate_done)

    def animate_click(self, msec=100):
        self.setDown(True)
        self.update()
        self.timer.start(msec)

    def animate_done(self):
        self.setDown(False)
        self.update()


class PushButton(AnimatablePushButton):

    def __init__(self, text, action, parent):
        AnimatablePushButton.__init__(self, text, parent)
        self.clicked.connect(lambda : parent.search_triggered.emit(action))


def expand_template(line_edit):
    pos = line_edit.cursorPosition()
    text = line_edit.text()[:pos]
    if text:
        snip, trigger = find_matching_snip(text)
        if snip is None:
            error_dialog(line_edit, _('No snippet found'), _(
                'No matching snippet was found'), show=True)
            return False
        text, tab_stops = parse_template(snip['template'])
        ft = line_edit.text()
        l = string_length(trigger)
        line_edit.setText(ft[:pos - l] + text + ft[pos:])
        line_edit.setCursorPosition(pos - l + string_length(text))
        return True
    return False


class HistoryBox(HistoryComboBox):

    max_history_items = 100
    save_search = pyqtSignal()
    show_saved_searches = pyqtSignal()

    def __init__(self, parent, clear_msg):
        HistoryComboBox.__init__(self, parent)
        self.disable_popup = tprefs['disable_completion_popup_for_search']
        self.clear_msg = clear_msg
        self.ignore_snip_expansion = False

    def event(self, ev):
        if ev.type() in (ev.ShortcutOverride, ev.KeyPress) and ev.key() == KEY and ev.modifiers() & MODIFIER:
            if not self.ignore_snip_expansion:
                self.ignore_snip_expansion = True
                expand_template(self.lineEdit())
                QTimer.singleShot(100, lambda : setattr(self, 'ignore_snip_expansion', False))
            ev.accept()
            return True
        return HistoryComboBox.event(self, ev)

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
        self.addItems([_('Current file'), _('All text files'), _('All style files'), _('Selected files'), _('Open files'), _('Marked text')])
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
            <dd>Search in the files currently selected in the File Browser</dd>
            <dt><b>Open files</b></dt>
            <dd>Search in the files currently open in the editor</dd>
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
        wm = {0:'current', 1:'text', 2:'styles', 3:'selected', 4:'open', 5:'selected-text'}

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
        self.addItems([_('Normal'), _('Regex'), _('Regex-Function')])
        self.setToolTip('<style>dd {margin-bottom: 1.5ex}</style>' + _(
            '''Select how the search expression is interpreted
            <dl>
            <dt><b>Normal</b></dt>
            <dd>The search expression is treated as normal text, calibre will look for the exact text.</dd>
            <dt><b>Regex</b></dt>
            <dd>The search expression is interpreted as a regular expression. See the User Manual for more help on using regular expressions.</dd>
            <dt><b>Regex-Function</b></dt>
            <dd>The search expression is interpreted as a regular expression. The replace expression is an arbitrarily powerful python function.</dd>
            </dl>'''))

    @dynamic_property
    def mode(self):
        def fget(self):
            return ('normal', 'regex', 'function')[self.currentIndex()]

        def fset(self, val):
            self.setCurrentIndex({'regex':1, 'function':2}.get(val, 0))
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
        l.setColumnStretch(1, 10)

        self.rl = rl = QLabel(_('&Replace:'))
        rl.setAlignment(Qt.AlignRight | Qt.AlignCenter)
        self.replace_text = rt = HistoryBox(self, _('Clear replace history'))
        rt.save_search.connect(self.save_search)
        rt.show_saved_searches.connect(self.show_saved_searches)
        rt.initialize('tweak_book_replace_edit')
        rl.setBuddy(rt)
        self.replace_stack1 = rs1 = QVBoxLayout()
        self.replace_stack2 = rs2 = QVBoxLayout()
        rs1.addWidget(rl), rs2.addWidget(rt)
        l.addLayout(rs1, 1, 0)
        l.addLayout(rs2, 1, 1)

        self.rl2 = rl2 = QLabel(_('F&unction:'))
        rl2.setAlignment(Qt.AlignRight | Qt.AlignCenter)
        self.functions = fb = FunctionBox(self, show_saved_search_actions=True)
        fb.show_saved_searches.connect(self.show_saved_searches)
        fb.save_search.connect(self.save_search)
        rl2.setBuddy(fb)
        rs1.addWidget(rl2)
        self.functions_container = w = QWidget(self)
        rs2.addWidget(w)
        self.fhl = fhl = QHBoxLayout(w)
        fhl.setContentsMargins(0, 0, 0, 0)
        fhl.addWidget(fb, stretch=10, alignment=Qt.AlignVCenter)
        self.ae_func = b = QPushButton(_('Create/&edit'), self)
        b.clicked.connect(self.edit_function)
        b.setToolTip(_('Create a new function, or edit an existing function'))
        fhl.addWidget(b)
        self.rm_func = b = QPushButton(_('Remo&ve'), self)
        b.setToolTip(_('Remove this function'))
        b.clicked.connect(self.remove_function)
        fhl.addWidget(b)
        self.fsep = f = QFrame(self)
        f.setFrameShape(f.VLine)
        fhl.addWidget(f)

        self.fb = fb = PushButton(_('Fin&d'), 'find', self)
        self.rfb = rfb = PushButton(_('Replace a&nd Find'), 'replace-find', self)
        self.rb = rb = PushButton(_('Re&place'), 'replace', self)
        self.rab = rab = PushButton(_('Replace &all'), 'replace-all', self)
        l.addWidget(fb, 0, 2)
        l.addWidget(rfb, 0, 3)
        l.addWidget(rb, 1, 2)
        l.addWidget(rab, 1, 3)

        self.ml = ml = QLabel(_('&Mode:'))
        self.ol = ol = FlowLayout()
        ml.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        l.addWidget(ml, 2, 0)
        l.addLayout(ol, 2, 1, 1, 3)
        self.mode_box = mb = ModeBox(self)
        ml.setBuddy(mb)
        ol.addWidget(mb)

        self.where_box = wb = WhereBox(self)
        ol.addWidget(wb)

        self.direction_box = db = DirectionBox(self)
        ol.addWidget(db)

        self.cs = cs = QCheckBox(_('&Case sensitive'))
        ol.addWidget(cs)

        self.wr = wr = QCheckBox(_('&Wrap'))
        wr.setToolTip('<p>'+_('When searching reaches the end, wrap around to the beginning and continue the search'))
        ol.addWidget(wr)

        self.da = da = QCheckBox(_('&Dot all'))
        da.setToolTip('<p>'+_("Make the '.' special character match any character at all, including a newline"))
        ol.addWidget(da)

        self.mode_box.currentIndexChanged[int].connect(self.mode_changed)
        self.mode_changed(self.mode_box.currentIndex())

    def edit_function(self):
        d = FunctionEditor(func_name=self.functions.text().strip(), parent=self)
        if d.exec_() == d.Accepted:
            self.functions.setText(d.func_name)

    def remove_function(self):
        fname = self.functions.text().strip()
        if fname:
            if remove_function(fname, self):
                self.functions.setText('')

    def mode_changed(self, idx):
        self.da.setVisible(idx > 0)
        function_mode = idx == 2
        self.rl.setVisible(not function_mode)
        self.rl2.setVisible(function_mode)
        self.replace_text.setVisible(not function_mode)
        self.functions_container.setVisible(function_mode)

    @dynamic_property
    def mode(self):
        def fget(self):
            return self.mode_box.mode

        def fset(self, val):
            self.mode_box.mode = val
            self.da.setVisible(self.mode in ('regex', 'function'))
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
            if self.mode == 'function':
                return self.functions.text()
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
        if self.mode in ('regex', 'function'):
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
        self.where_before_marked = None
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
        le = self.widget.find_text.lineEdit()
        le.setSelection(0, le.maxLength())

    @property
    def state(self):
        ans = self.widget.state
        ans['find'] = self.widget.find
        ans['replace'] = self.widget.replace
        return ans

    def set_where(self, val):
        if val == 'selected-text' and self.widget.where != 'selected-text':
            self.where_before_marked = self.widget.where
        self.widget.where = val

    def unset_marked(self):
        if self.widget.where == 'selected-text':
            self.widget.where = self.where_before_marked or self.widget.DEFAULT_STATE['where']
            self.where_before_marked = None

    def keyPressEvent(self, ev):
        if ev.key() == Qt.Key_Escape:
            self.hide_panel()
            ev.accept()
        else:
            return QWidget.keyPressEvent(self, ev)
# }}}


class SearchDescription(QScrollArea):

    def __init__(self, parent):
        QScrollArea.__init__(self, parent)
        self.label = QLabel(' \n \n ')
        self.setWidget(self.label)
        self.setWidgetResizable(True)
        self.label.setTextFormat(Qt.PlainText)
        self.label.setWordWrap(True)
        self.set_text = self.label.setText


class SearchesModel(QAbstractListModel):

    def __init__(self, parent):
        QAbstractListModel.__init__(self, parent)
        self.searches = tprefs['saved_searches']
        self.filtered_searches = list(xrange(len(self.searches)))

    def rowCount(self, parent=QModelIndex()):
        return len(self.filtered_searches)

    def supportedDropActions(self):
        return Qt.MoveAction

    def flags(self, index):
        ans = QAbstractListModel.flags(self, index)
        if index.isValid():
            ans |= Qt.ItemIsDragEnabled
        else:
            ans |= Qt.ItemIsDropEnabled
        return ans

    def mimeTypes(self):
        return ['x-calibre/searches-rows', 'application/vnd.text.list']

    def mimeData(self, indices):
        ans = QMimeData()
        names, rows = [], []
        for i in indices:
            if i.isValid():
                names.append(i.data())
                rows.append(i.row())
        ans.setData('x-calibre/searches-rows', ','.join(map(str, rows)).encode('ascii'))
        ans.setData('application/vnd.text.list', '\n'.join(names).encode('utf-8'))
        return ans

    def dropMimeData(self, data, action, row, column, parent):
        if parent.isValid() or action != Qt.MoveAction or not data.hasFormat('x-calibre/searches-rows') or not self.filtered_searches:
            return False
        rows = map(int, bytes(bytearray(data.data('x-calibre/searches-rows'))).decode('ascii').split(','))
        rows.sort()
        moved_searches = [self.searches[self.filtered_searches[r]] for r in rows]
        moved_searches_q = {id(s) for s in moved_searches}
        insert_at = max(0, min(row, len(self.filtered_searches)))
        while insert_at < len(self.filtered_searches):
            s = self.searches[self.filtered_searches[insert_at]]
            if id(s) in moved_searches_q:
                insert_at += 1
            else:
                break
        insert_before = id(self.searches[self.filtered_searches[insert_at]]) if insert_at < len(self.filtered_searches) else None
        visible_searches = {id(self.searches[self.filtered_searches[r]]) for r in self.filtered_searches}
        unmoved_searches = list(filter(lambda s:id(s) not in moved_searches_q, self.searches))
        if insert_before is None:
            searches = unmoved_searches + moved_searches
        else:
            idx = {id(x):i for i, x in enumerate(unmoved_searches)}[insert_before]
            searches = unmoved_searches[:idx] + moved_searches + unmoved_searches[idx:]
        filtered_searches = []
        for i, s in enumerate(searches):
            if id(s) in visible_searches:
                filtered_searches.append(i)
        self.modelAboutToBeReset.emit()
        self.searches, self.filtered_searches = searches, filtered_searches
        self.modelReset.emit()
        tprefs['saved_searches'] = self.searches
        return True

    def data(self, index, role):
        try:
            if role == Qt.DisplayRole:
                search = self.searches[self.filtered_searches[index.row()]]
                return search['name']
            if role == Qt.ToolTipRole:
                search = self.searches[self.filtered_searches[index.row()]]
                tt = '\n'.join((search['find'], search['replace']))
                return tt
            if role == Qt.UserRole:
                search = self.searches[self.filtered_searches[index.row()]]
                return (self.filtered_searches[index.row()], search)
        except IndexError:
            pass
        return None

    def do_filter(self, text):
        text = unicode(text)
        self.beginResetModel()
        self.filtered_searches = []
        for i, search in enumerate(self.searches):
            if primary_contains(text, search['name']):
                self.filtered_searches.append(i)
        self.endResetModel()

    def search_for_index(self, index):
        try:
            return self.searches[self.filtered_searches[index.row()]]
        except IndexError:
            pass

    def index_for_search(self, search):
        for row, si in enumerate(self.filtered_searches):
            if self.searches[si] is search:
                return self.index(row)
        return self.index(-1)

    def move_entry(self, row, delta):
        a, b = row, row + delta
        if 0 <= b < len(self.filtered_searches):
            ai, bi = self.filtered_searches[a], self.filtered_searches[b]
            self.searches[ai], self.searches[bi] = self.searches[bi], self.searches[ai]
            self.dataChanged.emit(self.index(a), self.index(a))
            self.dataChanged.emit(self.index(b), self.index(b))
            tprefs['saved_searches'] = self.searches

    def add_searches(self, count=1):
        self.beginResetModel()
        self.searches = tprefs['saved_searches']
        self.filtered_searches.extend(xrange(len(self.searches) - 1, len(self.searches) - 1 - count, -1))
        self.endResetModel()

    def remove_searches(self, rows):
        indices = {self.filtered_searches[row] for row in frozenset(rows)}
        for idx in sorted(indices, reverse=True):
            del self.searches[idx]
        tprefs['saved_searches'] = self.searches
        self.do_filter('')


class EditSearch(QFrame):  # {{{

    done = pyqtSignal(object)

    def __init__(self, parent=None):
        QFrame.__init__(self, parent)
        self.setFrameShape(self.StyledPanel)
        self.search_index = -1
        self.search = {}
        self.original_name = None

        self.l = l = QVBoxLayout(self)
        self.title = la = QLabel('<h2>Edit...')
        self.ht = h = QHBoxLayout()
        l.addLayout(h)
        h.addWidget(la)
        self.cb = cb = QToolButton(self)
        cb.setIcon(QIcon(I('window-close.png')))
        cb.setToolTip(_('Abort editing of search'))
        h.addWidget(cb)
        cb.clicked.connect(self.abort_editing)
        self.search_name = n = QLineEdit('', self)
        n.setPlaceholderText(_('The name with which to save this search'))
        self.la1 = la = QLabel(_('&Name:'))
        la.setBuddy(n)
        self.h3 = h = QHBoxLayout()
        h.addWidget(la), h.addWidget(n)
        l.addLayout(h)

        self.find = f = SnippetTextEdit('', self)
        self.la2 = la = QLabel(_('&Find:'))
        la.setBuddy(f)
        l.addWidget(la), l.addWidget(f)

        self.replace = r = SnippetTextEdit('', self)
        self.la3 = la = QLabel(_('&Replace:'))
        la.setBuddy(r)
        l.addWidget(la), l.addWidget(r)

        self.functions_container = w = QWidget()
        l.addWidget(w)
        w.g = g = QGridLayout(w)
        self.la7 = la = QLabel(_('F&unction:'))
        self.function = f = FunctionBox(self)
        g.addWidget(la), g.addWidget(f)
        g.setContentsMargins(0, 0, 0, 0)
        la.setBuddy(f)
        self.ae_func = b = QPushButton(_('Create/&edit'), self)
        b.setToolTip(_('Create a new function, or edit an existing function'))
        b.clicked.connect(self.edit_function)
        g.addWidget(b, 1, 1)
        g.setColumnStretch(0, 10)
        self.rm_func = b = QPushButton(_('Remo&ve'), self)
        b.setToolTip(_('Remove this function'))
        b.clicked.connect(self.remove_function)
        g.addWidget(b, 1, 2)

        self.case_sensitive = c = QCheckBox(_('Case sensitive'))
        self.h = h = QHBoxLayout()
        l.addLayout(h)
        h.addWidget(c)

        self.dot_all = d = QCheckBox(_('Dot matches all'))
        h.addWidget(d), h.addStretch(2)

        self.h2 = h = QHBoxLayout()
        l.addLayout(h)
        self.mode_box = m = ModeBox(self)
        m.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.la4 = la = QLabel(_('&Mode:'))
        la.setBuddy(m)
        h.addWidget(la), h.addWidget(m), h.addStretch(2)

        self.done_button = b = QPushButton(QIcon(I('ok.png')), _('&Done'))
        b.setToolTip(_('Finish editing of search'))
        h.addWidget(b)
        b.clicked.connect(self.emit_done)

        self.mode_box.currentIndexChanged[int].connect(self.mode_changed)
        self.mode_changed(self.mode_box.currentIndex())

    def edit_function(self):
        d = FunctionEditor(func_name=self.function.text().strip(), parent=self)
        if d.exec_() == d.Accepted:
            self.function.setText(d.func_name)

    def remove_function(self):
        fname = self.function.text().strip()
        if fname:
            if remove_function(fname, self):
                self.function.setText('')

    def mode_changed(self, idx):
        self.dot_all.setVisible(idx > 0)
        self.functions_container.setVisible(idx == 2)
        self.la3.setVisible(idx < 2)
        self.replace.setVisible(idx < 2)

    def show_search(self, search=None, search_index=-1, state=None):
        self.title.setText('<h2>' + (_('Add search') if search_index == -1 else _('Edit search')))
        self.search = search or {}
        self.original_name = self.search.get('name', None)
        self.search_index = search_index

        self.mode_box.mode = self.search.get('mode', 'regex')
        self.search_name.setText(self.search.get('name', ''))
        self.find.setPlainText(self.search.get('find', ''))
        if self.mode_box.mode == 'function':
            self.function.setText(self.search.get('replace', ''))
        else:
            self.replace.setPlainText(self.search.get('replace', ''))
        self.case_sensitive.setChecked(self.search.get('case_sensitive', SearchWidget.DEFAULT_STATE['case_sensitive']))
        self.dot_all.setChecked(self.search.get('dot_all', SearchWidget.DEFAULT_STATE['dot_all']))

        if state is not None:
            self.find.setPlainText(state['find'])
            self.mode_box.mode = state.get('mode')
            if self.mode_box.mode == 'function':
                self.function.setText(state['replace'])
            else:
                self.replace.setPlainText(state['replace'])
            self.case_sensitive.setChecked(state['case_sensitive'])
            self.dot_all.setChecked(state['dot_all'])

    def emit_done(self):
        self.done.emit(True)

    def keyPressEvent(self, ev):
        if ev.key() == Qt.Key_Escape:
            self.abort_editing()
            ev.accept()
            return
        return QFrame.keyPressEvent(self, ev)

    def abort_editing(self):
        self.done.emit(False)

    @property
    def current_search(self):
        search = self.search.copy()
        f = unicode(self.find.toPlainText())
        search['find'] = f
        search['dot_all'] = bool(self.dot_all.isChecked())
        search['case_sensitive'] = bool(self.case_sensitive.isChecked())
        search['mode'] = self.mode_box.mode
        if search['mode'] == 'function':
            r = self.function.text()
        else:
            r = unicode(self.replace.toPlainText())
        search['replace'] = r
        return search

    def save_changes(self):
        searches = tprefs['saved_searches']
        all_names = {x['name'] for x in searches} - {self.original_name}
        n = self.search_name.text().strip()
        if not n:
            error_dialog(self, _('Must specify name'), _(
                'You must specify a search name'), show=True)
            return False
        if n in all_names:
            error_dialog(self, _('Name exists'), _(
                'Another search with the name %s already exists') % n, show=True)
            return False
        search = self.search
        search['name'] = n

        f = unicode(self.find.toPlainText())
        if not f:
            error_dialog(self, _('Must specify find'), _(
                'You must specify a find expression'), show=True)
            return False
        search['find'] = f
        search['mode'] = self.mode_box.mode

        if search['mode'] == 'function':
            r = self.function.text()
            if not r:
                error_dialog(self, _('Must specify function'), _(
                    'You must specify a function name in Function-Regex mode'), show=True)
                return False
        else:
            r = unicode(self.replace.toPlainText())
        search['replace'] = r

        search['dot_all'] = bool(self.dot_all.isChecked())
        search['case_sensitive'] = bool(self.case_sensitive.isChecked())

        if self.search_index == -1:
            searches.append(search)
        else:
            searches[self.search_index] = search
        tprefs.set('saved_searches', searches)
        return True

# }}}


class SearchDelegate(QStyledItemDelegate):

    def sizeHint(self, *args):
        ans = QStyledItemDelegate.sizeHint(self, *args)
        ans.setHeight(ans.height() + 4)
        return ans


class SavedSearches(QWidget):

    run_saved_searches = pyqtSignal(object, object)

    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.setup_ui()

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
        self.stack = stack = QStackedLayout()
        self.main_widget = mw = QWidget(self)
        stack.addWidget(mw)
        self.edit_search_widget = es = EditSearch(mw)
        stack.addWidget(es)
        es.done.connect(self.search_editing_done)
        mw.v = QVBoxLayout(mw)
        mw.v.setContentsMargins(0, 0, 0, 0)
        mw.v.addWidget(searches)
        searches.doubleClicked.connect(self.edit_search)
        self.model = SearchesModel(self.searches)
        self.model.dataChanged.connect(self.show_details)
        searches.setModel(self.model)
        searches.selectionModel().currentChanged.connect(self.show_details)
        searches.setSelectionMode(searches.ExtendedSelection)
        self.delegate = SearchDelegate(searches)
        searches.setItemDelegate(self.delegate)
        searches.setAlternatingRowColors(True)
        searches.setDragEnabled(True), searches.setAcceptDrops(True), searches.setDragDropMode(searches.InternalMove)
        searches.setDropIndicatorShown(True)
        h.addLayout(stack, stretch=10)
        self.v = v = QVBoxLayout()
        h.addLayout(v)
        l.addLayout(h)
        stack.currentChanged.connect(self.stack_current_changed)

        def pb(text, tooltip=None):
            b = AnimatablePushButton(text, self)
            b.setToolTip(tooltip or '')
            b.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
            return b

        mulmsg = '\n\n' + _('The entries are tried in order until the first one matches.')
        self.action_button_map = {}

        for text, action, tooltip in [
                (_('&Find'), 'find', _('Run the search using the selected entries.') + mulmsg),
                (_('&Replace'), 'replace', _('Run replace using the selected entries.') + mulmsg),
                (_('Replace a&nd Find'), 'replace-find', _('Run replace and then find using the selected entries.') + mulmsg),
                (_('Replace &all'), 'replace-all', _('Run Replace All for all selected entries in the order selected')),
                (_('&Count all'), 'count', _('Run Count All for all selected entries')),
        ]:
            self.action_button_map[action] = b = pb(text, tooltip)
            v.addWidget(b)
            b.clicked.connect(partial(self.run_search, action))

        self.d1 = d = QFrame(self)
        d.setFrameStyle(QFrame.HLine)
        v.addWidget(d)

        self.h3 = h = QHBoxLayout()
        self.upb = b = QToolButton(self)
        self.move_up_action = a = QAction(self)
        a.setShortcut(QKeySequence('Alt+Up'))
        b.setIcon(QIcon(I('arrow-up.png'))), b.setToolTip(_('Move selected entries up') + ' [%s]' % a.shortcut().toString(QKeySequence.NativeText))
        a.triggered.connect(partial(self.move_entry, -1))
        self.searches.addAction(a)
        b.clicked.connect(partial(self.move_entry, -1))

        self.dnb = b = QToolButton(self)
        self.move_down_action = a = QAction(self)
        a.setShortcut(QKeySequence('Alt+Down'))
        b.setIcon(QIcon(I('arrow-down.png'))), b.setToolTip(_('Move selected entries down') + ' [%s]' % a.shortcut().toString(QKeySequence.NativeText))
        a.triggered.connect(partial(self.move_entry, 1))
        self.searches.addAction(a)
        b.clicked.connect(partial(self.move_entry, 1))
        h.addWidget(self.upb), h.addWidget(self.dnb)
        v.addLayout(h)

        self.eb = b = pb(_('&Edit search'), _('Edit the currently selected search'))
        b.clicked.connect(self.edit_search)
        v.addWidget(b)

        self.rb = b = pb(_('Re&move search'), _('Remove the currently selected searches'))
        b.clicked.connect(self.remove_search)
        v.addWidget(b)

        self.ab = b = pb(_('&Add search'), _('Add a new saved search'))
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

        self.d3 = d = QFrame(self)
        d.setFrameStyle(QFrame.HLine)
        v.addWidget(d)

        self.description = d = SearchDescription(self)
        mw.v.addWidget(d)
        mw.v.setStretch(0, 10)

        self.ib = b = pb(_('&Import'), _('Import saved searches'))
        b.clicked.connect(self.import_searches)
        v.addWidget(b)

        self.eb2 = b = pb(_('E&xport'), _('Export saved searches'))
        v.addWidget(b)
        self.em = m = QMenu(_('Export'))
        m.addAction(_('Export All'), lambda : QTimer.singleShot(0, partial(self.export_searches, all=True)))
        m.addAction(_('Export Selected'), lambda : QTimer.singleShot(0, partial(self.export_searches, all=False)))
        b.setMenu(m)

        self.searches.setFocus(Qt.OtherFocusReason)

    @dynamic_property
    def state(self):
        def fget(self):
            return {'wrap':self.wrap, 'direction':self.direction, 'where':self.where}

        def fset(self, val):
            self.wrap, self.where, self.direction = val['wrap'], val['where'], val['direction']
        return property(fget=fget, fset=fset)

    def save_state(self):
        tprefs['saved_seaches_state'] = self.state

    def restore_state(self):
        self.state = tprefs.get('saved_seaches_state', SearchWidget.DEFAULT_STATE)

    def has_focus(self):
        if self.hasFocus():
            return True
        for child in self.findChildren(QWidget):
            if child.hasFocus():
                return True
        return False

    def trigger_action(self, action, overrides=None):
        b = self.action_button_map.get(action)
        if b is not None:
            b.animate_click(300)
        self._run_search(action, overrides)

    def stack_current_changed(self, index):
        visible = index == 0
        for x in ('eb', 'ab', 'rb', 'upb', 'dnb', 'd2', 'filter_text', 'cft', 'd3', 'ib', 'eb2'):
            getattr(self, x).setVisible(visible)

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
        return self._run_search(action)

    def _run_search(self, action, overrides=None):
        searches = []

        def fill_in_search(search):
            search['wrap'] = self.wrap
            search['direction'] = self.direction
            search['where'] = self.where
            search['mode'] = search.get('mode', 'regex')

        if self.editing_search:
            search = SearchWidget.DEFAULT_STATE.copy()
            del search['mode']
            search.update(self.edit_search_widget.current_search)
            fill_in_search(search)
            searches.append(search)
        else:
            seen = set()
            for index in self.searches.selectionModel().selectedIndexes():
                if index.row() in seen:
                    continue
                seen.add(index.row())
                search = SearchWidget.DEFAULT_STATE.copy()
                del search['mode']
                search_index, s = index.data(Qt.UserRole)
                search.update(s)
                fill_in_search(search)
                searches.append(search)
        if not searches:
            return error_dialog(self, _('Cannot search'), _(
                'No saved search is selected'), show=True)
        if overrides:
            [sc.update(overrides) for sc in searches]
        self.run_saved_searches.emit(searches, action)

    @property
    def editing_search(self):
        return self.stack.currentIndex() != 0

    def move_entry(self, delta):
        if self.editing_search:
            return
        sm = self.searches.selectionModel()
        rows = {index.row() for index in sm.selectedIndexes()} - {-1}
        if rows:
            searches = [self.model.search_for_index(index) for index in sm.selectedIndexes()]
            current_search = self.model.search_for_index(self.searches.currentIndex())
            with tprefs:
                for row in sorted(rows, reverse=delta > 0):
                    self.model.move_entry(row, delta)
            sm.clear()
            for s in searches:
                index = self.model.index_for_search(s)
                if index.isValid() and index.row() > -1:
                    if s is current_search:
                        sm.setCurrentIndex(index, sm.Select)
                    else:
                        sm.select(index, sm.Select)

    def search_editing_done(self, save_changes):
        if save_changes and not self.edit_search_widget.save_changes():
            return
        self.stack.setCurrentIndex(0)
        if save_changes:
            if self.edit_search_widget.search_index == -1:
                self._add_search()
            else:
                index = self.searches.currentIndex()
                if index.isValid():
                    self.model.dataChanged.emit(index, index)

    def edit_search(self):
        index = self.searches.currentIndex()
        if not index.isValid():
            return error_dialog(self, _('Cannot edit'), _(
                'Cannot edit search - no search selected.'), show=True)
        if not self.editing_search:
            search_index, search = index.data(Qt.UserRole)
            self.edit_search_widget.show_search(search=search, search_index=search_index)
            self.stack.setCurrentIndex(1)
            self.edit_search_widget.find.setFocus(Qt.OtherFocusReason)

    def remove_search(self):
        if self.editing_search:
            return
        if confirm(_('Are you sure you want to permanently delete the selected saved searches?'),
                   'confirm-remove-editor-saved-search', config_set=tprefs):
            rows = {index.row() for index in self.searches.selectionModel().selectedIndexes()} - {-1}
            self.model.remove_searches(rows)
            self.show_details()

    def add_search(self):
        if self.editing_search:
            return
        self.edit_search_widget.show_search()
        self.stack.setCurrentIndex(1)
        self.edit_search_widget.search_name.setFocus(Qt.OtherFocusReason)

    def _add_search(self):
        self.model.add_searches()
        index = self.model.index(self.model.rowCount() - 1)
        self.searches.scrollTo(index)
        sm = self.searches.selectionModel()
        sm.setCurrentIndex(index, sm.ClearAndSelect)
        self.show_details()

    def add_predefined_search(self, state):
        if self.editing_search:
            return
        self.edit_search_widget.show_search(state=state)
        self.stack.setCurrentIndex(1)
        self.edit_search_widget.search_name.setFocus(Qt.OtherFocusReason)

    def show_details(self):
        self.description.set_text(' \n \n ')
        i = self.searches.currentIndex()
        if i.isValid():
            try:
                search_index, search = i.data(Qt.UserRole)
            except TypeError:
                return  # no saved searches
            cs = '✓' if search.get('case_sensitive', SearchWidget.DEFAULT_STATE['case_sensitive']) else '✗'
            da = '✓' if search.get('dot_all', SearchWidget.DEFAULT_STATE['dot_all']) else '✗'
            if search.get('mode', SearchWidget.DEFAULT_STATE['mode']) in ('regex', 'function'):
                ts = _('(Case sensitive: {0} Dot All: {1})').format(cs, da)
            else:
                ts = _('(Case sensitive: {0} [Normal search])').format(cs)
            self.description.set_text(_('{2} {3}\nFind: {0}\nReplace: {1}').format(
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
                search = index.data(Qt.UserRole)[-1]
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
        err = _('No files are selected in the File Browser')
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
    is_regex = state['mode'] != 'normal'
    if not is_regex:
        raw = regex.escape(raw, special_only=True)
    flags = REGEX_FLAGS
    if not state['case_sensitive']:
        flags |= regex.IGNORECASE
    if is_regex and state['dot_all']:
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


def get_search_function(state):
    ans = state['replace']
    is_regex = state['mode'] != 'normal'
    if not is_regex:
        # We dont want backslash escape sequences interpreted in normal mode
        return lambda m: ans
    if state['mode'] == 'function':
        try:
            return replace_functions()[ans]
        except KeyError:
            if not ans:
                return Function('empty-function', '')
            raise NoSuchFunction(ans)
    return ans


def initialize_search_request(state, action, current_editor, current_editor_name, searchable_names):
    editor = None
    where = state['where']
    files = OrderedDict()
    do_all = state.get('wrap') or action in {'replace-all', 'count'}
    marked = False
    if where == 'current':
        editor = current_editor
    elif where in {'styles', 'text', 'selected', 'open'}:
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


class NoSuchFunction(ValueError):
    pass


def show_function_debug_output(func):
    if isinstance(func, Function):
        val = func.debug_buf.getvalue().strip()
        func.debug_buf.truncate(0)
        if val:
            from calibre.gui2.tweak_book.boss import get_boss
            get_boss().gui.sr_debug_output.show_log(func.name, val)


def reorder_files(names, order):
    reverse = order in {'spine-reverse', 'reverse-spine'}
    spine_order = {name:i for i, (name, is_linear) in enumerate(current_container().spine_names)}
    return sorted(frozenset(names), key=spine_order.get, reverse=reverse)


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
        searches = [(get_search_regex(search), get_search_function(search)) for search in searches]
    except InvalidRegex as e:
        return error_dialog(gui_parent, _('Invalid regex'), '<p>' + _(
            'The regular expression you entered is invalid: <pre>{0}</pre>With error: {1}').format(
                prepare_string_for_xml(e.regex), e.message), show=True)
    except NoSuchFunction as e:
        return error_dialog(gui_parent, _('No such function'), '<p>' + _(
            'No replace function with the name: %s exists') % prepare_string_for_xml(e.message), show=True)

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
                    return True
                if wrap and not files and editor.find(p, wrap=True, marked=marked, save_match='gui'):
                    return True
            for fname, syntax in files.iteritems():
                ed = editors.get(fname, None)
                if ed is not None:
                    if not wrap and ed is editor:
                        continue
                    if ed.find(p, complete=True, save_match='gui'):
                        show_editor(fname)
                        return True
                else:
                    raw = current_container().raw_data(fname)
                    if p.search(raw) is not None:
                        edit_file(fname, syntax)
                        if editors[fname].find(p, complete=True, save_match='gui'):
                            return True
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
            repl_is_func = isinstance(repl, Function)
            if repl_is_func:
                repl.init_env(current_editor_name)
            if editor.replace(p, repl, saved_match='gui'):
                if repl_is_func:
                    repl.end()
                    show_function_debug_output(repl)
                return True
        return no_replace(_(
                'Currently selected text does not match the search query.'))

    def count_message(replaced, count, show_diff=False, show_dialog=True):
        if show_dialog:
            if replaced:
                msg = _('Performed the replacement at {num} occurrences of {query}')
            else:
                msg = _('Found {num} occurrences of {query}')
            msg = msg.format(num=count, query=errfind)
            if show_diff and count > 0:
                d = MessageBox(MessageBox.INFO, _('Searching done'), prepare_string_for_xml(msg), parent=gui_parent, show_copy_button=False)
                d.diffb = b = d.bb.addButton(_('See what &changed'), d.bb.ActionRole)
                b.setIcon(QIcon(I('diff.png'))), d.set_details(None), b.clicked.connect(d.accept)
                b.clicked.connect(partial(show_current_diff, allow_revert=True), type=Qt.QueuedConnection)
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
        for n in lfiles:
            if n in editors:
                raw = editors[n].get_raw_data()
            else:
                raw = current_container().raw_data(n)
            raw_data[n] = raw

        for p, repl in searches:
            repl_is_func = isinstance(repl, Function)
            file_iterator = lfiles
            if repl_is_func:
                repl.init_env()
                if repl.file_order is not None and len(lfiles) > 1:
                    file_iterator = reorder_files(file_iterator, repl.file_order)
            for n in file_iterator:
                raw = raw_data[n]
                if replace:
                    if repl_is_func:
                        repl.context_name = n
                    raw, num = p.subn(repl, raw)
                    if num > 0:
                        updates.add(n)
                        raw_data[n] = raw
                else:
                    num = len(p.findall(raw))
                count += num
            if repl_is_func:
                repl.end()
                show_function_debug_output(repl)

        for n in updates:
            raw = raw_data[n]
            if n in editors:
                editors[n].replace_data(raw)
            else:
                with current_container().open(n, 'wb') as f:
                    f.write(raw.encode('utf-8'))
        QApplication.restoreOverrideCursor()
        count_message(replace, count, show_diff=replace)
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
                show_result_dialog = True
                for p, repl in searches:
                    if getattr(getattr(repl, 'func', None), 'suppress_result_dialog', False):
                        show_result_dialog = False
                        break
                return count_message(True, sum(editor.all_in_marked(p, repl) for p, repl in searches), show_dialog=show_result_dialog)
            add_savepoint(_('Before: Replace all'))
            count = do_all()
            if count == 0:
                rewind_savepoint()
            else:
                set_modified()
            return
        if action == 'count':
            if marked:
                return count_message(False, sum(editor.all_in_marked(p) for p, __ in searches))
            return do_all(replace=False)


if __name__ == '__main__':
    app = QApplication([])
    d = SavedSearches()
    d.show()
    app.exec_()
