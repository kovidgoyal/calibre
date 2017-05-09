#!/usr/bin/env python2
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

import time, sys, weakref

from PyQt5.Qt import (
    QObject, QMenuBar, QAction, QEvent, QSystemTrayIcon, QApplication, Qt)

from calibre.constants import iswindows, isosx

UNITY_WINDOW_REGISTRAR = ('com.canonical.AppMenu.Registrar', '/com/canonical/AppMenu/Registrar', 'com.canonical.AppMenu.Registrar')
STATUS_NOTIFIER = ("org.kde.StatusNotifierWatcher", "/StatusNotifierWatcher", "org.kde.StatusNotifierWatcher")


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


class ExportedMenuBar(QMenuBar):  # {{{

    is_native_menubar = True

    def __init__(self, parent, menu_registrar, bus):
        global menu_counter
        if not parent.isWindow():
            raise ValueError('You must supply a top level window widget as the parent for an exported menu bar')
        self._blocked = False
        self.is_visible = True
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

    def register(self, menu_registrar=None):
        self.menu_registrar = menu_registrar or self.menu_registrar
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
        self.is_visible = visible
        self.dbus_menu.set_visible(self.is_visible and not self._blocked)

    def isVisible(self):
        return self.is_visible

    def show(self):
        self.setVisible(True)

    def hide(self):
        self.setVisible(False)

    def menuAction(self):
        return self.menu_action

    def _block(self):
        self._blocked = True
        self.setVisible(self.is_visible)

    def _unblock(self):
        self._blocked = False
        self.setVisible(self.is_visible)

    def eventFilter(self, obj, ev):
        etype = ev.type()
        if etype == QEvent.Show:
            # Hiding a window causes the registrar to auto-unregister it, so we
            # have to re-register it on show events.
            self.register()
        elif etype == QEvent.WinIdChange:
            self.unregister()
            self.register()
        return False

# }}}


class Factory(QObject):

    def __init__(self, app_id=None):
        QObject.__init__(self)
        self.app_id = app_id or QApplication.instance().applicationName() or 'unknown_application'
        if iswindows or isosx:
            self.dbus = None
        else:
            try:
                import dbus
                self.dbus = dbus
            except ImportError as err:
                log('Failed to import dbus, with error:', str(err))
                self.dbus = None

        self.menu_registrar = None
        self.status_notifier = None
        self._bus = None
        self.status_notifiers, self.window_menus = [], []

    def prune_dead_refs(self):
        self.status_notifiers = [ref for ref in self.status_notifiers if ref() is not None]
        self.window_menus = [ref for ref in self.window_menus if ref() is not None]

    def window_registrar_changed(self, new_owner):
        if new_owner:
            self.menu_registrar = None
            if self.has_global_menu:
                for ref in self.window_menus:
                    w = ref()
                    if w is not None:
                        w.register(self.menu_registrar)

    def status_notifier_registrar_changed(self, new_owner):
        if new_owner:
            self.status_notifier = None
            if self.has_status_notifier:
                for ref in self.status_notifiers:
                    w = ref()
                    if w is not None:
                        self.register_status_notifier(w)

    @property
    def bus(self):
        if self._bus is None:
            try:
                self._bus = self.dbus.SessionBus()
                self._bus.call_on_disconnection(self.bus_disconnected)
                self._bus.watch_name_owner(UNITY_WINDOW_REGISTRAR[0], self.window_registrar_changed)
                self._bus.watch_name_owner(STATUS_NOTIFIER[0], self.status_notifier_registrar_changed)
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
        if self.bus is not None and self.bus.name_has_owner(UNITY_WINDOW_REGISTRAR[0]):
            self.menu_registrar = UNITY_WINDOW_REGISTRAR

    @property
    def has_status_notifier(self):
        if self.status_notifier is None:
            if self.dbus is None:
                self.status_notifier = False
            else:
                try:
                    self.detect_status_notifier()
                except Exception as err:
                    self.status_notifier = False
                    log('Failed to detect window status notifier, with error:', str(err))
        return bool(self.status_notifier)

    def detect_status_notifier(self):
        'See http://www.notmart.org/misc/statusnotifieritem/statusnotifierwatcher.html'
        self.status_notifier = False
        if self.bus is not None and self.bus.name_has_owner(STATUS_NOTIFIER[0]):
            args = STATUS_NOTIFIER[:2] + (self.dbus.PROPERTIES_IFACE, 'Get', 'ss', (STATUS_NOTIFIER[-1], 'IsStatusNotifierHostRegistered'))
            self.status_notifier = bool(self.bus.call_blocking(*args, timeout=0.1))

    def create_window_menubar(self, parent):
        if not QApplication.instance().testAttribute(Qt.AA_DontUseNativeMenuBar) and self.has_global_menu:
            ans = ExportedMenuBar(parent, self.menu_registrar, self.bus)
            self.prune_dead_refs()
            self.window_menus.append(weakref.ref(ans))
            return ans
        ans = QMenuBar(parent)
        parent.setMenuBar(ans)
        ans.is_native_menubar = False
        return ans

    def register_status_notifier(self, item):
        args = STATUS_NOTIFIER + ('RegisterStatusNotifierItem', 's', (item.dbus_api.name,))
        self.bus.call_blocking(*args, timeout=1)

    def create_system_tray_icon(self, parent=None, title=None, category=None):
        if self.has_status_notifier:
            from calibre.gui2.dbus_export.tray import StatusNotifierItem
            ans = StatusNotifierItem(parent=parent, title=title, app_id=self.app_id, category=category)
            self.register_status_notifier(ans)
            self.prune_dead_refs()
            self.status_notifiers.append(weakref.ref(ans))
            return ans
        if iswindows or isosx:
            return QSystemTrayIcon(parent)

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


def factory(app_id=None):
    global _factory
    if _factory is None:
        _factory = Factory(app_id=app_id)
    return _factory
