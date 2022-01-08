#!/usr/bin/env python


__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import traceback, re

from calibre.constants import iswindows
from polyglot.builtins import iteritems


supernote_settings = {
    'calibre_file_paths': {'metadata':'Document/metadata.calibre', 'driveinfo':'Document/driveinfo.calibre'},
    'send_to': ['Document', 'Documents'],
}


class DeviceDefaults:

    def __init__(self):
        self.rules = (
                # Amazon devices
                ({'vendor':0x1949}, {
                    'format_map': ['azw3', 'mobi', 'azw',
                                    'azw1', 'azw4', 'kfx', 'pdf'],
                    'send_to': ['documents', 'kindle', 'books'],
                    }
                ),
                # B&N devices
                ({'vendor':0x2080}, {
                    'format_map': ['epub', 'pdf'],
                    'send_to': ['NOOK/My Books', 'NOOK/My Files', 'NOOK', 'Calibre_Companion', 'Books',
                    'eBooks/import', 'eBooks', 'sdcard/ebooks'],
                    }
                ),
                # Supernote A5 and A5X
                ({'vendor': 0x2207, 'product': 0x0031}, supernote_settings),
                ({'vendor': 0x2207, 'product': 0x0011}, supernote_settings),
        )

    def __call__(self, device, driver):
        if iswindows:
            vid = pid = 0xffff
            m = re.search(r'(?i)vid_([0-9a-fA-F]+)&pid_([0-9a-fA-F]+)', device)
            if m is not None:
                try:
                    vid, pid = int(m.group(1), 16), int(m.group(2), 16)
                except:
                    traceback.print_exc()
        else:
            vid, pid = device.vendor_id, device.product_id

        for rule in self.rules:
            tests = rule[0]
            matches = True
            for k, v in iteritems(tests):
                if k == 'vendor' and v != vid:
                    matches = False
                    break
                if k == 'product' and v != pid:
                    matches = False
                    break
            if matches:
                ans = rule[1]
                if vid == 0x2080 and pid == 0x000a:
                    ans['calibre_file_paths'] = {'metadata':'NOOK/metadata.calibre', 'driveinfo':'NOOK/driveinfo.calibre'}
                return ans

        return {}
