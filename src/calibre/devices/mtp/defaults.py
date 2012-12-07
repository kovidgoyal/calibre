#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import traceback, re

from calibre.constants import iswindows

class DeviceDefaults(object):

    def __init__(self):
        self.rules = (
                # Amazon devices
                ({'vendor':0x1949}, {
                    'format_map': ['azw3', 'mobi', 'azw',
                                    'azw1', 'azw4', 'pdf'],
                    'send_to': ['documents', 'books', 'kindle'],
                    }
                ),
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
            for k, v in tests.iteritems():
                if k == 'vendor' and v != vid:
                    matches = False
                    break
                if k == 'product' and v != pid:
                    matches = False
                    break
            if matches:
                return rule[1]

        return {}


