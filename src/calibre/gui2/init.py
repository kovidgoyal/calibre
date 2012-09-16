#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import functools

from PyQt4.Qt import Qt, QStackedWidget, QMenu, \
        QSize, QSizePolicy, QStatusBar, QLabel, QFont

from calibre.utils.config import prefs
from calibre.constants import (isosx, __appname__, preferred_encoding,
    get_version)
from calibre.gui2 import config, is_widescreen, gprefs
from calibre.gui2.library.views import BooksView, DeviceBooksView
from calibre.gui2.widgets import Splitter
from calibre.gui2.tag_browser.ui import TagBrowserWidget
from calibre.gui2.book_details import BookDetails
from calibre.gui2.notify import get_notifier

_keep_refs = []

def partial(*args, **kwargs):
    ans = functools.partial(*args, **kwargs)
    _keep_refs.append(ans)
    return ans

class LibraryViewMixin(object): # {{{

    def __init__(self, db):
        self.library_view.files_dropped.connect(self.iactions['Add Books'].files_dropped, type=Qt.QueuedConnection)
        self.library_view.add_column_signal.connect(partial(self.iactions['Preferences'].do_config,
            initial_plugin=('Interface', 'Custom Columns')),
                type=Qt.QueuedConnection)
        for func, args in [
                             ('connect_to_search_box', (self.search,
                                 self.search_done)),
                             ('connect_to_book_display',
                                 (self.book_details.show_data,)),
                             ]:
            for view in (self.library_view, self.memory_view, self.card_a_view, self.card_b_view):
                getattr(view, func)(*args)

        self.memory_view.connect_dirtied_signal(self.upload_dirtied_booklists)
        self.memory_view.connect_upload_collections_signal(
                                    func=self.upload_collections, oncard=None)
        self.card_a_view.connect_dirtied_signal(self.upload_dirtied_booklists)
        self.card_a_view.connect_upload_collections_signal(
                                    func=self.upload_collections, oncard='carda')
        self.card_b_view.connect_dirtied_signal(self.upload_dirtied_booklists)
        self.card_b_view.connect_upload_collections_signal(
                                    func=self.upload_collections, oncard='cardb')
        self.book_on_device(None, reset=True)
        db.set_book_on_device_func(self.book_on_device)
        self.library_view.set_database(db)
        self.library_view.model().set_book_on_device_func(self.book_on_device)
        prefs['library_path'] = self.library_path

        for view in ('library', 'memory', 'card_a', 'card_b'):
            view = getattr(self, view+'_view')
            view.verticalHeader().sectionDoubleClicked.connect(self.iactions['View'].view_specific_book)

        self.library_view.model().set_highlight_only(config['highlight_search_matches'])

    def build_context_menus(self):
        lm = QMenu(self)
        def populate_menu(m, items):
            for what in items:
                if what is None:
                    m.addSeparator()
                elif what in self.iactions:
                    m.addAction(self.iactions[what].qaction)
        populate_menu(lm, gprefs['action-layout-context-menu'])
        dm = QMenu(self)
        populate_menu(dm, gprefs['action-layout-context-menu-device'])
        ec = self.iactions['Edit Collections'].qaction
        self.library_view.set_context_menu(lm, ec)
        for v in (self.memory_view, self.card_a_view, self.card_b_view):
            v.set_context_menu(dm, ec)

        if self.cover_flow is not None:
            cm = QMenu(self.cover_flow)
            populate_menu(cm,
                    gprefs['action-layout-context-menu-cover-browser'])
            self.cover_flow.set_context_menu(cm)

    def search_done(self, view, ok):
        if view is self.current_view():
            self.search.search_done(ok)
            self.set_number_of_books_shown()
            if ok:
                v = self.current_view()
                if hasattr(v, 'set_current_row'):
                    v.set_current_row(0)

    # }}}

class LibraryWidget(Splitter): # {{{

    def __init__(self, parent):
        orientation = Qt.Vertical
        if config['gui_layout'] == 'narrow':
            orientation = Qt.Horizontal if is_widescreen() else Qt.Vertical
        idx = 0 if orientation == Qt.Vertical else 1
        size = 300 if orientation == Qt.Vertical else 550
        Splitter.__init__(self, 'cover_browser_splitter', _('Cover Browser'),
                I('cover_flow.png'),
                orientation=orientation, parent=parent,
                connect_button=not config['separate_cover_flow'],
                side_index=idx, initial_side_size=size, initial_show=False,
                shortcut=_('Shift+Alt+B'))
        parent.library_view = BooksView(parent)
        parent.library_view.setObjectName('library_view')
        self.addWidget(parent.library_view)
# }}}

class Stack(QStackedWidget): # {{{

    def __init__(self, parent):
        QStackedWidget.__init__(self, parent)

        parent.cb_splitter = LibraryWidget(parent)
        self.tb_widget = TagBrowserWidget(parent)
        parent.tb_splitter = Splitter('tag_browser_splitter',
                _('Tag Browser'), I('tags.png'),
                parent=parent, side_index=0, initial_side_size=200,
                shortcut=_('Shift+Alt+T'))
        parent.tb_splitter.state_changed.connect(
                        self.tb_widget.set_pane_is_visible, Qt.QueuedConnection)
        parent.tb_splitter.addWidget(self.tb_widget)
        parent.tb_splitter.addWidget(parent.cb_splitter)
        parent.tb_splitter.setCollapsible(parent.tb_splitter.other_index, False)

        self.addWidget(parent.tb_splitter)
        for x in ('memory', 'card_a', 'card_b'):
            name = x+'_view'
            w = DeviceBooksView(parent)
            setattr(parent, name, w)
            self.addWidget(w)
            w.setObjectName(name)


# }}}

class UpdateLabel(QLabel): # {{{

    def __init__(self, *args, **kwargs):
        QLabel.__init__(self, *args, **kwargs)
        self.setCursor(Qt.PointingHandCursor)

    def contextMenuEvent(self, e):
        pass
# }}}

class StatusBar(QStatusBar): # {{{

    def __init__(self, parent=None):
        QStatusBar.__init__(self, parent)
        self.default_message = __appname__ + ' ' + _('version') + ' ' + \
                self.get_version() + ' ' + _('created by Kovid Goyal')
        self.device_string = ''
        self.update_label = UpdateLabel('')
        self.addPermanentWidget(self.update_label)
        self.update_label.setVisible(False)
        self._font = QFont()
        self._font.setBold(True)
        self.setFont(self._font)
        self.defmsg = QLabel(self.default_message)
        self.defmsg.setFont(self._font)
        self.addWidget(self.defmsg)

    def initialize(self, systray=None):
        self.systray = systray
        self.notifier = get_notifier(systray)

    def device_connected(self, devname):
        self.device_string = _('Connected ') + devname
        self.defmsg.setText(self.default_message + ' ..::.. ' +
                self.device_string)
        self.clearMessage()

    def device_disconnected(self):
        self.device_string = ''
        self.defmsg.setText(self.default_message)
        self.clearMessage()

    def get_version(self):
        return get_version()

    def show_message(self, msg, timeout=0):
        self.showMessage(msg, timeout)
        if self.notifier is not None and not config['disable_tray_notification']:
            if isosx and isinstance(msg, unicode):
                try:
                    msg = msg.encode(preferred_encoding)
                except UnicodeEncodeError:
                    msg = msg.encode('utf-8')
            self.notifier(msg)

    def clear_message(self):
        self.clearMessage()

# }}}

class LayoutMixin(object): # {{{

    def __init__(self):

        if config['gui_layout'] == 'narrow': # narrow {{{
            self.book_details = BookDetails(False, self)
            self.stack = Stack(self)
            self.bd_splitter = Splitter('book_details_splitter',
                    _('Book Details'), I('book.png'),
                    orientation=Qt.Vertical, parent=self, side_index=1,
                    shortcut=_('Shift+Alt+D'))
            self.bd_splitter.addWidget(self.stack)
            self.bd_splitter.addWidget(self.book_details)
            self.bd_splitter.setCollapsible(self.bd_splitter.other_index, False)
            self.centralwidget.layout().addWidget(self.bd_splitter)
            button_order = ('tb', 'bd', 'cb')
        # }}}
        else: # wide {{{
            self.bd_splitter = Splitter('book_details_splitter',
                    _('Book Details'), I('book.png'), initial_side_size=200,
                    orientation=Qt.Horizontal, parent=self, side_index=1,
                    shortcut=_('Shift+Alt+D'))
            self.stack = Stack(self)
            self.bd_splitter.addWidget(self.stack)
            self.book_details = BookDetails(True, self)
            self.bd_splitter.addWidget(self.book_details)
            self.bd_splitter.setCollapsible(self.bd_splitter.other_index, False)
            self.bd_splitter.setSizePolicy(QSizePolicy(QSizePolicy.Expanding,
                QSizePolicy.Expanding))
            self.centralwidget.layout().addWidget(self.bd_splitter)
            button_order = ('tb', 'cb', 'bd')
        # }}}

        self.status_bar = StatusBar(self)
        stylename = unicode(self.style().objectName())
        for x in button_order:
            button = getattr(self, x+'_splitter').button
            button.setIconSize(QSize(24, 24))
            if isosx and stylename != u'Calibre':
                button.setStyleSheet('''
                        QToolButton { background: none; border:none; padding: 0px; }
                        QToolButton:checked { background: rgba(0, 0, 0, 25%); }
                ''')
            self.status_bar.addPermanentWidget(button)
        self.status_bar.addPermanentWidget(self.jobs_button)
        self.setStatusBar(self.status_bar)
        self.status_bar.update_label.linkActivated.connect(self.update_link_clicked)

    def finalize_layout(self):
        self.status_bar.initialize(self.system_tray_icon)
        self.book_details.show_book_info.connect(self.iactions['Show Book Details'].show_book_info)
        self.book_details.files_dropped.connect(self.iactions['Add Books'].files_dropped_on_book)
        self.book_details.cover_changed.connect(self.bd_cover_changed,
                type=Qt.QueuedConnection)
        self.book_details.cover_removed.connect(self.bd_cover_removed,
                type=Qt.QueuedConnection)
        self.book_details.remote_file_dropped.connect(
                self.iactions['Add Books'].remote_file_dropped_on_book,
                type=Qt.QueuedConnection)
        self.book_details.open_containing_folder.connect(self.iactions['View'].view_folder_for_id)
        self.book_details.view_specific_format.connect(self.iactions['View'].view_format_by_id)
        self.book_details.remove_specific_format.connect(
                self.iactions['Remove Books'].remove_format_by_id)
        self.book_details.save_specific_format.connect(
                self.iactions['Save To Disk'].save_library_format_by_ids)
        self.book_details.view_device_book.connect(
                self.iactions['View'].view_device_book)

        m = self.library_view.model()
        if m.rowCount(None) > 0:
            self.library_view.set_current_row(0)
            m.current_changed(self.library_view.currentIndex(),
                    self.library_view.currentIndex())
        self.library_view.setFocus(Qt.OtherFocusReason)

    def bd_cover_changed(self, id_, cdata):
        self.library_view.model().db.set_cover(id_, cdata)
        if self.cover_flow:
            self.cover_flow.dataChanged()

    def bd_cover_removed(self, id_):
        self.library_view.model().db.remove_cover(id_, commit=True,
                notify=False)
        if self.cover_flow:
            self.cover_flow.dataChanged()

    def save_layout_state(self):
        for x in ('library', 'memory', 'card_a', 'card_b'):
            getattr(self, x+'_view').save_state()

        for x in ('cb', 'tb', 'bd'):
            s = getattr(self, x+'_splitter')
            s.update_desired_state()
            s.save_state()

    def read_layout_settings(self):
        # View states are restored automatically when set_database is called

        for x in ('cb', 'tb', 'bd'):
            getattr(self, x+'_splitter').restore_state()

# }}}

