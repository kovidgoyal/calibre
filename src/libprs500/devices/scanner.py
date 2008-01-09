##    Copyright (C) 2008 Kovid Goyal kovid@kovidgoyal.net
##    This program is free software; you can redistribute it and/or modify
##    it under the terms of the GNU General Public License as published by
##    the Free Software Foundation; either version 2 of the License, or
##    (at your option) any later version.
##
##    This program is distributed in the hope that it will be useful,
##    but WITHOUT ANY WARRANTY; without even the implied warranty of
##    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
##    GNU General Public License for more details.
##
##    You should have received a copy of the GNU General Public License along
##    with this program; if not, write to the Free Software Foundation, Inc.,
##    51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
'''
Device scanner that fetches list of devices on system ina  platform dependent
manner.
'''

import sys

from libprs500 import iswindows, isosx
from libprs500.devices import libusb

osx_scanner = None
try:
    import usbobserver
    osx_scanner = usbobserver.get_devices
except ImportError:
    pass

linux_scanner = libusb.get_devices

class DeviceScanner(object):
    
    def __init__(self, wmi=None):
        self.wmi = wmi
        if iswindows and wmi is None:
            raise RuntimeError('You must pass a wmi instance to DeviceScanner on windows.')        
        if isosx and osx_scanner is None:
            raise RuntimeError('The Python extension usbobserver must be available on OS X.')
        if not (isosx or iswindows) and not libusb.has_library():
            raise RuntimeError('DeviceScanner requires libusb to work.')
        
        self.devices = []
        
    def get_devices(self):
        if iswindows:
            devices = []
            for c in self.wmi.USBControllerDevice():
                devices.append(c.Dependent.DeviceID.upper())
            return devices
        if isosx:
            return osx_scanner()
        return linux_scanner()
    
    def scan(self):
        self.devices = self.get_devices()
        
    def is_device_connected(self, device):
        if iswindows:
            for device_id in self.devices:
                if 'VEN_'+device.VENDOR_NAME in device_id and \
                   'PROD_'+device.PRODUCT_NAME in device_id:
                    return True
                vid, pid = hex(device.VENDOR_ID)[2:], hex(device.PRODUCT_ID)[2:]
                if len(vid) < 4: vid = '0'+vid
                if len(pid) < 4: pid = '0'+pid
                if 'VID_'+vid in device_id and \
                       'PID_'+pid in device_id:
                    return True
            return False
        else:
            for vendor, product in self.devices:
                if device.VENDOR_ID == vendor and device.PRODUCT_ID == product:
                    return True
            return False


def main(args=sys.argv):
    return 0

if __name__ == '__main__':
    sys.exit(main())