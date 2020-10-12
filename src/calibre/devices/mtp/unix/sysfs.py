#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai


__license__   = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os, glob


class MTPDetect(object):

    SYSFS_PATH = os.environ.get('SYSFS_PATH', '/sys')

    def __init__(self):
        self.base = os.path.join(self.SYSFS_PATH, 'subsystem', 'usb', 'devices')
        if not os.path.exists(self.base):
            self.base = os.path.join(self.SYSFS_PATH, 'bus', 'usb', 'devices')
        self.ok = os.path.exists(self.base)

    def __call__(self, dev, debug=None):
        '''
        Check if the device has an interface named "MTP" using sysfs, which
        avoids probing the device.
        '''
        if not self.ok:
            return False

        def read(x):
            try:
                with lopen(x, 'rb') as f:
                    return f.read()
            except EnvironmentError:
                pass

        ipath = os.path.join(self.base, '{0}-*/{0}-*/interface'.format(dev.busnum))
        for x in glob.glob(ipath):
            raw = read(x)
            if not raw or raw.strip() != b'MTP':
                continue
            raw = read(os.path.join(os.path.dirname(os.path.dirname(x)),
                                    'devnum'))
            try:
                if raw and int(raw) == dev.devnum:
                    if debug is not None:
                        debug('Unknown device {0} claims to be an MTP device'
                              .format(dev))
                    return True
            except (ValueError, TypeError):
                continue

        return False


