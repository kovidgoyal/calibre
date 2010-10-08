#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os
from functools import partial
from threading import Thread

from PyQt4.Qt import QMenu, QToolButton

from calibre.gui2.actions import InterfaceAction
from calibre.gui2 import error_dialog, Dispatcher
from calibre.gui2.dialogs.progress import ProgressDialog
from calibre.utils.config import prefs, tweaks

class Worker(Thread):

    def __init__(self, ids, db, loc, progress, done, delete_after):
        Thread.__init__(self)
        self.ids = ids
        self.processed = set([])
        self.db = db
        self.loc = loc
        self.error = None
        self.progress = progress
        self.done = done
        self.delete_after = delete_after

    def run(self):
        try:
            self.doit()
        except Exception, err:
            import traceback
            try:
                err = unicode(err)
            except:
                err = repr(err)
            self.error = (err, traceback.format_exc())

        self.done()

    def add_formats(self, id, paths, newdb, replace=True):
        for path in paths:
            fmt = os.path.splitext(path)[-1].replace('.', '').upper()
            with open(path, 'rb') as f:
                newdb.add_format(id, fmt, f, index_is_id=True,
                        notify=False, replace=replace)

    def doit(self):
        from calibre.library.database2 import LibraryDatabase2
        newdb = LibraryDatabase2(self.loc)
        for i, x in enumerate(self.ids):
            mi = self.db.get_metadata(x, index_is_id=True, get_cover=True)
            self.progress(i, mi.title)
            fmts = self.db.formats(x, index_is_id=True)
            if not fmts: fmts = []
            else: fmts = fmts.split(',')
            paths = [self.db.format_abspath(x, fmt, index_is_id=True) for fmt in
                    fmts]
            added = False
            if prefs['add_formats_to_existing']:
                identical_book_list = newdb.find_identical_books(mi)
                if identical_book_list: # books with same author and nearly same title exist in newdb
                    added = True
                    for identical_book in identical_book_list:
                        self.add_formats(identical_book, paths, newdb, replace=False)
            if not added:
                newdb.import_book(mi, paths, notify=False, import_hooks=False,
                    apply_import_tags=tweaks['add_new_book_tags_when_importing_books'],
                    preserve_uuid=self.delete_after)
                co = self.db.conversion_options(x, 'PIPE')
                if co is not None:
                    newdb.set_conversion_options(x, 'PIPE', co)
            self.processed.add(x)


class CopyToLibraryAction(InterfaceAction):

    name = 'Copy To Library'
    action_spec = (_('Copy to library'), 'lt.png',
            _('Copy selected books to the specified library'), None)
    popup_type = QToolButton.InstantPopup
    dont_add_to = frozenset(['toolbar-device', 'context-menu-device'])
    action_type = 'current'

    def genesis(self):
        self.menu = QMenu(self.gui)
        self.qaction.setMenu(self.menu)

    @property
    def stats(self):
        return self.gui.iactions['Choose Library'].stats

    def library_changed(self, db):
        self.build_menus()

    def initialization_complete(self):
        self.library_changed(self.gui.library_view.model().db)

    def location_selected(self, loc):
        enabled = loc == 'library'
        self.qaction.setEnabled(enabled)

    def build_menus(self):
        self.menu.clear()
        db = self.gui.library_view.model().db
        locations = list(self.stats.locations(db))
        for name, loc in locations:
            self.menu.addAction(name, partial(self.copy_to_library,
                loc))
            self.menu.addAction(name + ' ' + _('(delete after copy)'),
                    partial(self.copy_to_library,  loc, delete_after=True))
            self.menu.addSeparator()

        self.qaction.setVisible(bool(locations))

    def copy_to_library(self, loc, delete_after=False):
        rows = self.gui.library_view.selectionModel().selectedRows()
        if not rows or len(rows) == 0:
            return error_dialog(self.gui, _('Cannot copy'),
                    _('No books selected'), show=True)
        ids = list(map(self.gui.library_view.model().id, rows))
        db = self.gui.library_view.model().db
        if not db.exists_at(loc):
            return error_dialog(self.gui, _('No library'),
                    _('No library found at %s')%loc, show=True)


        self.pd = ProgressDialog(_('Copying'), min=0, max=len(ids)-1,
                parent=self.gui, cancelable=False)

        def progress(idx, title):
            self.pd.set_msg(_('Copying') + ' ' + title)
            self.pd.set_value(idx)

        self.worker = Worker(ids, db, loc, Dispatcher(progress),
                             Dispatcher(self.pd.accept), delete_after)
        self.worker.start()

        self.pd.exec_()

        if self.worker.error is not None:
            e, tb = self.worker.error
            error_dialog(self.gui, _('Failed'), _('Could not copy books: ') + e,
                    det_msg=tb, show=True)
        else:
            self.gui.status_bar.show_message(_('Copied %d books to %s') %
                    (len(ids), loc), 2000)
            if delete_after and self.worker.processed:
                v = self.gui.library_view
                ci = v.currentIndex()
                row = None
                if ci.isValid():
                    row = ci.row()

                v.model().delete_books_by_id(self.worker.processed)
                self.gui.iactions['Remove Books'].library_ids_deleted(
                        self.worker.processed, row)



