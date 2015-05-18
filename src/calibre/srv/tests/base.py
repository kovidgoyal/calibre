#!/usr/bin/env python2
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import unittest, shutil
from functools import partial

rmtree = partial(shutil.rmtree, ignore_errors=True)

class BaseTest(unittest.TestCase):

    longMessage = True
    maxDiff = None

    ae = unittest.TestCase.assertEqual


