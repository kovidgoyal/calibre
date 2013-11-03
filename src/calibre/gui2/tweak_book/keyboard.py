#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

from calibre.gui2.keyboard import Manager

class KeyboardManager(object):

    def __init__(self):
        self.modes = {mode: Manager(config_name='shortcuts/tweak-book-%s' % mode) for mode in
                      ('html', 'css', 'xml', 'other')}
        self.actions = {}
        self.current_mode = None

    def register_shortcut(self, unique_name, name, default_keys=(),
            description=None, action=None, group=None, modes=None):
        if modes is None:
            modes = tuple(self.modes)
        for mode in modes:
            self.modes[mode].register_shortcut(
                unique_name, name, default_keys=default_keys, description=description,
                action=None, group=group)
        self.actions[unique_name] = action

    def finalize(self):
        for km in self.modes.itervalues():
            km.finalize()

    def set_mode(self, name):
        try:
            km = self.modes[name]
        except KeyError:
            name = 'other'
            km = self.modes[name]
        if name != self.current_mode:
            for un, action in self.actions.iteritems():
                keys = km.keys_map[un]
                action.setShortcuts(list(keys))
            self.current_mode = name


