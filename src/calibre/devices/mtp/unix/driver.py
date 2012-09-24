#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import operator, traceback, pprint, sys, time
from threading import RLock
from collections import namedtuple
from functools import partial

from calibre import prints, as_unicode
from calibre.constants import plugins
from calibre.ptempfile import SpooledTemporaryFile
from calibre.devices.errors import OpenFailed, DeviceError, BlacklistedDevice
from calibre.devices.mtp.base import MTPDeviceBase, synchronous, debug

MTPDevice = namedtuple('MTPDevice', 'busnum devnum vendor_id product_id '
        'bcd serial manufacturer product')

def fingerprint(d):
    return MTPDevice(d.busnum, d.devnum, d.vendor_id, d.product_id, d.bcd,
            d.serial, d.manufacturer, d.product)

class MTP_DEVICE(MTPDeviceBase):

    # libusb(x) does not work on OS X. So no MTP support for OS X
    supported_platforms = ['linux']

    def __init__(self, *args, **kwargs):
        MTPDeviceBase.__init__(self, *args, **kwargs)
        self.libmtp = None
        self.known_devices = None
        self.detect_cache = {}

        self.dev = None
        self._filesystem_cache = None
        self.lock = RLock()
        self.blacklisted_devices = set()
        self.ejected_devices = set()
        self.currently_connected_dev = None

    def set_debug_level(self, lvl):
        self.libmtp.set_debug_level(lvl)

    @synchronous
    def detect_managed_devices(self, devices_on_system, force_refresh=False):
        if self.libmtp is None: return None
        # First remove blacklisted devices.
        devs = set()
        for d in devices_on_system:
            fp = fingerprint(d)
            if fp not in self.blacklisted_devices:
                devs.add(fp)

        # Clean up ejected devices
        self.ejected_devices = devs.intersection(self.ejected_devices)

        # Check if the currently connected device is still present
        if self.currently_connected_dev is not None:
            return (self.currently_connected_dev if
                    self.currently_connected_dev in devs else None)

        # Remove ejected devices
        devs = devs - self.ejected_devices

        # Now check for MTP devices
        if force_refresh:
            self.detect_cache = {}
        cache = self.detect_cache
        for d in devs:
            ans = cache.get(d, None)
            if ans is None:
                ans = (d.vendor_id, d.product_id) in self.known_devices
                cache[d] = ans
            if ans:
                return d

        return None

    @synchronous
    def debug_managed_device_detection(self, devices_on_system, output):
        if self.currently_connected_dev is not None:
            return True
        p = partial(prints, file=output)
        if self.libmtp is None:
            err = plugins['libmtp'][1]
            if not err:
                err = 'startup() not called on this device driver'
            p(err)
            return False
        devs = [d for d in devices_on_system if (d.vendor_id, d.product_id)
                in self.known_devices]
        if not devs:
            p('No known MTP devices connected to system')
            return False
        p('Known MTP devices connected:')
        for d in devs: p(d)

        for d in devs:
            p('\nTrying to open:', d)
            try:
                self.open(d, 'debug')
            except BlacklistedDevice:
                p('This device has been blacklisted by the user')
                continue
            except:
                p('Opening device failed:')
                p(traceback.format_exc())
                return False
            else:
                p('Opened', self.current_friendly_name, 'successfully')
                p('Storage info:')
                p(pprint.pformat(self.dev.storage_info))
                self.post_yank_cleanup()
                return True
        return False

    @synchronous
    def create_device(self, connected_device):
        d = connected_device
        return self.libmtp.Device(d.busnum, d.devnum, d.vendor_id,
                d.product_id, d.manufacturer, d.product, d.serial)

    @synchronous
    def eject(self):
        if self.currently_connected_dev is None: return
        self.ejected_devices.add(self.currently_connected_dev)
        self.post_yank_cleanup()

    @synchronous
    def post_yank_cleanup(self):
        self.dev = self._filesystem_cache = self.current_friendly_name = None
        self.currently_connected_dev = None
        self.current_serial_num = None

    @property
    def is_mtp_device_connected(self):
        return self.currently_connected_dev is not None

    @synchronous
    def startup(self):
        p = plugins['libmtp']
        self.libmtp = p[0]
        if self.libmtp is None:
            print ('Failed to load libmtp, MTP device detection disabled')
            print (p[1])
        else:
            self.known_devices = frozenset(self.libmtp.known_devices())

        for x in vars(self.libmtp):
            if x.startswith('LIBMTP'):
                setattr(self, x, getattr(self.libmtp, x))

    @synchronous
    def shutdown(self):
        self.dev = self._filesystem_cache = None

    def format_errorstack(self, errs):
        return '\n'.join(['%d:%s'%(code, msg.decode('utf-8', 'replace')) for
            code, msg in errs])

    @synchronous
    def open(self, connected_device, library_uuid):
        self.dev = self._filesystem_cache = None
        try:
            self.dev = self.create_device(connected_device)
        except Exception as e:
            self.blacklisted_devices.add(connected_device)
            raise OpenFailed('Failed to open %s: Error: %s'%(
                    connected_device, as_unicode(e)))

        storage = sorted(self.dev.storage_info, key=operator.itemgetter('id'))
        storage = [x for x in storage if x.get('rw', False)]
        if not storage:
            self.blacklisted_devices.add(connected_device)
            raise OpenFailed('No storage found for device %s'%(connected_device,))
        snum = self.dev.serial_number
        if snum in self.prefs.get('blacklist', []):
            self.blacklisted_devices.add(connected_device)
            self.dev = None
            raise BlacklistedDevice(
                'The %s device has been blacklisted by the user'%(connected_device,))
        self._main_id = storage[0]['id']
        self._carda_id = self._cardb_id = None
        if len(storage) > 1:
            self._carda_id = storage[1]['id']
        if len(storage) > 2:
            self._cardb_id = storage[2]['id']
        self.current_friendly_name = self.dev.friendly_name
        if not self.current_friendly_name:
            self.current_friendly_name = self.dev.model_name or _('Unknown MTP device')
        self.current_serial_num = snum
        self.currently_connected_dev = connected_device

    @synchronous
    def device_debug_info(self):
        ans = self.get_gui_name()
        ans += '\nSerial number: %s'%self.current_serial_num
        ans += '\nManufacturer: %s'%self.dev.manufacturer_name
        ans += '\nModel: %s'%self.dev.model_name
        ans += '\nids: %s'%(self.dev.ids,)
        ans += '\nDevice version: %s'%self.dev.device_version
        ans += '\nStorage:\n'
        storage = sorted(self.dev.storage_info, key=operator.itemgetter('id'))
        ans += pprint.pformat(storage)
        return ans

    @property
    def filesystem_cache(self):
        if self._filesystem_cache is None:
            st = time.time()
            debug('Loading filesystem metadata...')
            from calibre.devices.mtp.filesystem_cache import FilesystemCache
            with self.lock:
                storage, all_items, all_errs = [], [], []
                for sid, capacity in zip([self._main_id, self._carda_id,
                    self._cardb_id], self.total_space()):
                    if sid is None: continue
                    name = _('Unknown')
                    for x in self.dev.storage_info:
                        if x['id'] == sid:
                            name = x['name']
                            break
                    storage.append({'id':sid, 'size':capacity,
                        'is_folder':True, 'name':name, 'can_delete':False,
                        'is_system':True})
                    items, errs = self.dev.get_filesystem(sid)
                    all_items.extend(items), all_errs.extend(errs)
                if not all_items and all_errs:
                    raise DeviceError(
                            'Failed to read filesystem from %s with errors: %s'
                            %(self.current_friendly_name,
                                self.format_errorstack(all_errs)))
                if all_errs:
                    prints('There were some errors while getting the '
                            ' filesystem from %s: %s'%(
                                self.current_friendly_name,
                                self.format_errorstack(all_errs)))
                self._filesystem_cache = FilesystemCache(storage, all_items)
            debug('Filesystem metadata loaded in %g seconds (%d objects)'%(
                time.time()-st, len(self._filesystem_cache)))
        return self._filesystem_cache

    @synchronous
    def get_basic_device_information(self):
        d = self.dev
        return (self.current_friendly_name, d.device_version, d.device_version, '')

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
    def create_folder(self, parent, name):
        if not parent.is_folder:
            raise ValueError('%s is not a folder'%(parent.full_path,))
        e = parent.folder_named(name)
        if e is not None:
            return e
        ename = name.encode('utf-8') if isinstance(name, unicode) else name
        sid, pid = parent.storage_id, parent.object_id
        if pid == sid:
            pid = 0
        ans, errs = self.dev.create_folder(sid, pid, ename)
        if ans is None:
            raise DeviceError(
                    'Failed to create folder named %s in %s with error: %s'%
                    (name, parent.full_path, self.format_errorstack(errs)))
        return parent.add_child(ans)

    @synchronous
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
        ename = name.encode('utf-8') if isinstance(name, unicode) else name
        sid, pid = parent.storage_id, parent.object_id
        if pid == sid:
            pid = 0

        ans, errs = self.dev.put_file(sid, pid, ename, stream, size, callback)
        if ans is None:
            raise DeviceError('Failed to upload file named: %s to %s: %s'
                    %(name, parent.full_path, self.format_errorstack(errs)))
        return parent.add_child(ans)

    @synchronous
    def get_mtp_file(self, f, stream=None, callback=None):
        if f.is_folder:
            raise ValueError('%s if a folder'%(f.full_path,))
        set_name = stream is None
        if stream is None:
            stream = SpooledTemporaryFile(5*1024*1024, '_wpd_receive_file.dat')
        ok, errs = self.dev.get_file(f.object_id, stream, callback)
        if not ok:
            raise DeviceError('Failed to get file: %s with errors: %s'%(
                f.full_path, self.format_errorstack(errs)))
        stream.seek(0)
        if set_name:
            stream.name = f.name
        return stream

    @synchronous
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
        ok, errs = self.dev.delete_object(obj.object_id)
        if not ok:
            raise DeviceError('Failed to delete %s with error: %s'%
                (obj.full_path, self.format_errorstack(errs)))
        parent.remove_child(obj)
        return parent

def develop():
    from calibre.devices.scanner import DeviceScanner
    scanner = DeviceScanner()
    scanner.scan()
    dev = MTP_DEVICE(None)
    dev.startup()
    try:
        cd = dev.detect_managed_devices(scanner.devices)
        if cd is None: raise RuntimeError('No MTP device found')
        dev.open(cd, 'develop')
        pprint.pprint(dev.dev.storage_info)
        dev.filesystem_cache
    finally:
        dev.shutdown()

if __name__ == '__main__':
    dev = MTP_DEVICE(None)
    dev.startup()
    from calibre.devices.scanner import DeviceScanner
    scanner = DeviceScanner()
    scanner.scan()
    devs = scanner.devices
    dev.debug_managed_device_detection(devs, sys.stdout)
    dev.set_debug_level(dev.LIBMTP_DEBUG_ALL)
    dev.shutdown()

