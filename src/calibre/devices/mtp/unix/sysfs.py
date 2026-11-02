#!/usr/bin/env python
# License: GPLv3 Copyright: 2013, Kovid Goyal <kovid at kovidgoyal.net>

import glob
import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

    from calibre.devices.mtp.unix.driver import MTPCandidate


class MTPDetect:
    SYSFS_PATH = os.environ.get('SYSFS_PATH', '/sys')

    def __init__(self) -> None:
        self.base = os.path.join(self.SYSFS_PATH, 'subsystem', 'usb', 'devices')
        if not os.path.exists(self.base):
            self.base = os.path.join(self.SYSFS_PATH, 'bus', 'usb', 'devices')
        self.ok = os.path.exists(self.base)

    def __call__(self, dev: MTPCandidate, debug: Callable[..., object] | None = None) -> bool:
        '''
        Check if the device has an interface named "MTP" using sysfs, which
        avoids probing the device.
        '''
        if not self.ok:
            return False

        def read(x: str) -> bytes | None:
            try:
                with open(x, 'rb') as f:
                    return f.read()
            except OSError:
                pass

        ipath = os.path.join(self.base, f'{dev.busnum}-*/{dev.busnum}-*/interface')
        for x in glob.glob(ipath):
            raw = read(x)
            if not raw or raw.strip() != b'MTP':
                continue
            raw = read(os.path.join(os.path.dirname(os.path.dirname(x)), 'devnum'))
            try:
                if raw and int(raw) == dev.devnum:
                    if debug is not None:
                        debug(f'Unknown device {dev} claims to be an MTP device')
                    return True
            except ValueError, TypeError:
                continue

        return False
