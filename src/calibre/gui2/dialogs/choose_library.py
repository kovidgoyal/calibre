#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai


__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os, errno
from threading import Thread, Event

from PyQt5.Qt import QDialog, QTimer, Qt, pyqtSignal

from calibre.gui2.dialogs.choose_library_ui import Ui_Dialog
from calibre.gui2.dialogs.progress import ProgressDialog as PD
from calibre.gui2 import error_dialog, choose_dir
from calibre.constants import (filesystem_encoding, iswindows,
        get_portable_base)
from calibre import isbytestring, patheq, force_unicode
from polyglot.builtins import unicode_type


class ProgressDialog(PD):

    on_progress_update = pyqtSignal(object, object, object)
    finished_moving = pyqtSignal()

    def __init__(self, *args, **kwargs):
        PD.__init__(self, *args, **kwargs)
        self.on_progress_update.connect(self.progressed, type=Qt.QueuedConnection)
        self.finished_moving.connect(self.accept, type=Qt.QueuedConnection)

    def reject(self):
        return

    def progressed(self, item_name, count, total):
        self.max = total
        self.value = count
        self.set_msg(item_name)

    def show_new_progress(self, *args):
        self.on_progress_update.emit(*args)


class ChooseLibrary(QDialog, Ui_Dialog):

    def __init__(self, db, callback, parent):
        QDialog.__init__(self, parent)
        self.setupUi(self)
        self.db = db
        self.new_db = None
        self.callback = callback
        self.location.initialize('choose_library_dialog')

        lp = db.library_path
        if isbytestring(lp):
            lp = lp.decode(filesystem_encoding)
        loc = unicode_type(self.old_location.text()).format(lp)
        self.old_location.setText(loc)
        self.browse_button.clicked.connect(self.choose_loc)
        self.empty_library.toggled.connect(self.empty_library_toggled)
        self.copy_structure.setEnabled(False)

    def empty_library_toggled(self, to_what):
        self.copy_structure.setEnabled(to_what)

    def choose_loc(self, *args):
        base = get_portable_base()
        if base is None:
            loc = choose_dir(self, 'choose library location',
                    _('Choose location for calibre library'))
        else:
            name = force_unicode('choose library loc at' + base,
                    filesystem_encoding)
            loc = choose_dir(self, name,
                    _('Choose location for calibre library'), default_dir=base,
                    no_save_dir=True)
        if loc is not None:
            self.location.setText(loc)

    def check_action(self, ac, loc):
        exists = self.db.exists_at(loc)
        base = get_portable_base()
        if patheq(loc, self.db.library_path):
            error_dialog(self, _('Same as current'),
                    _('The location %s contains the current calibre'
                        ' library')%loc, show=True)
            return False

        if base is not None and ac in ('new', 'move'):
            abase = os.path.normcase(os.path.abspath(base))
            cal = os.path.normcase(os.path.abspath(os.path.join(abase,
                'Calibre')))
            aloc = os.path.normcase(os.path.abspath(loc))
            if (aloc.startswith(cal+os.sep) or aloc == cal):
                error_dialog(self, _('Bad location'),
                    _('You should not create a library inside the calibre'
                        ' folder as this folder is automatically deleted during upgrades.'),
                    show=True)
                return False
            if aloc.startswith(abase) and os.path.dirname(aloc) != abase:
                error_dialog(self, _('Bad location'),
                    _('You can only create libraries inside %s at the top '
                        'level, not in sub-folders')%base, show=True)
                return False

        empty = not os.listdir(loc)
        if ac == 'existing' and not exists:
            error_dialog(self, _('No existing library found'),
                    _('There is no existing calibre library at %s')%loc,
                    show=True)
            return False
        if ac in ('new', 'move'):
            from calibre.db.legacy import LibraryDatabase
            if not empty:
                error_dialog(self, _('Not empty'),
                    _('The folder %s is not empty. Please choose an empty'
                       ' folder')%loc,
                    show=True)
                return False
            if (iswindows and len(loc) >
                    LibraryDatabase.WINDOWS_LIBRARY_PATH_LIMIT):
                error_dialog(self, _('Too long'),
                    _('Path to library too long. Must be less than'
                    ' %d characters.')%LibraryDatabase.WINDOWS_LIBRARY_PATH_LIMIT,
                    show=True)
                return False

        return True

    def perform_action(self, ac, loc):
        if ac in ('new', 'existing'):
            self.callback(loc, copy_structure=self.copy_structure.isChecked())
        else:
            # move library
            self.db.prefs.disable_setting = True
            abort_move = Event()
            pd = ProgressDialog(_('Moving library, please wait...'), _('Scanning...'), max=0, min=0, icon='lt.png', parent=self)
            pd.canceled_signal.connect(abort_move.set)
            self.parent().library_view.model().stop_metadata_backup()
            move_error = []

            def do_move():
                try:
                    self.db.new_api.move_library_to(loc, abort=abort_move, progress=pd.show_new_progress)
                except Exception:
                    import traceback
                    move_error.append(traceback.format_exc())
                finally:
                    pd.finished_moving.emit()

            t = Thread(name='MoveLibrary', target=do_move)
            QTimer.singleShot(0, t.start)
            pd.exec_()
            if abort_move.is_set():
                self.callback(self.db.library_path)
                return
            if move_error:
                error_dialog(self.parent(), _('Failed to move library'), _(
                    'There was an error while moving the library. The operation has been aborted. Click'
                    ' "Show details" for details.'), det_msg=move_error[0], show=True)
                self.callback(self.db.library_path)
                return
            self.callback(loc, library_renamed=True)

    def accept(self):
        action = 'move'
        if self.existing_library.isChecked():
            action = 'existing'
        elif self.empty_library.isChecked():
            action = 'new'
        text = unicode_type(self.location.text()).strip()
        if not text:
            return error_dialog(self, _('No location'), _('No location selected'),
                    show=True)
        loc = os.path.abspath(text)
        if action == 'move':
            try:
                os.makedirs(loc)
            except EnvironmentError as e:
                if e.errno != errno.EEXIST:
                    raise
        if not loc or not os.path.exists(loc) or not os.path.isdir(loc):
            if action == 'new' and not os.path.exists(loc):
                os.makedirs(loc)
            else:
                return error_dialog(self, _('Bad location'),
                        _('%s is not an existing folder')%loc, show=True)
        if not self.check_action(action, loc):
            return
        self.location.save_history()
        self.perform_action(action, loc)
        QDialog.accept(self)  # Must be after perform action otherwise the progress dialog is not updated on windows
