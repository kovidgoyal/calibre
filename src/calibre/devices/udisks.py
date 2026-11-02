#!/usr/bin/env python
# License: GPLv3 Copyright: 2010, Kovid Goyal <kovid@kovidgoyal.net>

import json
import os
import re
import subprocess
from contextlib import suppress
from typing import TYPE_CHECKING, Self

from calibre.constants import isfreebsd

if TYPE_CHECKING:
    from collections.abc import Iterator

    from jeepney import DBusAddress, Message
    from jeepney.io.blocking import DBusConnection


def node_mountpoint(node: str | bytes) -> str | None:

    if isinstance(node, str):
        node = node.encode('utf-8')

    def de_mangle(raw: bytes) -> str:
        return raw.replace(b'\\040', b' ').replace(b'\\011', b'\t').replace(b'\\012', b'\n').replace(b'\\0134', b'\\').decode('utf-8')

    if isfreebsd:
        cmd = subprocess.run(['mount', '-p', '--libxo', 'json'], capture_output=True, encoding='UTF-8')
        stdout = json.loads(cmd.stdout)
        for row in stdout['mount']['fstab']:
            if row['device'].encode('utf-8') == node:
                return de_mangle(row['mntpoint'].encode('utf-8'))
    else:
        with open('/proc/mounts', 'rb') as src:
            for line in src:
                line = line.split()
                if line[0] == node:
                    return de_mangle(line[1])
    return None


def basic_mount_options() -> list[str]:
    return ['rw', 'noexec', 'nosuid', 'nodev', f'uid={os.geteuid()}', f'gid={os.getegid()}']


class UDisks:
    BUS_NAME = 'org.freedesktop.UDisks2'
    BLOCK = f'{BUS_NAME}.Block'
    FILESYSTEM = f'{BUS_NAME}.Filesystem'
    DRIVE = f'{BUS_NAME}.Drive'
    OBJECTMANAGER = 'org.freedesktop.DBus.ObjectManager'
    PATH = '/org/freedesktop/UDisks2'
    connection: DBusConnection

    def __enter__(self) -> Self:
        from jeepney.io.blocking import open_dbus_connection

        self.connection = open_dbus_connection(bus='SYSTEM')
        return self

    def __exit__(self, *args: object) -> None:
        self.connection.close()
        del self.connection

    def address(self, path: str = '', interface: str | None = None) -> DBusAddress:
        from jeepney import DBusAddress

        path = os.path.join(self.PATH, path)
        return DBusAddress(path, bus_name=self.BUS_NAME, interface=interface)

    def send(self, msg: Message) -> Message:
        from jeepney import DBusErrorResponse, MessageType

        reply = self.connection.send_and_get_reply(msg)
        if reply.header.message_type is MessageType.error:
            raise DBusErrorResponse(reply)
        return reply

    def introspect(self, object_path: str) -> str:
        from jeepney import Introspectable

        r = self.send(Introspectable(f'{self.PATH}/{object_path}', self.BUS_NAME).Introspect())
        return r.body[0]

    def get_device_node_path(self, devname: str) -> str:
        from jeepney import Properties

        p = Properties(self.address(f'block_devices/{devname}', self.BLOCK))
        r = self.send(p.get('Device'))
        return bytearray(r.body[0][1]).replace(b'\x00', b'').decode('utf-8')

    def iter_block_devices(self) -> Iterator[tuple[str, str]]:
        xml = self.introspect('block_devices')
        for m in re.finditer(r'name=[\'"](.+?)[\'"]', xml):
            devname = m.group(1)
            with suppress(Exception):
                yield devname, self.get_device_node_path(devname)

    def find_device_vols_by_serial(self, serial: str) -> list[dict[str, str]]:
        from jeepney import DBusAddress, new_method_call

        drives: list[str] = []
        blocks = []
        vols: list[dict[str, str]] = []
        a = DBusAddress(self.PATH, bus_name=self.BUS_NAME, interface=self.OBJECTMANAGER)
        msg = new_method_call(a, 'GetManagedObjects')
        r = self.send(msg)
        for k, v in r.body[0].items():
            if os.path.join(self.PATH, '/block_devices') in k:
                blocks.append({'k': k, 'v': v.get(f'{self.BUS_NAME}.Block', {})})
            if os.path.join(self.PATH, '/drives') in k:
                drive = v.get(f'{self.BUS_NAME}.Drive', {})
                if drive.get('ConnectionBus')[1] == 'usb' and drive.get('Removable')[1] and drive.get('Serial')[1] == serial:
                    drives.append(k)
        for block in blocks:
            if block['v']['Drive'][1] in drives:
                vols.append({
                    'Block': block['k'],
                    'Device': block['v']['Device'][1].decode('ascii').strip('\x00'),
                })
        return vols

    def device(self, device_node_path: str) -> str:
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

    def filesystem_operation_message(self, device_node_path: str, function_name: str, **kw: tuple[str, object]) -> Message:
        from jeepney import new_method_call

        devname = self.device(device_node_path)
        a = self.address(f'block_devices/{devname}', self.FILESYSTEM)
        kw['auth.no_user_interaction'] = ('b', True)
        return new_method_call(a, function_name, 'a{sv}', (kw,))

    def mount(self, device_node_path: str) -> str:
        msg = self.filesystem_operation_message(device_node_path, 'Mount', options=('s', ','.join(basic_mount_options())))
        try:
            r = self.send(msg)
            return r.body[0]
        except Exception:
            # May be already mounted, check
            mp = node_mountpoint(str(device_node_path))
            if mp is None:
                raise
            return mp

    def unmount(self, device_node_path: str) -> None:
        msg = self.filesystem_operation_message(device_node_path, 'Unmount', force=('b', True))
        self.send(msg)

    def drive_for_device(self, device_node_path: str) -> str:
        from jeepney import Properties

        devname = self.device(device_node_path)
        a = self.address(f'block_devices/{devname}', self.BLOCK)
        msg = Properties(a).get('Drive')
        r = self.send(msg)
        return r.body[0][1]

    def eject(self, device_node_path: str) -> None:
        from jeepney import new_method_call

        drive = self.drive_for_device(device_node_path)
        a = self.address(drive, self.DRIVE)
        msg = new_method_call(
            a,
            'Eject',
            'a{sv}',
            (
                {
                    'auth.no_user_interaction': ('b', True),
                },
            ),
        )
        self.send(msg)

    def rescan(self, device_node_path: str) -> None:
        from jeepney import new_method_call

        devname = self.device(device_node_path)
        a = self.address(f'block_devices/{devname}', self.BLOCK)
        msg = new_method_call(
            a,
            'Rescan',
            'a{sv}',
            (
                {
                    'auth.no_user_interaction': ('b', True),
                },
            ),
        )
        self.send(msg)


def get_udisks() -> UDisks:
    return UDisks()


def mount(node_path: str) -> str:
    with get_udisks() as u:
        return u.mount(node_path)


def eject(node_path: str) -> None:
    with get_udisks() as u:
        u.eject(node_path)


def umount(node_path: str) -> None:
    with get_udisks() as u:
        u.unmount(node_path)


def rescan(node_path: str) -> None:
    with get_udisks() as u:
        u.rescan(node_path)


def find_device_vols_by_serial(serial: str) -> list[dict[str, str]]:
    with get_udisks() as u:
        return u.find_device_vols_by_serial(serial)


def test_udisks() -> None:
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


def develop() -> None:
    dev = '/dev/nvme0n1p3'
    with get_udisks() as u:
        print(u.device(dev))
        print(u.drive_for_device(dev))


if __name__ == '__main__':
    test_udisks()
