__license__ = 'GPL 3'
__copyright__ = '2010, Hiroshi Miura <miurahr@linux.com>'
__docformat__ = 'restructuredtext en'

'''
Decode unicode text to an ASCII representation of the text for Japanese.
 Translate unicode string to ASCII roman string.

API is based on the python unidecode,
which is based on Ruby gem (http://rubyforge.org/projects/unidecode/)
and  perl module Text::Unidecode
(http://search.cpan.org/~sburke/Text-Unidecode-0.04/).

This functionality is owned by Kakasi Japanese processing engine.

Copyright (c) 2010 Hiroshi Miura
'''

import re

from pykakasi import kakasi

from calibre.ebooks.unihandecode.jacodepoints import CODEPOINTS as JACODES
from calibre.ebooks.unihandecode.unicodepoints import CODEPOINTS
from calibre.ebooks.unihandecode.unidecoder import Unidecoder


class Jadecoder(Unidecoder):

    def __init__(self):
        self.codepoints = CODEPOINTS.copy()
        self.codepoints.update(JACODES)
        self.kakasi = kakasi()
        self.kakasi.setMode("H","a") # Hiragana to ascii, default: no conversion
        self.kakasi.setMode("K","a") # Katakana to ascii, default: no conversion
        self.kakasi.setMode("J","a") # Japanese to ascii, default: no conversion
        self.kakasi.setMode("r","Hepburn") # default: use Hepburn Roman table
        self.kakasi.setMode("s", True) # add space, default: no separator
        self.kakasi.setMode("C", True) # capitalize, default: no capitalize
        self.conv = self.kakasi.getConverter()

    def decode(self, text):
        try:
            text = self.conv.do(text)
        except Exception:
            pass
        return re.sub('[^\x00-\x7f]', lambda x: self.replace_point(x.group()), text)
