#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

import os
from functools import partial
from itertools import product
from future_builtins import map

from PyQt4.Qt import (
    QDockWidget, Qt, QLabel, QIcon, QAction, QApplication, QWidget, QEvent,
    QVBoxLayout, QStackedWidget, QTabWidget, QImage, QPixmap, pyqtSignal,
    QMenu, QHBoxLayout, QTimer, QUrl)

from calibre.constants import __appname__, get_version, isosx
from calibre.gui2 import elided_text, open_url
from calibre.gui2.keyboard import Manager as KeyboardManager
from calibre.gui2.main_window import MainWindow
from calibre.gui2.throbber import ThrobbingButton, create_donate_widget
from calibre.gui2.tweak_book import current_container, tprefs, actions, capitalize
from calibre.gui2.tweak_book.file_list import FileListWidget
from calibre.gui2.tweak_book.job import BlockingJob
from calibre.gui2.tweak_book.boss import Boss
from calibre.gui2.tweak_book.undo import CheckpointView
from calibre.gui2.tweak_book.preview import Preview
from calibre.gui2.tweak_book.search import SearchPanel
from calibre.gui2.tweak_book.check import Check
from calibre.gui2.tweak_book.toc import TOCViewer
from calibre.gui2.tweak_book.char_select import CharSelect
from calibre.gui2.tweak_book.editor.widget import register_text_editor_actions
from calibre.gui2.tweak_book.editor.insert_resource import InsertImage
from calibre.utils.icu import character_name

def open_donate():
    open_url(QUrl('http://calibre-ebook.com/donate'))

class Central(QStackedWidget):  # {{{

    ' The central widget, hosts the editors '

    current_editor_changed = pyqtSignal()
    close_requested = pyqtSignal(object)

    def __init__(self, parent=None):
        QStackedWidget.__init__(self, parent)
        self.welcome = w = QLabel('<p>'+_(
            'Double click a file in the left panel to start editing'
            ' it.'))
        self.addWidget(w)
        w.setWordWrap(True)
        w.setAlignment(Qt.AlignTop | Qt.AlignHCenter)

        self.container = c = QWidget(self)
        self.addWidget(c)
        l = c.l = QVBoxLayout(c)
        c.setLayout(l)
        l.setContentsMargins(0, 0, 0, 0)
        self.editor_tabs = t = QTabWidget(c)
        l.addWidget(t)
        t.setDocumentMode(True)
        t.setTabsClosable(True)
        t.setMovable(True)
        pal = self.palette()
        if pal.color(pal.WindowText).lightness() > 128:
            i = QImage(I('modified.png'))
            i.invertPixels()
            self.modified_icon = QIcon(QPixmap.fromImage(i))
        else:
            self.modified_icon = QIcon(I('modified.png'))
        self.editor_tabs.currentChanged.connect(self.current_editor_changed)
        self.editor_tabs.tabCloseRequested.connect(self._close_requested)
        self.search_panel = SearchPanel(self)
        l.addWidget(self.search_panel)
        self.restore_state()
        self.editor_tabs.tabBar().installEventFilter(self)

    def _close_requested(self, index):
        editor = self.editor_tabs.widget(index)
        self.close_requested.emit(editor)

    def add_editor(self, name, editor):
        fname = name.rpartition('/')[2]
        index = self.editor_tabs.addTab(editor, fname)
        self.editor_tabs.setTabToolTip(index, _('Full path:') + ' ' + name)
        editor.modification_state_changed.connect(self.editor_modified)

    def rename_editor(self, editor, name):
        for i in xrange(self.editor_tabs.count()):
            if self.editor_tabs.widget(i) is editor:
                fname = name.rpartition('/')[2]
                self.editor_tabs.setTabText(i, fname)
                self.editor_tabs.setTabToolTip(i, _('Full path:') + ' ' + name)

    def show_editor(self, editor):
        self.setCurrentIndex(1)
        self.editor_tabs.setCurrentWidget(editor)

    def close_editor(self, editor):
        for i in xrange(self.editor_tabs.count()):
            if self.editor_tabs.widget(i) is editor:
                self.editor_tabs.removeTab(i)
                if self.editor_tabs.count() == 0:
                    self.setCurrentIndex(0)
                return True
        return False

    def editor_modified(self, *args):
        tb = self.editor_tabs.tabBar()
        for i in xrange(self.editor_tabs.count()):
            editor = self.editor_tabs.widget(i)
            modified = getattr(editor, 'is_modified', False)
            tb.setTabIcon(i, self.modified_icon if modified else QIcon())

    def close_current_editor(self):
        ed = self.current_editor
        if ed is not None:
            self.close_requested.emit(ed)

    def close_all_but_current_editor(self):
        self.close_all_but(self.current_editor)

    def close_all_but(self, ed):
        close = []
        if ed is not None:
            for i in xrange(self.editor_tabs.count()):
                q = self.editor_tabs.widget(i)
                if q is not None and q is not ed:
                    close.append(q)
        for q in close:
            self.close_requested.emit(q)

    @property
    def current_editor(self):
        return self.editor_tabs.currentWidget()

    def save_state(self):
        tprefs.set('search-panel-visible', self.search_panel.isVisible())
        self.search_panel.save_state()

    def restore_state(self):
        self.search_panel.setVisible(tprefs.get('search-panel-visible', False))
        self.search_panel.restore_state()

    def show_find(self):
        self.search_panel.show_panel()

    def pre_fill_search(self, text):
        self.search_panel.pre_fill(text)

    def eventFilter(self, obj, event):
        base = super(Central, self)
        if obj is not self.editor_tabs.tabBar() or event.type() != QEvent.MouseButtonPress or event.button() not in (Qt.RightButton, Qt.MidButton):
            return base.eventFilter(obj, event)
        index = self.editor_tabs.tabBar().tabAt(event.pos())
        if index < 0:
            return base.eventFilter(obj, event)
        if event.button() == Qt.MidButton:
            self._close_requested(index)
        ed = self.editor_tabs.widget(index)
        if ed is not None:
            menu = QMenu(self)
            menu.addAction(actions['close-current-tab'].icon(), _('Close tab'), partial(self.close_requested.emit, ed))
            menu.addSeparator()
            menu.addAction(actions['close-all-but-current-tab'].icon(), _('Close other tabs'), partial(self.close_all_but, ed))
            menu.exec_(self.editor_tabs.tabBar().mapToGlobal(event.pos()))

        return True
# }}}

class CursorPositionWidget(QWidget):  # {{{

    def __init__(self, parent):
        QWidget.__init__(self, parent)
        self.l = QHBoxLayout(self)
        self.setLayout(self.l)
        self.la = QLabel('')
        self.l.addWidget(self.la)
        self.l.setContentsMargins(0, 0, 0, 0)
        f = self.la.font()
        f.setBold(False)
        self.la.setFont(f)

    def update_position(self, line=None, col=None, character=None):
        if line is None:
            self.la.setText('')
        else:
            try:
                name = character_name(character) if character and tprefs['editor_show_char_under_cursor'] else None
            except Exception:
                name = None
            text = _('Line: {0} : {1}').format(line, col)
            if not name:
                name = {'\t':'TAB'}.get(character, None)
            if name and tprefs['editor_show_char_under_cursor']:
                text = name + ' : ' + text
            self.la.setText(text)
# }}}

class Main(MainWindow):

    APP_NAME = _('Edit Book')
    STATE_VERSION = 0

    def __init__(self, opts, notify=None):
        MainWindow.__init__(self, opts, disable_automatic_gc=True)
        self.boss = Boss(self, notify=notify)
        self.setWindowTitle(self.APP_NAME)
        self.setWindowIcon(QIcon(I('tweak.png')))
        self.opts = opts
        self.path_to_ebook = None
        self.container = None
        self.current_metadata = None
        self.blocking_job = BlockingJob(self)
        self.keyboard = KeyboardManager(self, config_name='shortcuts/tweak_book')

        self.central = Central(self)
        self.setCentralWidget(self.central)
        self.check_book = Check(self)
        self.toc_view = TOCViewer(self)
        self.image_browser = InsertImage(self, for_browsing=True)
        self.insert_char = CharSelect(self)

        self.create_actions()
        self.create_toolbars()
        self.create_docks()
        self.create_menubar()

        self.status_bar = self.statusBar()
        self.status_bar.addPermanentWidget(self.boss.save_manager.status_widget)
        self.cursor_position_widget = CursorPositionWidget(self)
        self.status_bar.addPermanentWidget(self.cursor_position_widget)
        self.status_bar_default_msg = la = QLabel(_('{0} {1} created by {2}').format(__appname__, get_version(), 'Kovid Goyal'))
        la.base_template = unicode(la.text())
        self.status_bar.addWidget(la)
        f = self.status_bar.font()
        f.setBold(True)
        self.status_bar.setFont(f)

        self.boss(self)
        g = QApplication.instance().desktop().availableGeometry(self)
        self.resize(g.width()-50, g.height()-50)

        self.restore_state()
        self.apply_settings()

    def apply_settings(self):
        self.keyboard.finalize()
        self.setDockNestingEnabled(tprefs['nestable_dock_widgets'])
        for v, h in product(('top', 'bottom'), ('left', 'right')):
            p = 'dock_%s_%s' % (v, h)
            pref = tprefs[p] or tprefs.defaults[p]
            area = getattr(Qt, '%sDockWidgetArea' % capitalize({'vertical':h, 'horizontal':v}[pref]))
            self.setCorner(getattr(Qt, '%s%sCorner' % tuple(map(capitalize, (v, h)))), area)
        self.preview.apply_settings()

    def show_status_message(self, msg, timeout=5):
        self.status_bar.showMessage(msg, int(timeout*1000))

    def elided_text(self, text, width=300):
        return elided_text(text, font=self.font(), width=width)

    @property
    def editor_tabs(self):
        return self.central.editor_tabs

    def create_actions(self):
        group = _('Global Actions')

        def reg(icon, text, target, sid, keys, description):
            if not isinstance(icon, QIcon):
                icon = QIcon(I(icon))
            ac = actions[sid] = QAction(icon, text, self) if icon else QAction(text, self)
            ac.setObjectName('action-' + sid)
            if target is not None:
                ac.triggered.connect(target)
            if isinstance(keys, type('')):
                keys = (keys,)
            self.keyboard.register_shortcut(
                sid, unicode(ac.text()).replace('&', ''), default_keys=keys, description=description, action=ac, group=group)
            self.addAction(ac)
            return ac

        self.action_new_file = reg('document-new.png', _('&New file (images/fonts/HTML/etc.)'), self.boss.add_file,
                                   'new-file', (), _('Create a new file in the current book'))
        self.action_import_files = reg(None, _('&Import files into book'), self.boss.add_files, 'new-files', (), _('Import files into book'))
        self.action_open_book = reg('document_open.png', _('Open &book'), self.boss.open_book, 'open-book', 'Ctrl+O', _('Open a new book'))
        # Qt does not generate shortcut overrides for cmd+arrow on os x which
        # means these shortcuts interfere with editing
        self.action_global_undo = reg('back.png', _('&Revert to before'), self.boss.do_global_undo, 'global-undo', () if isosx else 'Ctrl+Left',
                                      _('Revert book to before the last action (Undo)'))
        self.action_global_redo = reg('forward.png', _('&Revert to after'), self.boss.do_global_redo, 'global-redo', () if isosx else 'Ctrl+Right',
                                      _('Revert book state to after the next action (Redo)'))
        self.action_save = reg('save.png', _('&Save'), self.boss.save_book, 'save-book', 'Ctrl+S', _('Save book'))
        self.action_save.setEnabled(False)
        self.action_save_copy = reg('save.png', _('Save a &copy'), self.boss.save_copy, 'save-copy', 'Ctrl+Alt+S', _('Save a copy of the book'))
        self.action_quit = reg('quit.png', _('&Quit'), self.boss.quit, 'quit', 'Ctrl+Q', _('Quit'))
        self.action_preferences = reg('config.png', _('&Preferences'), self.boss.preferences, 'preferences', 'Ctrl+P', _('Preferences'))
        self.action_new_book = reg('book.png', _('Create &new, empty book'), self.boss.new_book, 'new-book', (), _('Create a new, empty book'))
        self.action_import_book = reg('book.png', _('&Import an HTML or DOCX file as a new book'),
                                      self.boss.import_book, 'import-book', (), _('Import an HTML or DOCX file as a new book'))
        self.action_quick_edit = reg('modified.png', _('&Quick open a file to edit'), self.boss.quick_open, 'quick-open', ('Ctrl+T'), _(
            'Quickly open a file from the book to edit it'))

        # Editor actions
        group = _('Editor actions')
        self.action_editor_undo = reg('edit-undo.png', _('&Undo'), self.boss.do_editor_undo, 'editor-undo', 'Ctrl+Z',
                                      _('Undo typing'))
        self.action_editor_redo = reg('edit-redo.png', _('&Redo'), self.boss.do_editor_redo, 'editor-redo', 'Ctrl+Y',
                                      _('Redo typing'))
        self.action_editor_cut = reg('edit-cut.png', _('C&ut text'), self.boss.do_editor_cut, 'editor-cut', ('Ctrl+X', 'Shift+Delete', ),
                                      _('Cut text'))
        self.action_editor_copy = reg('edit-copy.png', _('&Copy to clipboard'), self.boss.do_editor_copy, 'editor-copy', ('Ctrl+C', 'Ctrl+Insert'),
                                      _('Copy to clipboard'))
        self.action_editor_paste = reg('edit-paste.png', _('&Paste from clipboard'), self.boss.do_editor_paste, 'editor-paste', ('Ctrl+V', 'Shift+Insert', ),
                                      _('Paste from clipboard'))
        self.action_editor_cut.setEnabled(False)
        self.action_editor_copy.setEnabled(False)
        self.action_editor_undo.setEnabled(False)
        self.action_editor_redo.setEnabled(False)

        def ereg(icon, text, target, sid, keys, description):
            return reg(icon, text, partial(self.boss.editor_action, target), sid, keys, description)
        register_text_editor_actions(ereg, self.palette())

        # Tool actions
        group = _('Tools')
        self.action_toc = reg('toc.png', _('&Edit Table of Contents'), self.boss.edit_toc, 'edit-toc', (), _('Edit Table of Contents'))
        self.action_inline_toc = reg('chapters.png', _('&Insert inline Table of Contents'),
                                     self.boss.insert_inline_toc, 'insert-inline-toc', (), _('Insert inline Table of Contents'))
        self.action_fix_html_current = reg('html-fix.png', _('&Fix HTML'), partial(self.boss.fix_html, True), 'fix-html-current', (),
                                           _('Fix HTML in the current file'))
        self.action_fix_html_all = reg('html-fix.png', _('&Fix HTML - all files'), partial(self.boss.fix_html, False), 'fix-html-all', (),
                                       _('Fix HTML in all files'))
        self.action_pretty_current = reg('beautify.png', _('&Beautify current file'), partial(self.boss.pretty_print, True), 'pretty-current', (),
                                           _('Beautify current file'))
        self.action_pretty_all = reg('beautify.png', _('&Beautify all files'), partial(self.boss.pretty_print, False), 'pretty-all', (),
                                       _('Beautify all files'))
        self.action_insert_char = reg('character-set.png', _('&Insert special character'), self.boss.insert_character, 'insert-character', (),
                                      _('Insert special character'))
        self.action_rationalize_folders = reg('mimetypes/dir.png', _('&Arrange into folders'), self.boss.rationalize_folders, 'rationalize-folders', (),
                                      _('Arrange into folders'))

        # Polish actions
        group = _('Polish Book')
        self.action_subset_fonts = reg(
            'subset-fonts.png', _('&Subset embedded fonts'), partial(
                self.boss.polish, 'subset', _('Subset fonts')), 'subset-fonts', (), _('Subset embedded fonts'))
        self.action_embed_fonts = reg(
            'embed-fonts.png', _('&Embed referenced fonts'), partial(
                self.boss.polish, 'embed', _('Embed fonts')), 'embed-fonts', (), _('Embed referenced fonts'))
        self.action_smarten_punctuation = reg(
            'smarten-punctuation.png', _('&Smarten punctuation'), partial(
                self.boss.polish, 'smarten_punctuation', _('Smarten punctuation')), 'smarten-punctuation', (), _('Smarten punctuation'))
        self.action_remove_unused_css = reg(
            'edit-clear.png', _('Remove &unused CSS rules'), partial(
                self.boss.polish, 'remove_unused_css', _('Remove unused CSS rules')), 'remove-unused-css', (), _('Remove unused CSS rules'))

        # Preview actions
        group = _('Preview')
        self.action_auto_reload_preview = reg('auto-reload.png', _('Auto reload preview'), None, 'auto-reload-preview', (), _('Auto reload preview'))
        self.action_auto_sync_preview = reg('sync-right.png', _('Sync preview position to editor position'), None, 'sync-preview-to-editor', (), _(
            'Sync preview position to editor position'))
        self.action_reload_preview = reg('view-refresh.png', _('Refresh preview'), None, 'reload-preview', ('F5',), _('Refresh preview'))
        self.action_split_in_preview = reg('auto_author_sort.png', _('Split this file'), None, 'split-in-preview', (), _(
            'Split file in the preview panel'))
        self.action_find_next_preview = reg('arrow-down.png', _('Find Next'), None, 'find-next-preview', (), _('Find next in preview'))
        self.action_find_prev_preview = reg('arrow-up.png', _('Find Previous'), None, 'find-prev-preview', (), _('Find previous in preview'))

        # Search actions
        group = _('Search')
        self.action_find = reg('search.png', _('&Find/Replace'), self.boss.show_find, 'find-replace', ('Ctrl+F',), _('Show the Find/Replace panel'))
        def sreg(name, text, action, overrides={}, keys=(), description=None, icon=None):
            return reg(icon, text, partial(self.boss.search, action, overrides), name, keys, description or text.replace('&', ''))
        self.action_find_next = sreg('find-next', _('Find &Next'),
                                     'find', {'direction':'down'}, ('F3', 'Ctrl+G'), _('Find next match'))
        self.action_find_previous = sreg('find-previous', _('Find &Previous'),
                                         'find', {'direction':'up'}, ('Shift+F3', 'Shift+Ctrl+G'), _('Find previous match'))
        self.action_replace = sreg('replace', _('Replace'),
                                   'replace', keys=('Ctrl+R'), description=_('Replace current match'))
        self.action_replace_next = sreg('replace-next', _('&Replace and find next'),
                                        'replace-find', {'direction':'down'}, ('Ctrl+]'), _('Replace current match and find next'))
        self.action_replace_previous = sreg('replace-previous', _('R&eplace and find previous'),
                                        'replace-find', {'direction':'up'}, ('Ctrl+['), _('Replace current match and find previous'))
        self.action_replace_all = sreg('replace-all', _('Replace &all'),
                                   'replace-all', keys=('Ctrl+A'), description=_('Replace all matches'))
        self.action_count = sreg('count-matches', _('&Count all'),
                                   'count', keys=('Ctrl+N'), description=_('Count number of matches'))
        self.action_mark = reg(None, _('&Mark selected text'), self.boss.mark_selected_text, 'mark-selected-text', ('Ctrl+Shift+M',), _('Mark selected text'))
        self.action_go_to_line = reg(None, _('Go to &line'), self.boss.go_to_line_number, 'go-to-line-number', ('Ctrl+.',), _('Go to line number'))

        # Check Book actions
        group = _('Check Book')
        self.action_check_book = reg('debug.png', _('&Check Book'), self.boss.check_requested, 'check-book', ('F7'), _('Check book for errors'))
        self.action_check_book_next = reg('forward.png', _('&Next error'), partial(
            self.check_book.next_error, delta=1), 'check-book-next', ('Ctrl+F7'), _('Show next error'))
        self.action_check_book_previous = reg('back.png', _('&Previous error'), partial(
            self.check_book.next_error, delta=-1), 'check-book-previous', ('Ctrl+Shift+F7'), _('Show previous error'))

        # Miscellaneous actions
        group = _('Miscellaneous')
        self.action_create_checkpoint = reg(
            'marked.png', _('&Create checkpoint'), self.boss.create_checkpoint, 'create-checkpoint', (), _(
                'Create a checkpoint with the current state of the book'))
        self.action_close_current_tab = reg(
            'window-close.png', _('&Close current tab'), self.central.close_current_editor, 'close-current-tab', 'Ctrl+W', _(
                'Close the currently open tab'))
        self.action_close_all_but_current_tab = reg(
            'edit-clear.png', _('&Close other tabs'), self.central.close_all_but_current_editor, 'close-all-but-current-tab', 'Ctrl+Alt+W', _(
                'Close all tabs except the current tab'))
        self.action_help = reg(
            'help.png', _('User &Manual'), lambda : open_url(QUrl('http://manual.calibre-ebook.com/edit.html')), 'user-manual', 'F1', _(
                'Show User Manual'))
        self.action_browse_images = reg(
            'view-image.png', _('&Browse images in book'), self.boss.browse_images, 'browse-images', (), _(
                'Browse images in the books visually'))
        self.action_multiple_split = reg(
            'auto_author_sort.png', _('&Split at multiple locations'), self.boss.multisplit, 'multisplit', (), _(
                'Split HTML file at multiple locations'))
        self.action_compare_book = reg('diff.png', _('&Compare to another book'), self.boss.compare_book, 'compare-book', (), _(
            'Compare to another book'))

    def create_menubar(self):
        p, q = self.create_application_menubar()
        q.triggered.connect(self.action_quit.trigger)
        p.triggered.connect(self.action_preferences.trigger)
        b = self.menuBar()

        f = b.addMenu(_('&File'))
        f.addAction(self.action_new_file)
        f.addAction(self.action_import_files)
        f.addSeparator()
        f.addAction(self.action_open_book)
        f.addAction(self.action_new_book)
        f.addAction(self.action_import_book)
        self.recent_books_menu = f.addMenu(_('&Recently opened books'))
        self.update_recent_books()
        f.addSeparator()
        f.addAction(self.action_save)
        f.addAction(self.action_save_copy)
        f.addSeparator()
        f.addAction(self.action_compare_book)
        f.addAction(self.action_quit)

        e = b.addMenu(_('&Edit'))
        e.addAction(self.action_global_undo)
        e.addAction(self.action_global_redo)
        e.addAction(self.action_create_checkpoint)
        e.addSeparator()
        e.addAction(self.action_editor_undo)
        e.addAction(self.action_editor_redo)
        e.addSeparator()
        e.addAction(self.action_editor_cut)
        e.addAction(self.action_editor_copy)
        e.addAction(self.action_editor_paste)
        e.addAction(self.action_insert_char)
        e.addSeparator()
        e.addAction(self.action_quick_edit)
        e.addAction(self.action_preferences)

        e = b.addMenu(_('&Tools'))
        tm = e.addMenu(_('Table of Contents'))
        tm.addAction(self.action_toc)
        tm.addAction(self.action_inline_toc)
        e.addAction(self.action_embed_fonts)
        e.addAction(self.action_subset_fonts)
        e.addAction(self.action_smarten_punctuation)
        e.addAction(self.action_remove_unused_css)
        e.addAction(self.action_fix_html_all)
        e.addAction(self.action_pretty_all)
        e.addAction(self.action_rationalize_folders)
        e.addAction(self.action_check_book)

        e = b.addMenu(_('&View'))
        t = e.addMenu(_('Tool&bars'))
        e.addSeparator()
        for name, ac in actions.iteritems():
            if name.endswith('-dock'):
                e.addAction(ac)
            elif name.endswith('-bar'):
                t.addAction(ac)
        e.addAction(self.action_browse_images)
        e.addSeparator()
        e.addAction(self.action_close_current_tab)
        e.addAction(self.action_close_all_but_current_tab)

        e = b.addMenu(_('&Search'))
        a = e.addAction
        a(self.action_find)
        e.addSeparator()
        a(self.action_find_next)
        a(self.action_find_previous)
        e.addSeparator()
        a(self.action_replace)
        a(self.action_replace_next)
        a(self.action_replace_previous)
        a(self.action_replace_all)
        e.addSeparator()
        a(self.action_count)
        e.addSeparator()
        a(self.action_mark)
        e.addSeparator()
        a(self.action_go_to_line)

        e = b.addMenu(_('&Help'))
        a = e.addAction
        a(self.action_help)
        a(QIcon(I('donate.png')), _('Donate to support calibre development'), open_donate)
        a(self.action_preferences)

    def update_recent_books(self):
        m = self.recent_books_menu
        m.clear()
        books = tprefs.get('recent-books', [])
        for path in books:
            m.addAction(self.elided_text(path, width=500), partial(self.boss.open_book, path=path))

    def create_toolbars(self):
        def create(text, name):
            name += '-bar'
            b = self.addToolBar(text)
            b.setObjectName(name)  # Needed for saveState
            setattr(self, name.replace('-', '_'), b)
            actions[name] = b.toggleViewAction()
            return b

        a = create(_('Book tool bar'), 'global').addAction
        for x in ('new_file', 'open_book', None, 'global_undo', 'global_redo', 'create_checkpoint', 'save', None, 'toc', 'check_book'):
            if x is None:
                self.global_bar.addSeparator()
                continue
            a(getattr(self, 'action_' + x))
        self.donate_button = b = ThrobbingButton(self)
        b.clicked.connect(open_donate)
        b.setAutoRaise(True)
        self.donate_widget = w = create_donate_widget(b)
        if hasattr(w, 'filler'):
            w.filler.setVisible(False)
        b.set_normal_icon_size(self.global_bar.iconSize().width(), self.global_bar.iconSize().height())
        b.setIcon(QIcon(I('donate.png')))
        b.setToolTip(_('Donate to support calibre development'))
        QTimer.singleShot(10, b.start_animation)
        self.global_bar.addWidget(w)
        self.global_bar.addAction(self.action_insert_char)
        a(self.action_help)

        a = create(_('Polish book tool bar'), 'polish').addAction
        for x in ('embed_fonts', 'subset_fonts', 'smarten_punctuation', 'remove_unused_css'):
            a(getattr(self, 'action_' + x))

    def create_docks(self):

        def create(name, oname):
            oname += '-dock'
            d = QDockWidget(name, self)
            d.setObjectName(oname)  # Needed for saveState
            ac = d.toggleViewAction()
            desc = _('Toggle %s') % name.replace('&', '')
            self.keyboard.register_shortcut(
                oname, desc, description=desc, action=ac, group=_('Windows'))
            actions[oname] = ac
            setattr(self, oname.replace('-', '_'), d)
            return d

        d = create(_('Files Browser'), 'files-browser')
        d.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        self.file_list = FileListWidget(d)
        d.setWidget(self.file_list)
        self.addDockWidget(Qt.LeftDockWidgetArea, d)

        d = create(_('File Preview'), 'preview')
        d.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        self.preview = Preview(d)
        d.setWidget(self.preview)
        self.addDockWidget(Qt.RightDockWidgetArea, d)

        d = create(_('Check Book'), 'check-book')
        d.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea | Qt.BottomDockWidgetArea | Qt.TopDockWidgetArea)
        d.setWidget(self.check_book)
        self.addDockWidget(Qt.TopDockWidgetArea, d)
        d.close()  # By default the check window is closed

        d = create(_('Inspector'), 'inspector')
        d.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea | Qt.BottomDockWidgetArea | Qt.TopDockWidgetArea)
        d.setWidget(self.preview.inspector)
        self.preview.inspector.setParent(d)
        self.addDockWidget(Qt.BottomDockWidgetArea, d)
        d.close()  # By default the inspector window is closed
        d.setFeatures(d.DockWidgetClosable | d.DockWidgetMovable)  # QWebInspector does not work in a floating dock

        d = create(_('Table of Contents'), 'toc-viewer')
        d.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea | Qt.BottomDockWidgetArea | Qt.TopDockWidgetArea)
        d.setWidget(self.toc_view)
        self.addDockWidget(Qt.LeftDockWidgetArea, d)
        d.close()  # Hidden by default
        d.visibilityChanged.connect(self.toc_view.visibility_changed)

        d = create(_('Checkpoints'), 'checkpoints')
        d.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea | Qt.BottomDockWidgetArea | Qt.TopDockWidgetArea)
        self.checkpoints = CheckpointView(self.boss.global_undo, parent=d)
        d.setWidget(self.checkpoints)
        self.addDockWidget(Qt.LeftDockWidgetArea, d)
        d.close()  # Hidden by default

    def resizeEvent(self, ev):
        self.blocking_job.resize(ev.size())
        return super(Main, self).resizeEvent(ev)

    def update_window_title(self):
        fname = os.path.basename(current_container().path_to_ebook)
        self.setWindowTitle(self.current_metadata.title + ' [%s] :: %s :: %s' %(current_container().book_type.upper(), fname, self.APP_NAME))

    def closeEvent(self, e):
        if not self.boss.confirm_quit():
            e.ignore()
            return
        try:
            self.boss.shutdown()
        except:
            import traceback
            traceback.print_exc()
        e.accept()

    def save_state(self):
        tprefs.set('main_window_geometry', bytearray(self.saveGeometry()))
        tprefs.set('main_window_state', bytearray(self.saveState(self.STATE_VERSION)))
        self.central.save_state()
        self.check_book.save_state()

    def restore_state(self):
        geom = tprefs.get('main_window_geometry', None)
        if geom is not None:
            self.restoreGeometry(geom)
        state = tprefs.get('main_window_state', None)
        if state is not None:
            self.restoreState(state, self.STATE_VERSION)
        self.central.restore_state()

    def contextMenuEvent(self, ev):
        ev.ignore()
