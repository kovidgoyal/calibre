#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import functools, sys, os

from PyQt4.Qt import QMenu, Qt, pyqtSignal, QIcon, QStackedWidget, \
        QSize, QSizePolicy, QStatusBar, QUrl, QLabel, QFont

from calibre.utils.config import prefs
from calibre.ebooks import BOOK_EXTENSIONS
from calibre.constants import isosx, __appname__, preferred_encoding, \
    __version__
from calibre.gui2 import config, is_widescreen, open_url
from calibre.gui2.library.views import BooksView, DeviceBooksView
from calibre.gui2.widgets import Splitter
from calibre.gui2.tag_view import TagBrowserWidget
from calibre.gui2.book_details import BookDetails
from calibre.gui2.notify import get_notifier

_keep_refs = []

def partial(*args, **kwargs):
    ans = functools.partial(*args, **kwargs)
    _keep_refs.append(ans)
    return ans

class SaveMenu(QMenu): # {{{

    save_fmt = pyqtSignal(object)

    def __init__(self, parent):
        QMenu.__init__(self, _('Save single format to disk...'), parent)
        for ext in sorted(BOOK_EXTENSIONS):
            action = self.addAction(ext.upper())
            setattr(self, 'do_'+ext, partial(self.do, ext))
            action.triggered.connect(
                    getattr(self, 'do_'+ext))

    def do(self, ext, *args):
        self.save_fmt.emit(ext)

# }}}

class ToolbarMixin(object): # {{{

    def __init__(self):
        self.action_help.triggered.connect(self.show_help)
        md = QMenu()
        md.addAction(_('Edit metadata individually'),
                partial(self.edit_metadata, False, bulk=False))
        md.addSeparator()
        md.addAction(_('Edit metadata in bulk'),
                partial(self.edit_metadata, False, bulk=True))
        md.addSeparator()
        md.addAction(_('Download metadata and covers'),
                partial(self.download_metadata, False, covers=True),
                Qt.ControlModifier+Qt.Key_D)
        md.addAction(_('Download only metadata'),
                partial(self.download_metadata, False, covers=False))
        md.addAction(_('Download only covers'),
                partial(self.download_metadata, False, covers=True,
                    set_metadata=False, set_social_metadata=False))
        md.addAction(_('Download only social metadata'),
                partial(self.download_metadata, False, covers=False,
                    set_metadata=False, set_social_metadata=True))
        self.metadata_menu = md

        mb = QMenu()
        mb.addAction(_('Merge into first selected book - delete others'),
                self.merge_books)
        mb.addSeparator()
        mb.addAction(_('Merge into first selected book - keep others'),
                partial(self.merge_books, safe_merge=True))
        self.merge_menu = mb
        self.action_merge.setMenu(mb)
        md.addSeparator()
        md.addAction(self.action_merge)

        self.add_menu = QMenu()
        self.add_menu.addAction(_('Add books from a single directory'),
                self.add_books)
        self.add_menu.addAction(_('Add books from directories, including '
            'sub-directories (One book per directory, assumes every ebook '
            'file is the same book in a different format)'),
            self.add_recursive_single)
        self.add_menu.addAction(_('Add books from directories, including '
            'sub directories (Multiple books per directory, assumes every '
            'ebook file is a different book)'), self.add_recursive_multiple)
        self.add_menu.addAction(_('Add Empty book. (Book entry with no '
            'formats)'), self.add_empty)
        self.action_add.setMenu(self.add_menu)
        self.action_add.triggered.connect(self.add_books)
        self.action_del.triggered.connect(self.delete_books)
        self.action_edit.triggered.connect(self.edit_metadata)
        self.action_merge.triggered.connect(self.merge_books)

        self.action_save.triggered.connect(self.save_to_disk)
        self.save_menu = QMenu()
        self.save_menu.addAction(_('Save to disk'), partial(self.save_to_disk,
            False))
        self.save_menu.addAction(_('Save to disk in a single directory'),
                partial(self.save_to_single_dir, False))
        self.save_menu.addAction(_('Save only %s format to disk')%
                prefs['output_format'].upper(),
                partial(self.save_single_format_to_disk, False))
        self.save_menu.addAction(
                _('Save only %s format to disk in a single directory')%
                prefs['output_format'].upper(),
                partial(self.save_single_fmt_to_single_dir, False))
        self.save_sub_menu = SaveMenu(self)
        self.save_menu.addMenu(self.save_sub_menu)
        self.save_sub_menu.save_fmt.connect(self.save_specific_format_disk)

        self.action_view.triggered.connect(self.view_book)
        self.view_menu = QMenu()
        self.view_menu.addAction(_('View'), partial(self.view_book, False))
        ac = self.view_menu.addAction(_('View specific format'))
        ac.setShortcut((Qt.ControlModifier if isosx else Qt.AltModifier)+Qt.Key_V)
        self.action_view.setMenu(self.view_menu)
        ac.triggered.connect(self.view_specific_format, type=Qt.QueuedConnection)

        self.delete_menu = QMenu()
        self.delete_menu.addAction(_('Remove selected books'), self.delete_books)
        self.delete_menu.addAction(
                _('Remove files of a specific format from selected books..'),
                self.delete_selected_formats)
        self.delete_menu.addAction(
                _('Remove all formats from selected books, except...'),
                self.delete_all_but_selected_formats)
        self.delete_menu.addAction(
                _('Remove covers from selected books'), self.delete_covers)
        self.delete_menu.addSeparator()
        self.delete_menu.addAction(
                _('Remove matching books from device'),
                self.remove_matching_books_from_device)
        self.action_del.setMenu(self.delete_menu)

        self.action_open_containing_folder.setShortcut(Qt.Key_O)
        self.addAction(self.action_open_containing_folder)
        self.action_open_containing_folder.triggered.connect(self.view_folder)
        self.action_sync.setShortcut(Qt.Key_D)
        self.action_sync.setEnabled(True)
        self.create_device_menu()
        self.action_sync.triggered.connect(
                self._sync_action_triggered)

        self.action_edit.setMenu(md)
        self.action_save.setMenu(self.save_menu)

        cm = QMenu()
        cm.addAction(_('Convert individually'), partial(self.convert_ebook,
            False, bulk=False))
        cm.addAction(_('Bulk convert'),
                partial(self.convert_ebook, False, bulk=True))
        cm.addSeparator()
        ac = cm.addAction(
                _('Create catalog of books in your calibre library'))
        ac.triggered.connect(self.generate_catalog)
        self.action_convert.setMenu(cm)
        self.action_convert.triggered.connect(self.convert_ebook)
        self.convert_menu = cm

        pm = QMenu()
        pm.addAction(QIcon(I('config.svg')), _('Preferences'), self.do_config)
        pm.addAction(QIcon(I('wizard.svg')), _('Run welcome wizard'),
                self.run_wizard)
        self.action_preferences.setMenu(pm)
        self.preferences_menu = pm
        for x in (self.preferences_action, self.action_preferences):
            x.triggered.connect(self.do_config)

    def show_help(self, *args):
        open_url(QUrl('http://calibre-ebook.com/user_manual'))

    def read_toolbar_settings(self):
        self.tool_bar.setIconSize(config['toolbar_icon_size'])
        self.tool_bar.setToolButtonStyle(
                Qt.ToolButtonTextUnderIcon if \
                    config['show_text_in_toolbar'] else \
                    Qt.ToolButtonIconOnly)

# }}}

class LibraryViewMixin(object): # {{{

    def __init__(self, db):
        similar_menu = QMenu(_('Similar books...'))
        similar_menu.addAction(self.action_books_by_same_author)
        similar_menu.addAction(self.action_books_in_this_series)
        similar_menu.addAction(self.action_books_with_the_same_tags)
        similar_menu.addAction(self.action_books_by_this_publisher)
        self.action_books_by_same_author.setShortcut(Qt.ALT + Qt.Key_A)
        self.action_books_in_this_series.setShortcut(Qt.ALT + Qt.Key_S)
        self.action_books_by_this_publisher.setShortcut(Qt.ALT + Qt.Key_P)
        self.action_books_with_the_same_tags.setShortcut(Qt.ALT+Qt.Key_T)
        self.addAction(self.action_books_by_same_author)
        self.addAction(self.action_books_by_this_publisher)
        self.addAction(self.action_books_in_this_series)
        self.addAction(self.action_books_with_the_same_tags)
        self.similar_menu = similar_menu
        self.action_books_by_same_author.triggered.connect(
                partial(self.show_similar_books, 'authors'))
        self.action_books_in_this_series.triggered.connect(
                partial(self.show_similar_books, 'series'))
        self.action_books_with_the_same_tags.triggered.connect(
                partial(self.show_similar_books, 'tag'))
        self.action_books_by_this_publisher.triggered.connect(
                partial(self.show_similar_books, 'publisher'))

        self.library_view.set_context_menu(self.action_edit, self.action_sync,
                                        self.action_convert, self.action_view,
                                        self.action_save,
                                        self.action_open_containing_folder,
                                        self.action_show_book_details,
                                        self.action_del,
                                        add_to_library = None,
                                        edit_device_collections=None,
                                        similar_menu=similar_menu)
        add_to_library = (_('Add books to library'), self.add_books_from_device)

        edit_device_collections = (_('Manage collections'),
                            partial(self.edit_device_collections, oncard=None))
        self.memory_view.set_context_menu(None, None, None,
                self.action_view, self.action_save, None, None, self.action_del,
                add_to_library=add_to_library,
                edit_device_collections=edit_device_collections)

        edit_device_collections = (_('Manage collections'),
                            partial(self.edit_device_collections, oncard='carda'))
        self.card_a_view.set_context_menu(None, None, None,
                self.action_view, self.action_save, None, None, self.action_del,
                add_to_library=add_to_library,
                edit_device_collections=edit_device_collections)

        edit_device_collections = (_('Manage collections'),
                            partial(self.edit_device_collections, oncard='cardb'))
        self.card_b_view.set_context_menu(None, None, None,
                self.action_view, self.action_save, None, None, self.action_del,
                add_to_library=add_to_library,
                edit_device_collections=edit_device_collections)

        self.library_view.files_dropped.connect(self.files_dropped, type=Qt.QueuedConnection)
        for func, args in [
                             ('connect_to_search_box', (self.search,
                                 self.search_done)),
                             ('connect_to_book_display',
                                 (self.book_details.show_data,)),
                             ]:
            for view in (self.library_view, self.memory_view, self.card_a_view, self.card_b_view):
                getattr(view, func)(*args)

        self.memory_view.connect_dirtied_signal(self.upload_booklists)
        self.memory_view.connect_upload_collections_signal(
                                    func=self.upload_collections, oncard=None)
        self.card_a_view.connect_dirtied_signal(self.upload_booklists)
        self.card_a_view.connect_upload_collections_signal(
                                    func=self.upload_collections, oncard='carda')
        self.card_b_view.connect_dirtied_signal(self.upload_booklists)
        self.card_b_view.connect_upload_collections_signal(
                                    func=self.upload_collections, oncard='cardb')
        self.book_on_device(None, reset=True)
        db.set_book_on_device_func(self.book_on_device)
        self.library_view.set_database(db)
        self.library_view.model().set_book_on_device_func(self.book_on_device)
        prefs['library_path'] = self.library_path

        for view in ('library', 'memory', 'card_a', 'card_b'):
            view = getattr(self, view+'_view')
            view.verticalHeader().sectionDoubleClicked.connect(self.view_specific_book)



    def show_similar_books(self, type, *args):
        search, join = [], ' '
        idx = self.library_view.currentIndex()
        if not idx.isValid():
            return
        row = idx.row()
        if type == 'series':
            series = idx.model().db.series(row)
            if series:
                search = ['series:"'+series+'"']
        elif type == 'publisher':
            publisher = idx.model().db.publisher(row)
            if publisher:
                search = ['publisher:"'+publisher+'"']
        elif type == 'tag':
            tags = idx.model().db.tags(row)
            if tags:
                search = ['tag:"='+t+'"' for t in tags.split(',')]
        elif type in ('author', 'authors'):
            authors = idx.model().db.authors(row)
            if authors:
                search = ['author:"='+a.strip().replace('|', ',')+'"' \
                                for a in authors.split(',')]
                join = ' or '
        if search:
            self.search.set_search_string(join.join(search))

    def search_done(self, view, ok):
        if view is self.current_view():
            self.search.search_done(ok)
            self.set_number_of_books_shown()

    # }}}

class LibraryWidget(Splitter): # {{{

    def __init__(self, parent):
        orientation = Qt.Vertical
        if config['gui_layout'] == 'narrow':
            orientation = Qt.Horizontal if is_widescreen() else Qt.Vertical
        idx = 0 if orientation == Qt.Vertical else 1
        size = 300 if orientation == Qt.Vertical else 550
        Splitter.__init__(self, 'cover_browser_splitter', _('Cover Browser'),
                I('cover_flow.svg'),
                orientation=orientation, parent=parent,
                connect_button=not config['separate_cover_flow'],
                side_index=idx, initial_side_size=size, initial_show=False)
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
                _('Tag Browser'), I('tags.svg'),
                parent=parent, side_index=0, initial_side_size=200)
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

class StatusBar(QStatusBar): # {{{

    def __init__(self, parent=None):
        QStatusBar.__init__(self, parent)
        self.default_message = __appname__ + ' ' + _('version') + ' ' + \
                self.get_version() + ' ' + _('created by Kovid Goyal')
        self.device_string = ''
        self.update_label = QLabel('')
        self.update_label.setOpenExternalLinks(True)
        self.addPermanentWidget(self.update_label)
        self.update_label.setVisible(False)
        self._font = QFont()
        self._font.setBold(True)
        self.setFont(self._font)

    def initialize(self, systray=None):
        self.systray = systray
        self.notifier = get_notifier(systray)
        self.messageChanged.connect(self.message_changed,
                type=Qt.QueuedConnection)
        self.message_changed('')

    def device_connected(self, devname):
        self.device_string = _('Connected ') + devname
        self.clearMessage()

    def device_disconnected(self):
        self.device_string = ''
        self.clearMessage()

    def new_version_available(self, ver, url):
        msg = (u'<span style="color:red; font-weight: bold">%s: <a href="%s">%s<a></span>') % (
                _('Update found'), url, ver)
        self.update_label.setText(msg)
        self.update_label.setCursor(Qt.PointingHandCursor)
        self.update_label.setVisible(True)

    def get_version(self):
        dv = os.environ.get('CALIBRE_DEVELOP_FROM', None)
        v = __version__
        if getattr(sys, 'frozen', False) and dv and os.path.abspath(dv) in sys.path:
            v += '*'
        return v

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

    def message_changed(self, msg):
        if not msg or msg.isEmpty() or msg.isNull() or \
                not unicode(msg).strip():
            extra = ''
            if self.device_string:
                extra = ' ..::.. ' + self.device_string
            self.showMessage(self.default_message + extra)


# }}}

class LayoutMixin(object): # {{{

    def __init__(self):

        if config['gui_layout'] == 'narrow': # narrow {{{
            self.book_details = BookDetails(False, self)
            self.stack = Stack(self)
            self.bd_splitter = Splitter('book_details_splitter',
                    _('Book Details'), I('book.svg'),
                    orientation=Qt.Vertical, parent=self, side_index=1)
            self.bd_splitter.addWidget(self.stack)
            self.bd_splitter.addWidget(self.book_details)
            self.bd_splitter.setCollapsible(self.bd_splitter.other_index, False)
            self.centralwidget.layout().addWidget(self.bd_splitter)
            # }}}
        else: # wide {{{
            self.bd_splitter = Splitter('book_details_splitter',
                    _('Book Details'), I('book.svg'), initial_side_size=200,
                    orientation=Qt.Horizontal, parent=self, side_index=1)
            self.stack = Stack(self)
            self.bd_splitter.addWidget(self.stack)
            self.book_details = BookDetails(True, self)
            self.bd_splitter.addWidget(self.book_details)
            self.bd_splitter.setCollapsible(self.bd_splitter.other_index, False)
            self.bd_splitter.setSizePolicy(QSizePolicy(QSizePolicy.Expanding,
                QSizePolicy.Expanding))
            self.centralwidget.layout().addWidget(self.bd_splitter)
        # }}}

        self.status_bar = StatusBar(self)
        for x in ('cb', 'tb', 'bd'):
            button = getattr(self, x+'_splitter').button
            button.setIconSize(QSize(24, 24))
            self.status_bar.addPermanentWidget(button)
        self.status_bar.addPermanentWidget(self.jobs_button)
        self.setStatusBar(self.status_bar)

    def finalize_layout(self):
        self.status_bar.initialize(self.system_tray_icon)
        self.book_details.show_book_info.connect(self.show_book_info)
        self.book_details.files_dropped.connect(self.files_dropped_on_book)
        self.book_details.open_containing_folder.connect(self.view_folder_for_id)
        self.book_details.view_specific_format.connect(self.view_format_by_id)

        m = self.library_view.model()
        if m.rowCount(None) > 0:
            self.library_view.set_current_row(0)
            m.current_changed(self.library_view.currentIndex(),
                    self.library_view.currentIndex())
        self.library_view.setFocus(Qt.OtherFocusReason)


    def save_layout_state(self):
        for x in ('library', 'memory', 'card_a', 'card_b'):
            getattr(self, x+'_view').save_state()

        for x in ('cb', 'tb', 'bd'):
            getattr(self, x+'_splitter').save_state()

    def read_layout_settings(self):
        # View states are restored automatically when set_database is called

        for x in ('cb', 'tb', 'bd'):
            getattr(self, x+'_splitter').restore_state()

# }}}

