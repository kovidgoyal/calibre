#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import time
from threading import RLock

from calibre import as_unicode, prints
from calibre.constants import plugins, __appname__, numeric_version
from calibre.devices.mtp.base import MTPDeviceBase, synchronous

class MTP_DEVICE(MTPDeviceBase):

    supported_platforms = ['windows']

    def __init__(self, *args, **kwargs):
        MTPDeviceBase.__init__(self, *args, **kwargs)
        self.dev = None
        self.lock = RLock()
        self.blacklisted_devices = set()
        self.ejected_devices = set()
        self.currently_connected_pnp_id = None
        self.detected_devices = {}
        self.previous_devices_on_system = frozenset()
        self.last_refresh_devices_time = time.time()
        self.wpd = self.wpd_error = None

    @synchronous
    def startup(self):
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

    @synchronous
    def shutdown(self):
        if self.wpd is not None:
            self.wpd.uninit()

    @synchronous
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
                # devices
                self.ejected_devices = set(self.detected_devices).intersection(self.ejected_devices)

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

    @synchronous
    def post_yank_cleanup(self):
        self.currently_connected_pnp_id = None

    @synchronous
    def eject(self):
        if self.currently_connected_pnp_id is None: return
        self.ejected_devices.add(self.currently_connected_pnp_id)
        self.currently_connected_pnp_id = None


