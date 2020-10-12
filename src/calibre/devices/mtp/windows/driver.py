#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai


__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import time, threading, traceback
from functools import wraps, partial
from polyglot.builtins import iteritems, itervalues, unicode_type, zip
from itertools import chain

from calibre import as_unicode, prints, force_unicode
from calibre.constants import plugins, __appname__, numeric_version, isxp
from calibre.ptempfile import SpooledTemporaryFile
from calibre.devices.errors import OpenFailed, DeviceError, BlacklistedDevice
from calibre.devices.mtp.base import MTPDeviceBase, debug

null = object()


class ThreadingViolation(Exception):

    def __init__(self):
        Exception.__init__(self,
                'You cannot use the MTP driver from a thread other than the '
                ' thread in which startup() was called')


def same_thread(func):
    @wraps(func)
    def check_thread(self, *args, **kwargs):
        if self.start_thread is not threading.current_thread():
            raise ThreadingViolation()
        return func(self, *args, **kwargs)
    return check_thread


class MTP_DEVICE(MTPDeviceBase):

    supported_platforms = ['windows']

    def __init__(self, *args, **kwargs):
        MTPDeviceBase.__init__(self, *args, **kwargs)
        self.dev = None
        self.blacklisted_devices = set()
        self.ejected_devices = set()
        self.currently_connected_pnp_id = None
        self.detected_devices = {}
        self.previous_devices_on_system = frozenset()
        self.last_refresh_devices_time = time.time()
        self.wpd = self.wpd_error = None
        self._main_id = self._carda_id = self._cardb_id = None
        self.start_thread = None
        self._filesystem_cache = None
        self.eject_dev_on_next_scan = False
        self.current_device_data = {}

    def startup(self):
        self.start_thread = threading.current_thread()
        if isxp:
            self.wpd = None
            self.wpd_error = _('MTP devices are not supported on Windows XP')
        else:
            self.wpd, self.wpd_error = plugins['wpd']
        if self.wpd is not None:
            try:
                self.wpd.init(__appname__, *(numeric_version[:3]))
            except self.wpd.NoWPD:
                self.wpd_error = _(
                    'The Windows Portable Devices service is not available'
                    ' on your computer. You may need to install Windows'
                    ' Media Player 11 or newer and/or restart your computer')
            except Exception as e:
                self.wpd_error = as_unicode(e)

    @same_thread
    def shutdown(self):
        self.dev = self._filesystem_cache = self.start_thread = None
        if self.wpd is not None:
            self.wpd.uninit()

    @same_thread
    def detect_managed_devices(self, devices_on_system, force_refresh=False):
        if self.wpd is None:
            return None
        if self.eject_dev_on_next_scan:
            self.eject_dev_on_next_scan = False
            if self.currently_connected_pnp_id is not None:
                self.do_eject()

        devices_on_system = frozenset(devices_on_system)
        if (force_refresh or
                devices_on_system != self.previous_devices_on_system or
                time.time() - self.last_refresh_devices_time > 10):
            self.previous_devices_on_system = devices_on_system
            self.last_refresh_devices_time = time.time()
            try:
                pnp_ids = frozenset(self.wpd.enumerate_devices())
            except:
                return None

            self.detected_devices = {dev:self.detected_devices.get(dev, None)
                    for dev in pnp_ids}

        # Get device data for detected devices. If there is an error, we will
        # try again for that device the next time this method is called.
        for dev in tuple(self.detected_devices):
            data = self.detected_devices.get(dev, None)
            if data is None or data is False:
                try:
                    data = self.wpd.device_info(dev)
                except Exception as e:
                    prints('Failed to get device info for device:', dev,
                            as_unicode(e))
                    data = {} if data is False else False
                self.detected_devices[dev] = data

        # Remove devices that have been disconnected from ejected
        # devices and blacklisted devices
        self.ejected_devices = set(self.detected_devices).intersection(
                self.ejected_devices)
        self.blacklisted_devices = set(self.detected_devices).intersection(
                self.blacklisted_devices)

        if self.currently_connected_pnp_id is not None:
            return (self.currently_connected_pnp_id if
                    self.currently_connected_pnp_id in self.detected_devices
                    else None)

        for dev, data in iteritems(self.detected_devices):
            if dev in self.blacklisted_devices or dev in self.ejected_devices:
                # Ignore blacklisted and ejected devices
                continue
            if data and self.is_suitable_wpd_device(data):
                return dev

        return None

    @same_thread
    def debug_managed_device_detection(self, devices_on_system, output):
        import pprint
        p = partial(prints, file=output)
        if self.currently_connected_pnp_id is not None:
            return True
        if self.wpd_error:
            p('Cannot detect MTP devices')
            p(force_unicode(self.wpd_error))
            return False
        try:
            pnp_ids = frozenset(self.wpd.enumerate_devices())
        except:
            p("Failed to get list of PNP ids on system")
            p(traceback.format_exc())
            return False

        if not pnp_ids:
            p('The Windows WPD service says there are no portable devices connected')
            return False

        p('List of WPD PNP ids:')
        p(pprint.pformat(list(pnp_ids)))

        for pnp_id in pnp_ids:
            try:
                data = self.wpd.device_info(pnp_id)
            except:
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
            except:
                p('Open failed:')
                p(traceback.format_exc())
                continue
            break
        if self.currently_connected_pnp_id:
            p('Opened', self.current_friendly_name, 'successfully')
            p('Device info:')
            p(pprint.pformat(self.dev.data))
            self.post_yank_cleanup()
            return True
        p('No suitable MTP devices found')
        return False

    def is_suitable_wpd_device(self, devdata):
        # Check that protocol is MTP
        protocol = devdata.get('protocol', '').lower()
        if not protocol.startswith('mtp:'):
            return False

        # Check that the device has some read-write storage
        if not devdata.get('has_storage', False):
            return False
        has_rw_storage = False
        for s in devdata.get('storage', []):
            if s.get('filesystem', None) == 'DCF':
                # DCF filesystem indicates a camera or an iPhone
                # See https://bugs.launchpad.net/calibre/+bug/1054562
                continue
            if s.get('type', 'unknown_unknown').split('_')[-1] == 'rom':
                continue  # Read only storage
            if s.get('rw', False):
                has_rw_storage = True
                break
        if not has_rw_storage:
            return False

        return True

    def _filesystem_callback(self, fs_map, obj, level):
        name = obj.get('name', '')
        self.filesystem_callback(_('Found object: %s')%name)
        if not obj.get('is_folder', False):
            return False
        fs_map[obj.get('id', null)] = obj
        path = [name]
        pid = obj.get('parent_id', 0)
        while pid != 0 and pid in fs_map:
            parent = fs_map[pid]
            path.append(parent.get('name', ''))
            pid = parent.get('parent_id', 0)
            if fs_map.get(pid, None) is parent:
                break  # An object is its own parent

        path = tuple(reversed(path))
        ok = not self.is_folder_ignored(self._currently_getting_sid, path)
        if not ok:
            debug('Ignored object: %s' % '/'.join(path))
        return ok

    @property
    def filesystem_cache(self):
        if self._filesystem_cache is None:
            debug('Loading filesystem metadata...')
            st = time.time()
            from calibre.devices.mtp.filesystem_cache import FilesystemCache
            ts = self.total_space()
            all_storage = []
            items = []
            for storage_id, capacity in zip([self._main_id, self._carda_id,
                self._cardb_id], ts):
                if storage_id is None:
                    continue
                name = _('Unknown')
                for s in self.dev.data['storage']:
                    if s['id'] == storage_id:
                        name = s['name']
                        break
                storage = {'id':storage_id, 'size':capacity, 'name':name,
                        'is_folder':True, 'can_delete':False, 'is_system':True}
                self._currently_getting_sid = unicode_type(storage_id)
                id_map = self.dev.get_filesystem(storage_id, partial(
                        self._filesystem_callback, {}))
                for x in itervalues(id_map):
                    x['storage_id'] = storage_id
                all_storage.append(storage)
                items.append(itervalues(id_map))
            self._filesystem_cache = FilesystemCache(all_storage, chain(*items))
            debug('Filesystem metadata loaded in %g seconds (%d objects)'%(
                time.time()-st, len(self._filesystem_cache)))
        return self._filesystem_cache

    @same_thread
    def do_eject(self):
        if self.currently_connected_pnp_id is None:
            return
        self.ejected_devices.add(self.currently_connected_pnp_id)
        self.currently_connected_pnp_id = self.current_friendly_name = None
        self._main_id = self._carda_id = self._cardb_id = None
        self.dev = self._filesystem_cache = None

    @same_thread
    def post_yank_cleanup(self):
        self.currently_connected_pnp_id = self.current_friendly_name = None
        self._main_id = self._carda_id = self._cardb_id = None
        self.dev = self._filesystem_cache = None
        self.current_serial_num = None

    @property
    def is_mtp_device_connected(self):
        return self.currently_connected_pnp_id is not None

    def eject(self):
        if self.currently_connected_pnp_id is None:
            return
        self.eject_dev_on_next_scan = True
        self.current_serial_num = None

    @same_thread
    def open(self, connected_device, library_uuid):
        self.dev = self._filesystem_cache = None
        try:
            self.dev = self.wpd.Device(connected_device)
        except self.wpd.WPDError:
            time.sleep(2)
            try:
                self.dev = self.wpd.Device(connected_device)
            except self.wpd.WPDError as e:
                self.blacklisted_devices.add(connected_device)
                raise OpenFailed('Failed to open %s with error: %s'%(
                    connected_device, as_unicode(e)))
        devdata = self.dev.data
        storage = [s for s in devdata.get('storage', []) if s.get('rw', False)]
        if not storage:
            self.blacklisted_devices.add(connected_device)
            raise OpenFailed('No storage found for device %s'%(connected_device,))
        snum = devdata.get('serial_number', None)
        if snum in self.prefs.get('blacklist', []):
            self.blacklisted_devices.add(connected_device)
            self.dev = None
            raise BlacklistedDevice(
                'The %s device has been blacklisted by the user'%(connected_device,))

        storage.sort(key=lambda x:x.get('id', 'zzzzz'))

        self._main_id = storage[0]['id']
        if len(storage) > 1:
            self._carda_id = storage[1]['id']
        if len(storage) > 2:
            self._cardb_id = storage[2]['id']
        self.current_friendly_name = devdata.get('friendly_name', '')
        if not self.current_friendly_name:
            self.current_friendly_name = devdata.get('model_name',
                _('Unknown MTP device'))
        self.currently_connected_pnp_id = connected_device
        self.current_serial_num = snum
        self.current_device_data = devdata.copy()

    def device_debug_info(self):
        import pprint
        return pprint.pformat(self.current_device_data)

    @same_thread
    def get_basic_device_information(self):
        d = self.dev.data
        dv = d.get('device_version', '')
        return (self.current_friendly_name, dv, dv, '')

    @same_thread
    def total_space(self, end_session=True):
        ans = [0, 0, 0]
        dd = self.dev.data
        for s in dd.get('storage', []):
            i = {self._main_id:0, self._carda_id:1,
                    self._cardb_id:2}.get(s.get('id', -1), None)
            if i is not None:
                ans[i] = s['capacity']
        return tuple(ans)

    @same_thread
    def free_space(self, end_session=True):
        self.dev.update_data()
        ans = [0, 0, 0]
        dd = self.dev.data
        for s in dd.get('storage', []):
            i = {self._main_id:0, self._carda_id:1,
                    self._cardb_id:2}.get(s.get('id', -1), None)
            if i is not None:
                ans[i] = s['free_space']
        return tuple(ans)

    @same_thread
    def get_mtp_file(self, f, stream=None, callback=None):
        if f.is_folder:
            raise ValueError('%s if a folder'%(f.full_path,))
        set_name = stream is None
        if stream is None:
            stream = SpooledTemporaryFile(5*1024*1024, '_wpd_receive_file.dat')
        try:
            try:
                self.dev.get_file(f.object_id, stream, callback)
            except self.wpd.WPDFileBusy:
                time.sleep(2)
                self.dev.get_file(f.object_id, stream, callback)
        except Exception as e:
            raise DeviceError('Failed to fetch the file %s with error: %s'%
                    (f.full_path, as_unicode(e)))
        stream.seek(0)
        if set_name:
            stream.name = f.name
        return stream

    @same_thread
    def create_folder(self, parent, name):
        if not parent.is_folder:
            raise ValueError('%s is not a folder'%(parent.full_path,))
        e = parent.folder_named(name)
        if e is not None:
            return e
        ans = self.dev.create_folder(parent.object_id, name)
        ans['storage_id'] = parent.storage_id
        return parent.add_child(ans)

    @same_thread
    def delete_file_or_folder(self, obj):
        if obj.deleted:
            return
        if not obj.can_delete:
            raise ValueError('Cannot delete %s as deletion not allowed'%
                    (obj.full_path,))
        if obj.is_system:
            raise ValueError('Cannot delete %s as it is a system object'%
                    (obj.full_path,))
        if obj.files or obj.folders:
            raise ValueError('Cannot delete %s as it is not empty'%
                    (obj.full_path,))
        parent = obj.parent
        self.dev.delete_object(obj.object_id)
        parent.remove_child(obj)
        return parent

    @same_thread
    def put_file(self, parent, name, stream, size, callback=None, replace=True):
        e = parent.folder_named(name)
        if e is not None:
            raise ValueError('Cannot upload file, %s already has a folder named: %s'%(
                parent.full_path, e.name))
        e = parent.file_named(name)
        if e is not None:
            if not replace:
                raise ValueError('Cannot upload file %s, it already exists'%(
                    e.full_path,))
            self.delete_file_or_folder(e)
        sid, pid = parent.storage_id, parent.object_id
        ans = self.dev.put_file(pid, name, stream, size, callback)
        ans['storage_id'] = sid
        return parent.add_child(ans)
