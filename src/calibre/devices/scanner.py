
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
'''
Device scanner that fetches list of devices on system ina  platform dependent
manner.
'''

import sys, os, time
from collections import namedtuple
from threading import Lock

from calibre import prints, as_unicode
from calibre.constants import (iswindows, ismacos, islinux, isfreebsd,
        isnetbsd)
from polyglot.builtins import range

osx_scanner = linux_scanner = freebsd_scanner = netbsd_scanner = None

if iswindows:
    drive_ok_lock = Lock()

    def drive_is_ok(letter, max_tries=10, debug=False):
        from calibre_extensions import winutil
        with drive_ok_lock:
            for i in range(max_tries):
                try:
                    winutil.get_disk_free_space(letter+':\\')
                    return True
                except Exception as e:
                    if i >= max_tries - 1 and debug:
                        prints('Unable to get free space for drive:', letter)
                        prints(as_unicode(e))
                    time.sleep(0.2)
            return False

_USBDevice = namedtuple('USBDevice',
    'vendor_id product_id bcd manufacturer product serial')


class USBDevice(_USBDevice):

    def __new__(cls, *args, **kwargs):
        self = super(USBDevice, cls).__new__(cls, *args)
        self.busnum = self.devnum = -1
        return self

    def __repr__(self):
        return (u'USBDevice(busnum=%s, devnum=%s, '
                'vendor_id=0x%04x, product_id=0x%04x, bcd=0x%04x, '
                'manufacturer=%s, product=%s, serial=%s)')%(
                self.busnum, self.devnum, self.vendor_id, self.product_id,
                self.bcd, self.manufacturer, self.product, self.serial)

    __str__ = __repr__
    __unicode__ = __repr__


class LibUSBScanner(object):

    def __call__(self):
        if not hasattr(self, 'libusb'):
            from calibre_extensions import libusb
            self.libusb = libusb

        ans = set()
        seen = set()
        for fingerprint, ids in self.libusb.get_devices():
            seen.add(fingerprint)
            man = ids.get('manufacturer', None)
            prod = ids.get('product', None)
            serial = ids.get('serial', None)
            dev = fingerprint[2:] + (man, prod, serial)
            dev = USBDevice(*dev)
            dev.busnum, dev.devnum = fingerprint[:2]
            ans.add(dev)
        extra = set(self.libusb.cache) - seen
        for x in extra:
            self.libusb.cache.pop(x, None)
        return ans

    def check_for_mem_leak(self):
        import gc
        from calibre.utils.mem import memory
        memory()
        for num in (1, 10, 100):
            start = memory()
            for i in range(num):
                self()
            for i in range(3):
                gc.collect()
            print('Mem consumption increased by:', memory() - start, 'MB', end=' ')
            print('after', num, 'repeats')


class LinuxScanner(object):

    SYSFS_PATH = os.environ.get('SYSFS_PATH', '/sys')

    def __init__(self):
        self.base = os.path.join(self.SYSFS_PATH, 'subsystem', 'usb', 'devices')
        if not os.path.exists(self.base):
            self.base = os.path.join(self.SYSFS_PATH, 'bus', 'usb', 'devices')
        self.ok = os.path.exists(self.base)

    def __call__(self):
        ans = set()
        if not self.ok:
            raise RuntimeError('DeviceScanner requires the /sys filesystem to work.')

        def read(f):
            with lopen(f, 'rb') as s:
                return s.read().strip()

        for x in os.listdir(self.base):
            base = os.path.join(self.base, x)
            ven = os.path.join(base, 'idVendor')
            prod = os.path.join(base, 'idProduct')
            bcd = os.path.join(base, 'bcdDevice')
            man = os.path.join(base, 'manufacturer')
            serial = os.path.join(base, 'serial')
            prod_string = os.path.join(base, 'product')
            dev = []
            try:
                # Ignore USB HUBs
                if read(os.path.join(base, 'bDeviceClass')) == b'09':
                    continue
            except Exception:
                continue
            try:
                dev.append(int(b'0x'+read(ven), 16))
            except Exception:
                continue
            try:
                dev.append(int(b'0x'+read(prod), 16))
            except Exception:
                continue
            try:
                dev.append(int(b'0x'+read(bcd), 16))
            except Exception:
                continue
            try:
                dev.append(read(man).decode('utf-8'))
            except Exception:
                dev.append(u'')
            try:
                dev.append(read(prod_string).decode('utf-8'))
            except Exception:
                dev.append(u'')
            try:
                dev.append(read(serial).decode('utf-8'))
            except Exception:
                dev.append(u'')

            dev = USBDevice(*dev)
            try:
                dev.busnum = int(read(os.path.join(base, 'busnum')))
            except Exception:
                pass
            try:
                dev.devnum = int(read(os.path.join(base, 'devnum')))
            except Exception:
                pass
            ans.add(dev)
        return ans


if islinux:
    linux_scanner = LinuxScanner()

libusb_scanner = LibUSBScanner()

if isfreebsd:
    freebsd_scanner = libusb_scanner

''' NetBSD support currently not written yet '''
if isnetbsd:
    netbsd_scanner = None


class DeviceScanner(object):

    def __init__(self, *args):
        if iswindows:
            from calibre.devices.winusb import scan_usb_devices as win_scanner
        self.scanner = (win_scanner if iswindows else osx_scanner if ismacos else
                freebsd_scanner if isfreebsd else netbsd_scanner if isnetbsd
                else linux_scanner if islinux else libusb_scanner)
        if self.scanner is None:
            self.scanner = libusb_scanner
        self.devices = []

    def scan(self):
        '''Fetch list of connected USB devices from operating system'''
        self.devices = self.scanner()

    def is_device_connected(self, device, debug=False, only_presence=False):
        ''' If only_presence is True don't perform any expensive checks '''
        return device.is_usb_connected(self.devices, debug=debug,
                only_presence=only_presence)


def test_for_mem_leak():
    from calibre.utils.mem import memory, gc_histogram, diff_hists
    import gc
    gc.disable()
    scanner = DeviceScanner()
    scanner.scan()
    memory()  # load the psutil library
    for i in range(3):
        gc.collect()

    for reps in (1, 10, 100, 1000):
        for i in range(3):
            gc.collect()
        h1 = gc_histogram()
        startmem = memory()
        for i in range(reps):
            scanner.scan()
        for i in range(3):
            gc.collect()
        usedmem = memory(startmem)
        prints('Memory used in %d repetitions of scan(): %.5f KB'%(reps,
            1024*usedmem))
        prints('Differences in python object counts:')
        diff_hists(h1, gc_histogram())
        prints()


def main(args=sys.argv):
    test_for_mem_leak()
    return 0


if __name__ == '__main__':
    sys.exit(main())
