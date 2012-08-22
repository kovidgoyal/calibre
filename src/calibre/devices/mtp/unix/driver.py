#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import time, operator
from threading import RLock
from io import BytesIO

from calibre.devices.errors import OpenFailed, DeviceError
from calibre.devices.mtp.base import MTPDeviceBase, synchronous
from calibre.devices.mtp.filesystem_cache import FilesystemCache
from calibre.devices.mtp.unix.detect import MTPDetect

class MTP_DEVICE(MTPDeviceBase):

    supported_platforms = ['linux']

    def __init__(self, *args, **kwargs):
        MTPDeviceBase.__init__(self, *args, **kwargs)
        self.dev = None
        self._filesystem_cache = None
        self.lock = RLock()
        self.blacklisted_devices = set()

    def set_debug_level(self, lvl):
        self.detect.libmtp.set_debug_level(lvl)

    def report_progress(self, sent, total):
        try:
            p = int(sent/total * 100)
        except ZeroDivisionError:
            p = 100
        if self.progress_reporter is not None:
            self.progress_reporter(p)

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
        self.dev = self._filesystem_cache = self.current_friendly_name = None

    @synchronous
    def startup(self):
        self.detect = MTPDetect()
        for x in vars(self.detect.libmtp):
            if x.startswith('LIBMTP'):
                setattr(self, x, getattr(self.detect.libmtp, x))

    @synchronous
    def shutdown(self):
        self.dev = self._filesystem_cache = None

    def format_errorstack(self, errs):
        return '\n'.join(['%d:%s'%(code, msg.decode('utf-8', 'replace')) for
            code, msg in errs])

    @synchronous
    def open(self, connected_device, library_uuid):
        self.dev = self._filesystem_cache = None
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
        self.current_friendly_name = self.dev.friendly_name

    @property
    def filesystem_cache(self):
        if self._filesystem_cache is None:
            with self.lock:
                files, errs = self.dev.get_filelist(self)
                if errs and not files:
                    raise DeviceError('Failed to read files from device. Underlying errors:\n'
                            +self.format_errorstack(errs))
                folders, errs = self.dev.get_folderlist()
                if errs and not folders:
                    raise DeviceError('Failed to read folders from device. Underlying errors:\n'
                            +self.format_errorstack(errs))
                storage = []
                for sid, capacity in zip([self._main_id, self._carda_id,
                    self._cardb_id], self.total_space()):
                    if sid is not None:
                        name = _('Unknown')
                        for x in self.dev.storage_info:
                            if x['id'] == sid:
                                name = x['name']
                                break
                        storage.append({'id':sid, 'size':capacity,
                            'is_folder':True, 'name':name})
                all_folders = []
                def recurse(f):
                    all_folders.append(f)
                    for c in f['children']:
                        recurse(c)

                for f in folders: recurse(f)
                self._filesystem_cache = FilesystemCache(storage,
                        all_folders+files)
        return self._filesystem_cache

    @synchronous
    def get_device_information(self, end_session=True):
        d = self.dev
        return (self.current_friendly_name, d.device_version, d.device_version, '')

    @synchronous
    def card_prefix(self, end_session=True):
        ans = [None, None]
        if self._carda_id is not None:
            ans[0] = 'mtp:::%d:::'%self._carda_id
        if self._cardb_id is not None:
            ans[1] = 'mtp:::%d:::'%self._cardb_id
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

    @synchronous
    def create_folder(self, parent_id, name):
        parent = self.filesystem_cache.id_map[parent_id]
        if not parent.is_folder:
            raise ValueError('%s is not a folder'%parent.full_path)
        e = parent.folder_named(name)
        if e is not None:
            return e
        ans = self.dev.create_folder(parent.storage_id, parent_id, name)
        return parent.add_child(ans)

if __name__ == '__main__':
    BytesIO
    class PR:
        def report_progress(self, sent, total):
            print (sent, total, end=', ')

    from pprint import pprint
    dev = MTP_DEVICE(None)
    dev.startup()
    from calibre.devices.scanner import linux_scanner
    devs = linux_scanner()
    mtp_devs = dev.detect(devs)
    dev.open(list(mtp_devs)[0], 'xxx')
    d = dev.dev
    print ("Opened device:", dev.get_gui_name())
    print ("Storage info:")
    pprint(d.storage_info)
    print("Free space:", dev.free_space())
    # print (d.create_folder(dev._main_id, 0, 'testf'))
    # raw = b'test'
    # fname = b'moose.txt'
    # src = BytesIO(raw)
    # print (d.put_file(dev._main_id, 0, fname, src, len(raw), PR()))
    dev.filesystem_cache.dump()
    # with open('/tmp/flint.epub', 'wb') as f:
    #     print(d.get_file(786, f, PR()))
    # print()
    # with open('/tmp/bleak.epub', 'wb') as f:
    #     print(d.get_file(601, f, PR()))
    # print()
    dev.set_debug_level(dev.LIBMTP_DEBUG_ALL)
    del d
    dev.shutdown()

