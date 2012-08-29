__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
'''
Device scanner that fetches list of devices on system ina  platform dependent
manner.
'''

import sys, os, re
from threading import RLock
from collections import namedtuple

from calibre import prints, as_unicode
from calibre.constants import (iswindows, isosx, plugins, islinux, isfreebsd,
        isnetbsd)

osx_scanner = win_scanner = linux_scanner = freebsd_scanner = netbsd_scanner = None

if iswindows:
    try:
        win_scanner = plugins['winutil'][0].get_usb_devices
    except:
        raise RuntimeError('Failed to load the winutil plugin: %s'%plugins['winutil'][1])

class Drive(str):

    def __new__(self, val, order=0):
        typ = str.__new__(self, val)
        typ.order = order
        return typ

def drivecmp(a, b):
    ans = cmp(getattr(a, 'order', 0), getattr(b, 'order', 0))
    if ans == 0:
        ans = cmp(a, b)
    return ans


class WinPNPScanner(object):

    def __init__(self):
        self.scanner = None
        if iswindows:
            self.scanner = plugins['winutil'][0].get_removable_drives
            self.lock = RLock()

    def drive_is_ok(self, letter, debug=False):
        import win32api, win32file
        with self.lock:
            oldError = win32api.SetErrorMode(1) #SEM_FAILCRITICALERRORS = 1
            try:
                ans = True
                try:
                    win32file.GetDiskFreeSpaceEx(letter+':\\')
                except Exception as e:
                    if debug:
                        prints('Unable to get free space for drive:', letter)
                        prints(as_unicode(e))
                    ans = False
                return ans
            finally:
                win32api.SetErrorMode(oldError)

    def drive_order(self, pnp_id):
        order = 0
        match = re.search(r'REV_.*?&(\d+)#', pnp_id)
        if match is None:
            # Windows XP
            # On the Nook Color this is the last digit
            #
            # USBSTOR\DISK&VEN_B&N&PROD_EBOOK_DISK&REV_0100\7&13EAFDB8&0&2004760017462009&1
            # USBSTOR\DISK&VEN_B&N&PROD_EBOOK_DISK&REV_0100\7&13EAFDB8&0&2004760017462009&0
            #
            match = re.search(r'REV_.*&(\d+)', pnp_id)
        if match is not None:
            order = int(match.group(1))
        return order

    def __call__(self, debug=False):
        #import traceback
        #traceback.print_stack()

        if self.scanner is None:
            return {}
        try:
            drives = self.scanner(debug)
        except:
            drives = {}
            if debug:
                import traceback
                traceback.print_exc()
        remove = set([])
        for letter in drives:
            if not self.drive_is_ok(letter, debug=debug):
                remove.add(letter)
        for letter in remove:
            drives.pop(letter)
        ans = {}
        for key, val in drives.items():
            val = [x.upper() for x in val]
            val = [x for x in val if 'USBSTOR' in x]
            if val:
                ans[Drive(key+':\\', order=self.drive_order(val[-1]))] = val[-1]
        return ans

win_pnp_drives = WinPNPScanner()

_USBDevice = namedtuple('USBDevice',
    'vendor_id product_id bcd manufacturer product serial')

class USBDevice(_USBDevice):

    def __init__(self, *args, **kwargs):
        _USBDevice.__init__(self, *args, **kwargs)
        self.busnum = self.devnum = -1

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
            self.libusb, self.libusb_err = plugins['libusb']
            if self.libusb is None:
                raise ValueError(
                    'DeviceScanner needs libusb to work. Error: %s'%
                    self.libusb_err)

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
        extra = set(self.libusb.cache.iterkeys()) - seen
        for x in extra:
            self.libusb.cache.pop(x, None)
        return ans

    def check_for_mem_leak(self):
        import gc
        from calibre.utils.mem import memory
        memory()
        for num in (1, 10, 100):
            start = memory()
            for i in xrange(num):
                self()
            for i in xrange(3): gc.collect()
            print 'Mem consumption increased by:', memory() - start, 'MB',
            print 'after', num, 'repeats'

class LinuxScanner(object):

    SYSFS_PATH = os.environ.get('SYSFS_PATH', '/sys')

    def __init__(self):
        self.base = os.path.join(self.SYSFS_PATH, 'subsystem', 'usb', 'devices')
        if not os.path.exists(self.base):
            self.base = os.path.join(self.SYSFS_PATH, 'bus', 'usb', 'devices')
        self.ok = os.path.exists(self.base)

    def __call__(self):
        ans = set([])
        if not self.ok:
            raise RuntimeError('DeviceScanner requires the /sys filesystem to work.')

        def read(f):
            with open(f, 'rb') as s:
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
            except:
                continue
            try:
                dev.append(int(b'0x'+read(ven), 16))
            except:
                continue
            try:
                dev.append(int(b'0x'+read(prod), 16))
            except:
                continue
            try:
                dev.append(int(b'0x'+read(bcd), 16))
            except:
                continue
            try:
                dev.append(read(man).decode('utf-8'))
            except:
                dev.append(u'')
            try:
                dev.append(read(prod_string).decode('utf-8'))
            except:
                dev.append(u'')
            try:
                dev.append(read(serial).decode('utf-8'))
            except:
                dev.append(u'')

            dev = USBDevice(*dev)
            try:
                dev.busnum = int(read(os.path.join(base, 'busnum')))
            except:
                pass
            try:
                dev.devnum = int(read(os.path.join(base, 'devnum')))
            except:
                pass
            ans.add(dev)
        return ans

class FreeBSDScanner(object):

    def __call__(self):
        ans = set([])
        import dbus

        try:
           bus = dbus.SystemBus()
           manager = dbus.Interface(bus.get_object('org.freedesktop.Hal',
                         '/org/freedesktop/Hal/Manager'), 'org.freedesktop.Hal.Manager')
           paths = manager.FindDeviceStringMatch('freebsd.driver','da')
           for path in paths:
              obj = bus.get_object('org.freedesktop.Hal', path)
              objif = dbus.Interface(obj, 'org.freedesktop.Hal.Device')
              parentdriver = None
              while parentdriver != 'umass':
                 try:
                    obj = bus.get_object('org.freedesktop.Hal',
                          objif.GetProperty('info.parent'))
                    objif = dbus.Interface(obj, 'org.freedesktop.Hal.Device')
                    try:
                       parentdriver = objif.GetProperty('freebsd.driver')
                    except dbus.exceptions.DBusException, e:
                       continue
                 except dbus.exceptions.DBusException, e:
                    break
              if parentdriver != 'umass':
                  continue
              dev = []
              try:
                 dev.append(objif.GetProperty('usb.vendor_id'))
                 dev.append(objif.GetProperty('usb.product_id'))
                 dev.append(objif.GetProperty('usb.device_revision_bcd'))
              except dbus.exceptions.DBusException, e:
                 continue
              try:
                 dev.append(objif.GetProperty('info.vendor'))
              except:
                 dev.append('')
              try:
                 dev.append(objif.GetProperty('info.product'))
              except:
                 dev.append('')
              try:
                 dev.append(objif.GetProperty('usb.serial'))
              except:
                 dev.append('')
              dev.append(path)
              ans.add(tuple(dev))
        except dbus.exceptions.DBusException, e:
           print >>sys.stderr, "Execution failed:", e
        return ans



if islinux:
    linux_scanner = LinuxScanner()

libusb_scanner = LibUSBScanner()
if isosx:
    osx_scanner = libusb_scanner

if isfreebsd:
    freebsd_scanner = FreeBSDScanner()

''' NetBSD support currently not written yet '''
if isnetbsd:
    netbsd_scanner = None

class DeviceScanner(object):

    def __init__(self, *args):
        self.scanner = (win_scanner if iswindows else osx_scanner if isosx else
                freebsd_scanner if isfreebsd else netbsd_scanner if isnetbsd
                else linux_scanner if islinux else libusb_scanner)
        if self.scanner is None:
            self.scanner = libusb_scanner
        self.devices = []

    def scan(self):
        '''Fetch list of connected USB devices from operating system'''
        self.devices = self.scanner()

    def is_device_connected(self, device, debug=False, only_presence=False):
        ''' If only_presence is True don't perform any expensive checks (used
        only in windows)'''
        return device.is_usb_connected(self.devices, debug=debug,
                only_presence=only_presence)


def main(args=sys.argv):
    return 0

if __name__ == '__main__':
    sys.exit(main())
