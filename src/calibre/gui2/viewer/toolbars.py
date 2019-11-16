#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2019, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import absolute_import, division, print_function, unicode_literals

import os
from functools import partial

from PyQt5.Qt import QAction, QIcon, QKeySequence, QMenu, Qt, QToolBar, pyqtSignal
from PyQt5.QtWebEngineWidgets import QWebEnginePage

from calibre.gui2 import elided_text
from calibre.gui2.viewer.shortcuts import index_to_key_sequence
from calibre.gui2.viewer.web_view import get_session_pref, set_book_path
from polyglot.builtins import iteritems


class Action(object):

    __slots__ = ('icon', 'text', 'shortcut_action')

    def __init__(self, icon=None, text=None, shortcut_action=None):
        self.icon, self.text, self.shortcut_action = QIcon(I(icon)), text, shortcut_action


class Actions(object):

    def __init__(self, a):
        self.__dict__.update(a)


def all_actions():
    if not hasattr(all_actions, 'ans'):
        all_actions.ans = Actions({
            'back': Action('back.png', _('Back')),
            'forward': Action('back.png', _('Forward')),
            'open': Action('document_open.png', _('Open e-book')),
            'copy': Action('edit-copy.png', _('Copy to clipboard')),
            'increase_font_size': Action('font_size_larger.png', _('Increase font size'), 'increase_font_size'),
            'decrease_font_size': Action('font_size_smaller.png', _('Decrease font size'), 'decrease_font_size'),
            'fullscreen': Action('page.png', _('Toggle full screen'), 'toggle_full_screen'),
            'next': Action('next.png', _('Next page'), 'next'),
            'previous': Action('previous.png', _('Previous page'), 'previous'),
            'toc': Action('toc.png', _('Table of Contents'), 'toggle_toc'),
            'bookmarks': Action('bookmarks.png', _('Bookmarks'), 'toggle_bookmarks'),
            'lookup': Action('search.png', _('Lookup words'), 'toggle_lookup'),
            'chrome': Action('tweaks.png', _('Show viewer controls'), 'show_chrome'),
            'mode': Action('scroll.png', _('Toggle paged mode'), 'toggle_paged_mode'),
            'print': Action('print.png', _('Print book'), 'print'),
            'preferences': Action('config.png', _('Preferences'), 'preferences'),
            'metadata': Action('metadata.png', _('Show book metadata'), 'metadata'),
        })
    return all_actions.ans


DEFAULT_ACTIONS = (
        'back', 'forward', None, 'open', 'copy', 'increase_font_size', 'decrease_font_size', 'fullscreen',
        None, 'previous', 'next', None, 'toc', 'bookmarks', 'lookup', 'chrome', None, 'mode', 'print', 'preferences',
        'metadata'
)


class ToolBar(QToolBar):

    def __init__(self, parent=None):
        QToolBar.__init__(self, parent)
        self.shortcut_actions = {}
        self.setToolButtonStyle(Qt.ToolButtonIconOnly)
        self.setVisible(False)
        self.setAllowedAreas(Qt.AllToolBarAreas)

    def create_shortcut_action(self, name):
        a = getattr(all_actions(), name)
        sc = a.shortcut_action
        a = QAction(a.icon, a.text, self)
        connect_lambda(a.triggered, self, lambda self: self.action_triggered.emit(sc))
        self.shortcut_actions[sc] = a
        return a


class ActionsToolBar(ToolBar):

    action_triggered = pyqtSignal(object)
    open_book_at_path = pyqtSignal(object)

    def __init__(self, parent=None):
        ToolBar.__init__(self, parent)
        self.setObjectName('actions_toolbar')

    def initialize(self, web_view):
        shortcut_action = self.create_shortcut_action
        aa = all_actions()
        self.action_triggered.connect(web_view.trigger_shortcut)
        page = web_view.page()
        web_view.paged_mode_changed.connect(self.update_mode_action)
        web_view.standalone_misc_settings_changed.connect(self.update_visibility)

        self.back_action = page.action(QWebEnginePage.Back)
        self.back_action.setIcon(aa.back.icon)
        self.back_action.setText(aa.back.text)
        self.forward_action = page.action(QWebEnginePage.Forward)
        self.forward_action.setIcon(aa.forward.icon)
        self.forward_action.setText(aa.forward.text)

        self.open_action = a = QAction(aa.open.icon, aa.open.text, self)
        self.open_menu = m = QMenu(self)
        a.setMenu(m)
        m.aboutToShow.connect(self.populate_open_menu)
        connect_lambda(a.triggered, self, lambda self: self.open_book_at_path.emit(None))
        self.copy_action = a = page.action(QWebEnginePage.Copy)
        a.setIcon(aa.copy.icon), a.setText(aa.copy.text)
        self.increase_font_size_action = shortcut_action('increase_font_size')
        self.decrease_font_size_action = shortcut_action('decrease_font_size')
        self.fullscreen_action = shortcut_action('fullscreen')

        self.next_action = shortcut_action('next')
        self.previous_action = shortcut_action('previous')

        self.toc_action = shortcut_action('toc')
        self.bookmarks_action = shortcut_action('bookmarks')
        self.lookup_action = shortcut_action('lookup')
        self.chrome_action = shortcut_action('chrome')

        self.mode_action = a = shortcut_action('mode')
        a.setCheckable(True)
        self.print_action = shortcut_action('print')
        self.preferences_action = shortcut_action('preferences')
        self.metadata_action = shortcut_action('metadata')
        self.update_mode_action()
        self.add_actions()

    def add_actions(self):
        self.clear()
        actions = DEFAULT_ACTIONS
        for x in actions:
            if x is None:
                self.addSeparator()
            else:
                try:
                    self.addAction(getattr(self, '{}_action'.format(x)))
                except AttributeError:
                    pass

    def update_mode_action(self):
        mode = get_session_pref('read_mode', default='paged', group=None)
        a = self.mode_action
        if mode == 'paged':
            a.setChecked(False)
            a.setToolTip(_('Switch to flow mode -- where the text is not broken into pages'))
        else:
            a.setChecked(True)
            a.setToolTip(_('Switch to paged mode -- where the text is broken into pages'))

    def set_tooltips(self, rmap):
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

    def update_visibility(self):
        self.setVisible(bool(get_session_pref('show_actions_toolbar', default=False)))
