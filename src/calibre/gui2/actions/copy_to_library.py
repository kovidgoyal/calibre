#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os
from functools import partial
from threading import Thread
from contextlib import closing

from PyQt4.Qt import (QToolButton, QDialog, QGridLayout, QIcon, QLabel,
                      QCheckBox, QDialogButtonBox)

from calibre.gui2.actions import InterfaceAction
from calibre.gui2 import (error_dialog, Dispatcher, warning_dialog, gprefs,
        info_dialog, choose_dir)
from calibre.gui2.dialogs.progress import ProgressDialog
from calibre.gui2.widgets import HistoryLineEdit
from calibre.utils.config import prefs, tweaks
from calibre.utils.date import now

class Worker(Thread): # {{{

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
        self.auto_merged_ids = {}

    def run(self):
        try:
            self.doit()
        except Exception as err:
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
        newdb = LibraryDatabase2(self.loc, is_second_db=True)
        with closing(newdb):
            self._doit(newdb)
        newdb.break_cycles()
        del newdb

    def _doit(self, newdb):
        for i, x in enumerate(self.ids):
            mi = self.db.get_metadata(x, index_is_id=True, get_cover=True,
                    cover_as_data=True)
            if not gprefs['preserve_date_on_ctl']:
                mi.timestamp = now()
            self.progress(i, mi.title)
            fmts = self.db.formats(x, index_is_id=True)
            if not fmts: fmts = []
            else: fmts = fmts.split(',')
            paths = []
            for fmt in fmts:
                p = self.db.format(x, fmt, index_is_id=True,
                    as_path=True)
                if p:
                    paths.append(p)
            automerged = False
            if prefs['add_formats_to_existing']:
                identical_book_list = newdb.find_identical_books(mi)
                if identical_book_list: # books with same author and nearly same title exist in newdb
                    self.auto_merged_ids[x] = _('%(title)s by %(author)s')%\
                    dict(title=mi.title, author=mi.format_field('authors')[1])
                    automerged = True
                    seen_fmts = set()
                    for identical_book in identical_book_list:
                        ib_fmts = newdb.formats(identical_book, index_is_id=True)
                        if ib_fmts:
                            seen_fmts |= set(ib_fmts.split(','))
                        replace = gprefs['automerge'] == 'overwrite'
                        self.add_formats(identical_book, paths, newdb,
                                replace=replace)

                    if gprefs['automerge'] == 'new record':
                        incoming_fmts = \
                            set([os.path.splitext(path)[-1].replace('.',
                                '').upper() for path in paths])

                        if incoming_fmts.intersection(seen_fmts):
                            # There was at least one duplicate format
                            # so create a new record and put the
                            # incoming formats into it
                            # We should arguably put only the duplicate
                            # formats, but no real harm is done by having
                            # all formats
                            newdb.import_book(mi, paths, notify=False, import_hooks=False,
                                apply_import_tags=tweaks['add_new_book_tags_when_importing_books'],
                                preserve_uuid=False)

            if not automerged:
                newdb.import_book(mi, paths, notify=False, import_hooks=False,
                    apply_import_tags=tweaks['add_new_book_tags_when_importing_books'],
                    preserve_uuid=self.delete_after)
                co = self.db.conversion_options(x, 'PIPE')
                if co is not None:
                    newdb.set_conversion_options(x, 'PIPE', co)
            self.processed.add(x)
            for path in paths:
                try:
                    os.remove(path)
                except:
                    pass

# }}}

class ChooseLibrary(QDialog): # {{{

    def __init__(self, parent):
        super(ChooseLibrary, self).__init__(parent)
        d = self
        d.l = l = QGridLayout()
        d.setLayout(l)
        d.setWindowTitle(_('Choose library'))
        la = d.la = QLabel(_('Library &path:'))
        l.addWidget(la, 0, 0)
        le = d.le = HistoryLineEdit(d)
        le.initialize('choose_library_for_copy')
        l.addWidget(le, 0, 1)
        la.setBuddy(le)
        b = d.b = QToolButton(d)
        b.setIcon(QIcon(I('document_open.png')))
        b.setToolTip(_('Browse for library'))
        b.clicked.connect(self.browse)
        l.addWidget(b, 0, 2)
        self.c = c = QCheckBox(_('&Delete after copy'))
        l.addWidget(c, 1, 0, 1, 3)
        self.bb = bb = QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        l.addWidget(bb, 2, 0, 1, 3)
        le.setMinimumWidth(350)
        self.resize(self.sizeHint())

    def browse(self):
        d = choose_dir(self, 'choose_library_for_copy',
                       _('Choose Library'))
        if d:
            self.le.setText(d)

    @property
    def args(self):
        return (unicode(self.le.text()), self.c.isChecked())
# }}}

class CopyToLibraryAction(InterfaceAction):

    name = 'Copy To Library'
    action_spec = (_('Copy to library'), 'lt.png',
            _('Copy selected books to the specified library'), None)
    popup_type = QToolButton.InstantPopup
    dont_add_to = frozenset(['context-menu-device'])
    action_type = 'current'
    action_add_menu = True

    def genesis(self):
        self.menu = self.qaction.menu()

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
        if os.environ.get('CALIBRE_OVERRIDE_DATABASE_PATH', None):
            self.menu.addAction('disabled', self.cannot_do_dialog)
            return
        db = self.gui.library_view.model().db
        locations = list(self.stats.locations(db))
        for name, loc in locations:
            self.menu.addAction(name, partial(self.copy_to_library,
                loc))
            self.menu.addAction(name + ' ' + _('(delete after copy)'),
                    partial(self.copy_to_library,  loc, delete_after=True))
            self.menu.addSeparator()

        self.menu.addAction(_('Choose library by path...'), self.choose_library)
        self.qaction.setVisible(bool(locations))

    def choose_library(self):
        d = ChooseLibrary(self.gui)
        if d.exec_() == d.Accepted:
            path, delete_after = d.args
            db = self.gui.library_view.model().db
            current = os.path.normcase(os.path.abspath(db.library_path))
            if current == os.path.normcase(os.path.abspath(path)):
                return error_dialog(self.gui, _('Cannot copy'),
                    _('Cannot copy to current library.'), show=True)
            self.copy_to_library(path, delete_after)

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

        aname = _('Moving to') if delete_after else _('Copying to')
        dtitle = '%s %s'%(aname, os.path.basename(loc))

        self.pd = ProgressDialog(dtitle, min=0, max=len(ids)-1,
                parent=self.gui, cancelable=False)

        def progress(idx, title):
            self.pd.set_msg(title)
            self.pd.set_value(idx)

        self.worker = Worker(ids, db, loc, Dispatcher(progress),
                             Dispatcher(self.pd.accept), delete_after)
        self.worker.start()

        self.pd.exec_()

        donemsg = _('Copied %(num)d books to %(loc)s')
        if delete_after:
            donemsg = _('Moved %(num)d books to %(loc)s')

        if self.worker.error is not None:
            e, tb = self.worker.error
            error_dialog(self.gui, _('Failed'), _('Could not copy books: ') + e,
                    det_msg=tb, show=True)
        else:
            self.gui.status_bar.show_message(donemsg %
                    dict(num=len(ids), loc=loc), 2000)
            if self.worker.auto_merged_ids:
                books = '\n'.join(self.worker.auto_merged_ids.itervalues())
                info_dialog(self.gui, _('Auto merged'),
                        _('Some books were automatically merged into existing '
                            'records in the target library. Click Show '
                            'details to see which ones. This behavior is '
                            'controlled by the Auto merge option in '
                            'Preferences->Adding books.'), det_msg=books,
                        show=True)
            if delete_after and self.worker.processed:
                v = self.gui.library_view
                ci = v.currentIndex()
                row = None
                if ci.isValid():
                    row = ci.row()

                v.model().delete_books_by_id(self.worker.processed,
                        permanent=True)
                self.gui.iactions['Remove Books'].library_ids_deleted(
                        self.worker.processed, row)

    def cannot_do_dialog(self):
        warning_dialog(self.gui, _('Not allowed'),
                    _('You cannot use other libraries while using the environment'
                      ' variable CALIBRE_OVERRIDE_DATABASE_PATH.'), show=True)


