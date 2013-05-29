#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os, posixpath
from functools import partial

from PyQt4.Qt import (QMenu, Qt, QInputDialog, QToolButton, QDialog,
        QDialogButtonBox, QGridLayout, QLabel, QLineEdit, QIcon, QSize,
        QCoreApplication, pyqtSignal)

from calibre import isbytestring, sanitize_file_name_unicode
from calibre.constants import (filesystem_encoding, iswindows,
        get_portable_base)
from calibre.utils.config import prefs, tweaks
from calibre.utils.icu import sort_key
from calibre.gui2 import (gprefs, warning_dialog, Dispatcher, error_dialog,
    question_dialog, info_dialog, open_local_file, choose_dir)
from calibre.library.database2 import LibraryDatabase2
from calibre.gui2.actions import InterfaceAction

class LibraryUsageStats(object):  # {{{

    def __init__(self):
        self.stats = {}
        self.read_stats()
        base = get_portable_base()
        if base is not None:
            lp = prefs['library_path']
            if lp:
                # Rename the current library. Renaming of other libraries is
                # handled by the switch function
                q = os.path.basename(lp)
                for loc in list(self.stats.iterkeys()):
                    bn = posixpath.basename(loc)
                    if bn.lower() == q.lower():
                        self.rename(loc, lp)

    def read_stats(self):
        stats = gprefs.get('library_usage_stats', {})
        self.stats = stats

    def write_stats(self):
        locs = list(self.stats.keys())
        locs.sort(cmp=lambda x, y: cmp(self.stats[x], self.stats[y]),
                reverse=True)
        for key in locs[500:]:
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
        return self.pretty(lpath)

    def locations(self, db):
        lpath = self.canonicalize_path(db.library_path)
        locs = list(self.stats.keys())
        if lpath in locs:
            locs.remove(lpath)
        limit = tweaks['many_libraries']
        key = sort_key if len(locs) > limit else lambda x:self.stats[x]
        locs.sort(key=key, reverse=len(locs)<=limit)
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

class MovedDialog(QDialog):  # {{{

    def __init__(self, stats, location, parent=None):
        QDialog.__init__(self, parent)
        self.setWindowTitle(_('No library found'))
        self._l = l = QGridLayout(self)
        self.setLayout(l)
        self.stats, self.location = stats, location

        loc = self.oldloc = location.replace('/', os.sep)
        self.header = QLabel(_('No existing calibre library was found at %s. '
            'If the library was moved, select its new location below. '
            'Otherwise calibre will forget this library.')%loc)
        self.header.setWordWrap(True)
        ncols = 2
        l.addWidget(self.header, 0, 0, 1, ncols)
        self.cl = QLabel('<br><b>'+_('New location of this library:'))
        l.addWidget(self.cl, 1, 0, 1, ncols)
        self.loc = QLineEdit(loc, self)
        l.addWidget(self.loc, 2, 0, 1, 1)
        self.cd = QToolButton(self)
        self.cd.setIcon(QIcon(I('document_open.png')))
        self.cd.clicked.connect(self.choose_dir)
        l.addWidget(self.cd, 2, 1, 1, 1)
        self.bb = QDialogButtonBox(QDialogButtonBox.Abort)
        b = self.bb.addButton(_('Library moved'), self.bb.AcceptRole)
        b.setIcon(QIcon(I('ok.png')))
        b = self.bb.addButton(_('Forget library'), self.bb.RejectRole)
        b.setIcon(QIcon(I('edit-clear.png')))
        b.clicked.connect(self.forget_library)
        self.bb.accepted.connect(self.accept)
        self.bb.rejected.connect(self.reject)
        l.addWidget(self.bb, 3, 0, 1, ncols)
        self.resize(self.sizeHint() + QSize(100, 50))

    def choose_dir(self):
        d = choose_dir(self, 'library moved choose new loc',
                _('New library location'), default_dir=self.oldloc)
        if d is not None:
            self.loc.setText(d)

    def forget_library(self):
        self.stats.remove(self.location)

    def accept(self):
        newloc = unicode(self.loc.text())
        if not LibraryDatabase2.exists_at(newloc):
            error_dialog(self, _('No library found'),
                    _('No existing calibre library found at %s')%newloc,
                    show=True)
            return
        self.stats.rename(self.location, newloc)
        self.newloc = newloc
        QDialog.accept(self)
# }}}

class ChooseLibraryAction(InterfaceAction):

    name = 'Choose Library'
    action_spec = (_('Choose Library'), 'lt.png',
            _('Choose calibre library to work with'), None)
    dont_add_to = frozenset(['context-menu-device'])
    action_add_menu = True
    action_menu_clone_qaction = _('Switch/create library...')
    restore_view_state = pyqtSignal(object)

    def genesis(self):
        self.count_changed(0)
        self.action_choose = self.menuless_qaction

        self.stats = LibraryUsageStats()
        self.popup_type = (QToolButton.InstantPopup if len(self.stats.stats) > 1 else
                QToolButton.MenuButtonPopup)
        if len(self.stats.stats) > 1:
            self.action_choose.triggered.connect(self.choose_library)
        else:
            self.qaction.triggered.connect(self.choose_library)

        self.choose_menu = self.qaction.menu()

        ac = self.create_action(spec=(_('Pick a random book'), 'random.png',
            None, None), attr='action_pick_random')
        ac.triggered.connect(self.pick_random)

        if not os.environ.get('CALIBRE_OVERRIDE_DATABASE_PATH', None):
            self.choose_menu.addAction(self.action_choose)

            self.quick_menu = QMenu(_('Quick switch'))
            self.quick_menu_action = self.choose_menu.addMenu(self.quick_menu)
            self.rename_menu = QMenu(_('Rename library'))
            self.rename_menu_action = self.choose_menu.addMenu(self.rename_menu)
            self.choose_menu.addAction(ac)
            self.delete_menu = QMenu(_('Remove library'))
            self.delete_menu_action = self.choose_menu.addMenu(self.delete_menu)
        else:
            self.choose_menu.addAction(ac)

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
        ac = self.create_action(spec=(_('Restore database'), 'lt.png',
                                      None, None),
                                      attr='action_restore_database')
        ac.triggered.connect(self.restore_database, type=Qt.QueuedConnection)
        self.maintenance_menu.addAction(ac)

        self.choose_menu.addMenu(self.maintenance_menu)
        self.view_state_map = {}
        self.restore_view_state.connect(self._restore_view_state,
                type=Qt.QueuedConnection)

    @property
    def preserve_state_on_switch(self):
        ans = getattr(self, '_preserve_state_on_switch', None)
        if ans is None:
            self._preserve_state_on_switch = ans = \
                self.gui.library_view.preserve_state(require_selected_ids=False)
        return ans

    def pick_random(self, *args):
        self.gui.iactions['Pick Random Book'].pick_random()

    def library_name(self):
        db = self.gui.library_view.model().db
        path = db.library_path
        if isbytestring(path):
            path = path.decode(filesystem_encoding)
        path = path.replace(os.sep, '/')
        return self.stats.pretty(path)

    def library_changed(self, db):
        lname = self.stats.library_used(db)
        tooltip = self.action_spec[2] + '\n\n' + _('{0} [{1} books]').format(lname, db.count())
        if len(lname) > 16:
            lname = lname[:16] + u'…'
        a = self.qaction
        a.setText(lname)
        a.setToolTip(tooltip)
        a.setStatusTip(tooltip)
        a.setWhatsThis(tooltip)
        self.build_menus()
        state = self.view_state_map.get(self.stats.canonicalize_path(
            db.library_path), None)
        if state is not None:
            self.restore_view_state.emit(state)

    def _restore_view_state(self, state):
        self.preserve_state_on_switch.state = state

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
        newname = sanitize_file_name_unicode(unicode(newname))
        if not ok or not newname or newname == name:
            return
        newloc = os.path.join(base, newname)
        if os.path.exists(newloc):
            return error_dialog(self.gui, _('Already exists'),
                    _('The folder %s already exists. Delete it first.') %
                    newloc, show=True)
        if (iswindows and len(newloc) >
                LibraryDatabase2.WINDOWS_LIBRARY_PATH_LIMIT):
            return error_dialog(self.gui, _('Too long'),
                    _('Path to library too long. Must be less than'
                    ' %d characters.')%LibraryDatabase2.WINDOWS_LIBRARY_PATH_LIMIT,
                    show=True)
        if not os.path.exists(loc):
            error_dialog(self.gui, _('Not found'),
                    _('Cannot rename as no library was found at %s. '
                      'Try switching to this library first, then switch back '
                      'and retry the renaming.')%loc, show=True)
            return
        try:
            os.rename(loc, newloc)
        except:
            import traceback
            det_msg = 'Location: %r New Location: %r\n%s'%(loc, newloc,
                                                        traceback.format_exc())
            error_dialog(self.gui, _('Rename failed'),
                    _('Failed to rename the library at %s. '
                'The most common cause for this is if one of the files'
                ' in the library is open in another program.') % loc,
                    det_msg=det_msg, show=True)
            return
        self.stats.rename(location, newloc)
        self.build_menus()
        self.gui.iactions['Copy To Library'].build_menus()

    def delete_requested(self, name, location):
        loc = location.replace('/', os.sep)
        self.stats.remove(location)
        self.build_menus()
        self.gui.iactions['Copy To Library'].build_menus()
        info_dialog(self.gui, _('Library removed'),
                _('The library %s has been removed from calibre. '
                    'The files remain on your computer, if you want '
                    'to delete them, you will have to do so manually.') % loc,
                show=True)
        if os.path.exists(loc):
            open_local_file(loc)

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
              'rate of approximately 1 book every three seconds.'), show=True)

    def restore_database(self):
        m = self.gui.library_view.model()
        db = m.db
        if (iswindows and len(db.library_path) >
                LibraryDatabase2.WINDOWS_LIBRARY_PATH_LIMIT):
            return error_dialog(self.gui, _('Too long'),
                    _('Path to library too long. Must be less than'
                    ' %d characters. Move your library to a location with'
                    ' a shorter path using Windows Explorer, then point'
                    ' calibre to the new location and try again.')%
                    LibraryDatabase2.WINDOWS_LIBRARY_PATH_LIMIT,
                    show=True)

        from calibre.gui2.dialogs.restore_library import restore_database
        m = self.gui.library_view.model()
        m.stop_metadata_backup()
        db = m.db
        db.prefs.disable_setting = True
        if restore_database(db, self.gui):
            self.gui.library_moved(db.library_path, call_close=False)

    def check_library(self):
        from calibre.gui2.dialogs.check_library import CheckLibraryDialog, DBCheck
        self.gui.library_view.save_state()
        m = self.gui.library_view.model()
        m.stop_metadata_backup()
        db = m.db
        db.prefs.disable_setting = True

        d = DBCheck(self.gui, db)
        d.start()
        try:
            d.conn.close()
        except:
            pass
        d.break_cycles()
        self.gui.library_moved(db.library_path, call_close=not
                d.closed_orig_conn)
        if d.rejected:
            return
        if d.error is None:
            if not question_dialog(self.gui, _('Success'),
                    _('Found no errors in your calibre library database.'
                        ' Do you want calibre to check if the files in your '
                        ' library match the information in the database?')):
                return
        else:
            return error_dialog(self.gui, _('Failed'),
                    _('Database integrity check failed, click Show details'
                        ' for details.'), show=True, det_msg=d.error[1])

        self.gui.status_bar.show_message(
                _('Starting library scan, this may take a while'))
        try:
            QCoreApplication.processEvents()
            d = CheckLibraryDialog(self.gui, m.db)

            if not d.do_exec():
                info_dialog(self.gui, _('No problems found'),
                        _('The files in your library match the information '
                        'in the database.'), show=True)
        finally:
            self.gui.status_bar.clear_message()

    def look_for_portable_lib(self, db, location):
        base = get_portable_base()
        if base is None:
            return False, None
        loc = location.replace('/', os.sep)
        candidate = os.path.join(base, os.path.basename(loc))
        if db.exists_at(candidate):
            newloc = candidate.replace(os.sep, '/')
            self.stats.rename(location, newloc)
            return True, newloc
        return False, None

    def switch_requested(self, location):
        if not self.change_library_allowed():
            return
        db = self.gui.library_view.model().db
        current_lib = self.stats.canonicalize_path(db.library_path)
        self.view_state_map[current_lib] = self.preserve_state_on_switch.state
        loc = location.replace('/', os.sep)
        exists = db.exists_at(loc)
        if not exists:
            exists, new_location = self.look_for_portable_lib(db, location)
            if exists:
                location = new_location
                loc = location.replace('/', os.sep)

        if not exists:
            d = MovedDialog(self.stats, location, self.gui)
            ret = d.exec_()
            self.build_menus()
            self.gui.iactions['Copy To Library'].build_menus()
            if ret == d.Accepted:
                loc = d.newloc.replace('/', os.sep)
            else:
                return

        # from calibre.utils.mem import memory
        # import weakref
        # from PyQt4.Qt import QTimer
        # self.dbref = weakref.ref(self.gui.library_view.model().db)
        # self.before_mem = memory()/1024**2
        self.gui.library_moved(loc, allow_rebuild=True)
        # QTimer.singleShot(5000, self.debug_leak)

    def debug_leak(self):
        import gc
        from calibre.utils.mem import memory
        ref = self.dbref
        for i in xrange(3):
            gc.collect()
        if ref() is not None:
            print 'DB object alive:', ref()
            for r in gc.get_referrers(ref())[:10]:
                print r
                print
        print 'before:', self.before_mem
        print 'after:', memory()/1024**2
        print
        self.dbref = self.before_mem = None

    def qs_requested(self, idx, *args):
        self.switch_requested(self.qs_locations[idx])

    def count_changed(self, new_count):
        pass

    def choose_library(self, *args):
        if not self.change_library_allowed():
            return
        from calibre.gui2.dialogs.choose_library import ChooseLibrary
        self.gui.library_view.save_state()
        db = self.gui.library_view.model().db
        location = self.stats.canonicalize_path(db.library_path)
        self.pre_choose_dialog_location = location
        c = ChooseLibrary(db, self.choose_library_callback, self.gui)
        c.exec_()
        self.choose_dialog_library_renamed = getattr(c, 'library_renamed', False)

    def choose_library_callback(self, newloc, copy_structure=False):
        self.gui.library_moved(newloc, copy_structure=copy_structure,
                allow_rebuild=True)
        if getattr(self, 'choose_dialog_library_renamed', False):
            self.stats.rename(self.pre_choose_dialog_location, prefs['library_path'])
        self.build_menus()
        self.gui.iactions['Copy To Library'].build_menus()

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

