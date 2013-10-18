#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

import tempfile, shutil

from PyQt4.Qt import QObject, QApplication

from calibre.gui2 import error_dialog, choose_files, question_dialog, info_dialog
from calibre.ptempfile import PersistentTemporaryDirectory
from calibre.ebooks.oeb.polish.main import SUPPORTED
from calibre.ebooks.oeb.polish.container import get_container, clone_container
from calibre.gui2.tweak_book import set_current_container, current_container, tprefs
from calibre.gui2.tweak_book.undo import GlobalUndoHistory
from calibre.gui2.tweak_book.save import SaveManager

class Boss(QObject):

    def __init__(self, parent):
        QObject.__init__(self, parent)
        self.global_undo = GlobalUndoHistory()
        self.container_count = 0
        self.tdir = None
        self.save_manager = SaveManager(parent)
        self.save_manager.report_error.connect(self.report_save_error)

    def __call__(self, gui):
        self.gui = gui
        gui.file_list.delete_requested.connect(self.delete_requested)

    def mkdtemp(self):
        self.container_count += 1
        return tempfile.mkdtemp(prefix='%05d-' % self.container_count, dir=self.tdir)

    def check_dirtied(self):
        # TODO: Implement this
        return True

    def open_book(self, path=None):
        if not self.check_dirtied():
            return
        if self.save_manager.has_tasks:
            return info_dialog(self.gui, _('Cannot open'),
                        _('The current book is being saved, you cannot open a new book until'
                          ' the saving is completed'), show=True)

        if not hasattr(path, 'rpartition'):
            path = choose_files(self.gui, 'open-book-for-tweaking', _('Choose book'),
                                [(_('Books'), [x.lower() for x in SUPPORTED])], all_files=False, select_only_single_file=True)
            if not path:
                return
            path = path[0]

        ext = path.rpartition('.')[-1].upper()
        if ext not in SUPPORTED:
            return error_dialog(self.gui, _('Unsupported format'),
                _('Tweaking is only supported for books in the %s formats.'
                  ' Convert your book to one of these formats first.') % _(' and ').join(sorted(SUPPORTED)),
                show=True)

        self.container_count = -1
        if self.tdir:
            shutil.rmtree(self.tdir, ignore_errors=True)
        self.tdir = PersistentTemporaryDirectory()
        self.gui.blocking_job('open_book', _('Opening book, please wait...'), self.book_opened, get_container, path, tdir=self.mkdtemp())

    def book_opened(self, job):
        if job.traceback is not None:
            return error_dialog(self.gui, _('Failed to open book'),
                    _('Failed to open book, click Show details for more information.'),
                                det_msg=job.traceback, show=True)
        container = job.result
        set_current_container(container)
        self.current_metadata = self.gui.current_metadata = container.mi
        self.global_undo.open_book(container)
        self.gui.update_window_title()
        self.gui.file_list.build(container, preserve_state=False)
        self.gui.action_save.setEnabled(False)
        self.update_global_history_actions()

    def update_global_history_actions(self):
        gu = self.global_undo
        for x, text in (('undo', _('&Revert to before')), ('redo', '&Revert to after')):
            ac = getattr(self.gui, 'action_global_%s' % x)
            ac.setEnabled(getattr(gu, 'can_' + x))
            ac.setText(text + ' ' + (getattr(gu, x + '_msg') or '...'))

    def add_savepoint(self, msg):
        nc = clone_container(current_container(), self.mkdtemp())
        self.global_undo.add_savepoint(nc, msg)
        set_current_container(nc)
        self.update_global_history_actions()

    def apply_container_update_to_gui(self):
        container = current_container()
        self.gui.file_list.build(container)
        self.update_global_history_actions()
        self.gui.action_save.setEnabled(True)
        # TODO: Apply to other GUI elements

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

    def delete_requested(self, spine_items, other_items):
        if not self.check_dirtied():
            return
        self.add_savepoint(_('Delete files'))
        c = current_container()
        c.remove_from_spine(spine_items)
        for name in other_items:
            c.remove_item(name)
        self.gui.action_save.setEnabled(True)
        self.gui.file_list.delete_done(spine_items, other_items)
        # TODO: Update other GUI elements

    def save_book(self):
        self.gui.action_save.setEnabled(False)
        tdir = tempfile.mkdtemp(prefix='save-%05d-' % self.container_count, dir=self.tdir)
        container = clone_container(current_container(), tdir)
        self.save_manager.schedule(tdir, container)

    def report_save_error(self, tb):
        error_dialog(self.gui, _('Could not save'),
                     _('Saving of the book failed. Click "Show Details"'
                       ' for more information.'), det_msg=tb, show=True)

    def quit(self):
        if not self.confirm_quit():
            return
        self.save_state()
        QApplication.instance().quit()

    def confirm_quit(self):
        if self.save_manager.has_tasks:
            if not question_dialog(
                self.gui, _('Are you sure?'), _(
                    'The current book is being saved in the background, quitting will abort'
                    ' the save process, are you sure?'), default_yes=False):
                return False
        if self.gui.action_save.isEnabled():
            if not question_dialog(
                self.gui, _('Are you sure?'), _(
                    'The current book has unsaved changes, you will lose them if you quit,'
                    ' are you sure?'), default_yes=False):
                return False

        return True

    def shutdown(self):
        self.save_state()
        self.save_manager.shutdown()
        self.save_manager.wait(0.1)

    def save_state(self):
        with tprefs:
            self.gui.save_state()
