__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
'''
Device scanner that fetches list of devices on system ina  platform dependent
manner.
'''

import sys, os

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

class LinuxScanner(object):

    SYSFS_PATH = os.environ.get('SYSFS_PATH', '/sys')

    def __init__(self):
        self.base = os.path.join(self.SYSFS_PATH, 'subsystem', 'usb', 'devices')
        if not os.path.exists(self.base):
            self.base = os.path.join(self.SYSFS_PATH, 'bus', 'usb', 'devices')
        self.ok = os.path.exists(self.base)

    def __call__(self):
        ans = set([])
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
        if islinux and not linux_scanner.ok:
            raise RuntimeError('DeviceScanner requires the /sys filesystem to work.')
        self.scanner = win_scanner if iswindows else osx_scanner if isosx else linux_scanner
        self.devices = []
        self.wmi = None
        self.pnp_ids = set([])
        self.rescan_pnp_ids = True

    def scan(self):
        '''Fetch list of connected USB devices from operating system'''
        self.devices = self.scanner()
        if self.rescan_pnp_ids:
            self.pnp_ids = set([])

    def pnp_id_iterator(self):
        if self.wmi is not None and not self.pnp_ids:
            for drive in self.wmi.Win32_DiskDrive():
                if drive.Partitions > 0:
                    self.pnp_ids.add(str(drive.PNPDeviceID))
        for x in self.pnp_ids:
            yield x

    def is_device_connected(self, device, debug=False):
        return device.is_usb_connected(self.devices, self.pnp_id_iterator, debug=debug)


def main(args=sys.argv):
    return 0

if __name__ == '__main__':
    sys.exit(main())
