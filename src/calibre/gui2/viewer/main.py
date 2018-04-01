#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2015, Kovid Goyal <kovid at kovidgoyal.net>

import functools
import os
import sys
import traceback
from functools import partial
from threading import Thread

from PyQt5.Qt import (
    QAction, QApplication, QByteArray, QIcon, QInputDialog, QMimeData, QModelIndex,
    QObject, QPropertyAnimation, QSize, Qt, QTime, QTimer, pyqtSignal
)

from calibre import as_unicode, force_unicode, isbytestring, prints
from calibre.constants import (
    DEBUG, VIEWER_APP_UID, filesystem_encoding, islinux, iswindows
)
from calibre.customize.ui import available_input_formats
from calibre.ebooks.oeb.iterator.book import EbookIterator
from calibre.gui2 import (
    Application, add_to_recent_docs, choose_files, error_dialog, info_dialog,
    open_url, set_app_uid, setup_gui_option_parser
)
from calibre.gui2.viewer.toc import TOC
from calibre.gui2.viewer.ui import Main as MainWindow
from calibre.gui2.widgets import ProgressIndicator
from calibre.ptempfile import reset_base_dir
from calibre.utils.config import Config, JSONConfig, StringConfig
from calibre.utils.ipc import RC, viewer_socket_address
from calibre.utils.localization import canonicalize_lang, get_lang, lang_as_iso639_1
from calibre.utils.zipfile import BadZipfile

try:
    from calibre.utils.monotonic import monotonic
except RuntimeError:
    from time import time as monotonic

vprefs = JSONConfig('viewer')
vprefs.defaults['singleinstance'] = False
dprefs = JSONConfig('viewer_dictionaries')
dprefs.defaults['word_lookups'] = {}
singleinstance_name = 'calibre_viewer'


class ResizeEvent(object):

    INTERVAL = 20  # mins

    def __init__(self, size_before, multiplier, last_loaded_path, page_number):
        self.size_before, self.multiplier, self.last_loaded_path = size_before, multiplier, last_loaded_path
        self.page_number = page_number
        self.timestamp = monotonic()
        self.finished_timestamp = 0
        self.multiplier_after = self.last_loaded_path_after = self.page_number_after = None

    def finished(self, size_after, multiplier, last_loaded_path, page_number):
        self.size_after, self.multiplier_after = size_after, multiplier
        self.last_loaded_path_after = last_loaded_path
        self.page_number_after = page_number
        self.finished_timestamp = monotonic()

    def is_a_toggle(self, previous):
        if self.finished_timestamp - previous.finished_timestamp > self.INTERVAL * 60:
            # The second resize occurred too long after the first one
            return False
        if self.size_after != previous.size_before:
            # The second resize is to a different size than the first one
            return False
        if self.multiplier_after != previous.multiplier or self.last_loaded_path_after != previous.last_loaded_path:
            # A new file has been loaded or the text size multiplier has changed
            return False
        if self.page_number != previous.page_number_after:
            # The use has scrolled between the two resizes
            return False
        return True


class Worker(Thread):

    def run(self):
        from calibre.utils.ipc.simple_worker import WorkerError
        try:
            Thread.run(self)
            self.exception = self.traceback = None
        except BadZipfile:
            self.exception = _(
                'This e-book is corrupted and cannot be opened. If you '
                'downloaded it from somewhere, try downloading it again.')
            self.traceback = ''
        except WorkerError as err:
            self.exception = Exception(_('Failed to read book, {0} click "Show Details" for more information').format(self.path_to_ebook))
            self.traceback = err.orig_tb or as_unicode(err)
        except Exception as err:
            self.exception = err
            self.traceback = traceback.format_exc()


class RecentAction(QAction):

    def __init__(self, path, parent):
        self.path = path
        QAction.__init__(self, os.path.basename(path), parent)


def default_lookup_website(lang):
    if lang == 'und':
        lang = get_lang()
    lang = lang_as_iso639_1(lang) or lang
    if lang == 'en':
        prefix = 'https://www.wordnik.com/words/'
    else:
        prefix = 'http://%s.wiktionary.org/wiki/' % lang
    return prefix + '{word}'


def lookup_website(lang):
    if lang == 'und':
        lang = get_lang()
    wm = dprefs['word_lookups']
    return wm.get(lang, default_lookup_website(lang))


def listen(self):
    while True:
        try:
            conn = self.listener.accept()
        except Exception:
            break
        try:
            self.msg_from_anotherinstance.emit(conn.recv())
            conn.close()
        except Exception as e:
            prints('Failed to read message from other instance with error: %s' % as_unicode(e))
    self.listener = None


class EbookViewer(MainWindow):

    STATE_VERSION = 2
    FLOW_MODE_TT = _('Switch to paged mode - where the text is broken up '
            'into pages like a paper book')
    PAGED_MODE_TT = _('Switch to flow mode - where the text is not broken up '
            'into pages')
    AUTOSAVE_INTERVAL = 10  # seconds
    msg_from_anotherinstance = pyqtSignal(object)

    def __init__(self, pathtoebook=None, debug_javascript=False, open_at=None,
                 start_in_fullscreen=False, continue_reading=False, listener=None, file_events=()):
        MainWindow.__init__(self, debug_javascript)
        self.view.magnification_changed.connect(self.magnification_changed)
        self.resize_events_stack = []
        self.closed = False
        self.show_toc_on_open = False
        self.listener = listener
        self.lookup_error_reported = {}
        if listener is not None:
            t = Thread(name='ConnListener', target=listen, args=(self,))
            t.daemon = True
            t.start()
            self.msg_from_anotherinstance.connect(self.another_instance_wants_to_talk, type=Qt.QueuedConnection)
        self.current_book_has_toc = False
        self.iterator          = None
        self.current_page      = None
        self.pending_search    = None
        self.pending_search_dir= None
        self.pending_anchor    = None
        self.pending_reference = None
        self.pending_bookmark  = None
        self.pending_restore   = False
        self.pending_goto_page = None
        self.pending_toc_click = None
        self.cursor_hidden     = False
        self.existing_bookmarks= []
        self.selected_text     = self.selected_html = None
        self.was_maximized     = False
        self.read_settings()
        self.autosave_timer = t = QTimer(self)
        t.setInterval(self.AUTOSAVE_INTERVAL * 1000), t.setSingleShot(True)
        t.timeout.connect(self.autosave)
        self.pos.value_changed.connect(self.update_pos_label)
        self.pos.value_changed.connect(self.autosave_timer.start)
        self.pos.setMinimumWidth(150)
        self.setFocusPolicy(Qt.StrongFocus)
        self.view.set_manager(self)
        self.pi = ProgressIndicator(self)
        self.action_quit = QAction(_('&Quit'), self)
        self.addAction(self.action_quit)
        self.view_resized_timer = QTimer(self)
        self.view_resized_timer.timeout.connect(self.viewport_resize_finished)
        self.view_resized_timer.setSingleShot(True)
        self.resize_in_progress = False
        self.action_reload = QAction(_('&Reload book'), self)
        self.action_reload.triggered.connect(self.reload_book)
        self.action_quit.triggered.connect(self.quit)
        QApplication.instance().shutdown_signal_received.connect(self.action_quit.trigger)
        self.action_reference_mode.triggered[bool].connect(self.view.reference_mode)
        self.action_metadata.triggered[bool].connect(self.metadata.setVisible)
        self.action_table_of_contents.toggled[bool].connect(self.set_toc_visible)
        self.action_copy.triggered[bool].connect(self.copy)
        self.action_font_size_larger.triggered.connect(self.font_size_larger)
        self.action_font_size_smaller.triggered.connect(self.font_size_smaller)
        self.action_open_ebook.triggered[bool].connect(self.open_ebook)
        self.action_next_page.triggered.connect(self.view.next_page)
        self.action_previous_page.triggered.connect(self.view.previous_page)
        self.action_find_next.triggered.connect(self.find_next)
        self.action_find_previous.triggered.connect(self.find_previous)
        self.action_full_screen.triggered[bool].connect(self.toggle_fullscreen)
        self.action_back.triggered[bool].connect(self.back)
        self.action_forward.triggered[bool].connect(self.forward)
        self.action_preferences.triggered.connect(self.do_config)
        self.pos.editingFinished.connect(self.goto_page_num)
        self.vertical_scrollbar.valueChanged[int].connect(lambda
                x:self.goto_page(x/100.))
        self.search.search.connect(self.find)
        self.search.focus_to_library.connect(lambda: self.view.setFocus(Qt.OtherFocusReason))
        self.toc.pressed[QModelIndex].connect(self.toc_clicked)
        self.toc.searched.connect(partial(self.toc_clicked, force=True))

        def toggle_toc(ev):
            try:
                key = self.view.shortcuts.get_match(ev)
            except AttributeError:
                pass
            if key == 'Table of Contents':
                ev.accept()
                self.action_table_of_contents.trigger()
                return True
            return False
        self.toc.handle_shortcuts = toggle_toc
        self.reference.goto.connect(self.goto)
        self.bookmarks.edited.connect(self.bookmarks_edited)
        self.bookmarks.activated.connect(self.goto_bookmark)
        self.bookmarks.create_requested.connect(self.bookmark)

        self.set_bookmarks([])
        self.load_theme_menu()

        file_events.got_file.connect(self.load_ebook)
        if pathtoebook is not None:
            f = functools.partial(self.load_ebook, pathtoebook, open_at=open_at)
            QTimer.singleShot(50, f)
        elif continue_reading:
            QTimer.singleShot(50, self.continue_reading)
        else:
            QTimer.singleShot(50, file_events.flush)
        self.window_mode_changed = None
        self.toggle_toolbar_action = QAction(_('Show/hide controls'), self)
        tts = self.view.shortcuts.get_shortcuts('Show/hide controls')
        if tts:
            self.toggle_toolbar_action.setText(self.toggle_toolbar_action.text() + '\t' + tts[0])
        self.toggle_toolbar_action.setCheckable(True)
        self.toggle_toolbar_action.triggered.connect(self.toggle_toolbars)
        self.toolbar_hidden = None
        self.addAction(self.toggle_toolbar_action)
        self.full_screen_label_anim = QPropertyAnimation(
                self.full_screen_label, b'size')
        self.clock_timer = QTimer(self)
        self.clock_timer.timeout.connect(self.update_clock)

        self.action_print.triggered.connect(self.print_book)
        self.clear_recent_history_action = QAction(
                _('Clear list of recently opened books'), self)
        self.clear_recent_history_action.triggered.connect(self.clear_recent_history)
        self.open_history_menu.aboutToShow.connect(self.build_recent_menu)
        self.open_history_menu.triggered.connect(self.open_recent)

        for x in ('tool_bar', 'tool_bar2'):
            x = getattr(self, x)
            for action in x.actions():
                # So that the keyboard shortcuts for these actions will
                # continue to function even when the toolbars are hidden
                self.addAction(action)

        for plugin in self.view.document.all_viewer_plugins:
            plugin.customize_ui(self)
        self.view.document.settings_changed.connect(self.settings_changed)

        self.restore_state()
        self.settings_changed()
        self.action_toggle_paged_mode.toggled[bool].connect(self.toggle_paged_mode)
        if (start_in_fullscreen or self.view.document.start_in_fullscreen):
            self.action_full_screen.trigger()
        self.hide_cursor_timer = t = QTimer(self)
        t.setSingleShot(True), t.setInterval(3000)
        t.timeout.connect(self.hide_cursor)
        t.start()

    def process_file_events(self):
        if self.file_events:
            self.load_ebook(self.file_events[-1])

    def eventFilter(self, obj, ev):
        if ev.type() == ev.MouseMove:
            if self.cursor_hidden:
                self.cursor_hidden = False
                QApplication.instance().restoreOverrideCursor()
            self.hide_cursor_timer.start()
        return False

    def hide_cursor(self):
        self.cursor_hidden = True
        QApplication.instance().setOverrideCursor(Qt.BlankCursor)

    def toggle_paged_mode(self, checked, at_start=False):
        in_paged_mode = not self.action_toggle_paged_mode.isChecked()
        self.view.document.in_paged_mode = in_paged_mode
        self.action_toggle_paged_mode.setToolTip(self.FLOW_MODE_TT if
                self.action_toggle_paged_mode.isChecked() else
                self.PAGED_MODE_TT)
        if at_start:
            return
        self.reload()

    def settings_changed(self):
        for x in ('', '2'):
            x = getattr(self, 'tool_bar'+x)
            x.setVisible(self.view.document.show_controls)

    def reload(self):
        if hasattr(self, 'current_index') and self.current_index > -1:
            self.view.document.page_position.save(overwrite=False)
            self.pending_restore = True
            self.load_path(self.view.last_loaded_path)

    def set_toc_visible(self, yes):
        self.toc_dock.setVisible(yes)
        if not yes:
            self.show_toc_on_open = False

    def clear_recent_history(self, *args):
        vprefs.set('viewer_open_history', [])

    def build_recent_menu(self):
        m = self.open_history_menu
        m.clear()
        recent = vprefs.get('viewer_open_history', [])
        if recent:
            m.addAction(self.clear_recent_history_action)
            m.addSeparator()
        count = 0
        for path in recent:
            if count > 9:
                break
            if os.path.exists(path):
                m.addAction(RecentAction(path, m))
                count += 1

    def continue_reading(self):
        recent = vprefs.get('viewer_open_history', [])
        if recent:
            for path in recent:
                if os.path.exists(path):
                    self.load_ebook(path)
                    break

    def shutdown(self):
        if self.isFullScreen() and not self.view.document.start_in_fullscreen:
            self.action_full_screen.trigger()
            return False
        self.save_state()
        if self.listener is not None:
            self.listener.close()
        return True

    def quit(self):
        if self.shutdown():
            QApplication.instance().quit()

    def closeEvent(self, e):
        if self.closed:
            e.ignore()
            return
        if self.shutdown():
            self.closed = True
            return MainWindow.closeEvent(self, e)
        else:
            e.ignore()

    def toggle_toolbars(self):
        for x in ('tool_bar', 'tool_bar2'):
            x = getattr(self, x)
            x.setVisible(not x.isVisible())

    def save_state(self):
        state = bytearray(self.saveState(self.STATE_VERSION))
        vprefs['main_window_state'] = state
        if not self.isFullScreen():
            vprefs.set('viewer_window_geometry', bytearray(self.saveGeometry()))
        if self.current_book_has_toc:
            vprefs.set('viewer_toc_isvisible', self.show_toc_on_open or bool(self.toc_dock.isVisible()))
        vprefs['multiplier'] = self.view.multiplier
        vprefs['in_paged_mode'] = not self.action_toggle_paged_mode.isChecked()

    def restore_state(self):
        state = vprefs.get('main_window_state', None)
        if state is not None:
            try:
                state = QByteArray(state)
                self.restoreState(state, self.STATE_VERSION)
            except:
                pass
        self.initialize_dock_state()
        mult = vprefs.get('multiplier', None)
        if mult:
            self.view.multiplier = mult
        # On windows Qt lets the user hide toolbars via a right click in a very
        # specific location, ensure they are visible.
        self.tool_bar.setVisible(True)
        self.tool_bar2.setVisible(True)
        self.toc_dock.close()  # This will be opened on book open, if the book has a toc and it was previously opened
        self.action_toggle_paged_mode.setChecked(not vprefs.get('in_paged_mode',
            True))
        self.toggle_paged_mode(self.action_toggle_paged_mode.isChecked(),
                at_start=True)

    def lookup(self, word):
        from urllib import quote
        word = word.replace(u'\u00ad', '')
        word = quote(word.encode('utf-8'))
        lang = canonicalize_lang(self.view.current_language) or get_lang() or 'en'
        try:
            url = lookup_website(lang).format(word=word)
        except Exception:
            if not self.lookup_error_reported.get(lang):
                self.lookup_error_reported[lang] = True
                error_dialog(self, _('Failed to use dictionary'), _(
                    'Failed to use the custom dictionary for language: %s Falling back to default dictionary.') % lang,
                             det_msg=traceback.format_exc(), show=True)
            url = default_lookup_website(lang).format(word=word)
        open_url(url)

    def print_book(self):
        if self.iterator is None:
            return error_dialog(self, _('No book opened'), _(
                'Cannot print as no book is opened'), show=True)
        from calibre.gui2.viewer.printing import print_book
        print_book(self.iterator.pathtoebook, self, self.current_title)

    def toggle_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    def showFullScreen(self):
        self.view.document.page_position.save()
        self.window_mode_changed = 'fullscreen'
        self.tool_bar.setVisible(False)
        self.tool_bar2.setVisible(False)
        self.was_maximized = self.isMaximized()
        if not self.view.document.fullscreen_scrollbar:
            self.vertical_scrollbar.setVisible(False)

        super(EbookViewer, self).showFullScreen()

    def show_full_screen_label(self):
        f = self.full_screen_label
        height = f.final_height
        width = int(0.7*self.view.width())
        f.resize(width, height)
        if self.view.document.show_fullscreen_help:
            f.setVisible(True)
            a = self.full_screen_label_anim
            a.setDuration(500)
            a.setStartValue(QSize(width, 0))
            a.setEndValue(QSize(width, height))
            a.start()
            QTimer.singleShot(3500, self.full_screen_label.hide)
        if self.view.document.fullscreen_clock:
            self.show_clock()
        if self.view.document.fullscreen_pos:
            self.show_pos_label()
        self.relayout_fullscreen_labels()

    def show_clock(self):
        self.clock_label.setVisible(True)
        self.clock_label.setText(QTime(22, 33,
            33).toString(Qt.SystemLocaleShortDate))
        self.clock_timer.start(1000)
        self.clock_label.setStyleSheet(self.info_label_style%(
                'rgba(0, 0, 0, 0)', self.view.document.colors()[1]))
        self.clock_label.resize(self.clock_label.sizeHint())
        self.update_clock()

    def show_pos_label(self):
        self.pos_label.setVisible(True)
        self.pos_label.setStyleSheet(self.info_label_style%(
                'rgba(0, 0, 0, 0)', self.view.document.colors()[1]))
        self.update_pos_label()

    def relayout_fullscreen_labels(self):
        vswidth = (self.vertical_scrollbar.width() if
                self.vertical_scrollbar.isVisible() else 0)
        p = self.pos_label
        p.move(15, p.parent().height() - p.height()-10)
        c = self.clock_label
        c.move(c.parent().width() - vswidth - 15 - c.width(), c.parent().height() - c.height() - 10)
        f = self.full_screen_label
        f.move((f.parent().width() - f.width())//2, (f.parent().height() - f.final_height)//2)

    def update_clock(self):
        self.clock_label.setText(QTime.currentTime().toString(Qt.SystemLocaleShortDate))

    def update_pos_label(self, *args):
        if self.pos_label.isVisible():
            try:
                value, maximum = args
            except:
                value, maximum = self.pos.value(), self.pos.maximum()
            text = '%g/%g'%(value, maximum)
            self.pos_label.setText(text)
            self.pos_label.resize(self.pos_label.sizeHint())

    def showNormal(self):
        self.view.document.page_position.save()
        self.clock_label.setVisible(False)
        self.pos_label.setVisible(False)
        self.clock_timer.stop()
        self.vertical_scrollbar.setVisible(True)
        self.window_mode_changed = 'normal'
        self.settings_changed()
        self.full_screen_label.setVisible(False)
        if self.was_maximized:
            super(EbookViewer, self).showMaximized()
        else:
            super(EbookViewer, self).showNormal()

    def goto(self, ref):
        if ref:
            tokens = ref.split('.')
            if len(tokens) > 1:
                spine_index = int(tokens[0]) -1
                if spine_index == self.current_index:
                    self.view.goto(ref)
                else:
                    self.pending_reference = ref
                    self.load_path(self.iterator.spine[spine_index])

    def goto_bookmark(self, bm):
        spine_index = bm['spine']
        if spine_index > -1 and self.current_index == spine_index:
            if self.resize_in_progress:
                self.view.document.page_position.set_pos(bm['pos'])
            else:
                self.view.goto_bookmark(bm)
                # Going to a bookmark does not call scrolled() so we update the
                # page position explicitly. Use a timer to ensure it is
                # accurate.
                QTimer.singleShot(100, self.update_page_number)
        else:
            self.pending_bookmark = bm
            if spine_index < 0 or spine_index >= len(self.iterator.spine):
                spine_index = 0
                self.pending_bookmark = None
            self.load_path(self.iterator.spine[spine_index])

    def toc_clicked(self, index, force=False):
        if force or QApplication.mouseButtons() & Qt.LeftButton:
            item = self.toc_model.itemFromIndex(index)
            if item.abspath is not None:
                if not os.path.exists(item.abspath):
                    return error_dialog(self, _('No such location'),
                            _('The location pointed to by this item'
                                ' does not exist.'), det_msg=item.abspath, show=True)
                url = self.view.as_url(item.abspath)
                if item.fragment:
                    url.setFragment(item.fragment)
                self.link_clicked(url)
        self.view.setFocus(Qt.OtherFocusReason)

    def selection_changed(self, selected_text, selected_html):
        self.selected_text = selected_text
        self.selected_html = selected_html
        self.action_copy.setEnabled(bool(self.selected_text) or bool(self.selected_html))

    def copy(self, x=False):
        if self.selected_text or self.selected_html:
            md = QMimeData()
            if self.selected_text:
                md.setText(self.selected_text)
            if self.selected_html:
                md.setHtml(self.selected_html)
            QApplication.clipboard().setMimeData(md)

    def back(self, x):
        pos = self.history.back(self.pos.value())
        if pos is not None:
            self.goto_page(pos)

    def goto_page_num(self):
        num = self.pos.value()
        self.goto_page(num)

    def forward(self, x):
        pos = self.history.forward(self.pos.value())
        if pos is not None:
            self.goto_page(pos)

    def goto_start(self):
        self.goto_page(1)

    def goto_end(self):
        self.goto_page(self.pos.maximum())

    def goto_page(self, new_page, loaded_check=True):
        if self.current_page is not None or not loaded_check:
            for page in self.iterator.spine:
                if new_page >= page.start_page and new_page <= page.max_page:
                    try:
                        frac = float(new_page-page.start_page)/(page.pages-1)
                    except ZeroDivisionError:
                        frac = 0
                    if page == self.current_page:
                        self.view.scroll_to(frac)
                    else:
                        self.load_path(page, pos=frac)

    def open_ebook(self, checked):
        files = choose_files(self, 'ebook viewer open dialog',
                     _('Choose e-book'),
                     [(_('E-books'), available_input_formats())],
                     all_files=False,
                     select_only_single_file=True)
        if files:
            self.load_ebook(files[0])

    def open_recent(self, action):
        if hasattr(action, 'path'):
            self.load_ebook(action.path)

    def font_size_larger(self):
        self.view.magnify_fonts()

    def font_size_smaller(self):
        self.view.shrink_fonts()

    def magnification_changed(self, val):
        tt = '%(action)s [%(sc)s]\n'+_('Current magnification: %(mag).1f')
        sc = _(' or ').join(self.view.shortcuts.get_shortcuts('Font larger'))
        self.action_font_size_larger.setToolTip(
                tt %dict(action=unicode(self.action_font_size_larger.text()),
                         mag=val, sc=sc))
        sc = _(' or ').join(self.view.shortcuts.get_shortcuts('Font smaller'))
        self.action_font_size_smaller.setToolTip(
                tt %dict(action=unicode(self.action_font_size_smaller.text()),
                         mag=val, sc=sc))
        self.action_font_size_larger.setEnabled(self.view.multiplier < 3)
        self.action_font_size_smaller.setEnabled(self.view.multiplier > 0.2)

    def find(self, text, repeat=False, backwards=False):
        if not text:
            self.view.search('')
            return self.search.search_done(False)
        if self.view.search(text, backwards=backwards):
            self.scrolled(self.view.scroll_fraction)
            return self.search.search_done(True)
        index = self.iterator.search(text, self.current_index,
                backwards=backwards)
        if index is None:
            if self.current_index > 0:
                index = self.iterator.search(text, 0)
                if index is None:
                    info_dialog(self, _('No matches found'),
                                _('No matches found for: %s')%text).exec_()
                    return self.search.search_done(True)
            return self.search.search_done(True)
        self.pending_search = text
        self.pending_search_dir = 'backwards' if backwards else 'forwards'
        self.load_path(self.iterator.spine[index])

    def find_next(self):
        self.find(unicode(self.search.text()), repeat=True)

    def find_previous(self):
        self.find(unicode(self.search.text()), repeat=True, backwards=True)

    def do_search(self, text, backwards):
        self.pending_search = None
        self.pending_search_dir = None
        if self.view.search(text, backwards=backwards):
            self.scrolled(self.view.scroll_fraction)

    def internal_link_clicked(self, prev_pos):
        self.history.add(prev_pos)

    def link_clicked(self, url):
        path = self.view.path(url)
        frag = None
        if path in self.iterator.spine:
            self.update_page_number()  # Ensure page number is accurate as it is used for history
            self.history.add(self.pos.value())
            path = self.iterator.spine[self.iterator.spine.index(path)]
            if url.hasFragment():
                frag = unicode(url.fragment())
            if path != self.current_page:
                self.pending_anchor = frag
                self.load_path(path)
            else:
                oldpos = self.view.document.ypos
                if frag:
                    self.view.scroll_to(frag)
                else:
                    # Scroll to top
                    self.view.scroll_to(0)
                if self.view.document.ypos == oldpos:
                    # If we are coming from goto_next_section() call this will
                    # cause another goto next section call with the next toc
                    # entry, since this one did not cause any scrolling at all.
                    QTimer.singleShot(10, self.update_indexing_state)
        else:
            open_url(url)

    def load_started(self):
        self.open_progress_indicator(_('Loading flow...'))

    def load_finished(self, ok):
        self.close_progress_indicator()
        path = self.view.path()
        try:
            index = self.iterator.spine.index(path)
        except (ValueError, AttributeError):
            return -1
        self.current_page = self.iterator.spine[index]
        self.current_index = index
        self.set_page_number(self.view.scroll_fraction)
        QTimer.singleShot(100, self.update_indexing_state)
        if self.pending_search is not None:
            self.do_search(self.pending_search,
                    self.pending_search_dir=='backwards')
            self.pending_search = None
            self.pending_search_dir = None
        if self.pending_anchor is not None:
            self.view.scroll_to(self.pending_anchor)
            self.pending_anchor = None
        if self.pending_reference is not None:
            self.view.goto(self.pending_reference)
            self.pending_reference = None
        if self.pending_bookmark is not None:
            self.goto_bookmark(self.pending_bookmark)
            self.pending_bookmark = None
        if self.pending_restore:
            self.view.document.page_position.restore()
        return self.current_index

    def goto_next_section(self):
        if hasattr(self, 'current_index'):
            entry = self.toc_model.next_entry(self.current_index,
                    self.view.document.read_anchor_positions(),
                    self.view.viewport_rect, self.view.document.in_paged_mode)
            if entry is not None:
                self.pending_goto_next_section = (
                        self.toc_model.currently_viewed_entry, entry, False)
                self.toc_clicked(entry.index(), force=True)

    def goto_previous_section(self):
        if hasattr(self, 'current_index'):
            entry = self.toc_model.next_entry(self.current_index,
                    self.view.document.read_anchor_positions(),
                    self.view.viewport_rect, self.view.document.in_paged_mode,
                    backwards=True)
            if entry is not None:
                self.pending_goto_next_section = (
                        self.toc_model.currently_viewed_entry, entry, True)
                self.toc_clicked(entry.index(), force=True)

    def update_indexing_state(self, anchor_positions=None):
        pgns = getattr(self, 'pending_goto_next_section', None)
        if hasattr(self, 'current_index'):
            if anchor_positions is None:
                anchor_positions = self.view.document.read_anchor_positions()
            items = self.toc_model.update_indexing_state(self.current_index,
                        self.view.viewport_rect, anchor_positions,
                        self.view.document.in_paged_mode)
            if items:
                self.toc.scrollTo(items[-1].index())
            if pgns is not None:
                self.pending_goto_next_section = None
                # Check that we actually progressed
                if pgns[0] is self.toc_model.currently_viewed_entry:
                    entry = self.toc_model.next_entry(self.current_index,
                            self.view.document.read_anchor_positions(),
                            self.view.viewport_rect,
                            self.view.document.in_paged_mode,
                            backwards=pgns[2], current_entry=pgns[1])
                    if entry is not None:
                        self.pending_goto_next_section = (
                                self.toc_model.currently_viewed_entry, entry,
                                pgns[2])
                        self.toc_clicked(entry.index(), force=True)

    def load_path(self, path, pos=0.0):
        self.open_progress_indicator(_('Laying out %s')%self.current_title)
        self.view.load_path(path, pos=pos)

    def viewport_resize_started(self, event):
        if not self.resize_in_progress:
            # First resize, so save the current page position
            self.resize_in_progress = True
            re = ResizeEvent(event.oldSize(), self.view.multiplier, self.view.last_loaded_path, self.view.document.page_number)
            self.resize_events_stack.append(re)
            if not self.window_mode_changed:
                # The special handling for window mode changed will already
                # have saved page position, so only save it if this is not a
                # mode change
                self.view.document.page_position.save()

        if self.resize_in_progress:
            self.view_resized_timer.start(75)

    def viewport_resize_finished(self):
        # There hasn't been a resize event for some time
        # restore the current page position.
        self.resize_in_progress = False
        wmc, self.window_mode_changed = self.window_mode_changed, None
        fs = wmc == 'fullscreen'
        if wmc:
            # Sets up body text margins, which can be limited in fs mode by a
            # separate config option, so must be done before relayout of text
            (self.view.document.switch_to_fullscreen_mode if fs else self.view.document.switch_to_window_mode)()
        # Re-layout text, must be done before restoring page position
        self.view.document.after_resize()
        if wmc:
            # This resize is part of a window mode change, special case it
            if fs:
                self.show_full_screen_label()
            self.view.document.page_position.restore()
            self.scrolled(self.view.scroll_fraction)
        else:
            if self.isFullScreen():
                self.relayout_fullscreen_labels()
            self.view.document.page_position.restore()
            self.update_page_number()

        if self.pending_goto_page is not None:
            pos, self.pending_goto_page = self.pending_goto_page, None
            self.goto_page(pos, loaded_check=False)
        elif self.pending_toc_click is not None:
            index, self.pending_toc_click = self.pending_toc_click, None
            self.toc_clicked(index, force=True)
        else:
            if self.resize_events_stack:
                self.resize_events_stack[-1].finished(self.view.size(), self.view.multiplier, self.view.last_loaded_path, self.view.document.page_number)
                if len(self.resize_events_stack) > 1:
                    previous, current = self.resize_events_stack[-2:]
                    if current.is_a_toggle(previous) and previous.page_number is not None and self.view.document.in_paged_mode:
                        if DEBUG:
                            print('Detected a toggle resize, restoring previous page')
                        self.view.document.page_number = previous.page_number
                        del self.resize_events_stack[-2:]
                    else:
                        del self.resize_events_stack[-2]

    def update_page_number(self):
        self.set_page_number(self.view.document.scroll_fraction)
        return self.pos.value()

    def close_progress_indicator(self):
        self.pi.stop()
        for o in ('tool_bar', 'tool_bar2', 'view', 'horizontal_scrollbar', 'vertical_scrollbar'):
            getattr(self, o).setEnabled(True)
        self.unsetCursor()
        self.view.setFocus(Qt.PopupFocusReason)

    def open_progress_indicator(self, msg=''):
        self.pi.start(msg)
        for o in ('tool_bar', 'tool_bar2', 'view', 'horizontal_scrollbar', 'vertical_scrollbar'):
            getattr(self, o).setEnabled(False)
        self.setCursor(Qt.BusyCursor)

    def load_theme_menu(self):
        from calibre.gui2.viewer.config import load_themes
        self.themes_menu.clear()
        for key in load_themes():
            title = key[len('theme_'):]
            self.themes_menu.addAction(title, partial(self.load_theme,
                key))

    def load_theme(self, theme_id):
        self.view.load_theme(theme_id)

    def do_config(self):
        self.view.config(self)
        self.load_theme_menu()
        if self.iterator is not None:
            self.iterator.copy_bookmarks_to_file = self.view.document.copy_bookmarks_to_file
        from calibre.gui2 import config
        if not config['viewer_search_history']:
            self.search.clear_history()

    def bookmark(self, *args):
        num = 1
        bm = None
        while True:
            bm = _('Bookmark #%d')%num
            if bm not in self.existing_bookmarks:
                break
            num += 1
        title, ok = QInputDialog.getText(self, _('Add bookmark'),
                _('Enter title for bookmark:'), text=bm)
        title = unicode(title).strip()
        if ok and title:
            bm = self.view.bookmark()
            bm['spine'] = self.current_index
            bm['title'] = title
            self.iterator.add_bookmark(bm)
            self.set_bookmarks(self.iterator.bookmarks)
            self.bookmarks.set_current_bookmark(bm)

    def autosave(self):
        self.save_current_position(no_copy_to_file=True)

    def bookmarks_edited(self, bookmarks):
        self.build_bookmarks_menu(bookmarks)
        self.iterator.set_bookmarks(bookmarks)
        self.iterator.save_bookmarks()

    def build_bookmarks_menu(self, bookmarks):
        self.bookmarks_menu.clear()
        sc = _(' or ').join(self.view.shortcuts.get_shortcuts('Bookmark'))
        self.bookmarks_menu.addAction(_("Bookmark this location [%s]") % sc, self.bookmark)
        self.bookmarks_menu.addAction(_("Show/hide bookmarks"), self.bookmarks_dock.toggleViewAction().trigger)
        self.bookmarks_menu.addSeparator()
        current_page = None
        self.existing_bookmarks = []
        for bm in bookmarks:
            if bm['title'] == 'calibre_current_page_bookmark':
                if self.view.document.remember_current_page:
                    current_page = bm
            else:
                self.existing_bookmarks.append(bm['title'])
                self.bookmarks_menu.addAction(bm['title'], partial(self.goto_bookmark, bm))
        return current_page

    def set_bookmarks(self, bookmarks):
        self.bookmarks.set_bookmarks(bookmarks)
        return self.build_bookmarks_menu(bookmarks)

    @property
    def current_page_bookmark(self):
        bm = self.view.bookmark()
        bm['spine'] = self.current_index
        bm['title'] = 'calibre_current_page_bookmark'
        return bm

    def save_current_position(self, no_copy_to_file=False):
        if not self.view.document.remember_current_page:
            return
        if hasattr(self, 'current_index'):
            try:
                self.iterator.add_bookmark(self.current_page_bookmark, no_copy_to_file=no_copy_to_file)
            except:
                traceback.print_exc()

    def another_instance_wants_to_talk(self, msg):
        try:
            path, open_at = msg
        except Exception:
            return
        self.load_ebook(path, open_at=open_at)
        self.raise_()

    def load_ebook(self, pathtoebook, open_at=None, reopen_at=None):
        del self.resize_events_stack[:]
        if self.iterator is not None:
            self.save_current_position()
            self.iterator.__exit__()
        self.iterator = EbookIterator(pathtoebook, copy_bookmarks_to_file=self.view.document.copy_bookmarks_to_file, use_tdir_in_cache=True)
        self.history.clear()
        self.open_progress_indicator(_('Loading e-book...'))
        worker = Worker(target=partial(self.iterator.__enter__, view_kepub=True))
        worker.path_to_ebook = pathtoebook
        worker.start()
        while worker.isAlive():
            worker.join(0.1)
            QApplication.processEvents()
        self.view.settings().clearMemoryCaches()
        if worker.exception is not None:
            tb = worker.traceback.strip()
            if tb and tb.splitlines()[-1].startswith('DRMError:'):
                from calibre.gui2.dialogs.drm_error import DRMErrorMessage
                DRMErrorMessage(self).exec_()
            else:
                r = getattr(worker.exception, 'reason', worker.exception)
                error_dialog(self, _('Could not open e-book'),
                        as_unicode(r) or _('Unknown error'),
                        det_msg=tb, show=True)
            self.close_progress_indicator()
        else:
            self.metadata.show_metadata(self.iterator.mi, self.iterator.book_format)
            self.view.current_language = self.iterator.language
            title = self.iterator.mi.title
            if not title:
                title = os.path.splitext(os.path.basename(pathtoebook))[0]
            if self.iterator.toc:
                self.toc_model = TOC(self.iterator.spine, self.iterator.toc)
                self.toc.setModel(self.toc_model)
                if self.show_toc_on_open:
                    self.action_table_of_contents.setChecked(True)
            else:
                self.toc_model = TOC(self.iterator.spine)
                self.toc.setModel(self.toc_model)
                self.action_table_of_contents.setChecked(False)
            if isbytestring(pathtoebook):
                pathtoebook = force_unicode(pathtoebook, filesystem_encoding)
            pathtoebook = os.path.abspath(pathtoebook)
            vh = vprefs.get('viewer_open_history', [])
            try:
                vh.remove(pathtoebook)
            except:
                pass
            vh.insert(0, pathtoebook)
            vprefs.set('viewer_open_history', vh[:50])
            if iswindows:
                try:
                    add_to_recent_docs(pathtoebook)
                except Exception:
                    import traceback
                    traceback.print_exc()
            self.view.set_book_data(self.iterator)

            self.footnotes_dock.close()
            self.action_table_of_contents.setDisabled(not self.iterator.toc)
            self.current_book_has_toc = bool(self.iterator.toc)
            self.current_title = title
            self.setWindowTitle(title + ' [%s]'%self.iterator.book_format + ' - ' + self.base_window_title)
            self.pos.setMaximum(sum(self.iterator.pages))
            self.pos.setSuffix(' / %d'%sum(self.iterator.pages))
            self.vertical_scrollbar.setMinimum(100)
            self.vertical_scrollbar.setMaximum(100*sum(self.iterator.pages))
            self.vertical_scrollbar.setSingleStep(10)
            self.vertical_scrollbar.setPageStep(100)
            self.set_vscrollbar_value(1)
            self.current_index = -1
            QApplication.instance().alert(self, 5000)
            previous = self.set_bookmarks(self.iterator.bookmarks)
            if reopen_at is not None:
                previous = reopen_at
            if open_at is None and previous is not None:
                self.goto_bookmark(previous)
            else:
                if open_at is None:
                    self.next_document()
                else:
                    if isinstance(open_at, float):
                        open_at = max(self.pos.minimum(), min(open_at, self.pos.maximum()))
                        if self.resize_in_progress:
                            self.pending_goto_page = open_at
                        else:
                            self.goto_page(open_at, loaded_check=False)
                    elif open_at.startswith('toc:'):
                        index = self.toc_model.search(open_at[4:])
                        if index.isValid():
                            if self.resize_in_progress:
                                self.pending_toc_click = index
                            else:
                                self.toc_clicked(index, force=True)

    def set_vscrollbar_value(self, pagenum):
        self.vertical_scrollbar.blockSignals(True)
        self.vertical_scrollbar.setValue(int(pagenum*100))
        self.vertical_scrollbar.blockSignals(False)

    def set_page_number(self, frac):
        if getattr(self, 'current_page', None) is not None:
            page = self.current_page.start_page + frac*float(self.current_page.pages-1)
            self.pos.set_value(page)
            self.set_vscrollbar_value(page)

    def scrolled(self, frac, onload=False):
        self.set_page_number(frac)
        if not onload:
            ap = self.view.document.read_anchor_positions()
            self.update_indexing_state(ap)

    def next_document(self):
        if (hasattr(self, 'current_index') and self.current_index <
                len(self.iterator.spine) - 1):
            self.load_path(self.iterator.spine[self.current_index+1])

    def previous_document(self):
        if hasattr(self, 'current_index') and self.current_index > 0:
            self.load_path(self.iterator.spine[self.current_index-1], pos=1.0)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            if self.metadata.isVisible():
                self.metadata.setVisible(False)
                event.accept()
                return
            if self.isFullScreen():
                self.action_full_screen.trigger()
                event.accept()
                return
        try:
            key = self.view.shortcuts.get_match(event)
        except AttributeError:
            return MainWindow.keyPressEvent(self, event)
        try:
            bac = self.bookmarks_menu.actions()[0]
        except (AttributeError, TypeError, IndexError, KeyError):
            bac = None
        action = {
            'Quit':self.action_quit,
            'Show metadata':self.action_metadata,
            'Copy':self.action_copy,
            'Font larger': self.action_font_size_larger,
            'Font smaller': self.action_font_size_smaller,
            'Fullscreen': self.action_full_screen,
            'Find next': self.action_find_next,
            'Find previous': self.action_find_previous,
            'Search online': self.view.search_online_action,
            'Lookup word': self.view.dictionary_action,
            'Next occurrence': self.view.search_action,
            'Bookmark': bac,
            'Reload': self.action_reload,
            'Table of Contents': self.action_table_of_contents,
            'Print': self.action_print,
            'Show/hide controls': self.toggle_toolbar_action,
        }.get(key, None)
        if action is not None:
            event.accept()
            action.trigger()
            return
        if key == 'Focus Search':
            if not self.tool_bar.isVisible():
                self.toggle_toolbars()
            self.search.setFocus(Qt.OtherFocusReason)
            self.search.lineEdit().selectAll()
            return
        if not self.view.handle_key_press(event):
            event.ignore()

    def reload_book(self):
        if getattr(self.iterator, 'pathtoebook', None):
            try:
                reopen_at = self.current_page_bookmark
            except Exception:
                reopen_at = None
            self.history.clear()
            self.load_ebook(self.iterator.pathtoebook, reopen_at=reopen_at)
            return

    def __enter__(self):
        return self

    def __exit__(self, *args):
        if self.iterator is not None:
            self.save_current_position()
            self.iterator.__exit__(*args)

    def read_settings(self):
        c = config().parse()
        if c.remember_window_size:
            wg = vprefs.get('viewer_window_geometry', None)
            if wg is not None:
                self.restoreGeometry(wg)
        self.show_toc_on_open = vprefs.get('viewer_toc_isvisible', False)
        desktop  = QApplication.instance().desktop()
        av = desktop.availableGeometry(self).height() - 30
        if self.height() > av:
            self.resize(self.width(), av)

    def show_footnote_view(self):
        self.footnotes_dock.show()


def config(defaults=None):
    desc = _('Options to control the e-book viewer')
    if defaults is None:
        c = Config('viewer', desc)
    else:
        c = StringConfig(defaults, desc)

    c.add_opt('raise_window', ['--raise-window'], default=False,
              help=_('If specified, viewer window will try to come to the '
                     'front when started.'))
    c.add_opt('full_screen', ['--full-screen', '--fullscreen', '-f'], default=False,
              help=_('If specified, viewer window will try to open '
                     'full screen when started.'))
    c.add_opt('remember_window_size', default=False,
        help=_('Remember last used window size'))
    c.add_opt('debug_javascript', ['--debug-javascript'], default=False,
        help=_('Print javascript alert and console messages to the console'))
    c.add_opt('open_at', ['--open-at'], default=None,
        help=_('The position at which to open the specified book. The position is '
               'a location as displayed in the top left corner of the viewer. '
               'Alternately, you can use the form toc:something and it will open '
               'at the location of the first Table of Contents entry that contains the string "something".'))
    c.add_opt('continue_reading', ['--continue'], default=False,
        help=_('Continue reading at the previously opened book'))

    return c


def option_parser():
    c = config()
    parser = c.option_parser(usage=_('''\
%prog [options] file

View an e-book.
'''))
    setup_gui_option_parser(parser)
    return parser


def create_listener():
    if islinux:
        from calibre.utils.ipc.server import LinuxListener as Listener
    else:
        from multiprocessing.connection import Listener
    return Listener(address=viewer_socket_address())


def ensure_single_instance(args, open_at):
    try:
        from calibre.utils.lock import singleinstance
        si = singleinstance(singleinstance_name)
    except Exception:
        import traceback
        error_dialog(None, _('Cannot start viewer'), _(
            'Failed to start viewer, could not insure only a single instance of the viewer is running. Click "Show Details" for more information'),
                    det_msg=traceback.format_exc(), show=True)
        raise SystemExit(1)
    if not si:
        if len(args) > 1:
            t = RC(print_error=True, socket_address=viewer_socket_address())
            t.start()
            t.join(3.0)
            if t.is_alive() or t.conn is None:
                error_dialog(None, _('Connect to viewer failed'), _(
                    'Unable to connect to existing viewer window, try restarting the viewer.'), show=True)
                raise SystemExit(1)
            t.conn.send((os.path.abspath(args[1]), open_at))
            t.conn.close()
            prints('Opened book in existing viewer instance')
        raise SystemExit(0)
    listener = create_listener()
    return listener


class EventAccumulator(QObject):

    got_file = pyqtSignal(object)

    def __init__(self):
        QObject.__init__(self)
        self.events = []

    def __call__(self, paths):
        for path in paths:
            if os.path.exists(path):
                self.events.append(path)
                self.got_file.emit(path)

    def flush(self):
        if self.events:
            self.got_file.emit(self.events[-1])
            self.events = []


def main(args=sys.argv):
    # Ensure viewer can continue to function if GUI is closed
    os.environ.pop('CALIBRE_WORKER_TEMP_DIR', None)
    reset_base_dir()
    if iswindows:
        # Ensure that all ebook editor instances are grouped together in the task
        # bar. This prevents them from being grouped with viewer process when
        # launched from within calibre, as both use calibre-parallel.exe
        set_app_uid(VIEWER_APP_UID)

    parser = option_parser()
    opts, args = parser.parse_args(args)
    open_at = None
    if opts.open_at is not None:
        if opts.open_at.startswith('toc:'):
            open_at = opts.open_at
        else:
            open_at = float(opts.open_at.replace(',', '.'))
    listener = None
    override = 'calibre-ebook-viewer' if islinux else None
    acc = EventAccumulator()
    app = Application(args, override_program_name=override, color_prefs=vprefs)
    app.file_event_hook = acc
    app.load_builtin_fonts()
    app.setWindowIcon(QIcon(I('viewer.png')))

    if vprefs['singleinstance']:
        try:
            listener = ensure_single_instance(args, open_at)
        except Exception as e:
            import traceback
            error_dialog(None, _('Failed to start viewer'), as_unicode(e), det_msg=traceback.format_exc(), show=True)
            raise SystemExit(1)

    main = EbookViewer(args[1] if len(args) > 1 else None,
            debug_javascript=opts.debug_javascript, open_at=open_at, continue_reading=opts.continue_reading,
                       start_in_fullscreen=opts.full_screen, listener=listener, file_events=acc)
    app.installEventFilter(main)
    # This is needed for paged mode. Without it, the first document that is
    # loaded will have extra blank space at the bottom, as
    # turn_off_internal_scrollbars does not take effect for the first
    # rendered document
    main.view.load_path(P('viewer/blank.html', allow_user_override=False))
    main.set_exception_handler()
    main.show()
    if opts.raise_window:
        main.raise_()
    with main:
        return app.exec_()
    return 0


if __name__ == '__main__':
    sys.exit(main())
