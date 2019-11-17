#!/usr/bin/env python
# vim:fileencoding=utf-8


__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

# A implementation of the GMenuModel export of menus/actions on DBus.
# GMenuModel is pretty bad, does not support icons, for instance, so I have not
# bothered to complete it. See gtk.py for an exmaple app that creates a
# GMenuModel menu.
#
# Partial spec: https://wiki.gnome.org/Projects/GLib/GApplication/DBusAPI

import dbus
from PyQt5.Qt import QObject, pyqtSignal, QTimer, Qt

from calibre.utils.dbus_service import Object, method as dbus_method, signal as dbus_signal
from calibre.gui2.dbus_export.utils import set_X_window_properties
from polyglot.builtins import unicode_type


def add_window_properties_for_menu(widget, object_path, bus):
    op = unicode_type(object_path)
    set_X_window_properties(
            widget.effectiveWinId(), _UNITY_OBJECT_PATH=op,
            _GTK_UNIQUE_BUS_NAME=unicode_type(bus.get_unique_name()),
            _GTK_MENUBAR_OBJECT_PATH=op)


class DBusMenu(QObject):

    handle_event_signal = pyqtSignal(object, object, object, object)

    def __init__(self, object_path, parent=None, bus=None):
        QObject.__init__(self, parent)
        # Unity barfs is the Event DBUS method does not return immediately, so
        # handle it asynchronously
        self.handle_event_signal.connect(self.handle_event, type=Qt.QueuedConnection)
        self.dbus_api = DBusMenuAPI(self, object_path, bus=bus)
        self.set_status = self.dbus_api.set_status
        self._next_id = 0
        self.action_changed_timer = t = QTimer(self)
        t.setInterval(0), t.setSingleShot(True), t.timeout.connect(self.actions_changed)
        self.layout_changed_timer = t = QTimer(self)
        t.setInterval(0), t.setSingleShot(True), t.timeout.connect(self.layouts_changed)
        self.init_maps()

    @property
    def object_path(self):
        return self.dbus_api._object_path


class DBusMenuAPI(Object):

    ACTIONS_IFACE = 'org.gtk.Actions'

    def __init__(self, menu, object_path, bus=None):
        if bus is None:
            bus = dbus.SessionBus()
        Object.__init__(self, bus, object_path)
        self.status = 'normal'
        self.menu = menu
        self.revision = 0

        dbus_method, dbus_signal
