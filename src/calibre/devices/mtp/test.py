#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import unittest

from calibre.devices.mtp.driver import MTP_DEVICE

class Test(unittest.TestCase):

    def setUp(self):
        self.dev = MTP_DEVICE(None)

    def tearDown(self):
        pass


