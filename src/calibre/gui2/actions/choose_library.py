#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os
from functools import partial

from PyQt4.Qt import QMenu

from calibre import isbytestring
from calibre.constants import filesystem_encoding
from calibre.utils.config import prefs
from calibre.gui2 import gprefs, warning_dialog
from calibre.gui2.actions import InterfaceAction

class LibraryUsageStats(object):

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


class ChooseLibraryAction(InterfaceAction):

    name = 'Choose Library'
    action_spec = (_('%d books'), 'lt.png',
            _('Choose calibre library to work with'), None)

    def genesis(self):
        self.count_changed(0)
        self.qaction.triggered.connect(self.choose_library)

        self.stats = LibraryUsageStats()
        self.create_action(spec=(_('Switch to library...'), 'lt.png', None,
            None), attr='action_choose')
        self.action_choose.triggered.connect(self.choose_library)
        self.choose_menu = QMenu(self.gui)
        self.choose_menu.addAction(self.action_choose)
        self.qaction.setMenu(self.choose_menu)

        self.quick_menu = QMenu(_('Quick switch'))
        self.quick_menu_action = self.choose_menu.addMenu(self.quick_menu)
        self.qs_separator = self.choose_menu.addSeparator()
        self.switch_actions = []
        for i in range(5):
            ac = self.create_action(spec=('', None, None, None),
                    attr='switch_action%d'%i)
            self.switch_actions.append(ac)
            ac.setVisible(False)
            ac.triggered.connect(partial(self.qs_requested, i))
            self.choose_menu.addAction(ac)

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
        db = self.gui.library_view.model().db
        locations = list(self.stats.locations(db))
        for ac in self.switch_actions:
            ac.setVisible(False)
        self.quick_menu.clear()
        self.qs_locations = [i[1] for i in locations]
        for name, loc in locations:
            self.quick_menu.addAction(name, partial(self.switch_requested,
                loc))

        for i, x in enumerate(locations[:len(self.switch_actions)]):
            name, loc = x
            ac = self.switch_actions[i]
            ac.setText(name)
            ac.setVisible(True)

        self.quick_menu_action.setVisible(bool(locations))


    def location_selected(self, loc):
        enabled = loc == 'library'
        self.qaction.setEnabled(enabled)

    def switch_requested(self, location):
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
        from calibre.gui2.dialogs.choose_library import ChooseLibrary
        db = self.gui.library_view.model().db
        c = ChooseLibrary(db, self.gui.library_moved, self.gui)
        c.exec_()


