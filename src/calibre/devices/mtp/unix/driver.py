#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import time, operator
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

    def report_progress(self, sent, total):
        try:
            p = int(sent/total * 100)
        except ZeroDivisionError:
            p = 100
        if self.progress_reporter is not None:
            self.progress_reporter(p)

    @synchronous
    def get_gui_name(self):
        if self.dev is None or not self.dev.friendly_name: return self.name
        return self.dev.friendly_name

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
    def shutdown(self):
        self.dev = None

    @synchronous
    def open(self, connected_device, library_uuid):
        def blacklist_device():
            d = connected_device
            self.blacklisted_devices.add((d.busnum, d.devnum, d.vendor_id,
                    d.product_id, d.bcd, d.serial))
        try:
            self.dev = self.detect.create_device(connected_device)
        except ValueError:
            # Give the device some time to settle
            time.sleep(2)
            try:
                self.dev = self.detect.create_device(connected_device)
            except ValueError:
                # Black list this device so that it is ignored for the
                # remainder of this session.
                blacklist_device()
                raise OpenFailed('%s is not a MTP device'%(connected_device,))
        except TypeError:
            blacklist_device()
            raise OpenFailed('')

        storage = sorted(self.dev.storage_info, key=operator.itemgetter('id'))
        if not storage:
            blacklist_device()
            raise OpenFailed('No storage found for device %s'%(connected_device,))
        self._main_id = storage[0]['id']
        self._carda_id = self._cardb_id = None
        if len(storage) > 1:
            self._carda_id = storage[1]['id']
        if len(storage) > 2:
            self._cardb_id = storage[2]['id']

    @synchronous
    def get_device_information(self, end_session=True):
        d = self.dev
        return (d.friendly_name, d.device_version, d.device_version, '')

    @synchronous
    def card_prefix(self, end_session=True):
        ans = [None, None]
        if self._carda_id is not None:
            ans[0] = 'mtp:%d:'%self._carda_id
        if self._cardb_id is not None:
            ans[1] = 'mtp:%d:'%self._cardb_id
        return tuple(ans)

    @synchronous
    def total_space(self, end_session=True):
        ans = [0, 0, 0]
        for s in self.dev.storage_info:
            i = {self._main_id:0, self._carda_id:1,
                    self._cardb_id:2}.get(s['id'], None)
            if i is not None:
                ans[i] = s['capacity']
        return tuple(ans)

    @synchronous
    def free_space(self, end_session=True):
        self.dev.update_storage_info()
        ans = [0, 0, 0]
        for s in self.dev.storage_info:
            i = {self._main_id:0, self._carda_id:1,
                    self._cardb_id:2}.get(s['id'], None)
            if i is not None:
                ans[i] = s['freespace_bytes']
        return tuple(ans)


if __name__ == '__main__':
    from pprint import pprint
    dev = MTP_DEVICE(None)
    from calibre.devices.scanner import linux_scanner
    devs = linux_scanner()
    mtp_devs = dev.detect(devs)
    dev.open(list(mtp_devs)[0], 'xxx')
    d = dev.dev
    print ("Opened device:", dev.get_gui_name())
    print ("Storage info:")
    pprint(d.storage_info)
    print("Free space:", dev.free_space())
    files, errs = d.get_filelist(dev)
    pprint((len(files), errs))
    folders, errs = d.get_folderlist()
    pprint((len(folders), errs))

