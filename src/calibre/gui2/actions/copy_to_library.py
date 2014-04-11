#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os
from functools import partial
from threading import Thread
from contextlib import closing
from collections import defaultdict

from PyQt5.Qt import (
    QToolButton, QDialog, QGridLayout, QIcon, QLabel, QDialogButtonBox, QApplication,
    QFormLayout, QCheckBox, QWidget, QScrollArea, QVBoxLayout, Qt, QListWidgetItem, QListWidget)

from calibre.gui2.actions import InterfaceAction
from calibre.gui2 import (error_dialog, Dispatcher, warning_dialog, gprefs,
        info_dialog, choose_dir)
from calibre.gui2.dialogs.progress import ProgressDialog
from calibre.gui2.widgets import HistoryLineEdit
from calibre.utils.config import prefs, tweaks
from calibre.utils.date import now
from calibre.utils.icu import sort_key

def ask_about_cc_mismatch(gui, db, newdb, missing_cols, incompatible_cols):  # {{{
    source_metadata = db.field_metadata.custom_field_metadata(include_composites=True)
    ndbname = os.path.basename(newdb.library_path)

    d = QDialog(gui)
    d.setWindowTitle(_('Different custom columns'))
    l = QFormLayout()
    tl = QVBoxLayout()
    d.setLayout(tl)
    d.s = QScrollArea(d)
    tl.addWidget(d.s)
    d.w = QWidget(d)
    d.s.setWidget(d.w)
    d.s.setWidgetResizable(True)
    d.w.setLayout(l)
    d.setMinimumWidth(600)
    d.setMinimumHeight(500)
    d.bb = QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel)

    msg = _('The custom columns in the <i>{0}</i> library are different from the '
        'custom columns in the <i>{1}</i> library. As a result, some metadata might not be copied.').format(
        os.path.basename(db.library_path), ndbname)
    d.la = la = QLabel(msg)
    la.setWordWrap(True)
    la.setStyleSheet('QLabel { margin-bottom: 1.5ex }')
    l.addRow(la)
    if incompatible_cols:
        la = d.la2 = QLabel(_('The following columns are incompatible - they have the same name'
                ' but different data types. They will be ignored: ') +
                    ', '.join(sorted(incompatible_cols, key=sort_key)))
        la.setWordWrap(True)
        la.setStyleSheet('QLabel { margin-bottom: 1.5ex }')
        l.addRow(la)

    missing_widgets = []
    if missing_cols:
        la = d.la3 = QLabel(_('The following columns are missing in the <i>{0}</i> library.'
                                ' You can choose to add them automatically below.').format(
                                    ndbname))
        la.setWordWrap(True)
        l.addRow(la)
        for k in missing_cols:
            widgets = (k, QCheckBox(_('Add to the %s library') % ndbname))
            l.addRow(QLabel(k), widgets[1])
            missing_widgets.append(widgets)
    d.la4 = la = QLabel(_('This warning is only shown once per library, per session'))
    la.setWordWrap(True)
    tl.addWidget(la)

    tl.addWidget(d.bb)
    d.bb.accepted.connect(d.accept)
    d.bb.rejected.connect(d.reject)
    d.resize(d.sizeHint())
    if d.exec_() == d.Accepted:
        for k, cb in missing_widgets:
            if cb.isChecked():
                col_meta = source_metadata[k]
                newdb.create_custom_column(
                            col_meta['label'], col_meta['name'], col_meta['datatype'],
                            len(col_meta['is_multiple']) > 0,
                            col_meta['is_editable'], col_meta['display'])
        return True
    return False
# }}}

class Worker(Thread):  # {{{

    def __init__(self, ids, db, loc, progress, done, delete_after, add_duplicates):
        Thread.__init__(self)
        self.ids = ids
        self.processed = set()
        self.db = db
        self.loc = loc
        self.error = None
        self.progress = progress
        self.done = done
        self.delete_after = delete_after
        self.auto_merged_ids = {}
        self.add_duplicates = add_duplicates
        self.duplicate_ids = {}

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

    def add_formats(self, id_, paths, newdb, replace=True):
        for path in paths:
            fmt = os.path.splitext(path)[-1].replace('.', '').upper()
            with open(path, 'rb') as f:
                newdb.add_format(id_, fmt, f, index_is_id=True,
                        notify=False, replace=replace)

    def doit(self):
        from calibre.db.legacy import LibraryDatabase
        newdb = LibraryDatabase(self.loc, is_second_db=True)
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
            if not fmts:
                fmts = []
            else:
                fmts = fmts.split(',')
            identical_book_list = set()
            paths = []
            for fmt in fmts:
                p = self.db.format(x, fmt, index_is_id=True,
                    as_path=True)
                if p:
                    paths.append(p)
            try:
                if not self.add_duplicates:
                    if prefs['add_formats_to_existing'] or prefs['check_for_dupes_on_ctl']:
                        # Scanning for dupes can be slow on a large library so
                        # only do it if the option is set
                        identical_book_list = newdb.find_identical_books(mi)
                    if identical_book_list:  # books with same author and nearly same title exist in newdb
                        if prefs['add_formats_to_existing']:
                            self.automerge_book(x, mi, identical_book_list, paths, newdb)
                        else:  # Report duplicates for later processing
                            self.duplicate_ids[x] = (mi.title, mi.authors)
                        continue

                newdb.import_book(mi, paths, notify=False, import_hooks=False,
                    apply_import_tags=tweaks['add_new_book_tags_when_importing_books'],
                    preserve_uuid=self.delete_after)
                co = self.db.conversion_options(x, 'PIPE')
                if co is not None:
                    newdb.set_conversion_options(x, 'PIPE', co)
                self.processed.add(x)
            finally:
                for path in paths:
                    try:
                        os.remove(path)
                    except:
                        pass

    def automerge_book(self, book_id, mi, identical_book_list, paths, newdb):
        self.auto_merged_ids[book_id] = _('%(title)s by %(author)s') % dict(title=mi.title, author=mi.format_field('authors')[1])
        seen_fmts = set()
        self.processed.add(book_id)
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


# }}}

class ChooseLibrary(QDialog):  # {{{

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
        self.bb = bb = QDialogButtonBox(QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        self.delete_after_copy = False
        b = bb.addButton(_('&Copy'), bb.AcceptRole)
        b.setIcon(QIcon(I('edit-copy.png')))
        b.setToolTip(_('Copy to the specified library'))
        b2 = bb.addButton(_('&Move'), bb.AcceptRole)
        b2.clicked.connect(lambda: setattr(self, 'delete_after_copy', True))
        b2.setIcon(QIcon(I('edit-cut.png')))
        b2.setToolTip(_('Copy to the specified library and delete from the current library'))
        b.setDefault(True)
        l.addWidget(bb, 1, 0, 1, 3)
        le.setMinimumWidth(350)
        self.resize(self.sizeHint())

    def browse(self):
        d = choose_dir(self, 'choose_library_for_copy',
                       _('Choose Library'))
        if d:
            self.le.setText(d)

    @property
    def args(self):
        return (unicode(self.le.text()), self.delete_after_copy)
# }}}

class DuplicatesQuestion(QDialog):  # {{{

    def __init__(self, parent, duplicates, loc):
        QDialog.__init__(self, parent)
        l = QVBoxLayout()
        self.setLayout(l)
        self.la = la = QLabel(_('Books with the same title and author as the following already exist in the library %s.'
                                ' Select which books you want copied anyway.') %
                              os.path.basename(loc))
        la.setWordWrap(True)
        l.addWidget(la)
        self.setWindowTitle(_('Duplicate books'))
        self.books = QListWidget(self)
        self.items = []
        for book_id, (title, authors) in duplicates.iteritems():
            i = QListWidgetItem(_('{0} by {1}').format(title, ' & '.join(authors[:3])), self.books)
            i.setData(Qt.UserRole, book_id)
            i.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            i.setCheckState(Qt.Checked)
            self.items.append(i)
        l.addWidget(self.books)
        self.bb = bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        self.a = b = bb.addButton(_('Select &all'), bb.ActionRole)
        b.clicked.connect(self.select_all), b.setIcon(QIcon(I('plus.png')))
        self.n = b = bb.addButton(_('Select &none'), bb.ActionRole)
        b.clicked.connect(self.select_none), b.setIcon(QIcon(I('minus.png')))
        self.ctc = b = bb.addButton(_('&Copy to clipboard'), bb.ActionRole)
        b.clicked.connect(self.copy_to_clipboard), b.setIcon(QIcon(I('edit-copy.png')))
        l.addWidget(bb)
        self.resize(600, 400)

    def copy_to_clipboard(self):
        items = [('✓' if item.checkState() == Qt.Checked else '✗') + ' ' + unicode(item.text())
                 for item in self.items]
        QApplication.clipboard().setText('\n'.join(items))

    def select_all(self):
        for i in self.items:
            i.setCheckState(Qt.Checked)

    def select_none(self):
        for i in self.items:
            i.setCheckState(Qt.Unchecked)

    @property
    def ids(self):
        return {i.data(Qt.UserRole).toInt()[0] for i in self.items if i.checkState() == Qt.Checked}

# }}}

# Static session-long set of pairs of libraries that have had their custom columns
# checked for compatibility
libraries_with_checked_columns = defaultdict(set)

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
        if len(locations) > 50:
            self.menu.addAction(_('Choose library by path...'), self.choose_library)
            self.menu.addSeparator()
        for name, loc in locations:
            self.menu.addAction(name, partial(self.copy_to_library,
                loc))
            self.menu.addAction(name + ' ' + _('(delete after copy)'),
                    partial(self.copy_to_library, loc, delete_after=True))
            self.menu.addSeparator()

        if len(locations) <= 50:
            self.menu.addAction(_('Choose library by path...'), self.choose_library)
        self.qaction.setVisible(bool(locations))

    def choose_library(self):
        d = ChooseLibrary(self.gui)
        if d.exec_() == d.Accepted:
            path, delete_after = d.args
            if not path:
                return
            db = self.gui.library_view.model().db
            current = os.path.normcase(os.path.abspath(db.library_path))
            if current == os.path.normcase(os.path.abspath(path)):
                return error_dialog(self.gui, _('Cannot copy'),
                    _('Cannot copy to current library.'), show=True)
            self.copy_to_library(path, delete_after)

    def _column_is_compatible(self, source_metadata, dest_metadata):
        return (source_metadata['datatype'] == dest_metadata['datatype'] and
                    (source_metadata['datatype'] != 'text' or
                     source_metadata['is_multiple'] == dest_metadata['is_multiple']))

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

        # Open the new db so we can check the custom columns. We use only the
        # backend since we only need the custom column definitions, not the
        # rest of the data in the db.
        global libraries_with_checked_columns

        from calibre.db.legacy import create_backend
        newdb = create_backend(loc)

        continue_processing = True
        with closing(newdb):
            if newdb.library_id not in libraries_with_checked_columns[db.library_id]:

                newdb_meta = newdb.field_metadata.custom_field_metadata()
                incompatible_columns = []
                missing_columns = []
                for k, m in db.field_metadata.custom_iteritems():
                    if m['datatype'] == 'composite':
                        continue
                    if k not in newdb_meta:
                        missing_columns.append(k)
                    elif not self._column_is_compatible(m, newdb_meta[k]):
                        incompatible_columns.append(k)

                if missing_columns or incompatible_columns:
                    continue_processing = ask_about_cc_mismatch(self.gui, db, newdb,
                                            missing_columns, incompatible_columns)
                if continue_processing:
                    libraries_with_checked_columns[db.library_id].add(newdb.library_id)

        newdb.close()
        del newdb
        if not continue_processing:
            return
        duplicate_ids = self.do_copy(ids, db, loc, delete_after, False)
        if duplicate_ids:
            d = DuplicatesQuestion(self.gui, duplicate_ids, loc)
            if d.exec_() == d.Accepted:
                ids = d.ids
                if ids:
                    self.do_copy(list(ids), db, loc, delete_after, add_duplicates=True)

    def do_copy(self, ids, db, loc, delete_after, add_duplicates=False):
        aname = _('Moving to') if delete_after else _('Copying to')
        dtitle = '%s %s'%(aname, os.path.basename(loc))
        self.pd = ProgressDialog(dtitle, min=0, max=len(ids)-1,
                parent=self.gui, cancelable=False)

        def progress(idx, title):
            self.pd.set_msg(title)
            self.pd.set_value(idx)

        self.worker = Worker(ids, db, loc, Dispatcher(progress),
                             Dispatcher(self.pd.accept), delete_after, add_duplicates)
        self.worker.start()

        self.pd.exec_()

        donemsg = _('Copied %(num)d books to %(loc)s')
        if delete_after:
            donemsg = _('Moved %(num)d books to %(loc)s')

        if self.worker.error is not None:
            e, tb = self.worker.error
            error_dialog(self.gui, _('Failed'), _('Could not copy books: ') + e,
                    det_msg=tb, show=True)
            return

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
        return self.worker.duplicate_ids

    def cannot_do_dialog(self):
        warning_dialog(self.gui, _('Not allowed'),
                    _('You cannot use other libraries while using the environment'
                      ' variable CALIBRE_OVERRIDE_DATABASE_PATH.'), show=True)


