#!/usr/bin/env python2
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

# Implement the StatusNotifierItem spec for creating a system tray icon in
# modern linux desktop environments. See
# http://www.notmart.org/misc/statusnotifieritem/index.html#introduction
# This is not an actual standard, but is apparently used by GNOME, KDE and
# Unity, which makes it necessary enough to implement.

import os

import dbus
from PyQt5.Qt import (
    QApplication, QObject, pyqtSignal, Qt, QPoint, QRect, QMenu,
    QSystemTrayIcon, QIcon)

from calibre.gui2.dbus_export.menu import DBusMenu
from calibre.gui2.dbus_export.utils import icon_cache
from calibre.utils.dbus_service import (
    Object, method as dbus_method, BusName, dbus_property, signal as dbus_signal)

_sni_count = 0


class StatusNotifierItem(QObject):

    IFACE = 'org.kde.StatusNotifierItem'
    activated = pyqtSignal(object)
    show_menu = pyqtSignal(int, int)

    def __init__(self, **kw):
        global _sni_count
        QObject.__init__(self, parent=kw.get('parent'))
        self.context_menu = None
        self.is_visible = True
        self.tool_tip = ''
        path = I('calibre-tray.png')
        if path and os.path.exists(path):
            self._icon = QIcon(path)
        else:
            self._icon = QApplication.instance().windowIcon()
        self.show_menu.connect(self._show_menu, type=Qt.QueuedConnection)
        _sni_count += 1
        kw['num'] = _sni_count
        self.dbus_api = StatusNotifierItemAPI(self, **kw)

    def _show_menu(self, x, y):
        m = self.contextMenu()
        if m is not None:
            m.exec_(QPoint(x, y))

    def isVisible(self):
        return self.is_visible

    def setVisible(self, visible):
        if self.is_visible != visible:
            self.is_visible = visible
            self.dbus_api.NewStatus(self.dbus_api.Status)

    def show(self):
        self.setVisible(True)

    def hide(self):
        self.setVisible(False)

    def toggle(self):
        self.setVisible(not self.isVisible())

    def contextMenu(self):
        return self.context_menu

    def setContextMenu(self, menu):
        self.context_menu = menu
        self.dbus_api.publish_new_menu()

    def geometry(self):
        return QRect()

    def toolTip(self):
        return self.tool_tip

    def setToolTip(self, val):
        self.tool_tip = val or ''
        self.dbus_api.NewToolTip()

    def setIcon(self, icon):
        self._icon = icon
        self.dbus_api.NewIcon()

    def icon(self):
        return self._icon

    @classmethod
    def supportsMessages(cls):
        return False

    def emit_activated(self):
        self.activated.emit(QSystemTrayIcon.Trigger)


_status_item_menu_count = 0


class StatusNotifierItemAPI(Object):

    'See http://www.notmart.org/misc/statusnotifieritem/statusnotifieritem.html'

    IFACE = 'org.kde.StatusNotifierItem'

    def __init__(self, notifier, **kw):
        global _status_item_menu_count
        self.notifier = notifier
        bus = kw.get('bus')
        if bus is None:
            bus = kw['bus'] = dbus.SessionBus()
        self.name = '%s-%s-%s' % (self.IFACE, os.getpid(), kw.get('num', 1))
        self.dbus_name = BusName(self.name, bus=bus, do_not_queue=True)
        self.app_id = kw.get('app_id') or QApplication.instance().applicationName() or 'unknown_application'
        self.category = kw.get('category') or 'ApplicationStatus'
        self.title = kw.get('title') or self.app_id
        Object.__init__(self, bus, '/' + self.IFACE.split('.')[-1])
        _status_item_menu_count += 1
        self.dbus_menu = DBusMenu('/StatusItemMenu/%d' % _status_item_menu_count, bus=bus, parent=kw.get('parent'))

    def publish_new_menu(self):
        menu = self.notifier.contextMenu()
        if menu is None:
            menu = QMenu()
        if len(menu.actions()) == 0:
            menu.addAction(self.notifier.icon(), _('Show/hide %s') % self.title, self.notifier.emit_activated)
        # The menu must have at least one entry, namely the show/hide entry.
        # This is necessary as Canonical in their infinite wisdom decided to
        # force all tray icons to show their popup menus when clicked.
        self.dbus_menu.publish_new_menu(menu)

    @dbus_property(IFACE, signature='s')
    def IconName(self):
        return icon_cache().name_for_icon(self.notifier.icon())

    @dbus_property(IFACE, signature='s')
    def IconThemePath(self):
        return icon_cache().icon_theme_path

    @dbus_property(IFACE, signature='a(iiay)')
    def IconPixmap(self):
        return dbus.Array(signature='(iiay)')

    @dbus_property(IFACE, signature='s')
    def OverlayIconName(self):
        return ''

    @dbus_property(IFACE, signature='(sa(iiay)ss)')
    def ToolTip(self):
        # This is ignored on Unity, Canonical believes in user interfaces
        # that are so functionality free that they dont need tooltips
        return self.IconName, self.IconPixmap, self.Title, self.notifier.toolTip()

    @dbus_property(IFACE, signature='a(iiay)')
    def OverlayIconPixmap(self):
        return dbus.Array(signature='(iiay)')

    @dbus_property(IFACE, signature='s')
    def AttentionIconName(self):
        return ''

    @dbus_property(IFACE, signature='a(iiay)')
    def AttentionIconPixmap(self):
        return dbus.Array(signature='(iiay)')

    @dbus_property(IFACE, signature='s')
    def Category(self):
        return self.category

    @dbus_property(IFACE, signature='s')
    def Id(self):
        return self.app_id

    @dbus_property(IFACE, signature='s')
    def Title(self):
        return self.title

    @dbus_property(IFACE, signature='s')
    def Status(self):
        return 'Active' if self.notifier.isVisible() else 'Passive'

    @dbus_property(IFACE, signature='o')
    def Menu(self):
        return dbus.ObjectPath(self.dbus_menu.object_path)

    @dbus_property(IFACE, signature='u')
    def WindowId(self):
        return 0

    @dbus_method(IFACE, in_signature='ii', out_signature='')
    def ContextMenu(self, x, y):
        self.notifier.show_menu.emit(x, y)

    @dbus_method(IFACE, in_signature='ii', out_signature='')
    def Activate(self, x, y):
        self.notifier.activated.emit(QSystemTrayIcon.Trigger)

    @dbus_method(IFACE, in_signature='u', out_signature='')
    def XAyatanaSecondaryActivate(self, timestamp):
        # This is called when the user middle clicks the icon in Unity
        self.notifier.activated.emit(QSystemTrayIcon.MiddleClick)

    @dbus_method(IFACE, in_signature='ii', out_signature='')
    def SecondaryActivate(self, x, y):
        self.notifier.activated.emit(QSystemTrayIcon.MiddleClick)

    @dbus_method(IFACE, in_signature='is', out_signature='')
    def Scroll(self, delta, orientation):
        pass

    @dbus_signal(IFACE, '')
    def NewTitle(self):
        pass

    @dbus_signal(IFACE, '')
    def NewIcon(self):
        pass

    @dbus_signal(IFACE, '')
    def NewAttentionIcon(self):
        pass

    @dbus_signal(IFACE, '')
    def NewOverlayIcon(self):
        pass

    @dbus_signal(IFACE, '')
    def NewToolTip(self):
        pass

    @dbus_signal(IFACE, 's')
    def NewStatus(self, status):
        pass
