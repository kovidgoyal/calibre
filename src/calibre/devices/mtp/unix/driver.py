#!/usr/bin/env python
# License: GPLv3 Copyright: 2012, Kovid Goyal <kovid at kovidgoyal.net>

import operator
import pprint
import time
import traceback
from collections.abc import Callable, Collection, Iterable, Mapping, Sequence
from functools import partial
from threading import RLock
from typing import IO, TYPE_CHECKING, NamedTuple, cast

from calibre import as_unicode, force_unicode, prints
from calibre.constants import islinux, ismacos
from calibre.devices.errors import BlacklistedDevice, DeviceError, OpenActionNeeded, OpenFailed
from calibre.devices.mtp.base import MTPDeviceBase, debug, synchronous
from calibre.ptempfile import SpooledTemporaryFile
from calibre.utils.localization import _

if TYPE_CHECKING:
    from calibre.devices.interface import DetectedDevice
    from calibre.devices.mtp.filesystem_cache import FileOrFolder, FilesystemCache, MTPEntry
    from calibre.devices.scanner import USBDevice
    from calibre_extensions.libmtp import Device as LibMTPDevice

    #: Called with the device being checked and an optional function used to
    #: output debugging information
    type MTPCheck = Callable[[MTPCandidate, Callable[..., object] | None], bool]
    #: A device as returned by fingerprint() or, when debugging device
    #: detection, as returned by the device scanner
    type MTPCandidate = MTPDevice | USBDevice


class MTPDevice(NamedTuple):
    busnum: int
    devnum: int
    vendor_id: int
    product_id: int
    bcd: int
    serial: str | None
    manufacturer: str | None
    product: str | None


null = object()


def fingerprint(d: USBDevice) -> MTPDevice:
    return MTPDevice(d.busnum, d.devnum, d.vendor_id, d.product_id, d.bcd, d.serial, d.manufacturer, d.product)


def sorted_storage[T: Mapping[str, object]](storage_info: Iterable[T]) -> list[T]:
    storage = sorted(storage_info, key=operator.itemgetter('id'))
    if len(storage) > 1 and storage[0].get('removable', False):
        for i in range(1, len(storage)):
            x = storage[i]
            if not x.get('removable', False):
                storage[0], storage[i] = storage[i], storage[0]
                break
    return storage


APPLE = 0x05AC


class MTP_DEVICE(MTPDeviceBase):
    supported_platforms = ['freebsd', 'linux', 'osx']

    def __init__(self, *args: str | None, **kwargs: str | None) -> None:
        MTPDeviceBase.__init__(self, *args, **kwargs)
        self.libmtp = None
        self.known_devices: frozenset[tuple[int, int]] = frozenset()
        self.detect_cache: dict[MTPCandidate, bool] = {}

        self.dev = None
        self._filesystem_cache: FilesystemCache | None = None
        self.lock = RLock()
        self.blacklisted_devices: set[MTPCandidate] = set()
        self.ejected_devices: set[MTPCandidate] = set()
        self.currently_connected_dev: MTPCandidate | None = None
        self._main_id: int | None = None
        self._carda_id: int | None = None
        self._cardb_id: int | None = None
        self._is_device_mtp: MTPCheck | None = None
        if islinux:
            from calibre.devices.mtp.unix.sysfs import MTPDetect

            self._is_device_mtp = MTPDetect()
        if ismacos and 'osx' in self.supported_platforms:
            from calibre_extensions import usbobserver

            self.usbobserver = usbobserver
            self._is_device_mtp = self.osx_is_device_mtp

    def is_device_mtp(self, d: MTPCandidate, debug: Callable[..., object] | None = None) -> bool:
        """Returns True iff the _is_device_mtp check returns True and libmtp
        is able to probe the device successfully."""
        if self._is_device_mtp is None:
            return False
        libmtp = self.libmtp
        assert libmtp is not None
        return self._is_device_mtp(d, debug) and libmtp.is_mtp_device(d.busnum, d.devnum)

    def osx_is_device_mtp(self, d: MTPCandidate, debug: Callable[..., object] | None = None) -> bool:
        if not d.serial:
            ans = False
        else:
            try:
                ans = self.usbobserver.is_mtp_device(d.vendor_id, d.product_id, d.bcd, d.serial)
            except Exception:
                if debug is not None:
                    import traceback

                    traceback.print_stack()
                return False
        if debug is not None and ans:
            debug(f'Device {d} claims to be an MTP device in the IOKit registry')
        return bool(ans)

    def set_debug_level(self, lvl: int) -> None:
        libmtp = self.libmtp
        assert libmtp is not None
        libmtp.set_debug_level(lvl)

    @synchronous
    def detect_managed_devices(self, devices_on_system: Collection[DetectedDevice], force_refresh: bool = False) -> MTPCandidate | None:
        if self.libmtp is None:
            return None
        # First remove blacklisted devices.
        devs: set[MTPCandidate] = set()
        # The device scanner on non-Windows platforms returns scanner.USBDevice objects
        for d in cast('Collection[USBDevice]', devices_on_system):
            fp = fingerprint(d)
            if fp not in self.blacklisted_devices and fp.vendor_id != APPLE:
                # Do not try to open Apple devices
                devs.add(fp)

        # Clean up ejected devices
        self.ejected_devices = devs.intersection(self.ejected_devices)

        # Check if the currently connected device is still present
        if self.currently_connected_dev is not None:
            return self.currently_connected_dev if self.currently_connected_dev in devs else None

        # Remove ejected devices
        devs = devs - self.ejected_devices

        # Now check for MTP devices
        if force_refresh:
            self.detect_cache = {}
        cache = self.detect_cache
        for d in devs:
            ans = cache.get(d, None)
            if ans is None:
                ans = (d.vendor_id, d.product_id) in self.known_devices or self.is_device_mtp(d)
                cache[d] = ans
            if ans:
                return d

        return None

    @synchronous
    def debug_managed_device_detection(self, devices_on_system: Collection[DetectedDevice], output: IO[str]) -> bool:
        if self.currently_connected_dev is not None:
            return True
        p = partial(prints, file=output)
        if self.libmtp is None:
            err = 'startup() not called on this device driver'
            p(err)
            return False
        devs = [
            d
            for d in cast('Collection[USBDevice]', devices_on_system)
            if ((d.vendor_id, d.product_id) in self.known_devices or self.is_device_mtp(d, debug=p)) and d.vendor_id != APPLE
        ]
        if not devs:
            p('No MTP devices connected to system')
            return False
        p('MTP devices connected:')
        for d in devs:
            p(d)

        for d in devs:
            p('\nTrying to open:', d)
            try:
                self.open(d, 'debug')
            except BlacklistedDevice:
                p('This device has been blacklisted by the user')
                continue
            except Exception:
                p('Opening device failed:')
                p(traceback.format_exc())
                return False
            else:
                p('Opened', self.current_friendly_name, 'successfully')
                p('Storage info:')
                assert self.dev is not None
                p(pprint.pformat(self.dev.storage_info))
                self.post_yank_cleanup()
                return True
        return False

    @synchronous
    def create_device(self, connected_device: MTPCandidate) -> LibMTPDevice:
        d = connected_device
        man, prod = d.manufacturer, d.product
        man = force_unicode(man, 'utf-8') if isinstance(man, bytes) else man
        prod = force_unicode(prod, 'utf-8') if isinstance(prod, bytes) else prod
        libmtp = self.libmtp
        assert libmtp is not None
        # libmtp requires strings for the manufacturer and product
        return libmtp.Device(d.busnum, d.devnum, d.vendor_id, d.product_id, man or '', prod or '', d.serial)

    @synchronous
    def eject(self) -> None:
        if self.currently_connected_dev is None:
            return
        self.ejected_devices.add(self.currently_connected_dev)
        self.post_yank_cleanup()

    @synchronous
    def post_yank_cleanup(self) -> None:
        self.dev = self._filesystem_cache = self.current_friendly_name = None
        self.currently_connected_dev = None
        self.current_serial_num = None

    @property
    def is_mtp_device_connected(self) -> bool:
        return self.currently_connected_dev is not None

    @synchronous
    def startup(self) -> None:
        try:
            from calibre_extensions import libmtp
        except Exception as err:
            print('Failed to load libmtp, MTP device detection disabled')
            print(err)
            self.libmtp = None
        else:
            self.libmtp = libmtp
            self.known_devices = frozenset(self.libmtp.known_devices())

            for x in vars(self.libmtp):
                if x.startswith('LIBMTP'):
                    setattr(self, x, getattr(self.libmtp, x))

    @synchronous
    def shutdown(self) -> None:
        self.dev = self._filesystem_cache = None

    def format_errorstack(self, errs: Iterable[tuple[int, str]]) -> str:
        return '\n'.join(f'{code}:{as_unicode(msg)}' for code, msg in errs)

    @synchronous
    def open(self, connected_device: object, library_uuid: str | None) -> None:
        # connected_device is the device returned by detect_managed_devices()
        connected_device = cast('MTPCandidate', connected_device)
        self.dev = self._filesystem_cache = None

        try:
            self.dev = self.create_device(connected_device)
        except Exception as e:
            self.blacklisted_devices.add(connected_device)
            raise OpenFailed(f'Failed to open {connected_device}: Error: {as_unicode(e)}')

        libmtp = self.libmtp
        assert libmtp is not None
        try:
            storage = sorted_storage(self.dev.storage_info)
        except libmtp.MTPError as e:
            if 'The device has no storage information.' in str(e):
                # This happens on newer Android devices while waiting for
                # the user to allow access. Apparently what happens is
                # that when the user clicks allow, the device disconnects
                # and re-connects as a new device.
                name = self.dev.friendly_name or ''
                if not name:
                    if connected_device.manufacturer:
                        name = connected_device.manufacturer
                    if connected_device.product:
                        name = name and (name + ' ')
                        name += connected_device.product
                    name = name or _('Unnamed device')
                raise OpenActionNeeded(
                    name,
                    _(
                        'The device {0} is not allowing connections.'
                        ' Unlock the screen on the {0}, tap "Allow" on any connection popup message you see,'
                        ' then either wait a minute or restart calibre. You might'
                        ' also have to change the mode of the USB connection on the {0}'
                        ' to "Media Transfer mode (MTP)" or similar.'
                    ).format(name),
                    (name, self.dev.serial_number),
                )
            raise

        storage = [x for x in storage if x.get('rw', False)]
        if not storage:
            self.blacklisted_devices.add(connected_device)
            raise OpenFailed(f'No storage found for device {connected_device}')
        snum = self.dev.serial_number
        if snum in self.prefs.get('blacklist', []):
            self.blacklisted_devices.add(connected_device)
            self.dev = None
            raise BlacklistedDevice(f'The {connected_device} device has been blacklisted by the user')
        self._main_id = cast('int', storage[0]['id'])
        self._carda_id = self._cardb_id = None
        if len(storage) > 1:
            self._carda_id = cast('int', storage[1]['id'])
        if len(storage) > 2:
            self._cardb_id = cast('int', storage[2]['id'])
        self.current_friendly_name = self.dev.friendly_name
        if not self.current_friendly_name:
            self.current_friendly_name = self.dev.model_name or _('Unknown MTP device')
        self.current_serial_num = snum
        self.currently_connected_dev = connected_device

    @synchronous
    def device_debug_info(self) -> str:
        ans = self.get_gui_name()
        ans += f'\nSerial number: {self.current_serial_num}'
        dev = self.dev
        assert dev is not None
        ans += f'\nManufacturer: {dev.manufacturer_name}'
        ans += f'\nModel: {dev.model_name}'
        ans += f'\nids: {dev.ids}'
        ans += f'\nDevice version: {dev.device_version}'
        ans += '\nStorage:\n'
        storage = sorted_storage(dev.storage_info)
        ans += pprint.pformat(storage)
        return ans

    def _filesystem_callback(self, fs_map: dict[object, MTPEntry], entry: MTPEntry, level: int) -> bool:
        name = cast('str', entry.get('name', ''))
        self.filesystem_callback(_('Found object: %s') % name)
        fs_map[entry.get('id', null)] = entry
        path = [name]
        pid = entry.get('parent_id', 0)
        while pid != 0 and pid in fs_map:
            parent = fs_map[pid]
            path.append(cast('str', parent.get('name', '')))
            pid = parent.get('parent_id', 0)
            if fs_map.get(pid, None) is parent:
                break  # An object is its own parent
        rpath = tuple(reversed(path))
        ok = not self.is_folder_ignored(self._currently_getting_sid, rpath)
        if not ok:
            debug('Ignored object: {}'.format('/'.join(rpath)))
        return ok

    @property
    def filesystem_cache(self) -> FilesystemCache:
        if self._filesystem_cache is None:
            st = time.time()
            debug('Loading filesystem metadata...')
            from calibre.devices.mtp.filesystem_cache import FilesystemCache

            with self.lock:
                dev = self.dev
                assert dev is not None
                storage: list[dict[str, object]] = []
                all_items: list[MTPEntry] = []
                all_errs: list[tuple[int, str]] = []
                for sid, capacity in zip([self._main_id, self._carda_id, self._cardb_id], self.total_space()):
                    if sid is None:
                        continue
                    name = _('Unknown')
                    for x in dev.storage_info:
                        if x['id'] == sid:
                            name = x['name']
                            break
                    storage.append({
                        'id': sid,
                        'size': capacity,
                        'is_folder': True,
                        'name': name,
                        'can_delete': False,
                        'is_system': True,
                    })
                    self._currently_getting_sid = str(sid)
                    items, errs = dev.get_filesystem(sid, partial(self._filesystem_callback, {}))
                    all_items.extend(items), all_errs.extend(errs)
                if not all_items and all_errs:
                    raise DeviceError(f'Failed to read filesystem from {self.current_friendly_name} with errors: {self.format_errorstack(all_errs)}')
                if all_errs:
                    prints(f'There were some errors while getting the  filesystem from {self.current_friendly_name}: {self.format_errorstack(all_errs)}')
                self._filesystem_cache = FilesystemCache(storage, all_items)
            debug(f'Filesystem metadata loaded in {time.time() - st:g} seconds ({len(self._filesystem_cache)} objects)')
        return self._filesystem_cache

    @synchronous
    def get_basic_device_information(self) -> tuple[str | None, str | None, str | None, str]:
        d = self.dev
        assert d is not None
        return (self.current_friendly_name, d.device_version, d.device_version, '')

    @synchronous
    def total_space(self, end_session: bool = True) -> tuple[int, int, int]:
        ans = [0, 0, 0]
        assert self.dev is not None
        for s in self.dev.storage_info:
            i = {self._main_id: 0, self._carda_id: 1, self._cardb_id: 2}.get(cast('int', s['id']), None)
            if i is not None:
                ans[i] = cast('int', s['capacity'])
        return ans[0], ans[1], ans[2]

    @synchronous
    def free_space(self, end_session: bool = True) -> tuple[int, int, int]:
        dev = self.dev
        assert dev is not None
        dev.update_storage_info()
        ans = [0, 0, 0]
        for s in dev.storage_info:
            i = {self._main_id: 0, self._carda_id: 1, self._cardb_id: 2}.get(cast('int', s['id']), None)
            if i is not None:
                ans[i] = cast('int', s['freespace_bytes'])
        return ans[0], ans[1], ans[2]

    @synchronous
    def create_folder(self, parent: FileOrFolder, name: str) -> FileOrFolder:
        if not parent.is_folder:
            raise ValueError(f'{parent.full_path} is not a folder')
        e = parent.folder_named(name)
        if e is not None:
            return e
        sid, pid = cast('int', parent.storage_id), cast('int', parent.object_id)
        if pid == sid:
            pid = 0
        assert self.dev is not None
        ans, errs = self.dev.create_folder(sid, pid, name)
        if ans is None:
            raise DeviceError(f'Failed to create folder named {name} in {parent.full_path} with error: {self.format_errorstack(errs)}')
        return parent.add_child(ans)

    @synchronous
    def put_file(
        self,
        parent: FileOrFolder,
        name: str,
        stream: IO[bytes],
        size: int,
        callback: Callable[[int, int], None] | None = None,
        replace: bool = True,
    ) -> FileOrFolder:
        e = parent.folder_named(name)
        if e is not None:
            raise ValueError(f'Cannot upload file, {parent.full_path} already has a folder named: {e.name}')
        e = parent.file_named(name)
        if e is not None:
            if not replace:
                raise ValueError(f'Cannot upload file {e.full_path}, it already exists')
            self.delete_file_or_folder(e)
        sid, pid = cast('int', parent.storage_id), cast('int', parent.object_id)
        if pid == sid:
            pid = 0xFFFFFFFF

        assert self.dev is not None
        ans, errs = self.dev.put_file(sid, pid, name, stream, size, callback)
        if ans is None:
            raise DeviceError(f'Failed to upload file named: {name} to {parent.full_path}: {self.format_errorstack(errs)}')
        return parent.add_child(ans)

    @synchronous
    def get_mtp_file(self, f: FileOrFolder, stream: IO[bytes] | None = None, callback: Callable[[int, int], None] | None = None) -> IO[bytes]:
        if f.is_folder:
            raise ValueError(f'{f.full_path} if a folder')
        set_name = stream is None
        if stream is None:
            stream = SpooledTemporaryFile(5 * 1024 * 1024, '_wpd_receive_file.dat')
        assert self.dev is not None
        ok, errs = self.dev.get_file(cast('int', f.object_id), stream, callback)
        if not ok:
            raise DeviceError(f'Failed to get file: {f.full_path} with errors: {self.format_errorstack(errs)}')
        stream.seek(0)
        if set_name:
            cast('SpooledTemporaryFile', stream).name = f.name
        return stream

    @synchronous
    def list_mtp_folder_by_name(self, parent: FileOrFolder, *names: str) -> Sequence[MTPEntry]:
        if not parent.is_folder:
            raise ValueError(f'{parent.full_path} is not a folder')
        libmtp = self.libmtp
        assert libmtp is not None
        assert self.dev is not None
        parent_id = libmtp.LIBMTP_FILES_AND_FOLDERS_ROOT if parent.is_storage else cast('int', parent.object_id)
        x = self.dev.list_folder_by_name(cast('int', parent.storage_id), parent_id, names)
        if x is None:
            raise FileNotFoundError(f'Could not find folder named: {"/".join(names)} in {parent.full_path}')
        return x

    @synchronous
    def get_mtp_metadata_by_name(self, parent: FileOrFolder, *names: str) -> MTPEntry:
        if not parent.is_folder:
            raise ValueError(f'{parent.full_path} is not a folder')
        libmtp = self.libmtp
        assert libmtp is not None
        assert self.dev is not None
        parent_id = libmtp.LIBMTP_FILES_AND_FOLDERS_ROOT if parent.is_storage else cast('int', parent.object_id)
        x = self.dev.get_metadata_by_name(cast('int', parent.storage_id), parent_id, names)
        if x is None:
            raise DeviceError(f'Could not find file named: {"/".join(names)} in {parent.full_path}')
        m, errs = x
        if not m:
            raise DeviceError(f'Failed to get metadata for: {"/".join(names)} in {parent.full_path} with errors: {self.format_errorstack(errs)}')
        return m

    @synchronous
    def get_mtp_file_by_name(
        self, parent: FileOrFolder, *names: str, stream: IO[bytes] | None = None, callback: Callable[[int, int], None] | None = None
    ) -> IO[bytes]:
        if not parent.is_folder:
            raise ValueError(f'{parent.full_path} is not a folder')
        set_name = stream is None
        if stream is None:
            stream = SpooledTemporaryFile(5 * 1024 * 1024, '_wpd_receive_file.dat')
        libmtp = self.libmtp
        assert libmtp is not None
        assert self.dev is not None
        parent_id = libmtp.LIBMTP_FILES_AND_FOLDERS_ROOT if parent.is_storage else cast('int', parent.object_id)
        x = self.dev.get_file_by_name(cast('int', parent.storage_id), parent_id, names, stream, callback)
        if x is None:
            raise FileNotFoundError(f'Could not find file named: {"/".join(names)} in {parent.full_path}')
        ok, errs = x
        if not ok:
            raise DeviceError(f'Failed to get file: {"/".join(names)} in {parent.full_path} with errors: {self.format_errorstack(errs)}')
        stream.seek(0)
        if set_name:
            cast('SpooledTemporaryFile', stream).name = '/'.join(names)
        return stream

    @synchronous
    def delete_file_or_folder(self, obj: FileOrFolder) -> FileOrFolder | None:
        if obj.deleted:
            return
        if not obj.can_delete:
            raise ValueError(f'Cannot delete {obj.full_path} as deletion not allowed')
        if obj.is_system:
            raise ValueError(f'Cannot delete {obj.full_path} as it is a system object')
        if obj.files or obj.folders:
            raise ValueError(f'Cannot delete {obj.full_path} as it is not empty')
        parent = obj.parent
        assert parent is not None
        assert self.dev is not None
        ok, errs = self.dev.delete_object(cast('int', obj.object_id))
        if not ok:
            raise DeviceError(f'Failed to delete {obj.full_path} with error: {self.format_errorstack(errs)}')
        parent.remove_child(obj)
        return parent
