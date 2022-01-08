#!/usr/bin/env python
# License: GPLv3 Copyright: 2010, Kovid Goyal <kovid at kovidgoyal.net>


from contextlib import suppress

from calibre.constants import isbsd, islinux, iswindows
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
        from jeepney import DBusAddress, Properties, new_method_call
        # Prefer desktop portal interface here since it can theoretically
        # work with network management solutions other than NetworkManager
        # and is controlled by the current desktop session
        #
        # There is no difference in terms of “features” provided between
        # the two APIs from our point of view.
        self.xdp_call = lambda : new_method_call(DBusAddress(
            '/org/freedesktop/portal/desktop',
            bus_name='org.freedesktop.portal.Desktop',
            interface="org.freedesktop.portal.NetworkMonitor"), 'GetConnectivity')
        self.nm_call = lambda : Properties(DBusAddress('/org/freedesktop/NetworkManager',
                bus_name='org.freedesktop.NetworkManager',
                interface="org.freedesktop.NetworkManager")).get('Connectivity')

        if self.xdp() is not None:
            self.get_connectivity = self.xdp
        elif self.nm() is not None:
            self.get_connectivity = self.nm
        else:
            self.get_connectivity = lambda : 4

    def connect(self, which='SESSION'):
        from jeepney.io.blocking import open_dbus_connection
        if not hasattr(self, 'connection'):
            self.connection = open_dbus_connection(which)

    def xdp(self):
        with suppress(Exception):
            self.connect('SESSION')
            return self.send(self.xdp_call())
        if hasattr(self, 'connection'):
            self.connection.close()
            del self.connection

    def nm(self):
        with suppress(Exception):
            self.connect('SYSTEM')
            return self.NM_XDP_CONNECTIVITY_MAP.get(self.send(self.nm_call()), 4)
        if hasattr(self, 'connection'):
            self.connection.close()
            del self.connection

    def send(self, msg):
        from jeepney import DBusErrorResponse, MessageType
        reply = self.connection.send_and_get_reply(msg)
        if reply.header.message_type is MessageType.error:
            raise DBusErrorResponse(reply)
        return reply.body[0]

    def __call__(self):
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


def internet_connected():
    if tweaks['skip_network_check']:
        return True
    if not hasattr(internet_connected, 'checker'):
        internet_connected.checker = WindowsNetworkStatus() if iswindows else \
        LinuxNetworkStatus() if (islinux or isbsd) else \
        DummyNetworkStatus()

    return internet_connected.checker()
