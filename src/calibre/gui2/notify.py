#!/usr/bin/env python


__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'


import sys
from contextlib import suppress
from functools import lru_cache

from calibre.constants import DEBUG, __appname__, get_osx_version, islinux, ismacos


class Notifier:

    DEFAULT_TIMEOUT = 5000

    def get_msg_parms(self, timeout, body, summary):
        if summary is None:
            summary = 'calibre'
        if timeout == 0:
            timeout = self.DEFAULT_TIMEOUT
        return timeout, body, summary

    def __call__(self, body, summary=None, replaces_id=None, timeout=0):
        raise NotImplementedError('implement in subclass')


@lru_cache(maxsize=2)
def icon(data=False):
    return I('lt.png', data=data)


class DBUSNotifier(Notifier):

    def __init__(self):
        self.initialized = False

    def initialize(self):
        from jeepney.io.blocking import open_dbus_connection
        if self.initialized:
            return
        self.initialized = True
        self.ok = False
        try:
            self.connection = open_dbus_connection(bus='SESSION')
        except Exception:
            return
        with suppress(Exception):
            self.ok = self.initialize_fdo()
        if self.ok:
            self.notify = self.fdo_notify
            return
        if DEBUG:
            print('Failed to connect to FDO Notifications service', file=sys.stderr)
        with suppress(Exception):
            self.ok = self.initialize_portal()
        if self.ok:
            self.notify = self.portal_notify
        else:
            print('Failed to connect to Portal Notifications service', file=sys.stderr)

    def initialize_fdo(self):
        from jeepney import DBusAddress, MessageType, new_method_call
        self.address = DBusAddress(
            '/org/freedesktop/Notifications',
            bus_name='org.freedesktop.Notifications',
            interface='org.freedesktop.Notifications')

        msg = new_method_call(self.address, 'GetCapabilities')
        reply = self.connection.send_and_get_reply(msg)
        return bool(reply and reply.header.message_type is MessageType.method_return)

    def initialize_portal(self):
        from jeepney import DBusAddress, MessageType, Properties
        self.address = DBusAddress(
            '/org/freedesktop/portal/desktop',
            bus_name='org.freedesktop.portal.Desktop',
            interface='org.freedesktop.portal.Notification')
        p = Properties(self.address)
        msg = p.get('version')
        reply = self.connection.send_and_get_reply(msg)
        return bool(reply and reply.header.message_type is MessageType.method_return and reply.body[0][1] >= 1)

    def fdo_notify(self, body, summary=None, replaces_id=None, timeout=0):
        from jeepney import new_method_call
        timeout, body, summary = self.get_msg_parms(timeout, body, summary)
        msg = new_method_call(
            self.address, 'Notify', 'susssasa{sv}i',
            (__appname__,
            replaces_id or 0,
            icon(),
            summary,
            body,
            [], {},  # Actions, hints
            timeout,
            ))
        try:
            self.connection.send(msg)
        except Exception:
            import traceback
            traceback.print_exc()

    def portal_notify(self, body, summary=None, replaces_id=None, timeout=0):
        from jeepney import new_method_call
        _, body, summary = self.get_msg_parms(timeout, body, summary)
        # Note: This backend does not natively support the notion of timeouts
        #
        # While the effect may be emulated by manually withdrawing the notifi-
        # cation from the Calibre side, this resulted in a less than optimal
        # User Experience. Based on this, KG decided it to be better to not
        # support timeouts at all for this backend.
        #
        # See discussion at https://github.com/kovidgoyal/calibre/pull/1268.

        # For the icon: This should instead just send the themable icon name
        #
        # Doing that however, requires Calibre to first be converted to use
        # its AppID everywhere and then we still need a fallback for portable
        # installations.
        msg = new_method_call(
            self.address, 'AddNotification', 'sa{sv}', (
                str(replaces_id or 0),
                {
                "title": ('s', summary),
                "body": ('s', body),
                "icon": (
                    '(sv)',
                    (
                        "bytes",
                        ('ay', icon(data=True))
                    )
                ),
                }))
        try:
            self.connection.send(msg)
        except Exception:
            import traceback
            traceback.print_exc()

    def __call__(self, body, summary=None, replaces_id=None, timeout=0):
        self.initialize()
        if not self.ok:
            if DEBUG:
                print('Failed to connect to any notification service', file=sys.stderr)
            return
        self.notify(body, summary, replaces_id, timeout)


class QtNotifier(Notifier):

    def __init__(self, systray=None):
        self.systray = systray
        self.ok = self.systray is not None and self.systray.supportsMessages()

    def __call__(self, body, summary=None, replaces_id=None, timeout=0):
        timeout, body, summary = self.get_msg_parms(timeout, body, summary)
        from qt.core import QSystemTrayIcon
        if self.systray is not None:
            try:
                hide = False
                try:
                    if not isinstance(body, str):
                        body = body.decode('utf-8')
                    if ismacos and not self.systray.isVisible():
                        self.systray.show()
                        hide = True
                    self.systray.showMessage(summary, body, QSystemTrayIcon.MessageIcon.Information,
                            timeout)
                finally:
                    if hide:
                        self.systray.hide()
            except Exception:
                pass


class DummyNotifier(Notifier):

    ok = True

    def __call__(self, body, summary=None, replaces_id=None, timeout=0):
        pass


class AppleNotifier(Notifier):

    def __init__(self):
        from calibre_extensions import cocoa
        self.cocoa = cocoa
        self.ok = True

    def notify(self, body, summary):
        if summary:
            title, informative_text = summary, body
        else:
            title, informative_text = body, None
        self.cocoa.send_notification(None, title, informative_text)

    def __call__(self, body, summary=None, replaces_id=None, timeout=0):
        timeout, body, summary = self.get_msg_parms(timeout, body, summary)
        if self.ok:
            try:
                self.notify(body, summary)
            except Exception:
                import traceback
                traceback.print_exc()


def get_notifier(systray=None):
    ans = None
    if islinux:
        ans = DBUSNotifier()
    elif ismacos:
        if get_osx_version() >= (10, 8, 0):
            ans = AppleNotifier()
            if not ans.ok:
                ans = DummyNotifier()
        else:
            # We dont use Qt's systray based notifier as it uses Growl and is
            # broken with different versions of Growl
            ans = DummyNotifier()
    if ans is None:
        ans = QtNotifier(systray)
        if not ans.ok:
            ans = None
    return ans


def hello():
    n = get_notifier()
    n('hello')


if __name__ == '__main__':
    hello()
