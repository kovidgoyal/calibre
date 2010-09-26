#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'


from calibre.constants import islinux, isosx

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

    ICON = I('notify.png')

    def __init__(self, server, path, interface):
        self.ok, self.err = True, None
        try:
            import dbus
            self.dbus = dbus
            self._notify = dbus.Interface(dbus.SessionBus().get_object(server, path), interface)
        except Exception, err:
            self.ok = False
            self.err = str(err)


class KDENotifier(DBUSNotifier):

    def __init__(self):
        DBUSNotifier.__init__(self, 'org.kde.VisualNotifications',
                '/VisualNotifications', 'org.kde.VisualNotifications')

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

    def __init__(self):
        DBUSNotifier.__init__(self, 'org.freedesktop.Notifications',
                '/org/freedesktop/Notifications', 'org.freedesktop.Notifications')

    def __call__(self, body, summary=None, replaces_id=None, timeout=0):
        if replaces_id is None:
            replaces_id = self.dbus.UInt32()
        timeout, body, summary = self.get_msg_parms(timeout, body, summary)
        try:
            self._notify.Notify('calibre', replaces_id, self.ICON, summary, body,
                self.dbus.Array(signature='s'), self.dbus.Dictionary(signature='sv'),
                timeout)
        except:
            import traceback
            traceback.print_exc()

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
                    if not isinstance(body, unicode):
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

class GrowlNotifier(Notifier):

    notification_type = 'All notifications'

    def __init__(self):
        try:
            import Growl
            self.icon = Growl.Image.imageFromPath(I('notify.png'))
            self.growl = Growl.GrowlNotifier(applicationName='calibre',
                    applicationIcon=self.icon, notifications=[self.notification_type])
            self.growl.register()
            self.ok = True
        except:
            self.ok = False

    def encode(self, msg):
        if isinstance(msg, unicode):
            msg = msg.encode('utf-8')
        return msg

    def __call__(self, body, summary=None, replaces_id=None, timeout=0):
        timeout, body, summary = self.get_msg_parms(timeout, body, summary)
        if self.ok:
            try:
                self.growl.notify(self.notification_type, self.encode(summary),
                        self.encode(body))
            except:
                import traceback
                traceback.print_exc()


def get_notifier(systray=None):
    ans = None
    if islinux:
        ans = KDENotifier()
        if not ans.ok:
            ans = FDONotifier()
            if not ans.ok:
                ans = None
    #if isosx:
    #    ans = GrowlNotifier()
    #    if not ans.ok:
    #        ans = None
    if ans is None:
        ans = QtNotifier(systray)
        if not ans.ok:
            ans = None
    return ans


if __name__ == '__main__':
    n = KDENotifier()
    n('hello')
    n = FDONotifier()
    n('hello')
    '''
    from PyQt4.Qt import QApplication, QSystemTrayIcon, QIcon
    app = QApplication([])
    ic = QIcon(I('notify.png'))
    tray = QSystemTrayIcon(ic)
    tray.setVisible(True)
    n = QtNotifier(tray)
    n('hello')
    '''
