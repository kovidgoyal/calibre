#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

import dbus

from calibre.utils.dbus_service import Object

class DBusMenu(Object):

    IFACE = 'com.canonical.dbusmenu'

    def __init__(self, notifier, object_path, **kw):
        self.notifier = notifier
        bus = kw.get('bus')
        if bus is None:
            bus = kw['bus'] = dbus.SessionBus()
        Object.__init__(self, bus, object_path)

    def publish_new_menu(self):
        pass


