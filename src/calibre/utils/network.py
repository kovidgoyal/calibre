#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
# License: GPLv3 Copyright: 2010, Kovid Goyal <kovid at kovidgoyal.net>



from calibre.constants import iswindows, islinux, isbsd
from calibre.utils.config_base import tweaks


class LinuxNetworkStatus(object):

    def __init__(self):
        try:
            import dbus
            bus = dbus.SystemBus()
            proxy = bus.get_object("org.freedesktop.NetworkManager",
                        "/org/freedesktop/NetworkManager")
            self.manager = dbus.Interface(proxy, "org.freedesktop.DBus.Properties")
        except:
            self.manager = None

    def __call__(self):
        if self.manager is None:
            return True
        try:
            connections = self.manager.Get("org.freedesktop.NetworkManager",
                        "ActiveConnections")
            return len(connections) > 0
        except:
            return True


class WindowsNetworkStatus(object):

    def __init__(self):
        from calibre.constants import plugins
        self.winutil = plugins['winutil'][0]

    def __call__(self):
        if self.winutil is None:
            return True
        return self.winutil.internet_connected()


class DummyNetworkStatus(object):

    def __call__(self):
        return True


_network_status = WindowsNetworkStatus() if iswindows else \
        LinuxNetworkStatus() if (islinux or isbsd) else \
        DummyNetworkStatus()


def internet_connected():
    if tweaks['skip_network_check']:
        return True
    return _network_status()
