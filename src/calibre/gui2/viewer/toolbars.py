#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2019, Kovid Goyal <kovid at kovidgoyal.net>


import os
from functools import partial

from PyQt5.Qt import (
    QAction, QGroupBox, QHBoxLayout, QIcon, QKeySequence, QLabel, QListWidget,
    QListWidgetItem, QMenu, Qt, QToolBar, QToolButton, QVBoxLayout, pyqtSignal
)
from PyQt5.QtWebEngineWidgets import QWebEnginePage

from calibre.constants import ismacos
from calibre.gui2 import elided_text
from calibre.gui2.viewer.config import get_session_pref
from calibre.gui2.viewer.shortcuts import index_to_key_sequence
from calibre.gui2.viewer.web_view import set_book_path, vprefs
from calibre.gui2.widgets2 import Dialog
from calibre.utils.icu import primary_sort_key
from polyglot.builtins import iteritems


class Action(object):

    __slots__ = ('icon', 'text', 'shortcut_action')

    def __init__(self, icon=None, text=None, shortcut_action=None):
        self.icon, self.text, self.shortcut_action = QIcon(I(icon)), text, shortcut_action


class Actions(object):

    def __init__(self, a):
        self.__dict__.update(a)
        self.all_action_names = frozenset(a)


def all_actions():
    if not hasattr(all_actions, 'ans'):
        amap = {
            'color_scheme': Action('format-fill-color.png', _('Switch color scheme')),
            'back': Action('back.png', _('Back')),
            'forward': Action('forward.png', _('Forward')),
            'open': Action('document_open.png', _('Open e-book')),
            'copy': Action('edit-copy.png', _('Copy to clipboard'), 'copy_to_clipboard'),
            'increase_font_size': Action('font_size_larger.png', _('Increase font size'), 'increase_font_size'),
            'decrease_font_size': Action('font_size_smaller.png', _('Decrease font size'), 'decrease_font_size'),
            'fullscreen': Action('page.png', _('Toggle full screen'), 'toggle_full_screen'),
            'next': Action('next.png', _('Next page'), 'next'),
            'previous': Action('previous.png', _('Previous page'), 'previous'),
            'next_section': Action('arrow-down.png', _('Next section'), 'next_section'),
            'previous_section': Action('arrow-up.png', _('Previous section'), 'previous_section'),
            'toc': Action('toc.png', _('Table of Contents'), 'toggle_toc'),
            'search': Action('search.png', _('Search'), 'toggle_search'),
            'bookmarks': Action('bookmarks.png', _('Bookmarks'), 'toggle_bookmarks'),
            'inspector': Action('debug.png', _('Inspector'), 'toggle_inspector'),
            'reference': Action('reference.png', _('Toggle Reference mode'), 'toggle_reference_mode'),
            'autoscroll': Action('auto-scroll.png', _('Toggle auto-scrolling'), 'toggle_autoscroll'),
            'lookup': Action('generic-library.png', _('Lookup words'), 'toggle_lookup'),
            'chrome': Action('tweaks.png', _('Show viewer controls'), 'show_chrome_force'),
            'mode': Action('scroll.png', _('Toggle paged mode'), 'toggle_paged_mode'),
            'print': Action('print.png', _('Print book'), 'print'),
            'preferences': Action('config.png', _('Preferences'), 'preferences'),
            'metadata': Action('metadata.png', _('Show book metadata'), 'metadata'),
            'toggle_highlights': Action('highlight_only_on.png', _('Browse highlights in book'), 'toggle_highlights'),
        }
        all_actions.ans = Actions(amap)
    return all_actions.ans


DEFAULT_ACTIONS = (
    'back', 'forward', None, 'open', 'copy', 'increase_font_size', 'decrease_font_size', 'fullscreen', 'color_scheme',
    None, 'previous', 'next', None, 'toc', 'search', 'bookmarks', 'lookup', 'toggle_highlights', 'chrome', None,
    'mode', 'print', 'preferences', 'metadata', 'inspector'
)


def current_actions():
    ans = vprefs.get('actions-toolbar-actions')
    if not ans:
        ans = DEFAULT_ACTIONS
    return tuple(ans)


class ToolBar(QToolBar):

    def __init__(self, parent=None):
        QToolBar.__init__(self, parent)
        self.setWindowTitle(_('Toolbar'))
        self.shortcut_actions = {}
        self.setToolButtonStyle(Qt.ToolButtonIconOnly)
        self.setVisible(False)
        self.setAllowedAreas(Qt.AllToolBarAreas)
        self.setContextMenuPolicy(Qt.CustomContextMenu)

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
        self.customContextMenuRequested.connect(self.show_context_menu)

    def show_context_menu(self, pos):
        m = QMenu(self)
        a = m.addAction(_('Customize this toolbar'))
        a.triggered.connect(self.customize)
        a = m.addAction(_('Hide this toolbar'))
        a.triggered.connect(self.hide_toolbar)
        m.exec_(self.mapToGlobal(pos))

    def hide_toolbar(self):
        self.web_view.trigger_shortcut('toggle_toolbar')

    def initialize(self, web_view, toggle_search_action):
        self.web_view = web_view
        shortcut_action = self.create_shortcut_action
        aa = all_actions()
        self.action_triggered.connect(web_view.trigger_shortcut)
        page = web_view.page()
        web_view.paged_mode_changed.connect(self.update_mode_action)
        web_view.reference_mode_changed.connect(self.update_reference_mode_action)
        web_view.standalone_misc_settings_changed.connect(self.update_visibility)
        web_view.autoscroll_state_changed.connect(self.update_autoscroll_action)
        web_view.customize_toolbar.connect(self.customize, type=Qt.QueuedConnection)
        web_view.view_created.connect(self.on_view_created)

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
        self.copy_action = shortcut_action('copy')
        self.increase_font_size_action = shortcut_action('increase_font_size')
        self.decrease_font_size_action = shortcut_action('decrease_font_size')
        self.fullscreen_action = shortcut_action('fullscreen')

        self.next_action = shortcut_action('next')
        self.previous_action = shortcut_action('previous')
        self.next_section_action = shortcut_action('next_section')
        self.previous_section_action = shortcut_action('previous_section')

        self.search_action = a = toggle_search_action
        a.setText(aa.search.text), a.setIcon(aa.search.icon)
        self.toc_action = a = shortcut_action('toc')
        a.setCheckable(True)
        self.bookmarks_action = a = shortcut_action('bookmarks')
        a.setCheckable(True)
        self.reference_action = a = shortcut_action('reference')
        a.setCheckable(True)
        self.toggle_highlights_action = self.highlights_action = a = shortcut_action('toggle_highlights')
        a.setCheckable(True)
        self.lookup_action = a = shortcut_action('lookup')
        a.setCheckable(True)
        self.inspector_action = a = shortcut_action('inspector')
        a.setCheckable(True)
        self.autoscroll_action = a = shortcut_action('autoscroll')
        a.setCheckable(True)
        self.update_autoscroll_action(False)
        self.chrome_action = shortcut_action('chrome')

        self.mode_action = a = shortcut_action('mode')
        a.setCheckable(True)
        self.print_action = shortcut_action('print')
        self.preferences_action = shortcut_action('preferences')
        self.metadata_action = shortcut_action('metadata')
        self.update_mode_action()
        self.color_scheme_action = a = QAction(aa.color_scheme.icon, aa.color_scheme.text, self)
        self.color_scheme_menu = m = QMenu(self)
        a.setMenu(m)
        m.aboutToShow.connect(self.populate_color_scheme_menu)

        self.add_actions()

    def add_actions(self):
        self.clear()
        actions = current_actions()
        for x in actions:
            if x is None:
                self.addSeparator()
            else:
                try:
                    self.addAction(getattr(self, '{}_action'.format(x)))
                except AttributeError:
                    pass
        w = self.widgetForAction(self.color_scheme_action)
        if w:
            w.setPopupMode(w.InstantPopup)

    def update_mode_action(self):
        mode = get_session_pref('read_mode', default='paged', group=None)
        a = self.mode_action
        if mode == 'paged':
            a.setChecked(False)
            a.setToolTip(_('Switch to flow mode -- where the text is not broken into pages'))
        else:
            a.setChecked(True)
            a.setToolTip(_('Switch to paged mode -- where the text is broken into pages'))

    def update_autoscroll_action(self, active):
        self.autoscroll_action.setChecked(active)
        self.autoscroll_action.setToolTip(
            _('Turn off auto-scrolling') if active else _('Turn on auto-scrolling'))

    def update_reference_mode_action(self, enabled):
        self.reference_action.setChecked(enabled)

    def update_dock_actions(self, visibility_map):
        for k in ('toc', 'bookmarks', 'lookup', 'inspector', 'highlights'):
            ac = getattr(self, '{}_action'.format(k))
            ac.setChecked(visibility_map[k])

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
                if hasattr(set_book_path, 'pathtoebook') and path == os.path.abspath(set_book_path.pathtoebook):
                    continue
                m.addAction('{}\t {}'.format(
                    elided_text(entry['title'], pos='right', width=250),
                    elided_text(os.path.basename(path), width=250))).triggered.connect(partial(
                    self.open_book_at_path.emit, path))

    def on_view_created(self, data):
        self.default_color_schemes = data['default_color_schemes']

    def populate_color_scheme_menu(self):
        m = self.color_scheme_menu
        m.clear()
        ccs = get_session_pref('current_color_scheme', group=None) or ''
        ucs = get_session_pref('user_color_schemes', group=None) or {}

        def add_action(key, defns):
            a = m.addAction(defns[key]['name'])
            a.setCheckable(True)
            a.setObjectName('color-switch-action:{}'.format(key))
            a.triggered.connect(self.color_switch_triggerred)
            if key == ccs:
                a.setChecked(True)

        for key in sorted(ucs, key=lambda x: primary_sort_key(ucs[x]['name'])):
            add_action(key, ucs)
        m.addSeparator()
        for key in sorted(self.default_color_schemes, key=lambda x: primary_sort_key(self.default_color_schemes[x]['name'])):
            add_action(key, self.default_color_schemes)

    def color_switch_triggerred(self):
        key = self.sender().objectName().partition(':')[-1]
        self.action_triggered.emit('switch_color_scheme:' + key)

    def update_visibility(self):
        self.setVisible(bool(get_session_pref('show_actions_toolbar', default=False)))

    @property
    def visible_in_fullscreen(self):
        return bool(get_session_pref('show_actions_toolbar_in_fullscreen', default=False))

    def customize(self):
        d = ConfigureToolBar(parent=self.parent())
        if d.exec_() == d.Accepted:
            self.add_actions()


class ActionsList(QListWidget):

    def __init__(self, actions, parent=None, is_source=True):
        QListWidget.__init__(self, parent)
        self.setSelectionMode(self.ExtendedSelection)
        self.setDragEnabled(True)
        self.viewport().setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(self.InternalMove)
        self.setDefaultDropAction(Qt.CopyAction if ismacos else Qt.MoveAction)
        self.setMinimumHeight(400)
        self.is_source = is_source
        if is_source:
            actions = self.sort_actions_alphabetically(actions)
            actions = [None] + actions
        self.set_names(actions)

    def sort_actions_alphabetically(self, actions):
        aa = all_actions()
        return sorted(actions, key=lambda name: primary_sort_key(getattr(aa, name).text) if name else primary_sort_key(''))

    def add_item_from_name(self, action):
        aa = all_actions()
        if action is None:
            i = QListWidgetItem('-- {} --'.format(_('Separator')), self)
        else:
            try:
                a = getattr(aa, action)
            except AttributeError:
                return
            i = QListWidgetItem(a.icon, a.text, self)
        i.setData(Qt.UserRole, action)
        return i

    def set_names(self, names):
        self.clear()
        for name in names:
            self.add_item_from_name(name)

    def remove_selected(self):
        ans = []
        for item in tuple(self.selectedItems()):
            action = item.data(Qt.UserRole)
            if action is not None or not self.is_source:
                self.takeItem(self.row(item))
            ans.append(action)
        return ans

    def add_names(self, names):
        for action in names:
            if action or not self.is_source:
                self.add_item_from_name(action)
        if self.is_source:
            actions = self.sort_actions_alphabetically(self.names)
            self.set_names(actions)

    @property
    def names(self):
        for i in range(self.count()):
            item = self.item(i)
            yield item.data(Qt.UserRole)


class ConfigureToolBar(Dialog):

    def __init__(self, parent=None):
        Dialog.__init__(self, _('Configure the toolbar'), 'configure-viewer-toolbar', parent=parent, prefs=vprefs)

    def setup_ui(self):
        acnames = all_actions().all_action_names
        self.available_actions = ActionsList(acnames - frozenset(current_actions()), parent=self)
        self.current_actions = ActionsList(current_actions(), parent=self, is_source=False)
        self.l = l = QVBoxLayout(self)
        self.la = la = QLabel(_('Choose the actions you want on the toolbar.'
            ' Drag and drop items in the right hand list to re-arrange the toolbar.'))
        la.setWordWrap(True)
        l.addWidget(la)
        self.bv = bv = QVBoxLayout()
        bv.addStretch(10)
        self.add_button = b = QToolButton(self)
        b.setIcon(QIcon(I('forward.png'))), b.setToolTip(_('Add selected actions to the toolbar'))
        bv.addWidget(b), bv.addStretch(10)
        b.clicked.connect(self.add_actions)
        self.remove_button = b = QToolButton(self)
        b.setIcon(QIcon(I('back.png'))), b.setToolTip(_('Remove selected actions from the toolbar'))
        b.clicked.connect(self.remove_actions)
        bv.addWidget(b), bv.addStretch(10)

        self.h = h = QHBoxLayout()
        l.addLayout(h)
        self.lg = lg = QGroupBox(_('A&vailable actions'), self)
        lg.v = v = QVBoxLayout(lg)
        v.addWidget(self.available_actions)
        h.addWidget(lg)
        self.rg = rg = QGroupBox(_('&Current actions'), self)
        rg.v = v = QVBoxLayout(rg)
        v.addWidget(self.current_actions)
        h.addLayout(bv), h.addWidget(rg)
        l.addWidget(self.bb)
        self.rdb = b = self.bb.addButton(_('Restore defaults'), self.bb.ActionRole)
        b.clicked.connect(self.restore_defaults)

    def remove_actions(self):
        names = self.current_actions.remove_selected()
        self.available_actions.add_names(names)

    def add_actions(self):
        names = self.available_actions.remove_selected()
        self.current_actions.add_names(names)

    def restore_defaults(self):
        self.current_actions.set_names(DEFAULT_ACTIONS)
        acnames = all_actions().all_action_names
        rest = acnames - frozenset(DEFAULT_ACTIONS)
        rest = [None] + list(rest)
        self.available_actions.set_names(rest)

    def accept(self):
        ans = tuple(self.current_actions.names)
        if ans == DEFAULT_ACTIONS:
            vprefs.__delitem__('actions-toolbar-actions')
        else:
            vprefs.set('actions-toolbar-actions', ans)
        return Dialog.accept(self)


if __name__ == '__main__':
    from calibre.gui2 import Application
    app = Application([])
    ConfigureToolBar().exec_()
