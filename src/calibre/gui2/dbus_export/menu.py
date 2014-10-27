#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

# Support for excporting Qt's MenuBars/Menus over DBUS. The API is defined in
# dbus-menu.xml from the libdbusmenu project https://launchpad.net/libdbusmenu

import dbus
from PyQt5.Qt import QApplication, QMenu, QIcon, QKeySequence

from calibre.utils.dbus_service import Object, BusName, method as dbus_method, dbus_property, signal as dbus_signal
from calibre.gui2.dbus_export.utils import setup_for_cli_run

class DBusMenu(Object):

    IFACE = 'com.canonical.dbusmenu'

    def __init__(self, object_path, **kw):
        bus = kw.get('bus')
        if bus is None:
            bus = kw['bus'] = dbus.SessionBus()
        Object.__init__(self, bus, object_path)
        self.status = 'normal'

    def publish_new_menu(self, qmenu):
        self.qmenu = qmenu

    @dbus_property(IFACE, signature='u')
    def Version(self):
        return 3  # GTK 3 uses 3, KDE 4 uses 2

    @dbus_property(IFACE, signature='s', emits_changed_signal=True)
    def Status(self):
        return self.status

    def set_status(self, normal=True):
        self.status = 'normal' if normal else 'notice'
        self.PropertiesChanged(self.IFACE, {'Status': self.status}, [])

    @dbus_property(IFACE, signature='s')
    def TextDirection(self):
        return 'ltr'

    @dbus_property(IFACE, signature='as')
    def IconThemePath(self):
        return dbus.Array(signature='s')

    @dbus_method(IFACE, in_signature='iias', out_signature='u(ia{sv}av)')
    def GetLayout(self, parentId, recursionDepth, propertyNames):
        pass

    @dbus_method(IFACE, in_signature='aias', out_signature='a(ia{sv})')
    def GetGroupProperties(self, ids, propertyNames):
        pass

    @dbus_method(IFACE, in_signature='is', out_signature='v')
    def GetProperty(self, id, name):
        pass

    @dbus_method(IFACE, in_signature='isvu', out_signature='')
    def Event(self, id, eventId, data, timestamp):
        ''' This is called by the applet to notify the application an event happened on a
        menu item. type can be one of the following::
            * "clicked"
            * "hovered"
            * "opened"
            * "closed"
        Vendor specific events can be added by prefixing them with "x-<vendor>-"'''
        pass

    @dbus_method(IFACE, in_signature='a(isvu)', out_signature='ai')
    def EventGroup(self, events):
        ''' Used to pass a set of events as a single message for possibily
        several different menuitems.  This is done to optimize DBus traffic.
        Should return a list of ids that are not found. events is a list of
        events in the same format as used for the Event method.'''
        return dbus.Array(signature='u')

    @dbus_method(IFACE, in_signature='i', out_signature='b')
    def AboutToShow(self, id):
        pass

    @dbus_method(IFACE, in_signature='ai', out_signature='aiai')
    def AboutToShowGroup(self, ids):
        pass

    @dbus_signal(IFACE, 'a(ia{sv})a(ias)')
    def ItemsPropertiesUpdated(self, updatedProps, removedProps):
        pass

    @dbus_signal(IFACE, 'ui')
    def LayoutUpdated(self, revision, parent):
        pass

    @dbus_signal(IFACE, 'iu')
    def ItemActivationRequested(self, id, timestamp):
        pass

def test():
    setup_for_cli_run()
    app = QApplication([])
    bus = dbus.SessionBus()
    dbus_name = BusName('com.calibre-ebook.TestDBusMenu', bus=bus, do_not_queue=True)
    m = QMenu()
    m.addAction(QIcon(I('window-close.png')), 'Quit', app.quit).setShortcut(QKeySequence(QKeySequence.Quit))
    menu = DBusMenu('/Menu', bus=bus)
    menu.publish_new_menu(m)
    app.exec_()
    del dbus_name

if __name__ == '__main__':
    test()
