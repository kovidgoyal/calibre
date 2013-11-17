#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

from functools import partial

from PyQt4.Qt import (
    QDockWidget, Qt, QLabel, QIcon, QAction, QApplication, QWidget, QFontMetrics,
    QVBoxLayout, QStackedWidget, QTabWidget, QImage, QPixmap, pyqtSignal)

from calibre.constants import __appname__, get_version
from calibre.gui2.main_window import MainWindow
from calibre.gui2.tweak_book import current_container, tprefs, actions
from calibre.gui2.tweak_book.file_list import FileListWidget
from calibre.gui2.tweak_book.job import BlockingJob
from calibre.gui2.tweak_book.boss import Boss
from calibre.gui2.tweak_book.keyboard import KeyboardManager
from calibre.gui2.tweak_book.preview import Preview
from calibre.gui2.tweak_book.search import SearchPanel

def elided_text(font, text, width=200, mode=Qt.ElideMiddle):
    fm = QFontMetrics(font)
    return unicode(fm.elidedText(text, mode, int(width)))

class Central(QStackedWidget):

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

    def _close_requested(self, index):
        editor = self.editor_tabs.widget(index)
        self.close_requested.emit(editor)

    def add_editor(self, name, editor):
        fname = name.rpartition('/')[2]
        index = self.editor_tabs.addTab(editor, fname)
        self.editor_tabs.setTabToolTip(index, _('Full path:') + ' ' + name)
        editor.modification_state_changed.connect(self.editor_modified)

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

class Main(MainWindow):

    APP_NAME = _('Tweak Book')
    STATE_VERSION = 0

    def __init__(self, opts):
        MainWindow.__init__(self, opts, disable_automatic_gc=True)
        self.boss = Boss(self)
        self.setWindowTitle(self.APP_NAME)
        self.setWindowIcon(QIcon(I('tweak.png')))
        self.opts = opts
        self.path_to_ebook = None
        self.container = None
        self.current_metadata = None
        self.blocking_job = BlockingJob(self)
        self.keyboard = KeyboardManager()

        self.central = Central(self)
        self.setCentralWidget(self.central)

        self.create_actions()
        self.create_toolbars()
        self.create_docks()
        self.create_menubar()

        self.status_bar = self.statusBar()
        self.status_bar.addPermanentWidget(self.boss.save_manager.status_widget)
        self.status_bar.addWidget(QLabel(_('{0} {1} created by {2}').format(__appname__, get_version(), 'Kovid Goyal')))
        f = self.status_bar.font()
        f.setBold(True)
        self.status_bar.setFont(f)

        self.boss(self)
        g = QApplication.instance().desktop().availableGeometry(self)
        self.resize(g.width()-50, g.height()-50)
        self.restore_state()

        self.keyboard.finalize()
        self.keyboard.set_mode('other')

    def elided_text(self, text, width=200, mode=Qt.ElideMiddle):
        return elided_text(self.font(), text, width=width, mode=mode)

    @property
    def editor_tabs(self):
        return self.central.editor_tabs

    def create_actions(self):
        group = _('Global Actions')

        def reg(icon, text, target, sid, keys, description):
            ac = actions[sid] = QAction(QIcon(I(icon)), text, self) if icon else QAction(text, self)
            ac.setObjectName('action-' + sid)
            if target is not None:
                ac.triggered.connect(target)
            if isinstance(keys, type('')):
                keys = (keys,)
            self.keyboard.register_shortcut(
                sid, unicode(ac.text()), default_keys=keys, description=description, action=ac, group=group)
            self.addAction(ac)
            return ac

        self.action_new_file = reg('document-new.png', _('&New file'), self.boss.add_file, 'new-file', (), _('Create a new file in the current book'))
        self.action_open_book = reg('document_open.png', _('Open &book'), self.boss.open_book, 'open-book', 'Ctrl+O', _('Open a new book'))
        self.action_global_undo = reg('back.png', _('&Revert to before'), self.boss.do_global_undo, 'global-undo', 'Ctrl+Left',
                                      _('Revert book to before the last action (Undo)'))
        self.action_global_redo = reg('forward.png', _('&Revert to after'), self.boss.do_global_redo, 'global-redo', 'Ctrl+Right',
                                      _('Revert book state to after the next action (Redo)'))
        self.action_save = reg('save.png', _('&Save'), self.boss.save_book, 'save-book', 'Ctrl+Shift+S', _('Save book'))
        self.action_save.setEnabled(False)
        self.action_quit = reg('quit.png', _('&Quit'), self.boss.quit, 'quit', 'Ctrl+Q', _('Quit'))

        # Editor actions
        group = _('Editor actions')
        self.action_editor_undo = reg('edit-undo.png', _('&Undo'), self.boss.do_editor_undo, 'editor-undo', 'Ctrl+Z',
                                      _('Undo typing'))
        self.action_editor_redo = reg('edit-redo.png', _('&Redo'), self.boss.do_editor_redo, 'editor-redo', 'Ctrl+Y',
                                      _('Redo typing'))
        self.action_editor_save = reg('save.png', _('&Save'), self.boss.do_editor_save, 'editor-save', 'Ctrl+S',
                                      _('Save changes to the current file'))
        self.action_editor_cut = reg('edit-cut.png', _('C&ut text'), self.boss.do_editor_cut, 'editor-cut', ('Ctrl+X', 'Shift+Delete', ),
                                      _('Cut text'))
        self.action_editor_copy = reg('edit-copy.png', _('&Copy text'), self.boss.do_editor_copy, 'editor-copy', ('Ctrl+C', 'Ctrl+Insert'),
                                      _('Copy text'))
        self.action_editor_paste = reg('edit-paste.png', _('&Paste text'), self.boss.do_editor_paste, 'editor-paste', ('Ctrl+V', 'Shift+Insert', ),
                                      _('Paste text'))
        self.action_editor_cut.setEnabled(False)
        self.action_editor_copy.setEnabled(False)
        self.action_editor_undo.setEnabled(False)
        self.action_editor_redo.setEnabled(False)

        # Tool actions
        group = _('Tools')
        self.action_toc = reg('toc.png', _('&Edit Table of Contents'), self.boss.edit_toc, 'edit-toc', (), _('Edit Table of Contents'))

        # Polish actions
        group = _('Polish')
        self.action_subset_fonts = reg(
            'subset-fonts.png', _('&Subset embedded fonts'), partial(
                self.boss.polish, 'subset', _('Subset fonts')), 'subset-fonts', (), _('Subset embedded fonts'))
        self.action_embed_fonts = reg(
            'embed-fonts.png', _('&Embed referenced fonts'), partial(
                self.boss.polish, 'embed', _('Embed fonts')), 'embed-fonts', (), _('Embed referenced fonts'))
        self.action_smarten_punctuation = reg(
            'smarten-punctuation.png', _('&Smarten punctuation'), partial(
                self.boss.polish, 'smarten_punctuation', _('Smarten punctuation')), 'smarten-punctuation', (), _('Smarten punctuation'))

        # Preview actions
        group = _('Preview')
        self.action_auto_reload_preview = reg('auto-reload.png', _('Auto reload preview'), None, 'auto-reload-preview', (), _('Auto reload preview'))
        self.action_reload_preview = reg('view-refresh.png', _('Refresh preview'), None, 'reload-preview', ('F5',), _('Refresh preview'))

        # Search actions
        group = _('Search')
        self.action_find = reg('search.png', _('&Find/Replace'), self.central.show_find, 'find-replace', ('Ctrl+F',), _('Show the Find/Replace panel'))
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

        # Miscellaneous actions
        group = _('Miscellaneous')
        self.action_create_checkpoint = reg(
            'marked.png', _('&Create checkpoint'), self.boss.create_checkpoint, 'create-checkpoint', (), _(
                'Create a checkpoint with the current state of the book'))

    def create_menubar(self):
        b = self.menuBar()

        f = b.addMenu(_('&File'))
        f.addAction(self.action_new_file)
        f.addAction(self.action_open_book)
        f.addAction(self.action_save)
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

        e = b.addMenu(_('&Tools'))
        e.addAction(self.action_toc)
        e.addAction(self.action_embed_fonts)
        e.addAction(self.action_subset_fonts)
        e.addAction(self.action_smarten_punctuation)

        e = b.addMenu(_('&View'))
        t = e.addMenu(_('Tool&bars'))
        e.addSeparator()
        for name, ac in actions.iteritems():
            if name.endswith('-dock'):
                e.addAction(ac)
            elif name.endswith('-bar'):
                t.addAction(ac)

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

    def create_toolbars(self):
        def create(text, name):
            name += '-bar'
            b = self.addToolBar(text)
            b.setObjectName(name)  # Needed for saveState
            setattr(self, name.replace('-', '_'), b)
            actions[name] = b.toggleViewAction()
            return b

        a = create(_('Book tool bar'), 'global').addAction
        for x in ('new_file', 'open_book', 'global_undo', 'global_redo', 'save', 'create_checkpoint', 'toc'):
            a(getattr(self, 'action_' + x))

        a = create(_('Polish book tool bar'), 'polish').addAction
        for x in ('embed_fonts', 'subset_fonts', 'smarten_punctuation'):
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

        d = create(_('&Files Browser'), 'files-browser')
        d.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        self.file_list = FileListWidget(d)
        d.setWidget(self.file_list)
        self.addDockWidget(Qt.LeftDockWidgetArea, d)

        d = create(_('File &Preview'), 'preview')
        d.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        self.preview = Preview(d)
        d.setWidget(self.preview)
        self.addDockWidget(Qt.RightDockWidgetArea, d)

        d = create(_('&Inspector'), 'inspector')
        d.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea | Qt.BottomDockWidgetArea | Qt.TopDockWidgetArea)
        d.setWidget(self.preview.inspector)
        self.preview.inspector.setParent(d)
        self.addDockWidget(Qt.BottomDockWidgetArea, d)

    def resizeEvent(self, ev):
        self.blocking_job.resize(ev.size())
        return super(Main, self).resizeEvent(ev)

    def update_window_title(self):
        self.setWindowTitle(self.current_metadata.title + ' [%s] - %s' %(current_container().book_type.upper(), self.APP_NAME))

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

    def restore_state(self):
        geom = tprefs.get('main_window_geometry', None)
        if geom is not None:
            self.restoreGeometry(geom)
        state = tprefs.get('main_window_state', None)
        if state is not None:
            self.restoreState(state, self.STATE_VERSION)
        self.central.restore_state()
        # We never want to start with the inspector showing
        self.inspector_dock.close()

    def contextMenuEvent(self, ev):
        ev.ignore()
