__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
'''
Device scanner that fetches list of devices on system ina  platform dependent
manner.
'''

import sys, os, re
from threading import RLock

from calibre import iswindows, isosx, plugins, islinux

osx_scanner = win_scanner = linux_scanner = None

if iswindows:
    try:
        win_scanner = plugins['winutil'][0].get_usb_devices
    except:
        raise RuntimeError('Failed to load the winutil plugin: %s'%plugins['winutil'][1])
elif isosx:
    try:
        osx_scanner = plugins['usbobserver'][0].get_usb_devices
    except:
        raise RuntimeError('Failed to load the usbobserver plugin: %s'%plugins['usbobserver'][1])

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
                except:
                    ans = False
                return ans
            finally:
                win32api.SetErrorMode(oldError)

    def drive_order(self, pnp_id):
        order = 0
        match = re.search(r'REV_.*?&(\d+)#', pnp_id)
        if match is None:
            match = re.search(r'REV_.*?&(\d+)', pnp_id)
        if match is not None:
            order = int(match.group(1))
        return order

    def __call__(self, debug=False):
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
                dev.append(int('0x'+open(ven).read().strip(), 16))
            except:
                continue
            try:
                dev.append(int('0x'+open(prod).read().strip(), 16))
            except:
                continue
            try:
                dev.append(int('0x'+open(bcd).read().strip(), 16))
            except:
                continue
            try:
                dev.append(open(man).read().strip())
            except:
                dev.append('')
            try:
                dev.append(open(prod_string).read().strip())
            except:
                dev.append('')
            try:
                dev.append(open(serial).read().strip())
            except:
                dev.append('')

            ans.add(tuple(dev))
        return ans

linux_scanner = None

if islinux:
    linux_scanner = LinuxScanner()

class DeviceScanner(object):

    def __init__(self, *args):
        if isosx and osx_scanner is None:
            raise RuntimeError('The Python extension usbobserver must be available on OS X.')
        self.scanner = win_scanner if iswindows else osx_scanner if isosx else linux_scanner
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
