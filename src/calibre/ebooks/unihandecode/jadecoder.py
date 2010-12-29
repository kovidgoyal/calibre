# coding:utf8
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

from ctypes import *
import os, re
from unihandecode.unidecoder import Unidecoder
from unihandecode.unicodepoints import CODEPOINTS
from unihandecode.jacodepoints import CODEPOINTS as JACODES

class Jadecoder(Unidecoder):

    #kakasi instance
    kakasi = None

    codepoints = {}

    def __init__(self):
        self.codepoints = CODEPOINTS
        self.codepoints.update(JACODES)

        try:
            kakasi_location = os.environ['KAKASILIB'] 
                # May be "C:\\kakasi\\lib\\" in WIndows
                # "/opt/local/lib/" in Mac OS X
            kakasi_location = re.sub(r'/$', '', kakasi_location)
        except KeyError:
            if os.name is "nt":
                kakasi_location = "c:\\kakasi\\lib\\kakasi"
            elif os.name is "Darwin":
                kakasi_location = 'opt/local/lib'
            else:
                kakasi_location = ''

        if os.name is "nt":
            kakasi_libname = "kakasi"
        elif os.name is "Darwin":
            kakasi_libname = "libkakasi.dylib"
        elif os.name is "posix":
            kakasi_libname = "libkakasi.so.2"
        else:
            self.kakasi = None
            return

        try:
            self.kakasi = CDLL(os.path.join(kakasi_location, kakasi_libname))
        except:
            self.kakasi = None

    def decode(self, text):

        # if there is not kakasi library, we fall down to use unidecode
        if self.kakasi is None:
            return re.sub('[^\x00-\x7f]', lambda x: self.replace_point(x.group()),text)

        numopt = 9
        argArray = c_char_p * numopt
        args =  argArray( c_char_p("kakasi")
                               ,c_char_p("-Ja"),c_char_p("-Ha"),c_char_p("-Ka"),c_char_p("-Ea")
                               ,c_char_p("-ka"),c_char_p("-C"),c_char_p("-s")
                               ,c_char_p("-ieuc")
                              )
        self.kakasi.kakasi_getopt_argv(numopt, args)
        kakasi_do = self.kakasi.kakasi_do
        kakasi_do.restype = c_char_p

        try:
            cstr = c_char_p(text.encode("eucjp"))
            return kakasi_do(cstr).decode("eucjp")
        except:
            return re.sub('[^\x00-\x7f]', lambda x: self.replace_point(x.group()),text)
