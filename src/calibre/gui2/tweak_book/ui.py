#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

from PyQt4.Qt import (
    QDockWidget, Qt, QLabel, QIcon, QAction, QApplication, QWidget,
    QVBoxLayout, QStackedWidget, QTabWidget, QImage, QPixmap, pyqtSignal)

from calibre.constants import __appname__, get_version
from calibre.gui2.main_window import MainWindow
from calibre.gui2.tweak_book import current_container, tprefs, actions
from calibre.gui2.tweak_book.file_list import FileListWidget
from calibre.gui2.tweak_book.job import BlockingJob
from calibre.gui2.tweak_book.boss import Boss
from calibre.gui2.tweak_book.keyboard import KeyboardManager
from calibre.gui2.tweak_book.preview import Preview

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

        self.create_actions()
        self.create_menubar()
        self.create_toolbar()
        self.create_docks()

        self.status_bar = self.statusBar()
        self.status_bar.addPermanentWidget(self.boss.save_manager.status_widget)
        self.status_bar.addWidget(QLabel(_('{0} {1} created by {2}').format(__appname__, get_version(), 'Kovid Goyal')))
        f = self.status_bar.font()
        f.setBold(True)
        self.status_bar.setFont(f)

        self.central = Central(self)
        self.setCentralWidget(self.central)

        self.boss(self)
        g = QApplication.instance().desktop().availableGeometry(self)
        self.resize(g.width()-50, g.height()-50)
        self.restore_state()

        self.keyboard.finalize()
        self.keyboard.set_mode('other')

    @property
    def editor_tabs(self):
        return self.central.editor_tabs

    def create_actions(self):
        group = _('Global Actions')

        def reg(icon, text, target, sid, keys, description):
            ac = actions[sid] = QAction(QIcon(I(icon)), text, self)
            ac.setObjectName('action-' + sid)
            ac.triggered.connect(target)
            if isinstance(keys, type('')):
                keys = (keys,)
            self.keyboard.register_shortcut(
                sid, unicode(ac.text()), default_keys=keys, description=description, action=ac, group=group)
            self.addAction(ac)
            return ac

        self.action_open_book = reg('document_open.png', _('Open &book'), self.boss.open_book, 'open-book', 'Ctrl+O', _('Open a new book'))
        self.action_global_undo = reg('back.png', _('&Revert to before'), self.boss.do_global_undo, 'global-undo', 'Ctrl+Left',
                                      _('Revert book to before the last action (Undo)'))
        self.action_global_redo = reg('forward.png', _('&Revert to after'), self.boss.do_global_redo, 'global-redo', 'Ctrl+Right',
                                      _('Revert book state to after the next action (Redo)'))
        self.action_save = reg('save.png', _('&Save'), self.boss.save_book, 'save-book', 'Ctrl+Shift+S', _('Save book'))
        self.action_save.setEnabled(False)
        self.action_quit = reg('quit.png', _('&Quit'), self.boss.quit, 'quit', 'Ctrl+Q', _('Quit'))

        # Editor actions
        self.action_editor_undo = reg('edit-undo.png', _('&Undo'), self.boss.do_editor_undo, 'editor-undo', 'Ctrl+Z',
                                      _('Undo typing'))
        self.action_editor_redo = reg('edit-redo.png', _('&Redo'), self.boss.do_editor_redo, 'editor-redo', 'Ctrl+Y',
                                      _('Redo typing'))
        self.action_editor_save = reg('save.png', _('&Save'), self.boss.do_editor_save, 'editor-save', 'Ctrl+S',
                                      _('Save changes to the current file'))
        self.action_editor_cut = reg('edit-cut.png', _('C&ut text'), self.boss.do_editor_cut, 'editor-cut', 'Ctrl+X',
                                      _('Cut text'))
        self.action_editor_copy = reg('edit-copy.png', _('&Copy text'), self.boss.do_editor_copy, 'editor-copy', 'Ctrl+C',
                                      _('Copy text'))
        self.action_editor_paste = reg('edit-paste.png', _('&Paste text'), self.boss.do_editor_paste, 'editor-paste', 'Ctrl+V',
                                      _('Paste text'))

    def create_menubar(self):
        b = self.menuBar()

        f = b.addMenu(_('&File'))
        f.addAction(self.action_open_book)
        f.addAction(self.action_save)
        f.addAction(self.action_quit)

        e = b.addMenu(_('&Edit'))
        e.addAction(self.action_global_undo)
        e.addAction(self.action_global_redo)

    def create_toolbar(self):
        self.global_bar = b = self.addToolBar(_('Global tool bar'))
        b.setObjectName('global_bar')  # Needed for saveState
        b.addAction(self.action_open_book)
        b.addAction(self.action_global_undo)
        b.addAction(self.action_global_redo)
        b.addAction(self.action_save)

    def create_docks(self):
        self.file_list_dock = d = QDockWidget(_('&Files Browser'), self)
        d.setObjectName('file_list_dock')  # Needed for saveState
        d.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        self.file_list = FileListWidget(d)
        d.setWidget(self.file_list)
        self.addDockWidget(Qt.LeftDockWidgetArea, d)

        self.preview_dock = d = QDockWidget(_('File &Preview'), self)
        d.setObjectName('file_preview')  # Needed for saveState
        d.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        self.preview = Preview(d)
        d.setWidget(self.preview)
        self.addDockWidget(Qt.RightDockWidgetArea, d)

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

    def restore_state(self):
        geom = tprefs.get('main_window_geometry', None)
        if geom is not None:
            self.restoreGeometry(geom)
        state = tprefs.get('main_window_state', None)
        if state is not None:
            self.restoreState(state, self.STATE_VERSION)
