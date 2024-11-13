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

import pickle
import re
import warnings
from importlib.resources import files

from pykakasi import kakasi
from pykakasi.kanji import Itaiji, Kanwa
from pykakasi.properties import Configurations
from pykakasi.scripts import Jisyo

from calibre.ebooks.unihandecode.jacodepoints import CODEPOINTS as JACODES
from calibre.ebooks.unihandecode.unicodepoints import CODEPOINTS
from calibre.ebooks.unihandecode.unidecoder import Unidecoder


# pykakasi uses paths for its dictionaries rather than using the
# Traversable API of importlib.resources so we have to hack around it, sigh.
# https://codeberg.org/miurahr/pykakasi/pulls/174
def dictdata(dbfile: str):
    t = files('pykakasi')
    q = t.joinpath('data').joinpath(dbfile)
    return q.read_bytes()


def jisyo_init(self, dbname):
    self._dict = pickle.loads(dictdata(dbname))


def itaiji_init(self):
    if self._itaijidict is None:
        with self._lock:
            if self._itaijidict is None:
                self._itaijidict = pickle.loads(dictdata(Configurations.jisyo_itaiji))

def kanwa_init(self):
    if self._jisyo_table is None:
        with self._lock:
            if self._jisyo_table is None:
                self._jisyo_table = pickle.loads(dictdata(Configurations.jisyo_kanwa))

Jisyo.__init__ = jisyo_init
Itaiji.__init__ = itaiji_init
Kanwa.__init__ = kanwa_init

class Jadecoder(Unidecoder):

    def __init__(self):
        self.codepoints = CODEPOINTS.copy()
        self.codepoints.update(JACODES)

        # We have to use the deprecated API as the new API does not capitalize
        # words. Sigh.
        # https://codeberg.org/miurahr/pykakasi/issues/172
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
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
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                text = self.conv.do(text)
        except Exception:
            pass
        return re.sub('[^\x00-\x7f]', lambda x: self.replace_point(x.group()), text)
