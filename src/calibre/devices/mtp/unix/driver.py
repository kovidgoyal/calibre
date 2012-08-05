#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import time
from threading import RLock
from functools import wraps

from calibre.devices.errors import OpenFailed
from calibre.devices.mtp.base import MTPDeviceBase
from calibre.devices.mtp.unix.detect import MTPDetect

def synchronous(func):
    @wraps(func)
    def synchronizer(self, *args, **kwargs):
        with self.lock:
            return func(self, *args, **kwargs)
    return synchronizer

class MTP_DEVICE(MTPDeviceBase):

    supported_platforms = ['linux']

    def __init__(self, *args, **kwargs):
        MTPDeviceBase.__init__(self, *args, **kwargs)
        self.detect = MTPDetect()
        self.dev = None
        self.lock = RLock()
        self.blacklisted_devices = set()

    @synchronous
    def is_usb_connected(self, devices_on_system, debug=False,
            only_presence=False):

        # First remove blacklisted devices.
        devs = []
        for d in devices_on_system:
            if (d.busnum, d.devnum, d.vendor_id,
                d.product_id, d.bcd, d.serial) not in self.blacklisted_devices:
                devs.append(d)

        devs = self.detect(devs)
        if self.dev is not None:
            # Check if the currently opened device is still connected
            ids = self.dev.ids
            found = False
            for d in devs:
                if ( (d.busnum, d.devnum, d.vendor_id, d.product_id, d.serial)
                        == ids ):
                    found = True
                    break
            return found
        # Check if any MTP capable device is present
        return len(devs) > 0

    @synchronous
    def post_yank_cleanup(self):
        self.dev = None

    @synchronous
    def open(self, connected_device, library_uuid):
        try:
            self.detect.create_device(connected_device)
        except ValueError:
            # Give the device some time to settle
            time.sleep(2)
            try:
                self.detect.create_device(connected_device)
            except ValueError:
                # Black list this device so that it is ignored for the
                # remainder of this session.
                d = connected_device
                self.blacklisted_devices.add((d.busnum, d.devnum, d.vendor_id,
                    d.product_id, d.bcd, d.serial))
                raise OpenFailed('%s is not a MTP device'%connected_device)

