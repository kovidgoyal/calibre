# -*- coding: utf-8 -*-

__license__ = 'GPL 3'
__copyright__ = '2010, Hiroshi Miura <miurahr@linux.com>'
__docformat__ = 'restructuredtext en'

'''
Decode unicode text to an ASCII representation of the text in Vietnamese.

'''

import re
from unihandecode.unidecoder import Unidecoder
from unihandecode.vncodepoints import CODEPOINTS as HANCODES
from unihandecode.unicodepoints import CODEPOINTS

class Vndecoder(Unidecoder):

    codepoints = {}

    def __init__(self):
        self.codepoints = CODEPOINTS
        self.codepoints.update(HANCODES)

