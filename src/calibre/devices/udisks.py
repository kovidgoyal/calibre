#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai


__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os, re

from polyglot.builtins import unicode_type, as_unicode


def node_mountpoint(node):

    if isinstance(node, unicode_type):
        node = node.encode('utf-8')

    def de_mangle(raw):
        return raw.replace(b'\\040', b' ').replace(b'\\011', b'\t').replace(b'\\012',
                b'\n').replace(b'\\0134', b'\\').decode('utf-8')

    with open('/proc/mounts', 'rb') as src:
        for line in src.readlines():
            line = line.split()
            if line[0] == node:
                return de_mangle(line[1])
    return None


def basic_mount_options():
    return ['rw', 'noexec', 'nosuid', 'nodev', 'uid=%d'%os.geteuid(), 'gid=%d'%os.getegid()]


class NoUDisks2(Exception):
    pass


class UDisks2(object):

    BLOCK = 'org.freedesktop.UDisks2.Block'
    FILESYSTEM = 'org.freedesktop.UDisks2.Filesystem'
    DRIVE = 'org.freedesktop.UDisks2.Drive'

    def __init__(self):
        import dbus
        self.bus = dbus.SystemBus()
        try:
            self.bus.get_object('org.freedesktop.UDisks2',
                        '/org/freedesktop/UDisks2')
        except dbus.exceptions.DBusException as e:
            if getattr(e, '_dbus_error_name', None) == 'org.freedesktop.DBus.Error.ServiceUnknown':
                raise NoUDisks2()
            raise

    def device(self, device_node_path):
        device_node_path = os.path.realpath(device_node_path)
        devname = device_node_path.split('/')[-1]

        # First we try a direct object path
        bd = self.bus.get_object('org.freedesktop.UDisks2',
                        '/org/freedesktop/UDisks2/block_devices/%s'%devname)
        try:
            device = bd.Get(self.BLOCK, 'Device',
                dbus_interface='org.freedesktop.DBus.Properties')
            device = bytearray(device).replace(b'\x00', b'').decode('utf-8')
        except Exception:
            device = None

        if device == device_node_path:
            return bd

        # Enumerate all devices known to UDisks
        devs = self.bus.get_object('org.freedesktop.UDisks2',
                        '/org/freedesktop/UDisks2/block_devices')
        xml = unicode_type(devs.Introspect(dbus_interface='org.freedesktop.DBus.Introspectable'))
        for dev in re.finditer(r'name=[\'"](.+?)[\'"]', xml):
            bd = self.bus.get_object('org.freedesktop.UDisks2',
                '/org/freedesktop/UDisks2/block_devices/%s'%dev.group(1))
            try:
                device = bd.Get(self.BLOCK, 'Device',
                    dbus_interface='org.freedesktop.DBus.Properties')
                device = bytearray(device).replace(b'\x00', b'').decode('utf-8')
            except Exception:
                device = None
            if device == device_node_path:
                return bd

        raise ValueError('%r not known to UDisks2'%device_node_path)

    def mount(self, device_node_path):
        d = self.device(device_node_path)
        try:
            return as_unicode(d.Mount(
                {
                    'auth.no_user_interaction':True,
                    'options':','.join(basic_mount_options())
                },
                dbus_interface=self.FILESYSTEM))
        except Exception:
            # May be already mounted, check
            mp = node_mountpoint(unicode_type(device_node_path))
            if mp is None:
                raise
            return mp

    def unmount(self, device_node_path):
        d = self.device(device_node_path)
        d.Unmount({'force':True, 'auth.no_user_interaction':True},
                dbus_interface=self.FILESYSTEM)

    def drive_for_device(self, device):
        drive = device.Get(self.BLOCK, 'Drive',
            dbus_interface='org.freedesktop.DBus.Properties')
        return self.bus.get_object('org.freedesktop.UDisks2', drive)

    def eject(self, device_node_path):
        drive = self.drive_for_device(self.device(device_node_path))
        drive.Eject({'auth.no_user_interaction':True},
                dbus_interface=self.DRIVE)


def get_udisks():
    return UDisks2()


def mount(node_path):
    u = get_udisks()
    u.mount(node_path)


def eject(node_path):
    u = get_udisks()
    u.eject(node_path)


def umount(node_path):
    u = get_udisks()
    u.unmount(node_path)


def test_udisks(ver=None):
    import sys
    dev = sys.argv[1]
    print('Testing with node', dev)
    u = get_udisks(ver=ver)
    print('Using Udisks:', u.__class__.__name__)
    print('Mounted at:', u.mount(dev))
    print('Unmounting')
    u.unmount(dev)
    print('Ejecting:')
    u.eject(dev)


if __name__ == '__main__':
    test_udisks()
