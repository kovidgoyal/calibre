#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2019, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import absolute_import, division, print_function, unicode_literals

import os
from collections import defaultdict
from functools import partial

from PyQt5.Qt import QAction, QIcon, QKeySequence, QMenu, Qt, QToolBar, pyqtSignal
from PyQt5.QtWebEngineWidgets import QWebEnginePage

from calibre.gui2 import elided_text
from calibre.gui2.viewer.shortcuts import index_to_key_sequence
from calibre.gui2.viewer.web_view import get_session_pref, set_book_path
from polyglot.builtins import iteritems


class VerticalToolBar(QToolBar):

    action_triggered = pyqtSignal(object)
    open_book_at_path = pyqtSignal(object)

    def __init__(self, parent=None):
        QToolBar.__init__(self, parent)
        self.setObjectName('vertical_toolbar')
        self.setAllowedAreas(Qt.LeftToolBarArea | Qt.RightToolBarArea)
        self.setToolButtonStyle(Qt.ToolButtonIconOnly)
        self.setOrientation(Qt.Vertical)

    def initialize(self, web_view):
        self.action_triggered.connect(web_view.trigger_shortcut)
        page = web_view.page()
        web_view.shortcuts_changed.connect(self.set_tooltips)
        web_view.paged_mode_changed.connect(self.update_mode_action)
        self.shortcut_actions = {}

        self.back_action = page.action(QWebEnginePage.Back)
        self.back_action.setIcon(QIcon(I('back.png')))
        self.back_action.setText(_('Back'))
        self.addAction(self.back_action)
        self.forward_action = page.action(QWebEnginePage.Forward)
        self.forward_action.setIcon(QIcon(I('forward.png')))
        self.forward_action.setText(_('Forward'))
        self.addAction(self.forward_action)
        self.addSeparator()

        def shortcut_action(icon, text, sc):
            a = QAction(QIcon(I(icon)), text, self)
            self.addAction(a)
            connect_lambda(a.triggered, self, lambda self: self.action_triggered.emit(sc))
            self.shortcut_actions[sc] = a
            return a

        self.open_action = a = QAction(QIcon(I('document_open.png')), _('Open e-book'), self)
        self.open_menu = m = QMenu(self)
        a.setMenu(m)
        m.aboutToShow.connect(self.populate_open_menu)
        connect_lambda(a.triggered, self, lambda self: self.open_book_at_path.emit(None))
        self.addAction(a)
        self.copy_action = a = page.action(QWebEnginePage.Copy)
        a.setIcon(QIcon(I('edit-copy.png'))), a.setText(_('Copy to clipboard'))
        self.addAction(a)
        self.increase_font_size_action = shortcut_action('font_size_larger.png', _('Increase font size'), 'increase_font_size')
        self.decrease_font_size_action = shortcut_action('font_size_smaller.png', _('Decrease font size'), 'decrease_font_size')
        self.fullscreen_action = shortcut_action('page.png', _('Toggle full screen'), 'toggle_full_screen')
        self.addSeparator()

        self.next_action = shortcut_action('next.png', _('Next page'), 'next')
        self.previous_action = shortcut_action('previous.png', _('Previous page'), 'previous')
        self.addSeparator()

        self.toc_action = shortcut_action('toc.png', _('Table of Contents'), 'toggle_toc')
        self.bookmarks_action = shortcut_action('bookmarks.png', _('Bookmarks'), 'toggle_bookmarks')
        self.lookup_action = shortcut_action('search.png', _('Lookup words'), 'toggle_lookup')
        self.chrome_action = shortcut_action('tweaks.png', _('Show viewer controls'), 'show_chrome')
        self.addSeparator()

        self.mode_action = a = shortcut_action('scroll.png', _('Toggle paged mode'), 'toggle_paged_mode')
        a.setCheckable(True)
        self.print_action = shortcut_action('print.png', _('Print book'), 'print')
        self.preferences_action = shortcut_action('config.png', _('Preferences'), 'preferences')
        self.metadata_action = shortcut_action('metadata.png', _('Show book metadata'), 'metadata')
        self.update_mode_action()
        self.addSeparator()

    def update_mode_action(self):
        mode = get_session_pref('read_mode', default='paged', group=None)
        a = self.mode_action
        if mode == 'paged':
            a.setChecked(False)
            a.setToolTip(_('Switch to flow mode -- where the text is not broken into pages'))
        else:
            a.setChecked(True)
            a.setToolTip(_('Switch to paged mode -- where the text is broken into pages'))

    def set_tooltips(self, smap):
        rmap = defaultdict(list)
        for k, v in iteritems(smap):
            rmap[v].append(k)
        for sc, a in iteritems(self.shortcut_actions):
            if a.isCheckable():
                continue
            x = rmap.get(sc)
            if x is not None:

                def as_text(idx):
                    return index_to_key_sequence(idx).toString(QKeySequence.NativeText)

                keys = sorted(filter(None, map(as_text, x)))
                if keys:
                    a.setToolTip('{} [{}]'.format(a.text(), ', '.join(keys)))

    def populate_open_menu(self):
        m = self.open_menu
        m.clear()
        recent = get_session_pref('standalone_recently_opened', group=None, default=())
        if recent:
            for entry in recent:
                try:
                    path = os.path.abspath(entry['pathtoebook'])
                except Exception:
                    continue
                if path == os.path.abspath(set_book_path.pathtoebook):
                    continue
                m.addAction('{}\t {}'.format(
                    elided_text(entry['title'], pos='right', width=250),
                    elided_text(os.path.basename(path), width=250))).triggered.connect(partial(
                    self.open_book_at_path.emit, path))
