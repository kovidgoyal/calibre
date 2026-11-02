#!/usr/bin/env python
# License: GPLv3 Copyright: 2012, Kovid Goyal <kovid at kovidgoyal.net>

import os
import threading
import time
import traceback
from functools import partial, wraps
from itertools import chain
from typing import IO, TYPE_CHECKING, Concatenate, Protocol, cast

from calibre import as_unicode, force_unicode, prints
from calibre.constants import __appname__, isxp, numeric_version
from calibre.devices.errors import BlacklistedDevice, DeviceError, OpenFailed
from calibre.devices.mtp.base import MTPDeviceBase, debug
from calibre.ptempfile import SpooledTemporaryFile
from calibre.utils.localization import _

if TYPE_CHECKING:
    from collections.abc import Callable, Collection, Iterable, Sequence

    from calibre.devices.interface import DetectedDevice
    from calibre.devices.mtp.filesystem_cache import FileOrFolder, FilesystemCache, MTPEntry

null = object()


class ThreadingViolation(Exception):
    def __init__(self) -> None:
        Exception.__init__(self, 'You cannot use the MTP driver from a thread other than the  thread in which startup() was called')


class HasStartThread(Protocol):
    @property
    def start_thread(self) -> threading.Thread | None: ...


def same_thread[S: HasStartThread, **P, R](func: Callable[Concatenate[S, P], R]) -> Callable[Concatenate[S, P], R]:
    @wraps(func)
    def check_thread(self: S, *args: P.args, **kwargs: P.kwargs) -> R:
        if self.start_thread is not threading.current_thread():
            raise ThreadingViolation()
        return func(self, *args, **kwargs)

    return check_thread


def sorted_storage(storage_info: Iterable[dict[str, object]]) -> list[dict[str, object]]:
    storage = sorted(storage_info, key=lambda x: cast('str', x.get('id', 'zzzzz')))
    if len(storage) > 1 and 'removable' in cast('str', storage[0].get('type', '')):
        for i in range(1, len(storage)):
            x = storage[i]
            if 'fixed' in cast('str', x.get('type', '')):
                storage[0], storage[i] = storage[i], storage[0]
                break
    return storage


class MTP_DEVICE(MTPDeviceBase):
    supported_platforms = ['windows']

    def __init__(self, *args: str | None, **kwargs: str | None) -> None:
        MTPDeviceBase.__init__(self, *args, **kwargs)
        self.dev = None
        self.blacklisted_devices = set()
        self.ejected_devices = set()
        self.currently_connected_pnp_id: str | None = None
        self.detected_devices: dict[str, dict[str, object] | bool | None] = {}
        self.previous_devices_on_system: frozenset[DetectedDevice] = frozenset()
        self.last_refresh_devices_time = time.time()
        self.wpd = self.wpd_error = None
        self._main_id: str | None = None
        self._carda_id: str | None = None
        self._cardb_id: str | None = None
        self.start_thread: threading.Thread | None = None
        self._filesystem_cache: FilesystemCache | None = None
        self.eject_dev_on_next_scan = False
        self.current_device_data: dict[str, object] = {}

    def startup(self) -> None:
        self.start_thread = threading.current_thread()
        if isxp:
            self.wpd = None
            self.wpd_error = _('MTP devices are not supported on Windows XP')
        else:
            try:
                from calibre_extensions import wpd

                self.wpd = wpd
            except Exception as err:
                self.wpd = None
                self.wpd_error = as_unicode(err)
        if self.wpd is not None:
            try:
                self.wpd.init(__appname__, *(numeric_version[:3]))
            except self.wpd.NoWPD:
                self.wpd_error = _(
                    'The Windows Portable Devices service is not available'
                    ' on your computer. You may need to install Windows'
                    ' Media Player 11 or newer and/or restart your computer'
                )
            except Exception as e:
                self.wpd_error = as_unicode(e)

    @same_thread
    def shutdown(self) -> None:
        self.dev = self._filesystem_cache = self.start_thread = None
        if self.wpd is not None:
            self.wpd.uninit()

    @same_thread
    def detect_managed_devices(self, devices_on_system: Collection[DetectedDevice], force_refresh: bool = False) -> str | None:
        if self.wpd is None:
            return None
        if self.eject_dev_on_next_scan:
            self.eject_dev_on_next_scan = False
            if self.currently_connected_pnp_id is not None:
                self.do_eject()

        current_devices = frozenset(devices_on_system)
        if force_refresh or current_devices != self.previous_devices_on_system or time.time() - self.last_refresh_devices_time > 10:
            self.previous_devices_on_system = current_devices
            self.last_refresh_devices_time = time.time()
            try:
                pnp_ids = frozenset(self.wpd.enumerate_devices())
            except Exception:
                return None

            self.detected_devices = {dev: self.detected_devices.get(dev, None) for dev in pnp_ids}

        # Get device data for detected devices. If there is an error, we will
        # try again for that device the next time this method is called.
        for dev in tuple(self.detected_devices):
            data = self.detected_devices.get(dev, None)
            if data is None or data is False:
                try:
                    data = self.wpd.device_info(dev)
                except Exception as e:
                    prints('Failed to get device info for device:', dev, as_unicode(e))
                    data = {} if data is False else False
                self.detected_devices[dev] = data

        # Remove devices that have been disconnected from ejected
        # devices and blacklisted devices
        self.ejected_devices = set(self.detected_devices).intersection(self.ejected_devices)
        self.blacklisted_devices = set(self.detected_devices).intersection(self.blacklisted_devices)

        if self.currently_connected_pnp_id is not None:
            return self.currently_connected_pnp_id if self.currently_connected_pnp_id in self.detected_devices else None

        for dev, data in self.detected_devices.items():
            if dev in self.blacklisted_devices or dev in self.ejected_devices:
                # Ignore blacklisted and ejected devices
                continue
            if isinstance(data, dict) and data and self.is_suitable_wpd_device(data):
                return dev

        return None

    @same_thread
    def debug_managed_device_detection(self, devices_on_system: Collection[DetectedDevice], output: IO[str]) -> bool:
        import pprint

        p = partial(prints, file=output)
        if self.currently_connected_pnp_id is not None:
            return True
        if self.wpd_error:
            p('Cannot detect MTP devices')
            p(force_unicode(self.wpd_error))
            return False
        wpd = self.wpd
        assert wpd is not None
        try:
            pnp_ids = frozenset(wpd.enumerate_devices())
        except Exception:
            p('Failed to get list of PNP ids on system')
            p(traceback.format_exc())
            return False

        if not pnp_ids:
            p('The Windows WPD service says there are no portable devices connected')
            return False

        p('List of WPD PNP ids:')
        p(pprint.pformat(list(pnp_ids)))

        for pnp_id in pnp_ids:
            try:
                data = wpd.device_info(pnp_id)
            except Exception:
                p('Failed to get data for device:', pnp_id)
                p(traceback.format_exc())
                continue
            protocol = data.get('protocol', '').lower()
            if not protocol.startswith('mtp:'):
                continue
            p('MTP device:', pnp_id)
            p(pprint.pformat(data))
            if not self.is_suitable_wpd_device(data):
                p('Not a suitable MTP device, ignoring\n')
                continue
            p('\nTrying to open:', pnp_id)
            try:
                self.open(pnp_id, 'debug-detection')
            except BlacklistedDevice:
                p('This device has been blacklisted by the user')
                continue
            except Exception:
                p('Open failed:')
                p(traceback.format_exc())
                continue
            break
        if self.currently_connected_pnp_id:  # ty: ignore[redundant-condition]
            p('Opened', self.current_friendly_name, 'successfully')
            p('Device info:')
            p(pprint.pformat(self.dev.data))
            self.post_yank_cleanup()
            return True
        p('No suitable MTP devices found')
        return False

    def is_suitable_wpd_device(self, devdata: dict[str, object]) -> bool:
        # Check that protocol is MTP
        protocol = cast('str', devdata.get('protocol', '')).lower()
        if not protocol.startswith('mtp:'):
            return False

        # Check that the device has some read-write storage
        if not devdata.get('has_storage'):
            return False
        has_rw_storage = False
        for s in cast('list[dict[str, object]]', devdata.get('storage', [])):
            if s.get('filesystem', None) == 'DCF':
                # DCF filesystem indicates a camera or an iPhone
                # See https://bugs.launchpad.net/calibre/+bug/1054562
                continue
            if cast('str', s.get('type', 'unknown_unknown')).split('_')[-1] == 'rom':
                continue  # Read only storage
            if s.get('rw', False):
                has_rw_storage = True
                break
        return has_rw_storage

    def _filesystem_callback(self, fs_map: dict[object, MTPEntry], obj: MTPEntry, level: int) -> bool:
        name = cast('str', obj.get('name', ''))
        self.filesystem_callback(_('Found object: %s') % name)
        if not obj.get('is_folder', False):
            return False
        fs_map[obj.get('id', null)] = obj
        path = [name]
        pid = obj.get('parent_id', 0)
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
            debug('Loading filesystem metadata...')
            st = time.time()
            from calibre.devices.mtp.filesystem_cache import FilesystemCache

            ts = self.total_space()
            dev = self.dev
            assert dev is not None
            all_storage: list[dict[str, object]] = []
            items: list[Iterable[MTPEntry]] = []
            for storage_id, capacity in zip([self._main_id, self._carda_id, self._cardb_id], ts):
                if storage_id is None:
                    continue
                name = _('Unknown')
                for s in dev.data['storage']:
                    if s['id'] == storage_id:
                        name = s['name']
                        break
                storage: dict[str, object] = {
                    'id': storage_id,
                    'size': capacity,
                    'name': name,
                    'is_folder': True,
                    'can_delete': False,
                    'is_system': True,
                }
                self._currently_getting_sid = str(storage_id)
                id_map = dev.get_filesystem(storage_id, partial(self._filesystem_callback, {}))
                for x in id_map.values():
                    x['storage_id'] = storage_id
                all_storage.append(storage)
                items.append(id_map.values())
            self._filesystem_cache = FilesystemCache(all_storage, chain(*items))
            debug(f'Filesystem metadata loaded in {time.time() - st:g} seconds ({len(self._filesystem_cache)} objects)')
        return self._filesystem_cache

    @same_thread
    def do_eject(self) -> None:
        if self.currently_connected_pnp_id is None:
            return
        self.ejected_devices.add(self.currently_connected_pnp_id)
        self.currently_connected_pnp_id = self.current_friendly_name = None
        self._main_id = self._carda_id = self._cardb_id = None
        self.dev = self._filesystem_cache = None

    @same_thread
    def post_yank_cleanup(self) -> None:
        self.currently_connected_pnp_id = self.current_friendly_name = None
        self._main_id = self._carda_id = self._cardb_id = None
        self.dev = self._filesystem_cache = None
        self.current_serial_num = None

    @property
    def is_mtp_device_connected(self) -> bool:
        return self.currently_connected_pnp_id is not None

    def eject(self) -> None:
        if self.currently_connected_pnp_id is None:
            return
        self.eject_dev_on_next_scan = True
        self.current_serial_num = None

    @same_thread
    def open(self, connected_device: object, library_uuid: str | None) -> None:
        # connected_device is the PnP id returned by detect_managed_devices()
        pnp_id = cast('str', connected_device)
        self.dev = self._filesystem_cache = None
        wpd = self.wpd
        assert wpd is not None
        try:
            self.dev = wpd.Device(pnp_id)
        except wpd.WPDError:
            time.sleep(2)
            try:
                self.dev = wpd.Device(pnp_id)
            except wpd.WPDError as e:
                self.blacklisted_devices.add(pnp_id)
                raise OpenFailed(f'Failed to open {pnp_id} with error: {as_unicode(e)}')
        devdata = self.dev.data
        storage = sorted_storage([s for s in devdata.get('storage', []) if s.get('rw', False)])
        if not storage:
            self.blacklisted_devices.add(pnp_id)
            raise OpenFailed(f'No storage found for device {pnp_id}')
        snum = devdata.get('serial_number', None)
        if snum in self.prefs.get('blacklist', []):
            self.blacklisted_devices.add(pnp_id)
            self.dev = None
            raise BlacklistedDevice(f'The {pnp_id} device has been blacklisted by the user')

        self._main_id = cast('str', storage[0]['id'])
        if len(storage) > 1:
            self._carda_id = cast('str', storage[1]['id'])
        if len(storage) > 2:
            self._cardb_id = cast('str', storage[2]['id'])
        self.current_friendly_name = devdata.get('friendly_name', '')
        if not self.current_friendly_name:
            self.current_friendly_name = devdata.get('model_name', _('Unknown MTP device'))
        self.currently_connected_pnp_id = pnp_id
        self.current_serial_num = snum
        self.current_device_data = devdata.copy()

    def device_debug_info(self) -> str:
        import pprint

        return pprint.pformat(self.current_device_data)

    @same_thread
    def get_basic_device_information(self) -> tuple[str | None, str, str, str]:
        dev = self.dev
        assert dev is not None
        d = dev.data
        dv = d.get('device_version', '')
        return (self.current_friendly_name, dv, dv, '')

    @same_thread
    def total_space(self, end_session: bool = True) -> tuple[int, int, int]:
        ans = [0, 0, 0]
        dev = self.dev
        assert dev is not None
        dd = dev.data
        for s in dd.get('storage', []):
            i = {self._main_id: 0, self._carda_id: 1, self._cardb_id: 2}.get(s.get('id', -1), None)
            if i is not None:
                ans[i] = s['capacity']
        return ans[0], ans[1], ans[2]

    @same_thread
    def free_space(self, end_session: bool = True) -> tuple[int, int, int]:
        dev = self.dev
        assert dev is not None
        dev.update_data()
        ans = [0, 0, 0]
        dd = dev.data
        for s in dd.get('storage', []):
            i = {self._main_id: 0, self._carda_id: 1, self._cardb_id: 2}.get(s.get('id', -1), None)
            if i is not None:
                ans[i] = s['free_space']
        return ans[0], ans[1], ans[2]

    @same_thread
    def list_mtp_folder_by_name(self, parent: FileOrFolder, *names: str) -> Sequence[MTPEntry]:
        if not parent.is_folder:
            raise ValueError(f'{parent.full_path} is not a folder')
        dev = self.dev
        assert dev is not None
        x = dev.list_folder_by_name(cast('str', parent.object_id), names)
        if x is None:
            raise FileNotFoundError(f'Could not find folder named: {"/".join(names)} in {parent.full_path}')
        return list(x.values())

    @same_thread
    def get_mtp_metadata_by_name(self, parent: FileOrFolder, *names: str) -> MTPEntry:
        if not parent.is_folder:
            raise ValueError(f'{parent.full_path} is not a folder')
        dev = self.dev
        assert dev is not None
        x = dev.get_metadata_by_name(cast('str', parent.object_id), names)
        if x is None:
            raise DeviceError(f'Could not find folder named: {"/".join(names)} in {parent.full_path}')
        return x

    @same_thread
    def get_mtp_file_by_name(
        self, parent: FileOrFolder, *names: str, stream: IO[bytes] | None = None, callback: Callable[[int, int], None] | None = None
    ) -> IO[bytes]:
        if not parent.is_folder:
            raise ValueError(f'{parent.full_path} is not a folder')
        set_name = stream is None
        if stream is None:
            stream = SpooledTemporaryFile(5 * 1024 * 1024, '_wpd_receive_file.dat')
        dev = self.dev
        assert dev is not None
        wpd = self.wpd
        assert wpd is not None
        parent_id = cast('str', parent.object_id)
        try:
            try:
                dev.get_file_by_name(parent_id, names, stream, callback)
            except wpd.WPDFileBusy:
                time.sleep(2)
                dev.get_file_by_name(parent_id, names, stream, callback)
        except KeyError as e:
            raise FileNotFoundError(f'Failed to find the file {os.sep.join(names)} in {parent.full_path}') from e
        except Exception as e:
            raise DeviceError(f'Failed to fetch the file {os.sep.join(names)} in {parent.full_path} with error: {as_unicode(e)}')
        stream.seek(0)
        if set_name:
            cast('SpooledTemporaryFile', stream).name = '/'.join(names)
        return stream

    @same_thread
    def get_mtp_file(self, f: FileOrFolder, stream: IO[bytes] | None = None, callback: Callable[[int, int], None] | None = None) -> IO[bytes]:
        if f.is_folder:
            raise ValueError(f'{f.full_path} if a folder')
        set_name = stream is None
        if stream is None:
            stream = SpooledTemporaryFile(5 * 1024 * 1024, '_wpd_receive_file.dat')
        dev = self.dev
        assert dev is not None
        wpd = self.wpd
        assert wpd is not None
        object_id = cast('str', f.object_id)
        try:
            try:
                dev.get_file(object_id, stream, callback)
            except wpd.WPDFileBusy:
                time.sleep(2)
                dev.get_file(object_id, stream, callback)
        except Exception as e:
            raise DeviceError(f'Failed to fetch the file {f.full_path} with error: {as_unicode(e)}')
        stream.seek(0)
        if set_name:
            cast('SpooledTemporaryFile', stream).name = f.name
        return stream

    @same_thread
    def create_folder(self, parent: FileOrFolder, name: str) -> FileOrFolder:
        if not parent.is_folder:
            raise ValueError(f'{parent.full_path} is not a folder')
        e = parent.folder_named(name)
        if e is not None:
            return e
        dev = self.dev
        assert dev is not None
        try:
            ans = dev.create_folder(cast('str', parent.object_id), name)
        except Exception as err:
            raise OSError(f'Failed to create the folder: {name} in {parent.full_path} with error: {err}') from err
        ans['storage_id'] = parent.storage_id
        return parent.add_child(ans)

    @same_thread
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
        dev = self.dev
        assert dev is not None
        dev.delete_object(cast('str', obj.object_id))
        parent.remove_child(obj)
        return parent

    @same_thread
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
        sid, pid = parent.storage_id, parent.object_id
        dev = self.dev
        assert dev is not None
        ans = dev.put_file(cast('str', pid), name, stream, size, callback)
        ans['storage_id'] = sid
        return parent.add_child(ans)
