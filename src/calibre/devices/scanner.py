__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
'''
Device scanner that fetches list of devices on system ina  platform dependent
manner.
'''

import sys, re, os

from calibre import iswindows, isosx, plugins
from calibre.devices import libusb

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


_usb_re = re.compile(r'Vendor\s*=\s*([0-9a-fA-F]+)\s+ProdID\s*=\s*([0-9a-fA-F]+)\s+Rev\s*=\s*([0-9a-fA-f.]+)')
_DEVICES = '/proc/bus/usb/devices'


def _linux_scanner():
    raw = open(_DEVICES).read()
    devices = []
    device = None
    for x in raw.splitlines():
        x = x.strip()
        if x.startswith('T:'):
            if device:
                devices.append(device)
            device = []
        if device is not None and x.startswith('P:'):
            match = _usb_re.search(x)
            if match is not None:
                ven, prod, bcd = match.group(1), match.group(2), match.group(3)
                ven, prod, bcd = int(ven, 16), int(prod, 16), int(bcd.replace('.', ''), 16)
                device = [ven, prod, bcd]
    if device:
        devices.append(device)
    return devices

if libusb.has_library:
    linux_scanner = libusb.get_devices
else:
    linux_scanner = _linux_scanner

class DeviceScanner(object):

    def __init__(self, *args):
        if isosx and osx_scanner is None:
            raise RuntimeError('The Python extension usbobserver must be available on OS X.')
        if not (isosx or iswindows) and (not os.access(_DEVICES, os.R_OK) and not libusb.has_library):
            raise RuntimeError('DeviceScanner requires %s or libusb to work.'%_DEVICES)
        self.scanner = win_scanner if iswindows else osx_scanner if isosx else linux_scanner
        self.devices = []

    def scan(self):
        '''Fetch list of connected USB devices from operating system'''
        self.devices = self.scanner()

    def is_device_connected(self, device):
        return device.is_usb_connected(self.devices)


def main(args=sys.argv):
    return 0

if __name__ == '__main__':
    sys.exit(main())
