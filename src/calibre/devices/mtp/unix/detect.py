#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from calibre.constants import plugins

class MTPDetect(object):

    def __init__(self):
        p = plugins['libmtp']
        self.libmtp = p[0]
        if self.libmtp is None:
            print ('Failed to load libmtp, MTP device detection disabled')
            print (p[1])
        self.cache = {}

    def __call__(self, devices):
        '''
        Given a list of devices as returned by LinuxScanner, return the set of
        devices that are likely to be MTP devices. This class maintains a cache
        to minimize USB polling. Note that detection is partially based on a
        list of known vendor and product ids. This is because polling some
        older devices causes problems. Therefore, if this method identifies a
        device as MTP, it is not actually guaranteed that it will be a working
        MTP device.
        '''
        # First drop devices that have been disconnected from the cache
        connected_devices = {(d.busnum, d.devnum, d.vendor_id, d.product_id,
            d.bcd, d.serial) for d in devices}
        for d in tuple(self.cache.iterkeys()):
            if d not in connected_devices:
                del self.cache[d]

        # Since is_mtp_device() can cause USB traffic by probing the device, we
        # cache its result
        mtp_devices = set()
        if self.libmtp is None:
            return mtp_devices

        for d in devices:
            ans = self.cache.get((d.busnum, d.devnum, d.vendor_id, d.product_id,
                    d.bcd, d.serial), None)
            if ans is None:
                ans = self.libmtp.is_mtp_device(d.busnum, d.devnum,
                        d.vendor_id, d.product_id)
                self.cache[(d.busnum, d.devnum, d.vendor_id, d.product_id,
                    d.bcd, d.serial)] = ans
            if ans:
                mtp_devices.add(d)
        return mtp_devices

    def create_device(self, connected_device):
        d = connected_device
        return self.libmtp.Device(d.busnum, d.devnum, d.vendor_id,
                d.product_id, d.manufacturer, d.product, d.serial)

if __name__ == '__main__':
    from calibre.devices.scanner import linux_scanner
    mtp_detect = MTPDetect()
    devs = mtp_detect(linux_scanner())
    print ('Found %d MTP devices:'%len(devs))
    for dev in devs:
        print (dev, 'at busnum=%d and devnum=%d'%(dev.busnum, dev.devnum))
        print()


