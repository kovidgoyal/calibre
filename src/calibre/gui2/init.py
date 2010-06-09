#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import functools

from PyQt4.Qt import QMenu, Qt, pyqtSignal, QToolButton, QIcon

from calibre.utils.config import prefs
from calibre.ebooks import BOOK_EXTENSIONS
from calibre.constants import isosx
from calibre.gui2 import config

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
        md = QMenu()
        md.addAction(_('Edit metadata individually'),
                partial(self.edit_metadata, False))
        md.addSeparator()
        md.addAction(_('Edit metadata in bulk'),
                partial(self.edit_metadata, False, bulk=True))
        md.addSeparator()
        md.addAction(_('Download metadata and covers'),
                partial(self.download_metadata, False, covers=True))
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
        self.action_del.setMenu(self.delete_menu)

        self.action_open_containing_folder.setShortcut(Qt.Key_O)
        self.addAction(self.action_open_containing_folder)
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
        ap = self.action_preferences
        pm.addAction(ap)
        pm.addAction(QIcon(I('wizard.svg')), _('Run welcome wizard'),
                self.run_wizard)
        self.action_preferences.setMenu(pm)
        self.preferences_menu = pm
        for x in (self.preferences_action, self.action_preferences):
            x.triggered.connect(self.do_config)

        for x in ('news', 'edit', 'sync', 'convert', 'save', 'add', 'view',
                'del', 'preferences'):
            w = self.tool_bar.widgetForAction(getattr(self, 'action_'+x))
            w.setPopupMode(w.MenuButtonPopup)

        self.tool_bar.setContextMenuPolicy(Qt.PreventContextMenu)

        for ch in self.tool_bar.children():
            if isinstance(ch, QToolButton):
                ch.setCursor(Qt.PointingHandCursor)

        self.tool_bar.contextMenuEvent = self.no_op

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
                                        similar_menu=similar_menu)

        self.memory_view.set_context_menu(None, None, None,
                self.action_view, self.action_save, None, None, self.action_del)
        self.card_a_view.set_context_menu(None, None, None,
                self.action_view, self.action_save, None, None, self.action_del)
        self.card_b_view.set_context_menu(None, None, None,
                self.action_view, self.action_save, None, None, self.action_del)

        self.library_view.files_dropped.connect(self.files_dropped, type=Qt.QueuedConnection)
        for func, args in [
                             ('connect_to_search_box', (self.search,
                                 self.search_done)),
                             ('connect_to_book_display',
                                 (self.status_bar.book_info.show_data,)),
                             ]:
            for view in (self.library_view, self.memory_view, self.card_a_view, self.card_b_view):
                getattr(view, func)(*args)

        self.memory_view.connect_dirtied_signal(self.upload_booklists)
        self.card_a_view.connect_dirtied_signal(self.upload_booklists)
        self.card_b_view.connect_dirtied_signal(self.upload_booklists)

        self.book_on_device(None, reset=True)
        db.set_book_on_device_func(self.book_on_device)
        self.library_view.set_database(db)
        self.library_view.model().set_book_on_device_func(self.book_on_device)
        prefs['library_path'] = self.library_path

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



    # }}}

