#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
# License: GPLv3 Copyright: 2010, Kovid Goyal <kovid at kovidgoyal.net>


from contextlib import suppress
from calibre.constants import iswindows, islinux, isbsd
from calibre.utils.config_base import tweaks


class LinuxNetworkStatus:

    # Map of NetworkManager connectivity values to their XDP/GLib equivalents
    NM_XDP_CONNECTIVITY_MAP = {
        0: 4,  # NM_CONNECTIVITY_UNKNOWN → Full network
        1: 1,  # NM_CONNECTIVITY_NONE → Local only
        2: 3,  # NM_CONNECTIVITY_PORTAL → Captive portal
        3: 2,  # NM_CONNECTIVITY_LIMITED → Limited connectivity
        4: 4,  # NM_CONNECTIVITY_FULL → Full network
    }

    def __init__(self):
        # Prefer desktop portal interface here since it can theoretically
        # work with network management solutions other than NetworkManager
        # and is controlled by the current desktop session
        #
        # There is no difference in terms of “features” provided between
        # the two APIs from our point of view.
        self.get_connectivity = self.connect_to_xdp()
        if self.get_connectivity is None:
            self.get_connectivity = self.connect_to_nm()

    def connect_to_xdp(self):
        with suppress(Exception):
            import dbus
            bus = dbus.SessionBus()
            proxy = bus.get_object("org.freedesktop.portal.Desktop",
                        "/org/freedesktop/portal/desktop")
            return proxy.get_dbus_method("GetConnectivity",
                        "org.freedesktop.portal.NetworkMonitor")

    def connect_to_nm(self):
        with suppress(Exception):
            import dbus
            bus = dbus.SystemBus()
            proxy = bus.get_object("org.freedesktop.NetworkManager",
                        "/org/freedesktop/NetworkManager")
            prop_getter = proxy.get_dbus_method("Get",
                        "org.freedesktop.DBus.Properties")
            return (lambda: self.NM_XDP_CONNECTIVITY_MAP.get(
                 prop_getter("org.freedesktop.NetworkManager", "Connectivity"), 4
            ))

    def __call__(self):
        if self.get_connectivity is None:
            return True
        with suppress(Exception):
            # Meanings of returned XDP/GLib connectivity values:
            #   * 1: Local only. The host is not configured with a route to the internet.
            #   * 2: Limited connectivity. The host is connected to a network, but can't reach the full internet.
            #   * 3: Captive portal. The host is behind a captive portal and cannot reach the full internet.
            #   * 4: Full network. The host connected to a network, and can reach the full internet.
            return self.get_connectivity() == 4
        return True


class WindowsNetworkStatus:

    def __init__(self):
        from calibre_extensions import winutil
        self.winutil = winutil

    def __call__(self):
        if self.winutil is None:
            return True
        return self.winutil.internet_connected()


class DummyNetworkStatus:

    def __call__(self):
        return True


_network_status = WindowsNetworkStatus() if iswindows else \
        LinuxNetworkStatus() if (islinux or isbsd) else \
        DummyNetworkStatus()


def internet_connected():
    if tweaks['skip_network_check']:
        return True
    return _network_status()
