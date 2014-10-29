#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

import time, sys

from PyQt5.Qt import QObject, QMenuBar, QAction, QEvent

UNITY_WINDOW_REGISTRAR = ('com.canonical.AppMenu.Registrar', '/com/canonical/AppMenu/Registrar', 'com.canonical.AppMenu.Registrar')

def log(*args, **kw):
    kw['file'] = sys.stderr
    print('DBusExport:', *args, **kw)
    kw['file'].flush()

class MenuBarAction(QAction):

    def __init__(self, mb):
        QAction.__init__(self, mb)

    def menu(self):
        return self.parent()

menu_counter = 0

class ExportedMenuBar(QMenuBar):

    def __init__(self, parent, menu_registrar, bus):
        global menu_counter
        if not parent.isWindow():
            raise ValueError('You must supply a top level window widget as the parent for an exported menu bar')
        QMenuBar.__init__(self, parent)
        QMenuBar.setVisible(self, False)
        self.menu_action = MenuBarAction(self)
        self.menu_registrar = menu_registrar
        self.registered_window_id = None
        self.bus = bus
        menu_counter += 1
        import dbus
        from calibre.gui2.dbus_export.menu import DBusMenu
        self.object_path = dbus.ObjectPath('/MenuBar/%d' % menu_counter)
        self.dbus_menu = DBusMenu(self.object_path)
        self.dbus_menu.publish_new_menu(self)
        self.register()
        parent.installEventFilter(self)

    def register(self):
        wid = self.parent().effectiveWinId()
        if wid is not None:
            self.registered_window_id = int(wid)
            args = self.menu_registrar + ('RegisterWindow', 'uo', (self.registered_window_id, self.object_path))
            self.bus.call_blocking(*args)

    def unregister(self):
        if self.registered_window_id is not None:
            args = self.menu_registrar + ('UnregisterWindow', 'u', (self.registered_window_id,))
            self.registered_window_id = None
            self.bus.call_blocking(*args)

    def setVisible(self, visible):
        pass  # no-op

    def isVisible(self):
        return True

    def menuAction(self):
        return self.menu_action

    def eventFilter(self, obj, ev):
        etype = ev.type()
        if etype == QEvent.WinIdChange:
            self.unregister()
            self.register()
        return False

class Factory(QObject):

    def __init__(self):
        QObject.__init__(self)
        try:
            import dbus
            self.dbus = dbus
        except ImportError:
            self.dbus = None

        self.menu_registrar = None
        self._bus = None

    @property
    def bus(self):
        if self._bus is None:
            try:
                self._bus = self.dbus.SessionBus()
                self._bus.call_on_disconnection(self.bus_disconnected)
            except Exception as err:
                log('Failed to connect to DBUS session bus, with error:', str(err))
                self._bus = False
        return self._bus or None

    @property
    def has_global_menu(self):
        if self.menu_registrar is None:
            if self.dbus is None:
                self.menu_registrar = False
            else:
                try:
                    self.detect_menu_registrar()
                except Exception as err:
                    self.menu_registrar = False
                    log('Failed to detect window menu registrar, with error:', str(err))
        return bool(self.menu_registrar)

    def detect_menu_registrar(self):
        self.menu_registrar = False
        if self.bus.name_has_owner(UNITY_WINDOW_REGISTRAR[0]):
            self.menu_registrar = UNITY_WINDOW_REGISTRAR

    def create_window_menubar(self, parent):
        if self.has_global_menu:
            return ExportedMenuBar(parent, self.menu_registrar, self.bus)
        return QMenuBar(parent)

    def bus_disconnected(self):
        self._bus = None
        for i in xrange(5):
            try:
                self.bus
            except Exception:
                time.sleep(1)
                continue
            break
        else:
            self.bus
        # TODO: have the created widgets also handle bus disconnection

_factory = None
def factory():
    global _factory
    if _factory is None:
        _factory = Factory()
    return _factory
