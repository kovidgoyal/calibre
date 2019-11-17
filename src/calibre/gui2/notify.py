#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai


__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'


import time
from calibre import prints
from calibre.constants import islinux, isosx, get_osx_version, DEBUG, plugins
from polyglot.builtins import unicode_type


class Notifier(object):

    DEFAULT_TIMEOUT = 5000

    def get_msg_parms(self, timeout, body, summary):
        if summary is None:
            summary = 'calibre'
        if timeout == 0:
            timeout = self.DEFAULT_TIMEOUT
        return timeout, body, summary

    def __call__(self, body, summary=None, replaces_id=None, timeout=0):
        raise NotImplementedError


class DBUSNotifier(Notifier):

    ICON = I('lt.png')

    def __init__(self, session_bus):
        self.ok, self.err = True, None
        server, path, interface = self.SERVICE
        if DEBUG:
            start = time.time()
            prints('Looking for desktop notifier support from:', server)
        try:
            import dbus
            self.dbus = dbus
            self._notify = dbus.Interface(session_bus.get_object(server, path), interface)
        except Exception as err:
            self.ok = False
            self.err = unicode_type(err)
        if DEBUG:
            prints(server, 'found' if self.ok else 'not found', 'in', '%.1f' % (time.time() - start), 'seconds')


class KDENotifier(DBUSNotifier):

    SERVICE = 'org.kde.VisualNotifications', '/VisualNotifications', 'org.kde.VisualNotifications'

    def __call__(self, body, summary=None, replaces_id=None, timeout=0):
        if replaces_id is None:
            replaces_id = self.dbus.UInt32()
        event_id = ''
        timeout, body, summary = self.get_msg_parms(timeout, body, summary)
        try:
            self._notify.Notify('calibre', replaces_id, event_id, self.ICON, summary, body,
                self.dbus.Array(signature='s'), self.dbus.Dictionary(signature='sv'),
                timeout)
        except:
            import traceback
            traceback.print_exc()


class FDONotifier(DBUSNotifier):

    SERVICE = 'org.freedesktop.Notifications', '/org/freedesktop/Notifications', 'org.freedesktop.Notifications'

    def __call__(self, body, summary=None, replaces_id=None, timeout=0):
        if replaces_id is None:
            replaces_id = self.dbus.UInt32()
        timeout, body, summary = self.get_msg_parms(timeout, body, summary)
        try:
            self._notify.Notify('calibre', replaces_id, self.ICON, summary, body,
                self.dbus.Array(signature='s'), self.dbus.Dictionary({"desktop-entry": "calibre-gui"}, signature='sv'),
                timeout)
        except:
            import traceback
            traceback.print_exc()


def get_dbus_notifier():
    import dbus
    session_bus = dbus.SessionBus()
    names = frozenset(session_bus.list_names())
    for srv in KDENotifier, FDONotifier:
        if srv.SERVICE[0] in names:
            ans = srv(session_bus)
            if ans.ok:
                return ans


class QtNotifier(Notifier):

    def __init__(self, systray=None):
        self.systray = systray
        self.ok = self.systray is not None and self.systray.supportsMessages()

    def __call__(self, body, summary=None, replaces_id=None, timeout=0):
        timeout, body, summary = self.get_msg_parms(timeout, body, summary)
        if self.systray is not None:
            try:
                hide = False
                try:
                    if not isinstance(body, unicode_type):
                        body = body.decode('utf-8')
                    if isosx and not self.systray.isVisible():
                        self.systray.show()
                        hide = True
                    self.systray.showMessage(summary, body, self.systray.Information,
                            timeout)
                finally:
                    if hide:
                        self.systray.hide()
            except:
                pass


class DummyNotifier(Notifier):

    ok = True

    def __call__(self, body, summary=None, replaces_id=None, timeout=0):
        pass


class AppleNotifier(Notifier):

    def __init__(self):
        self.cocoa, err = plugins['cocoa']
        self.ok = not err

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
            except:
                import traceback
                traceback.print_exc()


def get_notifier(systray=None):
    ans = None
    if islinux:
        try:
            ans = get_dbus_notifier()
        except Exception:
            import traceback
            traceback.print_exc()
            ans = None
    elif isosx:
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


if __name__ == '__main__':
    n = get_notifier()
    n('hello')
