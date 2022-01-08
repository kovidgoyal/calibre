#!/usr/bin/env python


__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os
import re
from contextlib import suppress


def node_mountpoint(node):

    if isinstance(node, str):
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


class UDisks:

    BUS_NAME = 'org.freedesktop.UDisks2'
    BLOCK = f'{BUS_NAME}.Block'
    FILESYSTEM = f'{BUS_NAME}.Filesystem'
    DRIVE = f'{BUS_NAME}.Drive'
    PATH = '/org/freedesktop/UDisks2'

    def __enter__(self):
        from jeepney.io.blocking import open_dbus_connection
        self.connection = open_dbus_connection(bus='SYSTEM')
        return self

    def __exit__(self, *args):
        self.connection.close()
        del self.connection

    def address(self, path='', interface=None):
        from jeepney import DBusAddress
        path = os.path.join(self.PATH, path)
        return DBusAddress(path, bus_name=self.BUS_NAME, interface=interface)

    def send(self, msg):
        from jeepney import DBusErrorResponse, MessageType
        reply = self.connection.send_and_get_reply(msg)
        if reply.header.message_type is MessageType.error:
            raise DBusErrorResponse(reply)
        return reply

    def introspect(self, object_path):
        from jeepney import Introspectable
        r = self.send(Introspectable(f'{self.PATH}/{object_path}', self.BUS_NAME).Introspect())
        return r.body[0]

    def get_device_node_path(self, devname):
        from jeepney import Properties
        p = Properties(self.address(f'block_devices/{devname}', self.BLOCK))
        r = self.send(p.get('Device'))
        return bytearray(r.body[0][1]).replace(b'\x00', b'').decode('utf-8')

    def iter_block_devices(self):
        xml = self.introspect('block_devices')
        for m in re.finditer(r'name=[\'"](.+?)[\'"]', xml):
            devname = m.group(1)
            with suppress(Exception):
                yield devname, self.get_device_node_path(devname)

    def device(self, device_node_path):
        device_node_path = os.path.realpath(device_node_path)
        devname = device_node_path.split('/')[-1]
        # First try the device name directly
        with suppress(Exception):
            if self.get_device_node_path(devname) == device_node_path:
                return devname
        # Enumerate all devices known to UDisks
        for q, devpath in self.iter_block_devices():
            if devpath == device_node_path:
                return q
        raise KeyError(f'{device_node_path} not known to UDisks2')

    def filesystem_operation_message(self, device_node_path, function_name, **kw):
        from jeepney import new_method_call
        devname = self.device(device_node_path)
        a = self.address(f'block_devices/{devname}', self.FILESYSTEM)
        kw['auth.no_user_interaction'] = ('b', True)
        return new_method_call(a, function_name, 'a{sv}', (kw,))

    def mount(self, device_node_path):
        msg = self.filesystem_operation_message(device_node_path, 'Mount', options=('s', ','.join(basic_mount_options())))
        try:
            self.send(msg)
        except Exception:
            # May be already mounted, check
            mp = node_mountpoint(str(device_node_path))
            if mp is None:
                raise
            return mp

    def unmount(self, device_node_path):
        msg = self.filesystem_operation_message(device_node_path, 'Unmount', force=('b', True))
        self.send(msg)

    def drive_for_device(self, device_node_path):
        from jeepney import Properties
        devname = self.device(device_node_path)
        a = self.address(f'block_devices/{devname}', self.BLOCK)
        msg = Properties(a).get('Drive')
        r = self.send(msg)
        return r.body[0][1]

    def eject(self, device_node_path):
        from jeepney import new_method_call
        drive = self.drive_for_device(device_node_path)
        a = self.address(drive, self.DRIVE)
        msg = new_method_call(a, 'Eject', 'a{sv}', ({
            'auth.no_user_interaction': ('b', True),
        },))
        self.send(msg)


def get_udisks():
    return UDisks()


def mount(node_path):
    with get_udisks() as u:
        u.mount(node_path)


def eject(node_path):
    with get_udisks() as u:
        u.eject(node_path)


def umount(node_path):
    with get_udisks() as u:
        u.unmount(node_path)


def test_udisks():
    import sys
    dev = sys.argv[1]
    print('Testing with node', dev)
    with get_udisks() as u:
        print('Using Udisks:', u.__class__.__name__)
        print('Mounted at:', u.mount(dev))
        print('Unmounting')
        u.unmount(dev)
        print('Ejecting:')
        u.eject(dev)


def develop():
    dev = '/dev/nvme0n1p3'
    with get_udisks() as u:
        print(u.device(dev))
        print(u.drive_for_device(dev))


if __name__ == '__main__':
    test_udisks()
