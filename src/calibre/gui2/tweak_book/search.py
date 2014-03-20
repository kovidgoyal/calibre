#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

from functools import partial

from PyQt4.Qt import (
    QWidget, QToolBar, Qt, QHBoxLayout, QSize, QIcon, QGridLayout, QLabel,
    QPushButton, pyqtSignal, QComboBox, QCheckBox, QSizePolicy, QVBoxLayout,
    QLineEdit, QToolButton, QListView, QFrame, QApplication)

import regex

from calibre.gui2.widgets2 import HistoryLineEdit2
from calibre.gui2.tweak_book import tprefs
from calibre.gui2.tweak_book.widgets import Dialog

REGEX_FLAGS = regex.VERSION1 | regex.WORD | regex.FULLCASE | regex.MULTILINE | regex.UNICODE

# The search panel {{{

class PushButton(QPushButton):

    def __init__(self, text, action, parent):
        QPushButton.__init__(self, text, parent)
        self.clicked.connect(lambda : parent.search_triggered.emit(action))

class HistoryLineEdit(HistoryLineEdit2):

    max_history_items = 100

    def __init__(self, parent, clear_msg):
        HistoryLineEdit2.__init__(self, parent)
        self.disable_popup = tprefs['disable_completion_popup_for_search']
        self.clear_msg = clear_msg

    def contextMenuEvent(self, event):
        menu = self.createStandardContextMenu()
        menu.addSeparator()
        menu.addAction(self.clear_msg, self.clear_history)
        menu.addAction((_('Enable completion based on search history') if self.disable_popup else _(
            'Disable completion based on search history')), self.toggle_popups)
        menu.exec_(event.globalPos())

    def toggle_popups(self):
        self.disable_popup = not bool(self.disable_popup)
        tprefs['disable_completion_popup_for_search'] = self.disable_popup

class WhereBox(QComboBox):

    def __init__(self, parent):
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

    @dynamic_property
    def where(self):
        wm = {0:'current', 1:'text', 2:'styles', 3:'selected', 4:'selected-text'}
        def fget(self):
            return wm[self.currentIndex()]
        def fset(self, val):
            self.setCurrentIndex({v:k for k, v in wm.iteritems()}[val])
        return property(fget=fget, fset=fset)

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

    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.l = l = QGridLayout(self)
        l.setContentsMargins(0, 0, 0, 0)
        self.setLayout(l)

        self.fl = fl = QLabel(_('&Find:'))
        fl.setAlignment(Qt.AlignRight | Qt.AlignCenter)
        self.find_text = ft = HistoryLineEdit(self, _('Clear search history'))
        ft.initialize('tweak_book_find_edit')
        ft.returnPressed.connect(lambda : self.search_triggered.emit('find'))
        fl.setBuddy(ft)
        l.addWidget(fl, 0, 0)
        l.addWidget(ft, 0, 1)

        self.rl = rl = QLabel(_('&Replace:'))
        rl.setAlignment(Qt.AlignRight | Qt.AlignCenter)
        self.replace_text = rt = HistoryLineEdit(self, _('Clear replace history'))
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
        self.mode_box = mb = QComboBox(self)
        mb.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Maximum)
        mb.addItems([_('Normal'), _('Regex')])
        mb.setToolTip('<style>dd {margin-bottom: 1.5ex}</style>' + _(
            '''Select how the search expression is interpreted
            <dl>
            <dt><b>Normal</b></dt>
            <dd>The search expression is treated as normal text, calibre will look for the exact text.</dd>
            <dt><b>Regex</b></dt>
            <dd>The search expression is interpreted as a regular expression. See the User Manual for more help on using regular expressions.</dd>
            </dl>'''))
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
            return 'normal' if self.mode_box.currentIndex() == 0 else 'regex'
        def fset(self, val):
            self.mode_box.setCurrentIndex({'regex':1}.get(val, 0))
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
        self.find_text.setSelection(0, len(text)+10)

# }}}

regex_cache = {}

class SearchPanel(QWidget):

    search_triggered = pyqtSignal(object)

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

    def get_regex(self, state):
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
            ans = regex_cache[(flags, raw)] = regex.compile(raw, flags=flags)
        return ans

    def keyPressEvent(self, ev):
        if ev.key() == Qt.Key_Escape:
            self.hide_panel()
            ev.accept()
        else:
            return QWidget.keyPressEvent(self, ev)

class SavedSearches(Dialog):

    def __init__(self, parent=None):
        Dialog.__init__(self, _('Saved Searches'), 'saved-searches', parent=parent)

    def sizeHint(self):
        return QSize(800, 650)

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
                (_('&Count all'), 'count-all', _('Run Count All for all selected entries')),
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

        self.eb = b = pb(_('&Remove search'), _('Remove the currently selected searches'))
        b.clicked.connect(self.remove_search)
        v.addWidget(b)

        self.eb = b = pb(_('&Add search'), _('Add a new saved search'))
        b.clicked.connect(self.add_search)
        v.addWidget(b)

        self.d2 = d = QFrame(self)
        d.setFrameStyle(QFrame.HLine)
        v.addWidget(d)

        self.where_box = wb = WhereBox(self)
        v.addWidget(wb)
        self.direction_box = db = DirectionBox(self)
        v.addWidget(db)

        self.wr = wr = QCheckBox(_('&Wrap'))
        wr.setToolTip('<p>'+_('When searching reaches the end, wrap around to the beginning and continue the search'))
        v.addWidget(wr)

        l.addWidget(self.bb)
        self.bb.clear()
        self.bb.addButton(self.bb.Close)

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
        pass

    def run_search(self, action):
        pass

    def move_entry(self, delta):
        pass

    def edit_search(self):
        pass

    def remove_search(self):
        pass

    def add_search(self):
        pass

if __name__ == '__main__':
    app = QApplication([])
    d = SavedSearches()
    d.exec_()
