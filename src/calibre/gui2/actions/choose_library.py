#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os, shutil
from functools import partial

from PyQt4.Qt import QMenu, Qt, QInputDialog, QThread, pyqtSignal, QProgressDialog

from calibre import isbytestring
from calibre.constants import filesystem_encoding
from calibre.utils.config import prefs
from calibre.gui2 import gprefs, warning_dialog, Dispatcher, error_dialog, \
    question_dialog, info_dialog
from calibre.gui2.actions import InterfaceAction
from calibre.gui2.dialogs.check_library import CheckLibraryDialog

class LibraryUsageStats(object): # {{{

    def __init__(self):
        self.stats = {}
        self.read_stats()

    def read_stats(self):
        stats = gprefs.get('library_usage_stats', {})
        self.stats = stats

    def write_stats(self):
        locs = list(self.stats.keys())
        locs.sort(cmp=lambda x, y: cmp(self.stats[x], self.stats[y]),
                reverse=True)
        for key in locs[15:]:
            self.stats.pop(key)
        gprefs.set('library_usage_stats', self.stats)

    def remove(self, location):
        self.stats.pop(location, None)
        self.write_stats()

    def canonicalize_path(self, lpath):
        if isbytestring(lpath):
            lpath = lpath.decode(filesystem_encoding)
        lpath = lpath.replace(os.sep, '/')
        return lpath

    def library_used(self, db):
        lpath = self.canonicalize_path(db.library_path)
        if lpath not in self.stats:
            self.stats[lpath] = 0
        self.stats[lpath] += 1
        self.write_stats()

    def locations(self, db):
        lpath = self.canonicalize_path(db.library_path)
        locs = list(self.stats.keys())
        if lpath in locs:
            locs.remove(lpath)
        locs.sort(cmp=lambda x, y: cmp(self.stats[x], self.stats[y]),
                reverse=True)
        for loc in locs:
            yield self.pretty(loc), loc

    def pretty(self, loc):
        if loc.endswith('/'):
            loc = loc[:-1]
        return loc.split('/')[-1]

    def rename(self, location, newloc):
        newloc = self.canonicalize_path(newloc)
        stats = self.stats.pop(location, None)
        if stats is not None:
            self.stats[newloc] = stats
        self.write_stats()
# }}}

# Check Integrity {{{

class VacThread(QThread):

    check_done = pyqtSignal(object, object)
    callback   = pyqtSignal(object, object)

    def __init__(self, parent, db):
        QThread.__init__(self, parent)
        self.db = db
        self._parent = parent

    def run(self):
        err = bad = None
        try:
            bad = self.db.check_integrity(self.callbackf)
        except:
            import traceback
            err = traceback.format_exc()
        self.check_done.emit(bad, err)

    def callbackf(self, progress, msg):
        self.callback.emit(progress, msg)


class CheckIntegrity(QProgressDialog):

    def __init__(self, db, parent=None):
        QProgressDialog.__init__(self, parent)
        self.db = db
        self.setCancelButton(None)
        self.setMinimum(0)
        self.setMaximum(100)
        self.setWindowTitle(_('Checking database integrity'))
        self.setAutoReset(False)
        self.setValue(0)

        self.vthread = VacThread(self, db)
        self.vthread.check_done.connect(self.check_done,
                type=Qt.QueuedConnection)
        self.vthread.callback.connect(self.callback, type=Qt.QueuedConnection)
        self.vthread.start()

    def callback(self, progress, msg):
        self.setLabelText(msg)
        self.setValue(int(100*progress))

    def check_done(self, bad, err):
        if err:
            error_dialog(self, _('Error'),
                    _('Failed to check database integrity'),
                    det_msg=err, show=True)
        elif bad:
            titles = [self.db.title(x, index_is_id=True) for x in bad]
            det_msg = '\n'.join(titles)
            warning_dialog(self, _('Some inconsistencies found'),
                    _('The following books had formats or covers listed in the '
                        'database that are not actually available. '
                        'The entries for the formats/covers have been removed. '
                        'You should check them manually. This can '
                        'happen if you manipulate the files in the '
                        'library folder directly.'), det_msg=det_msg, show=True)
        self.reset()

# }}}

class ChooseLibraryAction(InterfaceAction):

    name = 'Choose Library'
    action_spec = (_('%d books'), 'lt.png',
            _('Choose calibre library to work with'), None)
    dont_add_to = frozenset(['toolbar-device', 'context-menu-device'])

    def genesis(self):
        self.count_changed(0)
        self.qaction.triggered.connect(self.choose_library,
                type=Qt.QueuedConnection)

        self.stats = LibraryUsageStats()
        self.create_action(spec=(_('Switch/create library...'), 'lt.png', None,
            None), attr='action_choose')
        self.action_choose.triggered.connect(self.choose_library,
                type=Qt.QueuedConnection)
        self.choose_menu = QMenu(self.gui)
        self.qaction.setMenu(self.choose_menu)

        if not os.environ.get('CALIBRE_OVERRIDE_DATABASE_PATH', None):
            self.choose_menu.addAction(self.action_choose)

            self.quick_menu = QMenu(_('Quick switch'))
            self.quick_menu_action = self.choose_menu.addMenu(self.quick_menu)
            self.rename_menu = QMenu(_('Rename library'))
            self.rename_menu_action = self.choose_menu.addMenu(self.rename_menu)
            self.delete_menu = QMenu(_('Delete library'))
            self.delete_menu_action = self.choose_menu.addMenu(self.delete_menu)

        self.rename_separator = self.choose_menu.addSeparator()

        self.switch_actions = []
        for i in range(5):
            ac = self.create_action(spec=('', None, None, None),
                    attr='switch_action%d'%i)
            self.switch_actions.append(ac)
            ac.setVisible(False)
            ac.triggered.connect(partial(self.qs_requested, i),
                    type=Qt.QueuedConnection)
            self.choose_menu.addAction(ac)

        self.rename_separator = self.choose_menu.addSeparator()

        self.maintenance_menu = QMenu(_('Library Maintenance'))
        ac = self.create_action(spec=(_('Library metadata backup status'),
                        'lt.png', None, None), attr='action_backup_status')
        ac.triggered.connect(self.backup_status, type=Qt.QueuedConnection)
        self.maintenance_menu.addAction(ac)
        ac = self.create_action(spec=(_('Start backing up metadata of all books'),
                        'lt.png', None, None), attr='action_backup_metadata')
        ac.triggered.connect(self.mark_dirty, type=Qt.QueuedConnection)
        self.maintenance_menu.addAction(ac)
        ac = self.create_action(spec=(_('Check library'), 'lt.png',
                                      None, None), attr='action_check_library')
        ac.triggered.connect(self.check_library, type=Qt.QueuedConnection)
        self.maintenance_menu.addAction(ac)
        ac = self.create_action(spec=(_('Check database integrity'), 'lt.png',
                                      None, None), attr='action_check_database')
        ac.triggered.connect(self.check_database, type=Qt.QueuedConnection)
        self.maintenance_menu.addAction(ac)
        ac = self.create_action(spec=(_('Recover database'), 'lt.png',
                                    None, None), attr='action_restore_database')
        ac.triggered.connect(self.restore_database, type=Qt.QueuedConnection)
        self.maintenance_menu.addAction(ac)
        self.choose_menu.addMenu(self.maintenance_menu)

    def library_name(self):
        db = self.gui.library_view.model().db
        path = db.library_path
        if isbytestring(path):
            path = path.decode(filesystem_encoding)
        path = path.replace(os.sep, '/')
        return self.stats.pretty(path)

    def library_changed(self, db):
        self.stats.library_used(db)
        self.build_menus()

    def initialization_complete(self):
        self.library_changed(self.gui.library_view.model().db)

    def build_menus(self):
        if os.environ.get('CALIBRE_OVERRIDE_DATABASE_PATH', None):
            return
        db = self.gui.library_view.model().db
        locations = list(self.stats.locations(db))
        for ac in self.switch_actions:
            ac.setVisible(False)
        self.quick_menu.clear()
        self.qs_locations = [i[1] for i in locations]
        self.rename_menu.clear()
        self.delete_menu.clear()
        quick_actions, rename_actions, delete_actions = [], [], []
        for name, loc in locations:
            ac = self.quick_menu.addAction(name, Dispatcher(partial(self.switch_requested,
                loc)))
            quick_actions.append(ac)
            ac = self.rename_menu.addAction(name, Dispatcher(partial(self.rename_requested,
                name, loc)))
            rename_actions.append(ac)
            ac = self.delete_menu.addAction(name, Dispatcher(partial(self.delete_requested,
                name, loc)))
            delete_actions.append(ac)

        qs_actions = []
        for i, x in enumerate(locations[:len(self.switch_actions)]):
            name, loc = x
            ac = self.switch_actions[i]
            ac.setText(name)
            ac.setVisible(True)
            qs_actions.append(ac)

        self.quick_menu_action.setVisible(bool(locations))
        self.rename_menu_action.setVisible(bool(locations))
        self.delete_menu_action.setVisible(bool(locations))
        self.gui.location_manager.set_switch_actions(quick_actions,
                rename_actions, delete_actions, qs_actions,
                self.action_choose)


    def location_selected(self, loc):
        enabled = loc == 'library'
        self.qaction.setEnabled(enabled)

    def rename_requested(self, name, location):
        loc = location.replace('/', os.sep)
        base = os.path.dirname(loc)
        newname, ok = QInputDialog.getText(self.gui, _('Rename') + ' ' + name,
                '<p>'+_('Choose a new name for the library <b>%s</b>. ')%name +
                '<p>'+_('Note that the actual library folder will be renamed.'),
                text=name)
        newname = unicode(newname)
        if not ok or not newname or newname == name:
            return
        newloc = os.path.join(base, newname)
        if os.path.exists(newloc):
            return error_dialog(self.gui, _('Already exists'),
                    _('The folder %s already exists. Delete it first.') %
                    newloc, show=True)
        try:
            os.rename(loc, newloc)
        except:
            import traceback
            error_dialog(self.gui, _('Rename failed'),
                    _('Failed to rename the library at %s. '
                'The most common cause for this is if one of the files'
                ' in the library is open in another program.') % loc,
                    det_msg=traceback.format_exc(), show=True)
            return
        self.stats.rename(location, newloc)
        self.build_menus()

    def delete_requested(self, name, location):
        loc = location.replace('/', os.sep)
        if not question_dialog(self.gui, _('Are you sure?'), '<p>'+
                _('All files from %s will be '
                '<b>permanently deleted</b>. Are you sure?') % loc,
                show_copy_button=False):
            return
        exists = self.gui.library_view.model().db.exists_at(loc)
        if exists:
            try:
                shutil.rmtree(loc, ignore_errors=True)
            except:
                pass
        self.stats.remove(location)
        self.build_menus()

    def backup_status(self, location):
        dirty_text = 'no'
        try:
            dirty_text = \
                  unicode(self.gui.library_view.model().db.dirty_queue_length())
        except:
            dirty_text = _('none')
        info_dialog(self.gui, _('Backup status'), '<p>'+
                _('Book metadata files remaining to be written: %s') % dirty_text,
                show=True)

    def mark_dirty(self):
        db = self.gui.library_view.model().db
        db.dirtied(list(db.data.iterallids()))
        info_dialog(self.gui, _('Backup metadata'),
            _('Metadata will be backed up while calibre is running, at the '
              'rate of approximately 1 book per second.'), show=True)

    def check_library(self):
        db = self.gui.library_view.model().db
        d = CheckLibraryDialog(self.gui.parent(), db)
        d.exec_()

    def check_database(self, *args):
        m = self.gui.library_view.model()
        m.stop_metadata_backup()
        try:
            d = CheckIntegrity(m.db, self.gui)
            d.exec_()
        finally:
            m.start_metadata_backup()

    def restore_database(self):
        info_dialog(self.gui, _('Recover database'), '<p>'+
            _(
              'This command rebuilds your calibre database from the information '
              'stored by calibre in the OPF files.<p>'
              'This function is not currently available in the GUI. You can '
              'recover your database using the \'calibredb restore_database\' '
              'command line function.'
              ), show=True)

    def switch_requested(self, location):
        if not self.change_library_allowed():
            return
        loc = location.replace('/', os.sep)
        exists = self.gui.library_view.model().db.exists_at(loc)
        if not exists:
            warning_dialog(self.gui, _('No library found'),
                    _('No existing calibre library was found at %s.'
                    ' It will be removed from the list of known'
                    ' libraries.')%loc, show=True)
            self.stats.remove(location)
            self.build_menus()
            return

        prefs['library_path'] = loc
        self.gui.library_moved(loc)

    def qs_requested(self, idx, *args):
        self.switch_requested(self.qs_locations[idx])

    def count_changed(self, new_count):
        text = self.action_spec[0]%new_count
        a = self.qaction
        a.setText(text)
        tooltip = self.action_spec[2] + '\n\n' + text
        a.setToolTip(tooltip)
        a.setStatusTip(tooltip)
        a.setWhatsThis(tooltip)

    def choose_library(self, *args):
        if not self.change_library_allowed():
            return
        from calibre.gui2.dialogs.choose_library import ChooseLibrary
        db = self.gui.library_view.model().db
        c = ChooseLibrary(db, self.gui.library_moved, self.gui)
        c.exec_()

    def change_library_allowed(self):
        if os.environ.get('CALIBRE_OVERRIDE_DATABASE_PATH', None):
            warning_dialog(self.gui, _('Not allowed'),
                    _('You cannot change libraries while using the environment'
                        ' variable CALIBRE_OVERRIDE_DATABASE_PATH.'), show=True)
            return False
        if self.gui.job_manager.has_jobs():
            warning_dialog(self.gui, _('Not allowed'),
                    _('You cannot change libraries while jobs'
                        ' are running.'), show=True)
            return False

        return True
