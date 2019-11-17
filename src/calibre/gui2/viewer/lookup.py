#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2019, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import absolute_import, division, print_function, unicode_literals

import os
import sys
import textwrap

from PyQt5.Qt import (
    QApplication, QComboBox, QDialog, QFormLayout, QHBoxLayout, QIcon, QLabel,
    QLineEdit, QListWidget, QListWidgetItem, QPushButton, Qt, QTimer, QUrl,
    QVBoxLayout, QWidget
)
from PyQt5.QtWebEngineWidgets import (
    QWebEnginePage, QWebEngineProfile, QWebEngineView
)

from calibre import prints, random_user_agent
from calibre.constants import cache_dir
from calibre.gui2 import error_dialog
from calibre.gui2.viewer.web_view import apply_font_settings, vprefs
from calibre.gui2.webengine import create_script, insert_scripts, secure_webengine
from calibre.gui2.widgets2 import Dialog

vprefs.defaults['lookup_locations'] = [
    {
        'name': 'Google dictionary',
        'url': 'https://www.google.com/search?q=define:{word}',
        'langs': [],
    },

    {
        'name': 'Google search',
        'url':  'https://www.google.com/search?q={word}',
        'langs': [],
    },

    {
        'name': 'Wordnik',
        'url':  'https://www.wordnik.com/words/{word}',
        'langs': ['eng'],
    },
]
vprefs.defaults['lookup_location'] = 'Google dictionary'


class SourceEditor(Dialog):

    def __init__(self, parent, source_to_edit=None):
        self.all_names = {x['name'] for x in parent.all_entries}
        self.initial_name = self.initial_url = None
        self.langs = []
        if source_to_edit is not None:
            self.langs = source_to_edit['langs']
            self.initial_name = source_to_edit['name']
            self.initial_url = source_to_edit['url']
        Dialog.__init__(self, _('Edit lookup source'), 'viewer-edit-lookup-location', parent=parent)

    def setup_ui(self):
        self.l = l = QFormLayout(self)
        self.name_edit = n = QLineEdit(self)
        n.setPlaceholderText(_('The name of the source'))
        n.setMinimumWidth(450)
        l.addRow(_('&Name:'), n)
        if self.initial_name:
            n.setText(self.initial_name)
            n.setReadOnly(True)
        self.url_edit = u = QLineEdit(self)
        u.setPlaceholderText(_('The URL template of the source'))
        u.setMinimumWidth(n.minimumWidth())
        u.setToolTip(textwrap.fill(_(
            'The URL template must starts with https:// and have {word} in it which will be replaced by the actual query')))
        l.addRow(_('&URL:'), u)
        if self.initial_url:
            u.setText(self.initial_url)
        l.addRow(self.bb)
        if self.initial_name:
            u.setFocus(Qt.OtherFocusReason)

    @property
    def source_name(self):
        return self.name_edit.text().strip()

    @property
    def url(self):
        return self.url_edit.text().strip()

    def accept(self):
        q = self.source_name
        if not q:
            return error_dialog(self, _('No name'), _(
                'You must specify a name'), show=True)
        if not self.initial_name and q in self.all_names:
            return error_dialog(self, _('Name already exists'), _(
                'A lookup source with the name {} already exists').format(q), show=True)
        if not self.url:
            return error_dialog(self, _('No name'), _(
                'You must specify a URL'), show=True)
        if not self.url.startswith('http://') and not self.url.startswith('https://'):
            return error_dialog(self, _('Invalid URL'), _(
                'The URL must start with https://'), show=True)
        if '{word}' not in self.url:
            return error_dialog(self, _('Invalid URL'), _(
                'The URL must contain the placeholder {word}'), show=True)
        return Dialog.accept(self)

    @property
    def entry(self):
        return {'name': self.source_name, 'url': self.url, 'langs': self.langs}


class SourcesEditor(Dialog):

    def __init__(self, parent):
        Dialog.__init__(self, _('Edit lookup sources'), 'viewer-edit-lookup-locations', parent=parent)

    def setup_ui(self):
        self.l = l = QVBoxLayout(self)
        self.la = la = QLabel(_('Double-click to edit an entry'))
        la.setWordWrap(True)
        l.addWidget(la)
        self.entries = e = QListWidget(self)
        e.setDragEnabled(True)
        e.itemDoubleClicked.connect(self.edit_source)
        e.viewport().setAcceptDrops(True)
        e.setDropIndicatorShown(True)
        e.setDragDropMode(e.InternalMove)
        e.setDefaultDropAction(Qt.MoveAction)
        l.addWidget(e)
        l.addWidget(self.bb)
        self.build_entries(vprefs['lookup_locations'])

        self.add_button = b = self.bb.addButton(_('Add'), self.bb.ActionRole)
        b.setIcon(QIcon(I('plus.png')))
        b.clicked.connect(self.add_source)
        self.remove_button = b = self.bb.addButton(_('Remove'), self.bb.ActionRole)
        b.setIcon(QIcon(I('minus.png')))
        b.clicked.connect(self.remove_source)
        self.restore_defaults_button = b = self.bb.addButton(_('Restore defaults'), self.bb.ActionRole)
        b.clicked.connect(self.restore_defaults)

    def add_entry(self, entry, prepend=False):
        i = QListWidgetItem(entry['name'])
        i.setData(Qt.UserRole, entry.copy())
        self.entries.insertItem(0, i) if prepend else self.entries.addItem(i)

    def build_entries(self, entries):
        self.entries.clear()
        for entry in entries:
            self.add_entry(entry)

    def restore_defaults(self):
        self.build_entries(vprefs.defaults['lookup_locations'])

    def add_source(self):
        d = SourceEditor(self)
        if d.exec_() == QDialog.Accepted:
            self.add_entry(d.entry, prepend=True)

    def remove_source(self):
        idx = self.entries.currentRow()
        if idx > -1:
            self.entries.takeItem(idx)

    def edit_source(self, source_item):
        d = SourceEditor(self, source_item.data(Qt.UserRole))
        if d.exec_() == QDialog.Accepted:
            source_item.setData(Qt.UserRole, d.entry)
            source_item.setData(Qt.DisplayRole, d.name)

    @property
    def all_entries(self):
        return [self.entries.item(r).data(Qt.UserRole) for r in range(self.entries.count())]

    def accept(self):
        entries = self.all_entries
        if not entries:
            return error_dialog(self, _('No sources'), _(
                'You must specify at least one lookup source'), show=True)
        if entries == vprefs.defaults['lookup_locations']:
            del vprefs['lookup_locations']
        else:
            vprefs['lookup_locations'] = entries
        return Dialog.accept(self)


def create_profile():
    ans = getattr(create_profile, 'ans', None)
    if ans is None:
        ans = QWebEngineProfile('viewer-lookup', QApplication.instance())
        ans.setHttpUserAgent(random_user_agent(allow_ie=False))
        ans.setCachePath(os.path.join(cache_dir(), 'ev2vl'))
        js = P('lookup.js', data=True, allow_user_override=False)
        insert_scripts(ans, create_script('lookup.js', js))
        s = ans.settings()
        s.setDefaultTextEncoding('utf-8')
        create_profile.ans = ans
    return ans


class Page(QWebEnginePage):

    def javaScriptConsoleMessage(self, level, msg, linenumber, source_id):
        prefix = {QWebEnginePage.InfoMessageLevel: 'INFO', QWebEnginePage.WarningMessageLevel: 'WARNING'}.get(
                level, 'ERROR')
        if source_id == 'userscript:lookup.js':
            prints('%s: %s:%s: %s' % (prefix, source_id, linenumber, msg), file=sys.stderr)
            sys.stderr.flush()

    def zoom_in(self):
        self.setZoomFactor(min(self.zoomFactor() + 0.25, 5))

    def zoom_out(self):
        self.setZoomFactor(max(0.25, self.zoomFactor() - 0.25))

    def default_zoom(self):
        self.setZoomFactor(1)


class View(QWebEngineView):

    def contextMenuEvent(self, ev):
        menu = self.page().createStandardContextMenu()
        menu.addSeparator()
        menu.addAction(_('Zoom in'), self.page().zoom_in)
        menu.addAction(_('Zoom out'), self.page().zoom_out)
        menu.addAction(_('Default zoom'), self.page().default_zoom)
        menu.exec_(ev.globalPos())


class Lookup(QWidget):

    def __init__(self, parent):
        QWidget.__init__(self, parent)
        self.is_visible = False
        self.selected_text = ''
        self.current_query = ''
        self.current_source = ''
        self.l = l = QVBoxLayout(self)
        self.h = h = QHBoxLayout()
        l.addLayout(h)
        self.debounce_timer = t = QTimer(self)
        t.setInterval(150), t.timeout.connect(self.update_query)
        self.source_box = sb = QComboBox(self)
        self.label = la = QLabel(_('Lookup &in:'))
        h.addWidget(la), h.addWidget(sb), la.setBuddy(sb)
        self.view = View(self)
        self._page = Page(create_profile(), self.view)
        apply_font_settings(self._page)
        secure_webengine(self._page, for_viewer=True)
        self.view.setPage(self._page)
        l.addWidget(self.view)
        self.populate_sources()
        self.source_box.currentIndexChanged.connect(self.source_changed)
        self.view.setHtml('<p>' + _('Double click on a word in the book\'s text'
            ' to look it up.'))
        self.add_button = b = QPushButton(QIcon(I('plus.png')), _('Add more sources'))
        b.clicked.connect(self.add_sources)
        l.addWidget(b)

    def add_sources(self):
        if SourcesEditor(self).exec_() == QDialog.Accepted:
            self.populate_sources()
            self.source_box.setCurrentIndex(0)
            self.update_query()

    def source_changed(self):
        s = self.source
        if s is not None:
            vprefs['lookup_location'] = s['name']
            self.update_query()

    def populate_sources(self):
        sb = self.source_box
        sb.clear()
        sb.blockSignals(True)
        for item in vprefs['lookup_locations']:
            sb.addItem(item['name'], item)
        idx = sb.findText(vprefs['lookup_location'], Qt.MatchExactly)
        if idx > -1:
            sb.setCurrentIndex(idx)
        sb.blockSignals(False)

    def visibility_changed(self, is_visible):
        self.is_visible = is_visible
        self.update_query()

    @property
    def source(self):
        idx = self.source_box.currentIndex()
        if idx > -1:
            return self.source_box.itemData(idx)

    @property
    def url_template(self):
        idx = self.source_box.currentIndex()
        if idx > -1:
            return self.source_box.itemData(idx)['url']

    def update_query(self):
        self.debounce_timer.stop()
        query = self.selected_text or self.current_query
        if self.current_query == query and self.current_source == self.url_template:
            return
        if not self.is_visible or not query:
            return
        self.current_source = self.url_template
        url = self.current_source.format(word=query)
        self.view.load(QUrl(url))
        self.current_query = query

    def selected_text_changed(self, text):
        self.selected_text = text or ''
        self.debounce_timer.start()
