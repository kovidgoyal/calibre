#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os, dbus, re

def node_mountpoint(node):

    def de_mangle(raw):
        return raw.replace('\\040', ' ').replace('\\011', '\t').replace('\\012',
                '\n').replace('\\0134', '\\')

    for line in open('/proc/mounts').readlines():
        line = line.split()
        if line[0] == node:
            return de_mangle(line[1])
    return None


class UDisks(object):

    def __init__(self):
        self.bus = dbus.SystemBus()
        self.main = dbus.Interface(self.bus.get_object('org.freedesktop.UDisks',
                        '/org/freedesktop/UDisks'), 'org.freedesktop.UDisks')

    def device(self, device_node_path):
        devpath = self.main.FindDeviceByDeviceFile(device_node_path)
        return dbus.Interface(self.bus.get_object('org.freedesktop.UDisks',
                        devpath), 'org.freedesktop.UDisks.Device')

    def mount(self, device_node_path):
        d = self.device(device_node_path)
        try:
            return unicode(d.FilesystemMount('',
                ['auth_no_user_interaction', 'rw', 'noexec', 'nosuid',
                'sync', 'nodev', 'uid=%d'%os.geteuid(), 'gid=%d'%os.getegid()]))
        except:
            # May be already mounted, check
            mp = node_mountpoint(str(device_node_path))
            if mp is None:
                raise
            return mp

    def unmount(self, device_node_path):
        d = self.device(device_node_path)
        d.FilesystemUnmount(['force'])

    def eject(self, device_node_path):
        parent = device_node_path
        while parent[-1] in '0123456789':
            parent = parent[:-1]
        d = self.device(parent)
        d.DriveEject([])

class NoUDisks2(Exception):
    pass

class UDisks2(object):

    BLOCK = 'org.freedesktop.UDisks2.Block'
    FILESYSTEM = 'org.freedesktop.UDisks2.Filesystem'
    DRIVE = 'org.freedesktop.UDisks2.Drive'

    def __init__(self):
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
        except:
            device = None

        if device == device_node_path:
            return bd

        # Enumerate all devices known to UDisks
        devs = self.bus.get_object('org.freedesktop.UDisks2',
                        '/org/freedesktop/UDisks2/block_devices')
        xml = devs.Introspect(dbus_interface='org.freedesktop.DBus.Introspectable')
        for dev in re.finditer(r'name=[\'"](.+?)[\'"]', type(u'')(xml)):
            bd = self.bus.get_object('org.freedesktop.UDisks2',
                '/org/freedesktop/UDisks2/block_devices/%s2'%dev.group(1))
            try:
                device = bd.Get(self.BLOCK, 'Device',
                    dbus_interface='org.freedesktop.DBus.Properties')
                device = bytearray(device).replace(b'\x00', b'').decode('utf-8')
            except:
                device = None
            if device == device_node_path:
                return bd

        raise ValueError('%r not known to UDisks2'%device_node_path)

    def mount(self, device_node_path):
        d = self.device(device_node_path)
        mount_options = ['rw', 'noexec', 'nosuid',
                'sync', 'nodev', 'uid=%d'%os.geteuid(), 'gid=%d'%os.getegid()]
        try:
            return unicode(d.Mount(
                {
                    'auth.no_user_interaction':True,
                    'options':','.join(mount_options)
                },
                dbus_interface=self.FILESYSTEM))
        except:
            # May be already mounted, check
            mp = node_mountpoint(str(device_node_path))
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

def get_udisks(ver=None):
    if ver is None:
        try:
            u = UDisks2()
        except NoUDisks2:
            u = UDisks()
        return u
    return UDisks2() if ver == 2 else UDisks()

def mount(node_path):
    u = UDisks()
    u.mount(node_path)

def eject(node_path):
    u = UDisks()
    u.eject(node_path)

def umount(node_path):
    u = UDisks()
    u.unmount(node_path)

def test_udisks(ver=None):
    import sys
    dev = sys.argv[1]
    print 'Testing with node', dev
    u = get_udisks(ver=ver)
    print 'Using Udisks:', u.__class__.__name__
    print 'Mounted at:', u.mount(dev)
    print 'Unmounting'
    u.unmount(dev)
    print 'Ejecting:'
    u.eject(dev)

if __name__ == '__main__':
    test_udisks()


