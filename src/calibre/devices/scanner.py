__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
'''
Device scanner that fetches list of devices on system ina  platform dependent
manner.
'''

import sys

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
else:
    linux_scanner = libusb.get_devices

class DeviceScanner(object):

    def __init__(self, *args):
        if isosx and osx_scanner is None:
            raise RuntimeError('The Python extension usbobserver must be available on OS X.')
        if not (isosx or iswindows) and not libusb.has_library():
            raise RuntimeError('DeviceScanner requires libusb to work.')
        self.scanner = win_scanner if iswindows else osx_scanner if isosx else linux_scanner
        self.devices = []

    def scan(self):
        '''Fetch list of connected USB devices from operating system'''
        self.devices = self.scanner()

    def test_bcd_windows(self, device_id, bcd):
        if bcd is None or len(bcd) == 0:
            return True
        for c in bcd:
            # Bug in winutil.get_usb_devices converts a to :
            rev = ('rev_%4.4x'%c).replace('a', ':')
            if rev in device_id:
                return True
        return False

    def test_bcd(self, bcdDevice, bcd):
        if bcd is None or len(bcd) == 0:
            return True
        for c in bcd:
            if c == bcdDevice:
                return True
        return False

    def is_device_connected(self, device):
        vendor_ids  = device.VENDOR_ID if hasattr(device.VENDOR_ID, '__len__') else [device.VENDOR_ID]
        product_ids =  device.PRODUCT_ID if hasattr(device.PRODUCT_ID, '__len__') else [device.PRODUCT_ID]
        if iswindows:
            for vendor_id in vendor_ids:
                for product_id in product_ids:
                    vid, pid = 'vid_%4.4x'%vendor_id, 'pid_%4.4x'%product_id
                    vidd, pidd = 'vid_%i'%vendor_id, 'pid_%i'%product_id
                    for device_id in self.devices:
                        if (vid in device_id or vidd in device_id) and (pid in device_id or pidd in device_id):
                            if self.test_bcd_windows(device_id, getattr(device, 'BCD', None)):
                                if device.can_handle(device_id):
                                    return True
        else:
            for vendor, product, bcdDevice in self.devices:
                if vendor in vendor_ids and product in product_ids:
                    if self.test_bcd(bcdDevice, getattr(device, 'BCD', None)):
                        if device.can_handle((vendor, product, bcdDevice)):
                            return True
        return False


def main(args=sys.argv):
    return 0

if __name__ == '__main__':
    sys.exit(main())
