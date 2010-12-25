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
from unidecoder import Unidecoder
from unicodepoints import CODEPOINTS
from jacodepoints import CODEPOINTS as JACODES

class Jadecoder(Unidecoder):

    #kakasi instance
    kakasi = None

    codepoints = {}

    def __init__(self):
        self.codepoints = CODEPOINTS
        self.codepoints.update(JACODES)

        try:
            if os.name is "nt":
                self.kakasi = CDLL("libkakasi")
            elif os.name is "posix":
                self.kakasi = CDLL("libkakasi.so")
            else:
                self.kakasi = None
        except:
            self.kakasi = None

    def decode(self, text):
        '''
        Translate the string from unicode characters to ASCII in Japanese.
        example convert "明日は明日の風が吹く", and "明天明天的风吹"
        >>> k = Jadecoder()
        >>> print k.decode(u'\u660e\u65e5\u306f\u660e\u65e5\u306e\u98a8\u304c\u5439\u304f')
        Ashita ha Ashita no Kaze ga Fuku
        >>> print k.decode(u'\u660e\u5929\u660e\u5929\u7684\u98ce\u5439')
        MeiTenMeiTenTekiSui
        '''        

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

def _test():
	import doctest
	doctest.testmod()

if __name__ == "__main__":
	_test()
