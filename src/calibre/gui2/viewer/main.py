__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'

import traceback, os, sys, functools, collections, textwrap
from functools import partial
from threading import Thread

from PyQt4.Qt import (QApplication, Qt, QIcon, QTimer, QByteArray, QSize,
        QDoubleSpinBox, QLabel, QTextBrowser, QPropertyAnimation, QPainter,
        QBrush, QColor, pyqtSignal, QUrl, QRegExpValidator, QRegExp, QLineEdit,
        QToolButton, QMenu, QInputDialog, QAction, QKeySequence, QModelIndex)

from calibre.gui2.viewer.main_ui import Ui_EbookViewer
from calibre.gui2.viewer.printing import Printing
from calibre.gui2.viewer.bookmarkmanager import BookmarkManager
from calibre.gui2.viewer.toc import TOC
from calibre.gui2.widgets import ProgressIndicator
from calibre.gui2.main_window import MainWindow
from calibre.gui2 import (Application, ORG_NAME, APP_UID, choose_files,
    info_dialog, error_dialog, open_url, available_height)
from calibre.ebooks.oeb.iterator.book import EbookIterator
from calibre.ebooks import DRMError
from calibre.constants import islinux, isbsd, isosx, filesystem_encoding
from calibre.utils.config import Config, StringConfig, JSONConfig
from calibre.gui2.search_box import SearchBox2
from calibre.ebooks.metadata import MetaInformation
from calibre.customize.ui import available_input_formats
from calibre.gui2.viewer.dictionary import Lookup
from calibre import as_unicode, force_unicode, isbytestring
from calibre.ptempfile import reset_base_dir
from calibre.utils.zipfile import BadZipfile

vprefs = JSONConfig('viewer')

class Worker(Thread):

    def run(self):
        try:
            Thread.run(self)
            self.exception = self.traceback = None
        except BadZipfile:
            self.exception = _(
                'This ebook is corrupted and cannot be opened. If you '
                'downloaded it from somewhere, try downloading it again.')
            self.traceback = ''
        except Exception as err:
            self.exception = err
            self.traceback = traceback.format_exc()

class History(collections.deque):

    def __init__(self, action_back, action_forward):
        self.action_back = action_back
        self.action_forward = action_forward
        collections.deque.__init__(self)
        self.pos = 0
        self.set_actions()

    def set_actions(self):
        self.action_back.setDisabled(self.pos < 1)
        self.action_forward.setDisabled(self.pos + 1 >= len(self))

    def back(self, from_pos):
        if self.pos - 1 < 0: return None
        if self.pos == len(self):
            self.append([])
        self[self.pos] = from_pos
        self.pos -= 1
        self.set_actions()
        return self[self.pos]

    def forward(self):
        if self.pos + 1 >= len(self): return None
        self.pos += 1
        self.set_actions()
        return self[self.pos]

    def add(self, item):
        while len(self) > self.pos+1:
            self.pop()
        self.append(item)
        self.pos += 1
        self.set_actions()

class Metadata(QLabel):

    def __init__(self, parent):
        QTextBrowser.__init__(self, parent.centralWidget())
        self.view = parent.splitter
        self.setGeometry(self.view.geometry())
        self.setWordWrap(True)
        self.setVisible(False)

    def show_opf(self, opf, ext=''):
        mi = MetaInformation(opf)
        html = '<h2 align="center">%s</h2>%s\n<b>%s:</b> %s'\
                %(_('Metadata'), u''.join(mi.to_html()),
                        _('Book format'), ext.upper())
        self.setText(html)

    def setVisible(self, x):
        self.setGeometry(self.view.geometry())
        QLabel.setVisible(self, x)

    def paintEvent(self, ev):
        p = QPainter(self)
        p.fillRect(ev.region().boundingRect(), QBrush(QColor(200, 200, 200, 220), Qt.SolidPattern))
        p.end()
        QLabel.paintEvent(self, ev)


class DoubleSpinBox(QDoubleSpinBox):

    def __init__(self, *args, **kwargs):
        QDoubleSpinBox.__init__(self, *args, **kwargs)
        self.tt = _('Position in book')
        self.setToolTip(self.tt)

    def set_value(self, val):
        self.blockSignals(True)
        self.setValue(val)
        self.setToolTip(self.tt +
                ' [{0:.0%}]'.format(float(val)/self.maximum()))
        self.blockSignals(False)

class Reference(QLineEdit):

    goto = pyqtSignal(object)

    def __init__(self, *args):
        QLineEdit.__init__(self, *args)
        self.setValidator(QRegExpValidator(QRegExp(r'\d+\.\d+'), self))
        self.setToolTip(textwrap.fill('<p>'+_(
            'Go to a reference. To get reference numbers, use the <i>reference '
            'mode</i>, by clicking the reference mode button in the toolbar.')))
        if hasattr(self, 'setPlaceholderText'):
            self.setPlaceholderText(_('Go to...'))
        self.editingFinished.connect(self.editing_finished)

    def editing_finished(self):
        text = unicode(self.text())
        self.setText('')
        self.goto.emit(text)

class RecentAction(QAction):

    def __init__(self, path, parent):
        self.path = path
        QAction.__init__(self, os.path.basename(path), parent)

class EbookViewer(MainWindow, Ui_EbookViewer):

    STATE_VERSION = 1

    def __init__(self, pathtoebook=None, debug_javascript=False, open_at=None):
        MainWindow.__init__(self, None)
        self.setupUi(self)
        self.view.initialize_view(debug_javascript)
        self.view.magnification_changed.connect(self.magnification_changed)
        self.show_toc_on_open = False
        self.current_book_has_toc = False
        self.base_window_title = unicode(self.windowTitle())
        self.iterator          = None
        self.current_page      = None
        self.pending_search    = None
        self.pending_search_dir= None
        self.pending_anchor    = None
        self.pending_reference = None
        self.pending_bookmark  = None
        self.existing_bookmarks= []
        self.selected_text     = None
        self.read_settings()
        self.dictionary_box.hide()
        self.close_dictionary_view.clicked.connect(lambda
                x:self.dictionary_box.hide())
        self.history = History(self.action_back, self.action_forward)
        self.metadata = Metadata(self)
        self.pos = DoubleSpinBox()
        self.pos.setDecimals(1)
        self.pos.setSuffix('/'+_('Unknown')+'     ')
        self.pos.setMinimum(1.)
        self.pos.setMinimumWidth(150)
        self.tool_bar2.insertWidget(self.action_find_next, self.pos)
        self.reference = Reference()
        self.tool_bar2.insertSeparator(self.action_find_next)
        self.tool_bar2.insertWidget(self.action_find_next, self.reference)
        self.tool_bar2.insertSeparator(self.action_find_next)
        self.setFocusPolicy(Qt.StrongFocus)
        self.search = SearchBox2(self)
        self.search.setMinimumContentsLength(20)
        self.search.initialize('viewer_search_history')
        self.search.setToolTip(_('Search for text in book'))
        self.search.setMinimumWidth(200)
        self.tool_bar2.insertWidget(self.action_find_next, self.search)
        self.view.set_manager(self)
        self.pi = ProgressIndicator(self)
        self.toc.setVisible(False)
        self.action_quit = QAction(self)
        self.addAction(self.action_quit)
        self.view_resized_timer = QTimer(self)
        self.view_resized_timer.timeout.connect(self.viewport_resize_finished)
        self.view_resized_timer.setSingleShot(True)
        self.resize_in_progress = False
        qs = [Qt.CTRL+Qt.Key_Q]
        if isosx:
            qs += [Qt.CTRL+Qt.Key_W]
        self.action_quit.setShortcuts(qs)
        self.action_quit.triggered.connect(self.quit)
        self.action_focus_search = QAction(self)
        self.addAction(self.action_focus_search)
        self.action_focus_search.setShortcuts([Qt.Key_Slash,
            QKeySequence(QKeySequence.Find)])
        self.action_focus_search.triggered.connect(lambda x:
                self.search.setFocus(Qt.OtherFocusReason))
        self.action_copy.setDisabled(True)
        self.action_metadata.setCheckable(True)
        self.action_metadata.setShortcut(Qt.CTRL+Qt.Key_I)
        self.action_table_of_contents.setCheckable(True)
        self.toc.setMinimumWidth(80)
        self.action_reference_mode.setCheckable(True)
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
        self.action_full_screen.setShortcuts([Qt.Key_F11, Qt.CTRL+Qt.SHIFT+Qt.Key_F])
        self.action_full_screen.setToolTip(_('Toggle full screen (%s)') %
                _(' or ').join([unicode(x.toString(x.NativeText)) for x in
                    self.action_full_screen.shortcuts()]))
        self.action_back.triggered[bool].connect(self.back)
        self.action_forward.triggered[bool].connect(self.forward)
        self.action_bookmark.triggered[bool].connect(self.bookmark)
        self.action_preferences.triggered.connect(lambda :
                self.view.config(self))
        self.pos.editingFinished.connect(self.goto_page_num)
        self.vertical_scrollbar.valueChanged[int].connect(lambda
                x:self.goto_page(x/100.))
        self.search.search.connect(self.find)
        self.search.focus_to_library.connect(lambda: self.view.setFocus(Qt.OtherFocusReason))
        self.toc.pressed[QModelIndex].connect(self.toc_clicked)
        self.reference.goto.connect(self.goto)

        self.bookmarks_menu = QMenu()
        self.action_bookmark.setMenu(self.bookmarks_menu)
        self.set_bookmarks([])


        if pathtoebook is not None:
            f = functools.partial(self.load_ebook, pathtoebook, open_at=open_at)
            QTimer.singleShot(50, f)
        self.view.setMinimumSize(100, 100)
        self.toc.setCursor(Qt.PointingHandCursor)
        self.tool_bar.setContextMenuPolicy(Qt.PreventContextMenu)
        self.tool_bar2.setContextMenuPolicy(Qt.PreventContextMenu)
        self.tool_bar.widgetForAction(self.action_bookmark).setPopupMode(QToolButton.MenuButtonPopup)
        self.action_full_screen.setCheckable(True)
        self.full_screen_label = QLabel('''
                <center>
                <h1>%s</h1>
                <h3>%s</h3>
                <h3>%s</h3>
                </center>
                '''%(_('Full screen mode'),
                    _('Right click to show controls'),
                    _('Press Esc to quit')),
                    self)
        self.full_screen_label.setVisible(False)
        self.full_screen_label.setStyleSheet('''
        QLabel {
            text-align: center;
            background-color: white;
            color: black;
            border-width: 1px;
            border-style: solid;
            border-radius: 20px;
        }
        ''')
        self.window_mode_changed = None
        self.toggle_toolbar_action = QAction(_('Show/hide controls'), self)
        self.toggle_toolbar_action.triggered.connect(self.toggle_toolbars)
        self.addAction(self.toggle_toolbar_action)
        self.full_screen_label_anim = QPropertyAnimation(
                self.full_screen_label, 'size')
        self.esc_full_screen_action = a = QAction(self)
        self.addAction(a)
        a.setShortcut(Qt.Key_Escape)
        a.setEnabled(False)
        a.triggered.connect(self.action_full_screen.trigger)

        self.print_menu = QMenu()
        self.print_menu.addAction(QIcon(I('print-preview.png')), _('Print Preview'))
        self.action_print.setMenu(self.print_menu)
        self.tool_bar.widgetForAction(self.action_print).setPopupMode(QToolButton.MenuButtonPopup)
        self.action_print.triggered.connect(self.print_book)
        self.print_menu.actions()[0].triggered.connect(self.print_preview)
        ca = self.view.copy_action
        ca.setShortcut(QKeySequence.Copy)
        self.addAction(ca)
        self.open_history_menu = QMenu()
        self.clear_recent_history_action = QAction(
                _('Clear list of recently opened books'), self)
        self.clear_recent_history_action.triggered.connect(self.clear_recent_history)
        self.build_recent_menu()
        self.action_open_ebook.setMenu(self.open_history_menu)
        self.open_history_menu.triggered[QAction].connect(self.open_recent)
        w = self.tool_bar.widgetForAction(self.action_open_ebook)
        w.setPopupMode(QToolButton.MenuButtonPopup)

        for x in ('tool_bar', 'tool_bar2'):
            x = getattr(self, x)
            for action in x.actions():
                # So that the keyboard shortcuts for these actions will
                # continue to function even when the toolbars are hidden
                self.addAction(action)

        self.restore_state()

    def set_toc_visible(self, yes):
        self.toc.setVisible(yes)

    def clear_recent_history(self, *args):
        vprefs.set('viewer_open_history', [])
        self.build_recent_menu()

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

    def shutdown(self):
        if self.isFullScreen():
            self.action_full_screen.trigger()
            return False
        self.save_state()
        return True

    def quit(self):
        if self.shutdown():
            QApplication.instance().quit()

    def closeEvent(self, e):
        if self.shutdown():
            return MainWindow.closeEvent(self, e)
        else:
            e.ignore()

    def toggle_toolbars(self):
        for x in ('tool_bar', 'tool_bar2'):
            x = getattr(self, x)
            x.setVisible(not x.isVisible())

    def save_state(self):
        state = bytearray(self.saveState(self.STATE_VERSION))
        vprefs['viewer_toolbar_state'] = state
        vprefs.set('viewer_window_geometry', bytearray(self.saveGeometry()))
        if self.current_book_has_toc:
            vprefs.set('viewer_toc_isvisible', bool(self.toc.isVisible()))
        if self.toc.isVisible():
            vprefs.set('viewer_splitter_state',
                bytearray(self.splitter.saveState()))
        vprefs['multiplier'] = self.view.multiplier

    def restore_state(self):
        state = vprefs.get('viewer_toolbar_state', None)
        if state is not None:
            try:
                state = QByteArray(state)
                self.restoreState(state, self.STATE_VERSION)
            except:
                pass
        mult = vprefs.get('multiplier', None)
        if mult:
            self.view.multiplier = mult
        # On windows Qt lets the user hide toolbars via a right click in a very
        # specific location, ensure they are visible.
        self.tool_bar.setVisible(True)
        self.tool_bar2.setVisible(True)

    def lookup(self, word):
        self.dictionary_view.setHtml('<html><body><p>'+ \
            _('Connecting to dict.org to lookup: <b>%s</b>&hellip;')%word + \
            '</p></body></html>')
        self.dictionary_box.show()
        self._lookup = Lookup(word, parent=self)
        self._lookup.finished.connect(self.looked_up)
        self._lookup.start()

    def looked_up(self, *args):
        html = self._lookup.html_result
        self._lookup = None
        self.dictionary_view.setHtml(html)

    def get_remember_current_page_opt(self):
        from calibre.gui2.viewer.documentview import config
        c = config().parse()
        return c.remember_current_page

    def print_book(self):
        p = Printing(self.iterator, self)
        p.start_print()

    def print_preview(self):
        p = Printing(self.iterator, self)
        p.start_preview()

    def toggle_fullscreen(self, x):
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    def showFullScreen(self):
        self.view.document.page_position.save()
        self.window_mode_changed = 'fullscreen'
        self.tool_bar.setVisible(False)
        self.tool_bar2.setVisible(False)
        self._original_frame_margins = (
            self.centralwidget.layout().contentsMargins(),
            self.frame.layout().contentsMargins())
        self.frame.layout().setContentsMargins(0, 0, 0, 0)
        self.centralwidget.layout().setContentsMargins(0, 0, 0, 0)

        super(EbookViewer, self).showFullScreen()

    def show_full_screen_label(self):
        f = self.full_screen_label
        self.esc_full_screen_action.setEnabled(True)
        f.setVisible(True)
        height = 200
        width = int(0.7*self.view.width())
        f.resize(width, height)
        f.move((self.view.width() - width)//2, (self.view.height()-height)//2)
        a = self.full_screen_label_anim
        a.setDuration(500)
        a.setStartValue(QSize(width, 0))
        a.setEndValue(QSize(width, height))
        a.start()
        QTimer.singleShot(2750, self.full_screen_label.hide)
        self.view.document.switch_to_fullscreen_mode()

    def showNormal(self):
        self.view.document.page_position.save()
        self.window_mode_changed = 'normal'
        self.esc_full_screen_action.setEnabled(False)
        self.tool_bar.setVisible(True)
        self.tool_bar2.setVisible(True)
        self.full_screen_label.setVisible(False)
        if hasattr(self, '_original_frame_margins'):
            om = self._original_frame_margins
            self.centralwidget.layout().setContentsMargins(om[0])
            self.frame.layout().setContentsMargins(om[1])
        super(EbookViewer, self).showNormal()

    def handle_window_mode_toggle(self):
        if self.window_mode_changed:
            fs = self.window_mode_changed == 'fullscreen'
            self.window_mode_changed = None
            if fs:
                self.show_full_screen_label()
            else:
                self.view.document.switch_to_window_mode()
            self.view.document.page_position.restore()
            self.scrolled(self.view.scroll_fraction)

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
                                ' does not exist.'), show=True)
                url = QUrl.fromLocalFile(item.abspath)
                if item.fragment:
                    url.setFragment(item.fragment)
                self.link_clicked(url)
        self.view.setFocus(Qt.OtherFocusReason)

    def selection_changed(self, selected_text):
        self.selected_text = selected_text.strip()
        self.action_copy.setEnabled(bool(self.selected_text))

    def copy(self, x):
        if self.selected_text:
            QApplication.clipboard().setText(self.selected_text)

    def back(self, x):
        pos = self.history.back(self.pos.value())
        if pos is not None:
            self.goto_page(pos)

    def goto_page_num(self):
        num = self.pos.value()
        self.goto_page(num)

    def forward(self, x):
        pos = self.history.forward()
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
                     _('Choose ebook'),
                     [(_('Ebooks'), available_input_formats())],
                     all_files=False,
                     select_only_single_file=True)
        if files:
            self.load_ebook(files[0])

    def open_recent(self, action):
        self.load_ebook(action.path)

    def font_size_larger(self):
        self.view.magnify_fonts()
        self.action_font_size_larger.setEnabled(self.view.multiplier < 3)
        self.action_font_size_smaller.setEnabled(self.view.multiplier > 0.2)

    def font_size_smaller(self):
        self.view.shrink_fonts()
        self.action_font_size_larger.setEnabled(self.view.multiplier < 3)
        self.action_font_size_smaller.setEnabled(self.view.multiplier > 0.2)

    def magnification_changed(self, val):
        tt = _('Make font size %(which)s\nCurrent magnification: %(mag).1f')
        self.action_font_size_larger.setToolTip(
                tt %dict(which=_('larger'), mag=val))
        self.action_font_size_smaller.setToolTip(
                tt %dict(which=_('smaller'), mag=val))

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

    def internal_link_clicked(self, frac):
        self.history.add(self.pos.value())

    def link_clicked(self, url):
        path = os.path.abspath(unicode(url.toLocalFile()))
        frag = None
        if path in self.iterator.spine:
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
                    self.view.scroll_to('#')
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
        old, curr = event.size(), event.oldSize()
        if not self.window_mode_changed and old.width() == curr.width():
            # No relayout changes, so page position does not need to be saved
            # This is needed as Qt generates a viewport resized event that
            # changes only the height after a file has been loaded. This can
            # cause the last read position bookmark to become slightly
            # inaccurate
            return
        if not self.resize_in_progress:
            # First resize, so save the current page position
            self.resize_in_progress = True
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
        if self.window_mode_changed:
            # This resize is part of a window mode change, special case it
            self.handle_window_mode_toggle()
        else:
            self.view.document.page_position.restore()
        self.view.document.after_resize()

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

    def set_bookmarks(self, bookmarks):
        self.bookmarks_menu.clear()
        self.bookmarks_menu.addAction(_("Manage Bookmarks"), self.manage_bookmarks)
        self.bookmarks_menu.addSeparator()
        current_page = None
        self.existing_bookmarks = []
        for bm in bookmarks:
            if bm['title'] == 'calibre_current_page_bookmark':
                if self.get_remember_current_page_opt():
                    current_page = bm
            else:
                self.existing_bookmarks.append(bm['title'])
                self.bookmarks_menu.addAction(bm['title'], partial(self.goto_bookmark, bm))
        return current_page

    def manage_bookmarks(self):
        bmm = BookmarkManager(self, self.iterator.bookmarks)
        if bmm.exec_() != BookmarkManager.Accepted:
            return

        bookmarks = bmm.get_bookmarks()

        if bookmarks != self.iterator.bookmarks:
            self.iterator.set_bookmarks(bookmarks)
            self.iterator.save_bookmarks()
            self.set_bookmarks(bookmarks)

    def save_current_position(self):
        if not self.get_remember_current_page_opt():
            return
        if hasattr(self, 'current_index'):
            try:
                bm = self.view.bookmark()
                bm['spine'] = self.current_index
                bm['title'] = 'calibre_current_page_bookmark'
                self.iterator.add_bookmark(bm)
            except:
                traceback.print_exc()

    def load_ebook(self, pathtoebook, open_at=None):
        if self.iterator is not None:
            self.save_current_position()
            self.iterator.__exit__()
        self.iterator = EbookIterator(pathtoebook)
        self.open_progress_indicator(_('Loading ebook...'))
        worker = Worker(target=self.iterator.__enter__)
        worker.start()
        while worker.isAlive():
            worker.join(0.1)
            QApplication.processEvents()
        if worker.exception is not None:
            if isinstance(worker.exception, DRMError):
                from calibre.gui2.dialogs.drm_error import DRMErrorMessage
                DRMErrorMessage(self).exec_()
            else:
                r = getattr(worker.exception, 'reason', worker.exception)
                error_dialog(self, _('Could not open ebook'),
                        as_unicode(r), det_msg=worker.traceback, show=True)
            self.close_progress_indicator()
        else:
            self.metadata.show_opf(self.iterator.opf,
                    self.iterator.book_format)
            self.view.current_language = self.iterator.language
            title = self.iterator.opf.title
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
            vh = vprefs.get('viewer_open_history', [])
            try:
                vh.remove(pathtoebook)
            except:
                pass
            vh.insert(0, pathtoebook)
            vprefs.set('viewer_open_history', vh[:50])
            self.build_recent_menu()

            self.action_table_of_contents.setDisabled(not self.iterator.toc)
            self.current_book_has_toc = bool(self.iterator.toc)
            self.current_title = title
            self.setWindowTitle(self.base_window_title+' - '+title +
                    ' [%s]'%self.iterator.book_format)
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
            if open_at is None and previous is not None:
                self.goto_bookmark(previous)
            else:
                if open_at is None:
                    self.next_document()
                else:
                    if open_at > self.pos.maximum():
                        open_at = self.pos.maximum()
                    if open_at < self.pos.minimum():
                        open_at = self.pos.minimum()
                    self.goto_page(open_at, loaded_check=False)

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
        MainWindow.keyPressEvent(self, event)
        if not event.isAccepted():
            if not self.view.handle_key_press(event):
                event.ignore()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        if self.iterator is not None:
            self.save_current_position()
            self.iterator.__exit__(*args)

    def read_settings(self):
        c = config().parse()
        self.splitter.setSizes([1, 300])
        if c.remember_window_size:
            wg = vprefs.get('viewer_window_geometry', None)
            if wg is not None:
                self.restoreGeometry(wg)
            ss = vprefs.get('viewer_splitter_state', None)
            if ss is not None:
                self.splitter.restoreState(ss)
            self.show_toc_on_open = vprefs.get('viewer_toc_isvisible', False)
        av = available_height() - 30
        if self.height() > av:
            self.resize(self.width(), av)

def config(defaults=None):
    desc = _('Options to control the ebook viewer')
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
            'a location as displayed in the top left corner of the viewer.'))

    return c

def option_parser():
    c = config()
    return c.option_parser(usage=_('''\
%prog [options] file

View an ebook.
'''))


def main(args=sys.argv):
    # Ensure viewer can continue to function if GUI is closed
    os.environ.pop('CALIBRE_WORKER_TEMP_DIR', None)
    reset_base_dir()

    parser = option_parser()
    opts, args = parser.parse_args(args)
    pid = os.fork() if False and (islinux or isbsd) else -1
    try:
        open_at = float(opts.open_at)
    except:
        open_at = None
    if pid <= 0:
        app = Application(args)
        app.setWindowIcon(QIcon(I('viewer.png')))
        QApplication.setOrganizationName(ORG_NAME)
        QApplication.setApplicationName(APP_UID)
        main = EbookViewer(args[1] if len(args) > 1 else None,
                debug_javascript=opts.debug_javascript, open_at=open_at)
        # This is needed for paged mode. Without it, the first document that is
        # loaded will have extra blank space at the bottom, as
        # turn_off_internal_scrollbars does not take effect for the first
        # rendered document
        main.view.load_path(P('viewer/blank.html', allow_user_override=False))

        sys.excepthook = main.unhandled_exception
        main.show()
        if opts.raise_window:
            main.raise_()
    if opts.full_screen:
        main.action_full_screen.trigger()
    with main:
        return app.exec_()
    return 0

if __name__ == '__main__':
    sys.exit(main())
