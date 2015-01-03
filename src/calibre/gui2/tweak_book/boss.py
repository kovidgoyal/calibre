#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

import tempfile, shutil, sys, os
from functools import partial, wraps
from urlparse import urlparse

from PyQt5.Qt import (
    QObject, QApplication, QDialog, QGridLayout, QLabel, QSize, Qt,
    QDialogButtonBox, QIcon, QPixmap, QInputDialog, QUrl, pyqtSignal)

from calibre import prints, isbytestring
from calibre.ptempfile import PersistentTemporaryDirectory, TemporaryDirectory
from calibre.ebooks.oeb.base import urlnormalize
from calibre.ebooks.oeb.polish.main import SUPPORTED, tweak_polish
from calibre.ebooks.oeb.polish.container import get_container as _gc, clone_container, guess_type, OEB_DOCS, OEB_STYLES
from calibre.ebooks.oeb.polish.cover import mark_as_cover, mark_as_titlepage, set_cover
from calibre.ebooks.oeb.polish.css import filter_css
from calibre.ebooks.oeb.polish.pretty import fix_all_html, pretty_all
from calibre.ebooks.oeb.polish.replace import rename_files, replace_file, get_recommended_folders, rationalize_folders
from calibre.ebooks.oeb.polish.split import split, merge, AbortError, multisplit
from calibre.ebooks.oeb.polish.toc import remove_names_from_toc, find_existing_toc, create_inline_toc
from calibre.ebooks.oeb.polish.utils import link_stylesheets, setup_cssutils_serialization as scs
from calibre.gui2 import error_dialog, choose_files, question_dialog, info_dialog, choose_save_file, open_url
from calibre.gui2.dialogs.confirm_delete import confirm
from calibre.gui2.tweak_book import (
    set_current_container, current_container, tprefs, actions, editors,
    set_book_locale, dictionaries, editor_name)
from calibre.gui2.tweak_book.completion.worker import completion_worker
from calibre.gui2.tweak_book.undo import GlobalUndoHistory
from calibre.gui2.tweak_book.file_list import NewFileDialog
from calibre.gui2.tweak_book.save import SaveManager, save_container, find_first_existing_ancestor
from calibre.gui2.tweak_book.preview import parse_worker
from calibre.gui2.tweak_book.toc import TOCEditor
from calibre.gui2.tweak_book.editor import editor_from_syntax, syntax_from_mime
from calibre.gui2.tweak_book.editor.insert_resource import get_resource_data, NewBook
from calibre.gui2.tweak_book.preferences import Preferences
from calibre.gui2.tweak_book.search import validate_search_request, run_search
from calibre.gui2.tweak_book.spell import find_next as find_next_word, find_next_error
from calibre.gui2.tweak_book.widgets import (
    RationalizeFolders, MultiSplit, ImportForeign, QuickOpen, InsertLink,
    InsertSemantics, BusyCursor, InsertTag, FilterCSS, AddCover)

_diff_dialogs = []

def get_container(*args, **kwargs):
    kwargs['tweak_mode'] = True
    container = _gc(*args, **kwargs)
    return container

def setup_cssutils_serialization():
    scs(tprefs['editor_tab_stop_width'])

def in_thread_job(func):
    @wraps(func)
    def ans(*args, **kwargs):
        with BusyCursor():
            return func(*args, **kwargs)
    return ans

_boss = None
def get_boss():
    return _boss

class Boss(QObject):

    handle_completion_result_signal = pyqtSignal(object)

    def __init__(self, parent, notify=None):
        global _boss
        QObject.__init__(self, parent)
        self.global_undo = GlobalUndoHistory()
        self.container_count = 0
        self.tdir = None
        self.save_manager = SaveManager(parent, notify)
        self.save_manager.report_error.connect(self.report_save_error)
        self.save_manager.check_for_completion.connect(self.check_terminal_save)
        self.doing_terminal_save = False
        self.ignore_preview_to_editor_sync = False
        setup_cssutils_serialization()
        _boss = self
        self.gui = parent
        completion_worker().result_callback = self.handle_completion_result_signal.emit
        self.handle_completion_result_signal.connect(self.handle_completion_result, Qt.QueuedConnection)
        self.completion_request_count = 0

    def __call__(self, gui):
        self.gui = gui
        fl = gui.file_list
        fl.delete_requested.connect(self.delete_requested)
        fl.reorder_spine.connect(self.reorder_spine)
        fl.rename_requested.connect(self.rename_requested)
        fl.bulk_rename_requested.connect(self.bulk_rename_requested)
        fl.edit_file.connect(self.edit_file_requested)
        fl.merge_requested.connect(self.merge_requested)
        fl.mark_requested.connect(self.mark_requested)
        fl.export_requested.connect(self.export_requested)
        fl.replace_requested.connect(self.replace_requested)
        fl.link_stylesheets_requested.connect(self.link_stylesheets_requested)
        self.gui.central.current_editor_changed.connect(self.apply_current_editor_state)
        self.gui.central.close_requested.connect(self.editor_close_requested)
        self.gui.central.search_panel.search_triggered.connect(self.search)
        self.gui.preview.sync_requested.connect(self.sync_editor_to_preview)
        self.gui.preview.split_start_requested.connect(self.split_start_requested)
        self.gui.preview.split_requested.connect(self.split_requested)
        self.gui.preview.link_clicked.connect(self.link_clicked)
        self.gui.check_book.item_activated.connect(self.check_item_activated)
        self.gui.check_book.check_requested.connect(self.check_requested)
        self.gui.check_book.fix_requested.connect(self.fix_requested)
        self.gui.toc_view.navigate_requested.connect(self.link_clicked)
        self.gui.toc_view.refresh_requested.connect(self.commit_all_editors_to_container)
        self.gui.image_browser.image_activated.connect(self.image_activated)
        self.gui.checkpoints.revert_requested.connect(self.revert_requested)
        self.gui.checkpoints.compare_requested.connect(self.compare_requested)
        self.gui.saved_searches.run_saved_searches.connect(self.run_saved_searches)
        self.gui.central.search_panel.save_search.connect(self.save_search)
        self.gui.central.search_panel.show_saved_searches.connect(self.show_saved_searches)
        self.gui.spell_check.find_word.connect(self.find_word)
        self.gui.spell_check.refresh_requested.connect(self.commit_all_editors_to_container)
        self.gui.spell_check.word_replaced.connect(self.word_replaced)
        self.gui.spell_check.word_ignored.connect(self.word_ignored)
        self.gui.spell_check.change_requested.connect(self.word_change_requested)
        self.gui.live_css.goto_declaration.connect(self.goto_style_declaration)
        self.gui.manage_fonts.container_changed.connect(self.apply_container_update_to_gui)
        self.gui.manage_fonts.embed_all_fonts.connect(self.manage_fonts_embed)
        self.gui.manage_fonts.subset_all_fonts.connect(self.manage_fonts_subset)

    @property
    def currently_editing(self):
        ' Return the name of the file being edited currently or None if no file is being edited '
        return editor_name(self.gui.central.current_editor)

    def preferences(self):
        orig_spell = tprefs['inline_spell_check']
        p = Preferences(self.gui)
        ret = p.exec_()
        if p.dictionaries_changed:
            dictionaries.clear_caches()
            dictionaries.initialize(force=True)  # Reread user dictionaries
        if p.toolbars_changed:
            self.gui.populate_toolbars()
            for ed in editors.itervalues():
                if hasattr(ed, 'populate_toolbars'):
                    ed.populate_toolbars()
        if ret == p.Accepted:
            setup_cssutils_serialization()
            self.gui.apply_settings()
        if ret == p.Accepted or p.dictionaries_changed:
            for ed in editors.itervalues():
                ed.apply_settings(dictionaries_changed=p.dictionaries_changed)
        if orig_spell != tprefs['inline_spell_check']:
            from calibre.gui2.tweak_book.editor.syntax.html import refresh_spell_check_status
            refresh_spell_check_status()
            for ed in editors.itervalues():
                try:
                    ed.editor.highlighter.rehighlight()
                except AttributeError:
                    pass

    def mark_requested(self, name, action):
        self.commit_dirty_opf()
        c = current_container()
        if action == 'cover':
            mark_as_cover(current_container(), name)
        elif action.startswith('titlepage:'):
            action, move_to_start = action.partition(':')[0::2]
            move_to_start = move_to_start == 'True'
            mark_as_titlepage(current_container(), name, move_to_start=move_to_start)

        if c.opf_name in editors:
            editors[c.opf_name].replace_data(c.raw_data(c.opf_name))
        self.gui.file_list.build(c)
        self.set_modified()

    def mkdtemp(self, prefix=''):
        self.container_count += 1
        return tempfile.mkdtemp(prefix='%s%05d-' % (prefix, self.container_count), dir=self.tdir)

    def _check_before_open(self):
        if self.gui.action_save.isEnabled():
            if not question_dialog(self.gui, _('Unsaved changes'), _(
                'The current book has unsaved changes. If you open a new book, they will be lost'
                ' are you sure you want to proceed?')):
                return
        if self.save_manager.has_tasks:
            return info_dialog(self.gui, _('Cannot open'),
                        _('The current book is being saved, you cannot open a new book until'
                          ' the saving is completed'), show=True)
        return True

    def new_book(self):
        if not self._check_before_open():
            return
        d = NewBook(self.gui)
        if d.exec_() == d.Accepted:
            fmt = d.fmt.lower()
            path = choose_save_file(self.gui, 'edit-book-new-book', _('Choose file location'),
                                    filters=[(fmt.upper(), (fmt,))], all_files=False)
            if path is not None:
                if not path.lower().endswith('.' + fmt):
                    path = path + '.' + fmt
                from calibre.ebooks.oeb.polish.create import create_book
                create_book(d.mi, path, fmt=fmt)
                self.open_book(path=path)

    def import_book(self, path=None):
        if not self._check_before_open():
            return
        d = ImportForeign(self.gui)
        if hasattr(path, 'rstrip'):
            d.set_src(os.path.abspath(path))
        if d.exec_() == d.Accepted:
            for name in tuple(editors):
                self.close_editor(name)
            from calibre.ebooks.oeb.polish.import_book import import_book_as_epub
            src, dest = d.data
            self._clear_notify_data = True
            def func(src, dest, tdir):
                import_book_as_epub(src, dest)
                return get_container(dest, tdir=tdir)
            self.gui.blocking_job('import_book', _('Importing book, please wait...'), self.book_opened, func, src, dest, tdir=self.mkdtemp())

    def open_book(self, path=None, edit_file=None, clear_notify_data=True):
        '''
        Open the ebook at ``path`` for editing. Will show an error if the ebook is not in a supported format or the current book has unsaved changes.

        :param edit_file: The name of a file inside the newly opened book to start editing. Can also be a list of names.
        '''
        if not self._check_before_open():
            return
        if not hasattr(path, 'rpartition'):
            path = choose_files(self.gui, 'open-book-for-tweaking', _('Choose book'),
                                [(_('Books'), [x.lower() for x in SUPPORTED])], all_files=False, select_only_single_file=True)
            if not path:
                return
            path = path[0]

        ext = path.rpartition('.')[-1].upper()
        if ext not in SUPPORTED:
            from calibre.ebooks.oeb.polish.import_book import IMPORTABLE
            if ext.lower() in IMPORTABLE:
                return self.import_book(path)
            return error_dialog(self.gui, _('Unsupported format'),
                _('Tweaking is only supported for books in the %s formats.'
                  ' Convert your book to one of these formats first.') % _(' and ').join(sorted(SUPPORTED)),
                show=True)
        if not os.path.exists(path):
            return error_dialog(self.gui, _('File not found'), _(
                'The file %s does not exist.') % path, show=True)

        for name in tuple(editors):
            self.close_editor(name)
        self.gui.preview.clear()
        self.gui.live_css.clear()
        self.container_count = -1
        if self.tdir:
            shutil.rmtree(self.tdir, ignore_errors=True)
        self.tdir = PersistentTemporaryDirectory()
        self._edit_file_on_open = edit_file
        self._clear_notify_data = clear_notify_data
        self.gui.blocking_job('open_book', _('Opening book, please wait...'), self.book_opened, get_container, path, tdir=self.mkdtemp())

    def book_opened(self, job):
        ef = getattr(self, '_edit_file_on_open', None)
        cn = getattr(self, '_clear_notify_data', True)
        self._edit_file_on_open = None

        if job.traceback is not None:
            if 'DRMError:' in job.traceback:
                from calibre.gui2.dialogs.drm_error import DRMErrorMessage
                return DRMErrorMessage(self.gui).exec_()
            if 'ObfuscationKeyMissing:' in job.traceback:
                return error_dialog(self.gui, _('Failed to open book'), _(
                    'Failed to open book, it has obfuscated fonts, but the obfuscation key is missing from the OPF.'
                    ' Do an EPUB to EPUB conversion before trying to edit this book.'), show=True)

            return error_dialog(self.gui, _('Failed to open book'),
                    _('Failed to open book, click Show details for more information.'),
                                det_msg=job.traceback, show=True)
        if cn:
            self.save_manager.clear_notify_data()
        self.gui.check_book.clear_at_startup()
        dictionaries.clear_ignored(), dictionaries.clear_caches()
        parse_worker.clear()
        container = job.result
        set_current_container(container)
        completion_worker().clear_caches()
        with BusyCursor():
            self.current_metadata = self.gui.current_metadata = container.mi
            lang = container.opf_xpath('//dc:language/text()') or [self.current_metadata.language]
            set_book_locale(lang[0])
            self.global_undo.open_book(container)
            self.gui.update_window_title()
            self.gui.file_list.current_edited_name = None
            self.gui.file_list.build(container, preserve_state=False)
            self.gui.action_save.setEnabled(False)
            self.update_global_history_actions()
            recent_books = list(tprefs.get('recent-books', []))
            path = container.path_to_ebook
            if path in recent_books:
                recent_books.remove(path)
            recent_books.insert(0, path)
            tprefs['recent-books'] = recent_books[:10]
            self.gui.update_recent_books()
            if ef:
                if isinstance(ef, type('')):
                    ef = [ef]
                map(self.gui.file_list.request_edit, ef)
            self.gui.toc_view.update_if_visible()
            self.add_savepoint(_('Start of editing session'))

    def update_editors_from_container(self, container=None, names=None):
        c = container or current_container()
        for name, ed in tuple(editors.iteritems()):
            if c.has_name(name):
                if names is None or name in names:
                    ed.replace_data(c.raw_data(name))
                    ed.is_synced_to_container = True
            else:
                self.close_editor(name)

    def refresh_file_list(self):
        container = current_container()
        self.gui.file_list.build(container)
        completion_worker().clear_caches('names')

    def apply_container_update_to_gui(self, mark_as_modified=True):
        '''
        Update all the components of the user interface to reflect the latest data in the current book container.

        :param mark_as_modified: If True, the book will be marked as modified, so the user will be prompted to save it
            when quitting.
        '''
        self.refresh_file_list()
        self.update_global_history_actions()
        self.update_editors_from_container()
        if mark_as_modified:
            self.set_modified()
        self.gui.toc_view.update_if_visible()
        completion_worker().clear_caches()

    @in_thread_job
    def delete_requested(self, spine_items, other_items):
        self.add_savepoint(_('Before: Delete files'))
        c = current_container()
        c.remove_from_spine(spine_items)
        for name in other_items:
            c.remove_item(name)
        self.set_modified()
        self.gui.file_list.delete_done(spine_items, other_items)
        spine_names = [x for x, remove in spine_items if remove]
        completion_worker().clear_caches('names')
        for name in spine_names + list(other_items):
            if name in editors:
                self.close_editor(name)
        if not editors:
            self.gui.preview.clear()
            self.gui.live_css.clear()
        if remove_names_from_toc(current_container(), spine_names + list(other_items)):
            self.gui.toc_view.update_if_visible()
            toc = find_existing_toc(current_container())
            if toc and toc in editors:
                editors[toc].replace_data(c.raw_data(toc))

    def commit_dirty_opf(self):
        c = current_container()
        if c.opf_name in editors and not editors[c.opf_name].is_synced_to_container:
            self.commit_editor_to_container(c.opf_name)

    def reorder_spine(self, items):
        self.add_savepoint(_('Before: Re-order text'))
        c = current_container()
        c.set_spine(items)
        self.set_modified()
        self.gui.file_list.build(current_container())  # needed as the linear flag may have changed on some items
        if c.opf_name in editors:
            editors[c.opf_name].replace_data(c.raw_data(c.opf_name))
        completion_worker().clear_caches('names')

    def add_file(self):
        if current_container() is None:
            return error_dialog(self.gui, _('No open book'), _(
                'You must first open a book to tweak, before trying to create new files'
                ' in it.'), show=True)

        self.commit_dirty_opf()
        d = NewFileDialog(self.gui)
        if d.exec_() != d.Accepted:
            return
        self.do_add_file(d.file_name, d.file_data, using_template=d.using_template, edit_file=True)

    def do_add_file(self, file_name, data, using_template=False, edit_file=False):
        self.add_savepoint(_('Before: Add file %s') % self.gui.elided_text(file_name))
        c = current_container()
        adata = data.replace(b'%CURSOR%', b'') if using_template else data
        try:
            c.add_file(file_name, adata)
        except:
            self.rewind_savepoint()
            raise
        self.gui.file_list.build(c)
        self.gui.file_list.select_name(file_name)
        if c.opf_name in editors:
            editors[c.opf_name].replace_data(c.raw_data(c.opf_name))
        mt = c.mime_map[file_name]
        syntax = syntax_from_mime(file_name, mt)
        if syntax and edit_file:
            if using_template:
                self.edit_file(file_name, syntax, use_template=data.decode('utf-8'))
            else:
                self.edit_file(file_name, syntax)
        self.set_modified()
        completion_worker().clear_caches('names')

    def add_files(self):
        if current_container() is None:
            return error_dialog(self.gui, _('No open book'), _(
                'You must first open a book to tweak, before trying to create new files'
                ' in it.'), show=True)

        files = choose_files(self.gui, 'tweak-book-bulk-import-files', _('Choose files'))
        if files:
            folder_map = get_recommended_folders(current_container(), files)
            files = {x:('/'.join((folder, os.path.basename(x))) if folder else os.path.basename(x))
                     for x, folder in folder_map.iteritems()}
            self.add_savepoint(_('Before Add files'))
            c = current_container()
            for path, name in files.iteritems():
                i = 0
                while c.exists(name):
                    i += 1
                    name, ext = name.rpartition('.')[0::2]
                    name = '%s_%d.%s' % (name, i, ext)
                try:
                    with open(path, 'rb') as f:
                        c.add_file(name, f.read())
                except:
                    self.rewind_savepoint()
                    raise
            self.gui.file_list.build(c)
            if c.opf_name in editors:
                editors[c.opf_name].replace_data(c.raw_data(c.opf_name))
            self.set_modified()
            completion_worker().clear_caches('names')

    def add_cover(self):
        d = AddCover(current_container(), self.gui)
        d.import_requested.connect(self.do_add_file)
        try:
            if d.exec_() == d.Accepted and d.file_name is not None:
                report = []
                with BusyCursor():
                    self.add_savepoint(_('Before: Add cover'))
                    set_cover(current_container(), d.file_name, report.append, options={
                        'existing_image':True, 'keep_aspect':tprefs['add_cover_preserve_aspect_ratio']})
                    self.apply_container_update_to_gui()
        finally:
            d.import_requested.disconnect()

    def edit_toc(self):
        if current_container() is None:
            return error_dialog(self.gui, _('No book opened'), _(
                'You must open a book before trying to edit the Table of Contents.'), show=True)
        self.add_savepoint(_('Before: Edit Table of Contents'))
        d = TOCEditor(title=self.current_metadata.title, parent=self.gui)
        if d.exec_() != d.Accepted:
            self.rewind_savepoint()
            return
        with BusyCursor():
            self.set_modified()
            self.update_editors_from_container()
            self.gui.toc_view.update_if_visible()

    def insert_inline_toc(self):
        self.commit_all_editors_to_container()
        self.add_savepoint(_('Before: Insert inline Table of Contents'))
        name = create_inline_toc(current_container())
        if name is None:
            self.rewind_savepoint()
            return error_dialog(self.gui, _('No Table of Contents'), _(
                'Cannot create an inline Table of Contents as this book has no existing'
                ' Table of Contents. You must first create a Table of Contents using the'
                ' Edit Table of Contents tool.'), show=True)
        self.apply_container_update_to_gui()
        self.edit_file(name, 'html')

    def polish(self, action, name, parent=None):
        from calibre.gui2.tweak_book.polish import get_customization, show_report
        customization = get_customization(action, name, parent or self.gui)
        if customization is None:
            return
        with BusyCursor():
            self.add_savepoint(_('Before: %s') % name)
            try:
                report, changed = tweak_polish(current_container(), {action:True}, customization=customization)
            except:
                self.rewind_savepoint()
                raise
            if changed:
                self.apply_container_update_to_gui()
        if not changed:
            self.rewind_savepoint()
        show_report(changed, self.current_metadata.title, report, parent or self.gui, self.show_current_diff)

    def manage_fonts(self):
        self.commit_all_editors_to_container()
        self.gui.manage_fonts.display()

    def manage_fonts_embed(self):
        self.polish('embed', _('Embed all fonts'), parent=self.gui.manage_fonts)
        self.gui.manage_fonts.refresh()

    def manage_fonts_subset(self):
        self.polish('subset', _('Subset all fonts'), parent=self.gui.manage_fonts)

    # Renaming {{{

    def rationalize_folders(self):
        c = current_container()
        if not c.SUPPORTS_FILENAMES:
            return error_dialog(self.gui, _('Not supported'),
                _('The %s format does not support file and folder names internally, therefore'
                  ' arranging files into folders is not allowed.') % c.book_type.upper(), show=True)
        d = RationalizeFolders(self.gui)
        if d.exec_() != d.Accepted:
            return
        self.commit_all_editors_to_container()
        name_map = rationalize_folders(c, d.folder_map)
        if not name_map:
            return info_dialog(self.gui, _('Nothing to do'), _(
                'The files in this book are already arranged into folders'), show=True)
        self.add_savepoint(_('Before: Arrange into folders'))
        self.gui.blocking_job(
            'rationalize_folders', _('Renaming and updating links...'), partial(self.rename_done, name_map),
            rename_files, current_container(), name_map)

    def rename_requested(self, oldname, newname):
        self.commit_all_editors_to_container()
        if guess_type(oldname) != guess_type(newname):
            args = os.path.splitext(oldname) + os.path.splitext(newname)
            if not confirm(
                _('You are changing the file type of {0}<b>{1}</b> to {2}<b>{3}</b>.'
                  ' Doing so can cause problems, are you sure?').format(*args),
                'confirm-filetype-change', parent=self.gui, title=_('Are you sure?'),
                config_set=tprefs):
                return
        if urlnormalize(newname) != newname:
            if not confirm(
                _('The name you have chosen {0} contains special characters, internally'
                  ' it will look like: {1}Try to use only the English alphabet [a-z], numbers [0-9],'
                  ' hyphens and underscores for file names. Other characters can cause problems for '
                  ' different ebook viewers. Are you sure you want to proceed?').format(
                      '<pre>%s</pre>'%newname, '<pre>%s</pre>' % urlnormalize(newname)),
                'confirm-urlunsafe-change', parent=self.gui, title=_('Are you sure?'), config_set=tprefs):
                    return
        self.add_savepoint(_('Before: Rename %s') % oldname)
        name_map = {oldname:newname}
        self.gui.blocking_job(
            'rename_file', _('Renaming and updating links...'), partial(self.rename_done, name_map),
            rename_files, current_container(), name_map)

    def bulk_rename_requested(self, name_map):
        self.add_savepoint(_('Before: Bulk rename'))
        self.gui.blocking_job(
            'bulk_rename_files', _('Renaming and updating links...'), partial(self.rename_done, name_map),
            rename_files, current_container(), name_map)

    def rename_done(self, name_map, job):
        if job.traceback is not None:
            return error_dialog(self.gui, _('Failed to rename files'),
                    _('Failed to rename files, click Show details for more information.'),
                                det_msg=job.traceback, show=True)
        self.gui.file_list.build(current_container())
        self.set_modified()
        for oldname, newname in name_map.iteritems():
            if oldname in editors:
                editors[newname] = ed = editors.pop(oldname)
                ed.change_document_name(newname)
                self.gui.central.rename_editor(editors[newname], newname)
            if self.gui.preview.current_name == oldname:
                self.gui.preview.current_name = newname
        self.apply_container_update_to_gui()
    # }}}

    # Global history {{{
    def do_global_undo(self):
        container = self.global_undo.undo()
        if container is not None:
            set_current_container(container)
            self.apply_container_update_to_gui()

    def do_global_redo(self):
        container = self.global_undo.redo()
        if container is not None:
            set_current_container(container)
            self.apply_container_update_to_gui()

    def update_global_history_actions(self):
        gu = self.global_undo
        for x, text in (('undo', _('&Revert to')), ('redo', _('&Revert to'))):
            ac = getattr(self.gui, 'action_global_%s' % x)
            ac.setEnabled(getattr(gu, 'can_' + x))
            ac.setText(text + ' "%s"'%(getattr(gu, x + '_msg') or '...'))

    def add_savepoint(self, msg):
        ' Create a restore checkpoint with the name specified as ``msg`` '
        self.commit_all_editors_to_container()
        nc = clone_container(current_container(), self.mkdtemp())
        self.global_undo.add_savepoint(nc, msg)
        set_current_container(nc)
        self.update_global_history_actions()

    def rewind_savepoint(self):
        ' Undo the previous creation of a restore checkpoint, useful if you create a checkpoint, then abort the operation with no changes '
        container = self.global_undo.rewind_savepoint()
        if container is not None:
            set_current_container(container)
            self.update_global_history_actions()

    def create_diff_dialog(self, revert_msg=_('&Revert changes'), show_open_in_editor=True):
        global _diff_dialogs
        from calibre.gui2.tweak_book.diff.main import Diff
        def line_activated(name, lnum, right):
            if right:
                self.edit_file_requested(name, None, guess_type(name))
                if name in editors:
                    editor = editors[name]
                    editor.go_to_line(lnum)
                    editor.setFocus(Qt.OtherFocusReason)
                    self.gui.raise_()
        d = Diff(revert_button_msg=revert_msg, show_open_in_editor=show_open_in_editor)
        [x.break_cycles() for x in _diff_dialogs if not x.isVisible()]
        _diff_dialogs = [x for x in _diff_dialogs if x.isVisible()] + [d]
        d.show(), d.raise_(), d.setFocus(Qt.OtherFocusReason), d.setWindowModality(Qt.NonModal)
        if show_open_in_editor:
            d.line_activated.connect(line_activated)
        return d

    def show_current_diff(self, allow_revert=True, to_container=None):
        '''
        Show the changes to the book from its last checkpointed state

        :param allow_revert: If True the diff dialog will have a button to allow the user to revert all changes
        :param to_container: A container object to compare the current container to. If None, the previously checkpointed container is used
        '''
        self.commit_all_editors_to_container()
        d = self.create_diff_dialog()
        d.revert_requested.connect(partial(self.revert_requested, self.global_undo.previous_container))
        other = to_container or self.global_undo.previous_container
        d.container_diff(other, self.global_undo.current_container,
                         names=(self.global_undo.label_for_container(other), self.global_undo.label_for_container(self.global_undo.current_container)))

    def compare_book(self):
        self.commit_all_editors_to_container()
        c = current_container()
        path = choose_files(self.gui, 'select-book-for-comparison', _('Choose book'), filters=[
            (_('%s books') % c.book_type.upper(), (c.book_type,))], select_only_single_file=True, all_files=False)
        if path and path[0]:
            with TemporaryDirectory('_compare') as tdir:
                other = _gc(path[0], tdir=tdir, tweak_mode=True)
                d = self.create_diff_dialog(revert_msg=None)
                d.container_diff(other, c,
                                 names=(_('Other book'), _('Current book')))

    def revert_requested(self, container):
        self.commit_all_editors_to_container()
        nc = self.global_undo.revert_to(container)
        set_current_container(nc)
        self.apply_container_update_to_gui()

    def compare_requested(self, container):
        self.show_current_diff(to_container=container)

    # }}}

    def set_modified(self):
        ' Mark the book as having been modified '
        self.gui.action_save.setEnabled(True)

    def request_completion(self, name, completion_type, completion_data, query=None):
        if completion_type is None:
            completion_worker().clear_caches(completion_data)
            return
        request_id = (self.completion_request_count, name)
        self.completion_request_count += 1
        completion_worker().queue_completion(request_id, completion_type, completion_data, query)
        return request_id[0]

    def handle_completion_result(self, result):
        name = result.request_id[1]
        editor = editors.get(name)
        if editor is not None:
            editor.handle_completion_result(result)

    def fix_html(self, current):
        if current:
            ed = self.gui.central.current_editor
            if hasattr(ed, 'fix_html'):
                ed.fix_html()
        else:
            with BusyCursor():
                self.add_savepoint(_('Before: Fix HTML'))
                fix_all_html(current_container())
                self.update_editors_from_container()
                self.set_modified()

    def pretty_print(self, current):
        if current:
            ed = self.gui.central.current_editor
            ed.pretty_print(editor_name(ed))
        else:
            with BusyCursor():
                self.add_savepoint(_('Before: Beautify files'))
                pretty_all(current_container())
                self.update_editors_from_container()
                self.set_modified()

    def mark_selected_text(self):
        ed = self.gui.central.current_editor
        if ed is not None:
            ed.mark_selected_text()
            if ed.has_marked_text:
                self.gui.central.search_panel.set_where('selected-text')

    def editor_action(self, action):
        ed = self.gui.central.current_editor
        edname = editor_name(ed)
        if hasattr(ed, 'action_triggered'):
            if action and action[0] == 'insert_resource':
                rtype = action[1]
                if rtype == 'image' and ed.syntax not in {'css', 'html'}:
                    return error_dialog(self.gui, _('Not supported'), _(
                        'Inserting images is only supported for HTML and CSS files.'), show=True)
                rdata = get_resource_data(rtype, self.gui)
                if rdata is None:
                    return
                if rtype == 'image':
                    chosen_name, chosen_image_is_external = rdata
                    if chosen_image_is_external:
                        with open(chosen_image_is_external[1], 'rb') as f:
                            current_container().add_file(chosen_image_is_external[0], f.read())
                        self.refresh_file_list()
                        chosen_name = chosen_image_is_external[0]
                    href = current_container().name_to_href(chosen_name, edname)
                    ed.insert_image(href)
            elif action[0] == 'insert_hyperlink':
                self.commit_all_editors_to_container()
                d = InsertLink(current_container(), edname, initial_text=ed.get_smart_selection(), parent=self.gui)
                if d.exec_() == d.Accepted:
                    ed.insert_hyperlink(d.href, d.text)
            elif action[0] == 'insert_tag':
                d = InsertTag(parent=self.gui)
                if d.exec_() == d.Accepted:
                    ed.insert_tag(d.tag)
            else:
                ed.action_triggered(action)

    def set_semantics(self):
        self.commit_all_editors_to_container()
        c = current_container()
        if c.book_type == 'azw3':
            return error_dialog(self.gui, _('Not supported'), _(
                'Semantics are not supported for the AZW3 format.'), show=True)
        d = InsertSemantics(c, parent=self.gui)
        if d.exec_() == d.Accepted and d.changed_type_map:
            self.add_savepoint(_('Before: Set Semantics'))
            d.apply_changes(current_container())
            self.apply_container_update_to_gui()

    def filter_css(self):
        self.commit_all_editors_to_container()
        c = current_container()
        ed = self.gui.central.current_editor
        current_name = editor_name(ed)
        if current_name and c.mime_map[current_name] not in OEB_DOCS | OEB_STYLES:
            current_name = None
        d = FilterCSS(current_name=current_name, parent=self.gui)
        if d.exec_() == d.Accepted and d.filtered_properties:
            self.add_savepoint(_('Before: Filter style information'))
            with BusyCursor():
                changed = filter_css(current_container(), d.filtered_properties, names=d.filter_names)
            if changed:
                self.apply_container_update_to_gui()
                self.show_current_diff()
            else:
                self.rewind_savepoint()
                return info_dialog(self.gui, _('No matches'), _(
                    'No matching style rules were found'), show=True)

    def show_find(self):
        self.gui.central.show_find()
        ed = self.gui.central.current_editor
        if ed is not None and hasattr(ed, 'selected_text'):
            text = ed.selected_text
            if text and text.strip():
                self.gui.central.pre_fill_search(text)

    def search_action_triggered(self, action, overrides=None):
        ss = self.gui.saved_searches.isVisible()
        trigger_saved_search = ss and (not self.gui.central.search_panel.isVisible() or self.gui.saved_searches.has_focus())
        if trigger_saved_search:
            return self.gui.saved_searches.trigger_action(action, overrides=overrides)
        self.search(action, overrides)

    def run_saved_searches(self, searches, action):
        ed = self.gui.central.current_editor
        name = editor_name(ed)
        searchable_names = self.gui.file_list.searchable_names
        if not searches or not validate_search_request(name, searchable_names, getattr(ed, 'has_marked_text', False), searches[0], self.gui):
            return
        ret = run_search(searches, action, ed, name, searchable_names,
                   self.gui, self.show_editor, self.edit_file, self.show_current_diff, self.add_savepoint, self.rewind_savepoint, self.set_modified)
        ed = ret is True and self.gui.central.current_editor
        if getattr(ed, 'has_line_numbers', False):
            ed.editor.setFocus(Qt.OtherFocusReason)
        else:
            self.gui.saved_searches.setFocus(Qt.OtherFocusReason)

    def search(self, action, overrides=None):
        # Run a search/replace
        sp = self.gui.central.search_panel
        # Ensure the search panel is visible
        sp.setVisible(True)
        ed = self.gui.central.current_editor
        name = editor_name(ed)
        state = sp.state
        if overrides:
            state.update(overrides)
        searchable_names = self.gui.file_list.searchable_names
        if not validate_search_request(name, searchable_names, getattr(ed, 'has_marked_text', False), state, self.gui):
            return

        ret = run_search(state, action, ed, name, searchable_names,
                   self.gui, self.show_editor, self.edit_file, self.show_current_diff, self.add_savepoint, self.rewind_savepoint, self.set_modified)
        ed = ret is True and self.gui.central.current_editor
        if getattr(ed, 'has_line_numbers', False):
            ed.editor.setFocus(Qt.OtherFocusReason)
        else:
            self.gui.saved_searches.setFocus(Qt.OtherFocusReason)

    def find_word(self, word, locations):
        # Go to a word from the spell check dialog
        ed = self.gui.central.current_editor
        name = editor_name(ed)
        find_next_word(word, locations, ed, name, self.gui, self.show_editor, self.edit_file)

    def next_spell_error(self):
        # Go to the next spelling error
        ed = self.gui.central.current_editor
        name = editor_name(ed)
        find_next_error(ed, name, self.gui, self.show_editor, self.edit_file)

    def word_change_requested(self, w, new_word):
        if self.commit_all_editors_to_container():
            self.gui.spell_check.change_word_after_update(w, new_word)
        else:
            self.gui.spell_check.do_change_word(w, new_word)

    def word_replaced(self, changed_names):
        self.set_modified()
        self.update_editors_from_container(names=set(changed_names))

    def word_ignored(self, word, locale):
        if tprefs['inline_spell_check']:
            for ed in editors.itervalues():
                try:
                    ed.editor.recheck_word(word, locale)
                except AttributeError:
                    pass

    def editor_link_clicked(self, url):
        ed = self.gui.central.current_editor
        name = editor_name(ed)
        if url.startswith('#'):
            target = name
        else:
            target = current_container().href_to_name(url, name)
        frag = url.partition('#')[-1]
        if current_container().has_name(target):
            self.link_clicked(target, frag, show_anchor_not_found=True)
        else:
            purl = urlparse(url)
            if purl.scheme not in {'', 'file'}:
                open_url(QUrl(url))
            else:
                error_dialog(self.gui, _('Not found'), _(
                    'No file with the name %s was found in the book') % target, show=True)

    def save_search(self):
        state = self.gui.central.search_panel.state
        self.show_saved_searches()
        self.gui.saved_searches.add_predefined_search(state)

    def show_saved_searches(self):
        self.gui.saved_searches_dock.show()
    saved_searches = show_saved_searches

    def create_checkpoint(self):
        text, ok = QInputDialog.getText(self.gui, _('Choose name'), _(
            'Choose a name for the checkpoint.\nYou can later restore the book'
            ' to this checkpoint via the\n"Revert to..." entries in the Edit menu.'))
        if ok:
            self.add_savepoint(text)

    def commit_editor_to_container(self, name, container=None):
        container = container or current_container()
        ed = editors[name]
        with container.open(name, 'wb') as f:
            f.write(ed.data)
        if name == container.opf_name:
            container.refresh_mime_map()
            set_book_locale(container.mi.language)
        if container is current_container():
            ed.is_synced_to_container = True
            if name == container.opf_name:
                self.gui.file_list.build(container)

    def commit_all_editors_to_container(self):
        ''' Commit any changes that the user has made to files open in editors to
        the container. You should call this method before performing any
        actions on the current container '''
        changed = False
        with BusyCursor():
            for name, ed in editors.iteritems():
                if not ed.is_synced_to_container:
                    self.commit_editor_to_container(name)
                    ed.is_synced_to_container = True
                    changed = True
        return changed

    def save_book(self):
        ' Save the book. Saving is performed in the background '
        c = current_container()
        for name, ed in editors.iteritems():
            if ed.is_modified or not ed.is_synced_to_container:
                self.commit_editor_to_container(name, c)
                ed.is_modified = False
        path_to_ebook = os.path.abspath(c.path_to_ebook)
        destdir = os.path.dirname(path_to_ebook)
        if not os.path.exists(destdir):
            info_dialog(self.gui, _('Path does not exist'), _(
                'The file you are editing (%s) no longer exists. You have to choose a new save location.') % path_to_ebook,
                        show_copy_button=False, show=True)
            fmt = path_to_ebook.rpartition('.')[-1].lower()
            start_dir = find_first_existing_ancestor(path_to_ebook)
            path = choose_save_file(
                self.gui, 'choose-new-save-location', _('Choose file location'), initial_path=os.path.join(start_dir, os.path.basename(path_to_ebook)),
                filters=[(fmt.upper(), (fmt,))], all_files=False)
            if path is not None:
                if not path.lower().endswith('.' + fmt):
                    path = path + '.' + fmt
                path = os.path.abspath(path)
                c.path_to_ebook = path
                self.global_undo.update_path_to_ebook(path)
            else:
                return
        self.gui.action_save.setEnabled(False)
        tdir = self.mkdtemp(prefix='save-')
        container = clone_container(c, tdir)
        self.save_manager.schedule(tdir, container)

    def save_copy(self):
        c = current_container()
        ext = c.path_to_ebook.rpartition('.')[-1]
        path = choose_save_file(self.gui, 'tweak_book_save_copy', _(
            'Choose path'), filters=[(_('Book (%s)') % ext.upper(), [ext.lower()])], all_files=False)
        if not path:
            return
        tdir = self.mkdtemp(prefix='save-copy-')
        container = clone_container(c, tdir)
        for name, ed in editors.iteritems():
            if ed.is_modified or not ed.is_synced_to_container:
                self.commit_editor_to_container(name, container)

        def do_save(c, path, tdir):
            save_container(c, path)
            shutil.rmtree(tdir, ignore_errors=True)
            return path

        self.gui.blocking_job('save_copy', _('Saving copy, please wait...'), self.copy_saved, do_save, container, path, tdir)

    def copy_saved(self, job):
        if job.traceback is not None:
            return error_dialog(self.gui, _('Failed to save copy'),
                    _('Failed to save copy, click Show details for more information.'), det_msg=job.traceback, show=True)
        msg = _('Copy saved to %s') % job.result
        info_dialog(self.gui, _('Copy saved'), msg, show=True)
        self.gui.show_status_message(msg, 5)

    def report_save_error(self, tb):
        if self.doing_terminal_save:
            prints(tb, file=sys.stderr)
            self.abort_terminal_save()
        self.set_modified()
        error_dialog(self.gui, _('Could not save'),
                     _('Saving of the book failed. Click "Show Details"'
                       ' for more information. You can try to save a copy'
                       ' to a different location, via File->Save a Copy'), det_msg=tb, show=True)

    def go_to_line_number(self):
        ed = self.gui.central.current_editor
        if ed is None or not ed.has_line_numbers:
            return
        num, ok = QInputDialog.getInt(self.gui, _('Enter line number'), ('Line number:'), ed.current_line, 1, max(100000, ed.number_of_lines))
        if ok:
            ed.current_line = num

    def split_start_requested(self):
        self.commit_all_editors_to_container()
        self.gui.preview.do_start_split()

    @in_thread_job
    def split_requested(self, name, loc, totals):
        self.add_savepoint(_('Before: Split %s') % self.gui.elided_text(name))
        try:
            bottom_name = split(current_container(), name, loc, totals=totals)
        except AbortError:
            self.rewind_savepoint()
            raise
        self.apply_container_update_to_gui()
        self.edit_file(bottom_name, 'html')

    def multisplit(self):
        ed = self.gui.central.current_editor
        if ed.syntax != 'html':
            return
        name = editor_name(ed)
        if name is None:
            return
        d = MultiSplit(self.gui)
        if d.exec_() == d.Accepted:
            with BusyCursor():
                self.add_savepoint(_('Before: Split %s') % self.gui.elided_text(name))
                try:
                    multisplit(current_container(), name, d.xpath)
                except AbortError:
                    self.rewind_savepoint()
                    raise
                self.apply_container_update_to_gui()

    def link_clicked(self, name, anchor, show_anchor_not_found=False):
        if not name:
            return
        if name in editors:
            editor = editors[name]
            self.gui.central.show_editor(editor)
        else:
            try:
                mt = current_container().mime_map[name]
            except KeyError:
                return error_dialog(self.gui, _('Does not exist'), _(
                    'The file %s does not exist. If you were trying to click an item in'
                    ' the Table of Contents, you may'
                    ' need to refresh it by right-clicking and choosing "Refresh".') % name, show=True)
            syntax = syntax_from_mime(name, mt)
            if not syntax:
                return error_dialog(
                    self.gui, _('Unsupported file format'),
                    _('Editing files of type %s is not supported' % mt), show=True)
            editor = self.edit_file(name, syntax)
        if anchor and editor is not None:
            if not editor.go_to_anchor(anchor) and show_anchor_not_found:
                error_dialog(self.gui, _('Not found'), _(
                    'The anchor %s was not found in this file') % anchor, show=True)

    @in_thread_job
    def check_item_activated(self, item):
        is_mult = item.has_multiple_locations and getattr(item, 'current_location_index', None) is not None
        name = item.all_locations[item.current_location_index][0] if is_mult else item.name
        if name in editors:
            editor = editors[name]
            self.gui.central.show_editor(editor)
        else:
            editor = self.edit_file_requested(name, None, current_container().mime_map[name])
        if getattr(editor, 'has_line_numbers', False):
            if is_mult:
                editor.go_to_line(*(item.all_locations[item.current_location_index][1:3]))
            else:
                editor.go_to_line(item.line, item.col)
            editor.set_focus()

    @in_thread_job
    def check_requested(self, *args):
        if current_container() is None:
            return
        self.commit_all_editors_to_container()
        c = self.gui.check_book
        c.parent().show()
        c.parent().raise_()
        c.run_checks(current_container())

    def spell_check_requested(self):
        if current_container() is None:
            return
        self.commit_all_editors_to_container()
        self.gui.spell_check.show()

    @in_thread_job
    def fix_requested(self, errors):
        self.add_savepoint(_('Before: Auto-fix errors'))
        c = self.gui.check_book
        c.parent().show()
        c.parent().raise_()
        changed = c.fix_errors(current_container(), errors)
        if changed:
            self.apply_container_update_to_gui()
            self.set_modified()
        else:
            self.rewind_savepoint()

    @in_thread_job
    def merge_requested(self, category, names, master):
        self.add_savepoint(_('Before: Merge files into %s') % self.gui.elided_text(master))
        try:
            merge(current_container(), category, names, master)
        except AbortError:
            self.rewind_savepoint()
            raise
        self.apply_container_update_to_gui()
        if master in editors:
            self.show_editor(master)

    @in_thread_job
    def link_stylesheets_requested(self, names, sheets, remove):
        self.add_savepoint(_('Before: Link stylesheets'))
        changed_names = link_stylesheets(current_container(), names, sheets, remove)
        if changed_names:
            self.update_editors_from_container(names=changed_names)
            self.set_modified()

    @in_thread_job
    def export_requested(self, name, path):
        if name in editors and not editors[name].is_synced_to_container:
            self.commit_editor_to_container(name)
        with current_container().open(name, 'rb') as src, open(path, 'wb') as dest:
            shutil.copyfileobj(src, dest)

    @in_thread_job
    def replace_requested(self, name, path, basename, force_mt):
        self.add_savepoint(_('Before: Replace %s') % name)
        replace_file(current_container(), name, path, basename, force_mt)
        self.apply_container_update_to_gui()

    def browse_images(self):
        self.gui.image_browser.refresh()
        self.gui.image_browser.show()
        self.gui.image_browser.raise_()

    def image_activated(self, name):
        mt = current_container().mime_map.get(name, guess_type(name))
        self.edit_file_requested(name, None, mt)

    def sync_editor_to_preview(self, name, sourceline_address):
        editor = self.edit_file(name, 'html')
        self.ignore_preview_to_editor_sync = True
        try:
            editor.goto_sourceline(*sourceline_address)
        finally:
            self.ignore_preview_to_editor_sync = False

    def sync_preview_to_editor(self):
        ' Sync the position of the preview panel to the current cursor position in the current editor '
        if self.ignore_preview_to_editor_sync:
            return
        ed = self.gui.central.current_editor
        if ed is not None:
            name = editor_name(ed)
            if name is not None and getattr(ed, 'syntax', None) == 'html':
                self.gui.preview.sync_to_editor(name, ed.current_tag())

    def goto_style_declaration(self, data):
        name = data['name']
        editor = self.edit_file(name, syntax=data['syntax'])
        self.gui.live_css.navigate_to_declaration(data, editor)

    def init_editor(self, name, editor, data=None, use_template=False):
        editor.undo_redo_state_changed.connect(self.editor_undo_redo_state_changed)
        editor.data_changed.connect(self.editor_data_changed)
        editor.copy_available_state_changed.connect(self.editor_copy_available_state_changed)
        editor.cursor_position_changed.connect(self.sync_preview_to_editor)
        editor.cursor_position_changed.connect(self.update_cursor_position)
        if hasattr(editor, 'word_ignored'):
            editor.word_ignored.connect(self.word_ignored)
        if hasattr(editor, 'link_clicked'):
            editor.link_clicked.connect(self.editor_link_clicked)
        if getattr(editor, 'syntax', None) == 'html':
            editor.smart_highlighting_updated.connect(self.gui.live_css.sync_to_editor)
        if hasattr(editor, 'set_request_completion'):
            editor.set_request_completion(partial(self.request_completion, name), name)
        if data is not None:
            if use_template:
                editor.init_from_template(data)
            else:
                editor.data = data
                editor.is_synced_to_container = True
        editor.modification_state_changed.connect(self.editor_modification_state_changed)
        self.gui.central.add_editor(name, editor)

    def edit_file(self, name, syntax=None, use_template=None):
        ''' Open the file specified by name in an editor

        :param syntax: The media type of the file, for example, ``'text/html'``. If not specified it is guessed from the file extension.
        :param use_template: A template to initialize the opened editor with
        '''
        editor = editors.get(name, None)
        if editor is None:
            syntax = syntax or syntax_from_mime(name, guess_type(name))
            if use_template is None:
                data = current_container().raw_data(name)
                if isbytestring(data) and syntax in {'html', 'css', 'text', 'xml'}:
                    try:
                        data = data.decode('utf-8')
                    except UnicodeDecodeError:
                        return error_dialog(self.gui, _('Cannot decode'), _(
                            'Cannot edit %s as it appears to be in an unknown character encoding') % name, show=True)
            else:
                data = use_template
            editor = editors[name] = editor_from_syntax(syntax, self.gui.editor_tabs)
            self.init_editor(name, editor, data, use_template=bool(use_template))
            if tprefs['pretty_print_on_open']:
                editor.pretty_print(name)
        self.show_editor(name)
        return editor

    def show_editor(self, name):
        ' Show the editor that is editing the file specified by ``name`` '
        self.gui.central.show_editor(editors[name])
        editors[name].set_focus()

    def edit_file_requested(self, name, syntax, mime):
        if name in editors:
            self.gui.central.show_editor(editors[name])
            return
        syntax = syntax or syntax_from_mime(name, mime)
        if not syntax:
            return error_dialog(
                self.gui, _('Unsupported file format'),
                _('Editing files of type %s is not supported' % mime), show=True)
        return self.edit_file(name, syntax)

    def quick_open(self):
        c = current_container()
        if c is None:
            return error_dialog(self.gui, _('No open book'), _(
                'No book is currently open. You must first open a book to edit.'), show=True)
        files = [name for name, mime in c.mime_map.iteritems() if c.exists(name) and syntax_from_mime(name, mime) is not None]
        d = QuickOpen(files, parent=self.gui)
        if d.exec_() == d.Accepted and d.selected_result is not None:
            self.edit_file_requested(d.selected_result, None, c.mime_map[d.selected_result])

    # Editor basic controls {{{
    def do_editor_undo(self):
        ed = self.gui.central.current_editor
        if ed is not None:
            ed.undo()

    def do_editor_redo(self):
        ed = self.gui.central.current_editor
        if ed is not None:
            ed.redo()

    def do_editor_copy(self):
        ed = self.gui.central.current_editor
        if ed is not None:
            ed.copy()

    def do_editor_cut(self):
        ed = self.gui.central.current_editor
        if ed is not None:
            ed.cut()

    def do_editor_paste(self):
        ed = self.gui.central.current_editor
        if ed is not None:
            ed.paste()

    def editor_data_changed(self, editor):
        self.gui.preview.start_refresh_timer()
        for name, ed in editors.iteritems():
            if ed is editor:
                self.gui.toc_view.start_refresh_timer(name)
                break

    def editor_undo_redo_state_changed(self, *args):
        self.apply_current_editor_state()

    def editor_copy_available_state_changed(self, *args):
        self.apply_current_editor_state()

    def editor_modification_state_changed(self, is_modified):
        self.apply_current_editor_state()
        if is_modified:
            self.set_modified()
    # }}}

    def apply_current_editor_state(self):
        ed = self.gui.central.current_editor
        self.gui.cursor_position_widget.update_position()
        if ed is not None:
            actions['editor-undo'].setEnabled(ed.undo_available)
            actions['editor-redo'].setEnabled(ed.redo_available)
            actions['editor-copy'].setEnabled(ed.copy_available)
            actions['editor-cut'].setEnabled(ed.cut_available)
            actions['go-to-line-number'].setEnabled(ed.has_line_numbers)
            actions['fix-html-current'].setEnabled(ed.syntax == 'html')
            name = editor_name(ed)
            if name is not None and getattr(ed, 'syntax', None) == 'html':
                if self.gui.preview.show(name):
                    # The file being displayed by the preview has changed.
                    # Set the preview's position to the current cursor
                    # position in the editor, in case the editors' cursor
                    # position has not changed, since the last time it was
                    # focused. This is not inefficient since multiple requests
                    # to sync are de-bounced with a 100 msec wait.
                    self.sync_preview_to_editor()
            if name is not None:
                self.gui.file_list.mark_name_as_current(name)
            if ed.has_line_numbers:
                self.gui.cursor_position_widget.update_position(*ed.cursor_position)
        else:
            actions['go-to-line-number'].setEnabled(False)
            self.gui.file_list.clear_currently_edited_name()

    def update_cursor_position(self):
        ed = self.gui.central.current_editor
        if getattr(ed, 'has_line_numbers', False):
            self.gui.cursor_position_widget.update_position(*ed.cursor_position)
        else:
            self.gui.cursor_position_widget.update_position()

    def editor_close_requested(self, editor):
        name = editor_name(editor)
        if not name:
            return
        if not editor.is_synced_to_container:
            self.commit_editor_to_container(name)
        self.close_editor(name)

    def close_editor(self, name):
        ' Close the editor that is editing the file specified by ``name`` '
        editor = editors.pop(name)
        self.gui.central.close_editor(editor)
        editor.break_cycles()
        if not editors or getattr(self.gui.central.current_editor, 'syntax', None) != 'html':
            self.gui.preview.clear()
            self.gui.live_css.clear()

    def insert_character(self):
        self.gui.insert_char.show()

    # Shutdown {{{

    def quit(self):
        if self.doing_terminal_save:
            return False
        if self.save_manager.has_tasks:
            if question_dialog(
                self.gui, _('Are you sure?'), _(
                    'The current book is being saved in the background. Quitting now will'
                    ' <b>abort the save process</b>! Finish saving first?'),
                    yes_text=_('Finish &saving first'), no_text=_('&Quit immediately')):
                if self.save_manager.has_tasks:
                    self.start_terminal_save_indicator()
                return False

        if not self.confirm_quit():
            return False
        self.save_state()
        self.shutdown()
        QApplication.instance().quit()
        return True

    def confirm_quit(self):
        if self.gui.action_save.isEnabled():
            d = QDialog(self.gui)
            d.l = QGridLayout(d)
            d.setLayout(d.l)
            d.setWindowTitle(_('Unsaved changes'))
            d.i = QLabel('')
            d.i.setPixmap(QPixmap(I('save.png')).scaledToHeight(64, Qt.SmoothTransformation))
            d.i.setMaximumSize(QSize(d.i.pixmap().width(), 64))
            d.i.setScaledContents(True)
            d.l.addWidget(d.i, 0, 0)
            d.m = QLabel(_('There are unsaved changes, if you quit without saving, you will lose them.'))
            d.m.setWordWrap(True)
            d.l.addWidget(d.m, 0, 1)
            d.bb = QDialogButtonBox(QDialogButtonBox.Cancel)
            d.bb.rejected.connect(d.reject)
            d.bb.accepted.connect(d.accept)
            d.l.addWidget(d.bb, 1, 0, 1, 2)
            d.do_save = None
            def endit(x):
                d.do_save = x
                d.accept()
            b = d.bb.addButton(_('&Save and Quit'), QDialogButtonBox.ActionRole)
            b.setIcon(QIcon(I('save.png')))
            b.clicked.connect(lambda *args: endit(True))
            b = d.bb.addButton(_('&Quit without saving'), QDialogButtonBox.ActionRole)
            b.clicked.connect(lambda *args: endit(False))
            d.resize(d.sizeHint())
            if d.exec_() != d.Accepted or d.do_save is None:
                return False
            if d.do_save:
                self.gui.action_save.trigger()
                self.start_terminal_save_indicator()
                return False

        return True

    def start_terminal_save_indicator(self):
        self.save_state()
        self.gui.blocking_job.set_msg(_('Saving, please wait...'))
        self.gui.blocking_job.start()
        self.doing_terminal_save = True

    def abort_terminal_save(self):
        self.doing_terminal_save = False
        self.gui.blocking_job.stop()

    def check_terminal_save(self):
        if self.doing_terminal_save and not self.save_manager.has_tasks:  # terminal save could have been aborted
            self.shutdown()
            QApplication.instance().quit()

    def shutdown(self):
        completion_worker().shutdown()
        self.save_manager.check_for_completion.disconnect()
        self.gui.preview.stop_refresh_timer()
        self.gui.live_css.stop_update_timer()
        self.save_state()
        [x.reject() for x in _diff_dialogs]
        del _diff_dialogs[:]
        self.save_manager.shutdown()
        parse_worker.shutdown()
        self.save_manager.wait(0.1)

    def save_state(self):
        with tprefs:
            self.gui.save_state()
    # }}}

