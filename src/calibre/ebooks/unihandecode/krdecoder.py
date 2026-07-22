# License: GPLv3 Copyright: 2010, Hiroshi Miura <miurahr@linux.com>

"""
Decode unicode text to an ASCII representation of the text in Korean.
Based on unidecoder.

"""

from calibre.ebooks.unihandecode.krcodepoints import CODEPOINTS as HANCODES
from calibre.ebooks.unihandecode.unicodepoints import CODEPOINTS
from calibre.ebooks.unihandecode.unidecoder import Unidecoder


class Krdecoder(Unidecoder):
    codepoints = {}

    def __init__(self):
        self.codepoints = CODEPOINTS
        self.codepoints.update(HANCODES)
