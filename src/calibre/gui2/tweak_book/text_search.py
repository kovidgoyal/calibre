#!/usr/bin/env python
# License: GPLv3 Copyright: 2016, Kovid Goyal <kovid at kovidgoyal.net>


from qt.core import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QComboBox, QPushButton, QIcon,
    pyqtSignal, QFont, QCheckBox, QSizePolicy
)
from lxml.etree import tostring

from calibre import prepare_string_for_xml
from calibre.gui2 import error_dialog
from calibre.gui2.tweak_book import tprefs, editors, current_container
from calibre.gui2.tweak_book.search import get_search_regex, InvalidRegex, initialize_search_request
from calibre.gui2.widgets import BusyCursor
from calibre.gui2.widgets2 import HistoryComboBox
from polyglot.builtins import iteritems, error_message

# UI {{{


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

    @property
    def mode(self):
        return ('normal', 'regex')[self.currentIndex()]

    @mode.setter
    def mode(self, val):
        self.setCurrentIndex({'regex':1}.get(val, 0))


class WhereBox(QComboBox):

    def __init__(self, parent, emphasize=False):
        QComboBox.__init__(self)
        self.addItems([_('Current file'), _('All text files'), _('Selected files'), _('Open files')])
        self.setToolTip('<style>dd {margin-bottom: 1.5ex}</style>' + _(
            '''
            Where to search/replace:
            <dl>
            <dt><b>Current file</b></dt>
            <dd>Search only inside the currently opened file</dd>
            <dt><b>All text files</b></dt>
            <dd>Search in all text (HTML) files</dd>
            <dt><b>Selected files</b></dt>
            <dd>Search in the files currently selected in the File browser</dd>
            <dt><b>Open files</b></dt>
            <dd>Search in the files currently open in the editor</dd>
            </dl>'''))
        self.emphasize = emphasize
        self.ofont = QFont(self.font())
        if emphasize:
            f = self.emph_font = QFont(self.ofont)
            f.setBold(True), f.setItalic(True)
            self.setFont(f)

    @property
    def where(self):
        wm = {0:'current', 1:'text', 2:'selected', 3:'open'}
        return wm[self.currentIndex()]

    @where.setter
    def where(self, val):
        wm = {0:'current', 1:'text', 2:'selected', 3:'open'}
        self.setCurrentIndex({v:k for k, v in iteritems(wm)}[val])

    def showPopup(self):
        # We do it like this so that the popup uses a normal font
        if self.emphasize:
            self.setFont(self.ofont)
        QComboBox.showPopup(self)

    def hidePopup(self):
        if self.emphasize:
            self.setFont(self.emph_font)
        QComboBox.hidePopup(self)


class TextSearch(QWidget):

    find_text = pyqtSignal(object)

    def __init__(self, ui):
        QWidget.__init__(self, ui)
        self.l = l = QVBoxLayout(self)
        self.la = la = QLabel(_('&Find:'))
        self.find = ft = HistoryComboBox(self)
        ft.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        ft.initialize('tweak_book_text_search_history')
        la.setBuddy(ft)
        self.h = h = QHBoxLayout()
        h.addWidget(la), h.addWidget(ft), l.addLayout(h)

        self.h2 = h = QHBoxLayout()
        l.addLayout(h)

        self.mode = m = ModeBox(self)
        h.addWidget(m)
        self.where_box = wb = WhereBox(self)
        h.addWidget(wb)
        self.cs = cs = QCheckBox(_('&Case sensitive'))
        h.addWidget(cs)
        self.da = da = QCheckBox(_('&Dot all'))
        da.setToolTip('<p>'+_("Make the '.' special character match any character at all, including a newline"))
        h.addWidget(da)

        self.h3 = h = QHBoxLayout()
        l.addLayout(h)
        h.addStretch(10)
        self.next_button = b = QPushButton(QIcon.ic('arrow-down.png'), _('&Next'), self)
        b.setToolTip(_('Find next match'))
        h.addWidget(b)
        connect_lambda(b.clicked, self, lambda self: self.do_search('down'))
        self.prev_button = b = QPushButton(QIcon.ic('arrow-up.png'), _('&Previous'), self)
        b.setToolTip(_('Find previous match'))
        h.addWidget(b)
        connect_lambda(b.clicked, self, lambda self: self.do_search('up'))

        state = tprefs.get('text_search_widget_state')
        self.state = state or {}

    @property
    def state(self):
        return {'mode': self.mode.mode, 'where':self.where_box.where, 'case_sensitive':self.cs.isChecked(), 'dot_all':self.da.isChecked()}

    @state.setter
    def state(self, val):
        self.mode.mode = val.get('mode', 'normal')
        self.where_box.where = val.get('where', 'current')
        self.cs.setChecked(bool(val.get('case_sensitive')))
        self.da.setChecked(bool(val.get('dot_all', True)))

    def save_state(self):
        tprefs['text_search_widget_state'] = self.state

    def do_search(self, direction='down'):
        state = self.state
        state['find'] = self.find.text()
        state['direction'] = direction
        self.find_text.emit(state)
# }}}


def file_matches_pattern(fname, pat):
    root = current_container().parsed(fname)
    if hasattr(root, 'xpath'):
        raw = tostring(root, method='text', encoding='unicode', with_tail=True)
    else:
        raw = current_container().raw_data(fname)
    return pat.search(raw) is not None


def run_text_search(search, current_editor, current_editor_name, searchable_names, gui_parent, show_editor, edit_file):
    try:
        pat = get_search_regex(search)
    except InvalidRegex as e:
        return error_dialog(gui_parent, _('Invalid regex'), '<p>' + _(
            'The regular expression you entered is invalid: <pre>{0}</pre>With error: {1}').format(
                prepare_string_for_xml(e.regex), error_message(e)), show=True)
    editor, where, files, do_all, marked = initialize_search_request(search, 'count', current_editor, current_editor_name, searchable_names)
    with BusyCursor():
        if editor is not None:
            if editor.find_text(pat):
                return True
            if not files and editor.find_text(pat, wrap=True):
                return True
        for fname, syntax in iteritems(files):
            ed = editors.get(fname, None)
            if ed is not None:
                if ed.find_text(pat, complete=True):
                    show_editor(fname)
                    return True
            else:
                if file_matches_pattern(fname, pat):
                    edit_file(fname, syntax)
                    if editors[fname].find_text(pat, complete=True):
                        return True

    msg = '<p>' + _('No matches were found for %s') % ('<pre style="font-style:italic">' + prepare_string_for_xml(search['find']) + '</pre>')
    return error_dialog(gui_parent, _('Not found'), msg, show=True)


def find_text_in_chunks(pat, chunks):
    text = ''.join(x[0] for x in chunks)
    m = pat.search(text)
    if m is None:
        return -1, -1
    start, after = m.span()

    def contains(clen, pt):
        return offset <= pt < offset + clen

    offset = 0
    start_pos = end_pos = None

    for chunk, chunk_start in chunks:
        clen = len(chunk)
        if offset + clen < start:
            offset += clen
            continue  # this chunk ends before start
        if start_pos is None:
            if contains(clen, start):
                start_pos = chunk_start + (start - offset)
        if start_pos is not None:
            if contains(clen, after-1):
                end_pos = chunk_start + (after - offset)
                return start_pos, end_pos
        offset += clen
        if offset > after:
            break  # the next chunk starts after end
    return -1, -1
