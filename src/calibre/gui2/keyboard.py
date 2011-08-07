#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from collections import OrderedDict

from PyQt4.Qt import (QObject, QKeySequence)

from calibre.utils.config import JSONConfig
from calibre.constants import DEBUG
from calibre import prints

class NameConflict(ValueError):
    pass

class Manager(QObject):

    def __init__(self, parent=None):
        QObject.__init__(self, parent)

        self.config = JSONConfig('shortcuts/main')
        self.custom_keys_map = {}
        self.shortcuts = OrderedDict()
        self.keys_map = {}

        for unique_name, keys in self.config.get(
                'map', {}).iteritems():
            self.custom_keys_map[unique_name] = tuple(keys)

    def register_shortcut(self, unique_name, name, default_keys=(),
            description=None, action=None):
        if unique_name in self.shortcuts:
            name = self.shortcuts[unique_name]['name']
            raise NameConflict('Shortcut for %r already registered by %s'%(
                    unique_name, name))
        shortcut = {'name':name, 'desc':description, 'action': action,
                'default_keys':tuple(default_keys)}
        self.shortcuts[unique_name] = shortcut

    def finalize(self):
        seen = {}
        for unique_name, shortcut in self.shortcuts.iteritems():
            custom_keys = self.custom_keys_map.get(unique_name, None)
            if custom_keys is None:
                candidates = shortcut['default_keys']
            else:
                candidates = custom_keys
            keys = []
            for x in candidates:
                ks = QKeySequence(x, QKeySequence.PortableText)
                x = unicode(ks.toString(QKeySequence.PortableText))
                if x in seen:
                    if DEBUG:
                        prints('Key %r for shortcut %s is already used by'
                                ' %s, ignoring'%(x, shortcut['name'], seen[x]['name']))
                    continue
                seen[x] = shortcut
                keys.append(ks)
            keys = tuple(keys)
            #print (111111, unique_name, candidates, keys)

            self.keys_map[unique_name] = keys
            ac = shortcut['action']
            if ac is not None:
                ac.setShortcuts(list(keys))

