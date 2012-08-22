#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import time, threading
from functools import wraps
from future_builtins import zip
from itertools import chain

from calibre import as_unicode, prints
from calibre.constants import plugins, __appname__, numeric_version
from calibre.ptempfile import SpooledTemporaryFile
from calibre.devices.errors import OpenFailed
from calibre.devices.mtp.base import MTPDeviceBase
from calibre.devices.mtp.filesystem_cache import FilesystemCache

class ThreadingViolation(Exception):

    def __init__(self):
        Exception.__init__('You cannot use the MTP driver from a thread other than the '
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

    def startup(self):
        self.start_thread = threading.current_thread()
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
    def detect_managed_devices(self, devices_on_system):
        if self.wpd is None: return None

        devices_on_system = frozenset(devices_on_system)
        if (devices_on_system != self.previous_devices_on_system or time.time()
                - self.last_refresh_devices_time > 10):
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
        for dev in tuple(self.detected_devices.iterkeys()):
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

        for dev, data in self.detected_devices.iteritems():
            if dev in self.blacklisted_devices or dev in self.ejected_devices:
                # Ignore blacklisted and ejected devices
                continue
            if data and self.is_suitable_wpd_device(data):
                return dev

        return None

    def is_suitable_wpd_device(self, devdata):
        # Check that protocol is MTP
        protocol = devdata.get('protocol', '').lower()
        if not protocol.startswith('mtp:'): return False

        # Check that the device has some read-write storage
        if not devdata.get('has_storage', False): return False
        has_rw_storage = False
        for s in devdata.get('storage', []):
            if s.get('rw', False):
                has_rw_storage = True
                break
        if not has_rw_storage: return False

        return True

    @property
    def filesystem_cache(self):
        if self._filesystem_cache is None:
            ts = self.total_space()
            all_storage = []
            items = []
            for storage_id, capacity in zip([self._main_id, self._carda_id,
                self._cardb_id], ts):
                if storage_id is None: continue
                name = _('Unknown')
                for s in self.dev.data['storage']:
                    if s['id'] == storage_id:
                        name = s['name']
                        break
                storage = {'id':storage_id, 'size':capacity, 'name':name,
                        'is_folder':True}
                id_map = self.dev.get_filesystem(storage_id)
                all_storage.append(storage)
                items.append(id_map.itervalues())
            self._filesystem_cache = FilesystemCache(all_storage, chain(*items))
        return self._filesystem_cache

    @same_thread
    def post_yank_cleanup(self):
        self.currently_connected_pnp_id = self.current_friendly_name = None
        self._main_id = self._carda_id = self._cardb_id = None
        self.dev = self._filesystem_cache = None

    @same_thread
    def eject(self):
        if self.currently_connected_pnp_id is None: return
        self.ejected_devices.add(self.currently_connected_pnp_id)
        self.currently_connected_pnp_id = self.current_friendly_name = None
        self._main_id = self._carda_id = self._cardb_id = None
        self.dev = self._filesystem_cache = None

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
        self._main_id = storage[0]['id']
        if len(storage) > 1:
            self._carda_id = storage[1]['id']
        if len(storage) > 2:
            self._cardb_id = storage[2]['id']
        self.current_friendly_name = devdata.get('friendly_name', None)

    @same_thread
    def get_device_information(self, end_session=True):
        d = self.dev.data
        dv = d.get('device_version', '')
        for sid, location_code in ( (self._main_id, 'main'), (self._carda_id,
            'A'), (self._cardb_id, 'B')):
            if sid is None: continue
            # TODO: Implement the drive info dict
        return (self.current_friendly_name, dv, dv, '')

    @same_thread
    def card_prefix(self, end_session=True):
        ans = [None, None]
        if self._carda_id is not None:
            ans[0] = 'mtp:::%s:::'%self._carda_id
        if self._cardb_id is not None:
            ans[1] = 'mtp:::%s:::'%self._cardb_id
        return tuple(ans)

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
    def get_file(self, object_id, stream=None, callback=None):
        if stream is None:
            stream = SpooledTemporaryFile(5*1024*1024, '_wpd_receive_file.dat')
        try:
            self.dev.get_file(object_id, stream, callback)
        except self.wpd.WPDFileBusy:
            time.sleep(2)
            self.dev.get_file(object_id, stream, callback)
        return stream

