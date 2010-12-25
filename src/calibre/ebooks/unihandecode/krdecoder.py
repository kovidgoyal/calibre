# -*- coding: utf-8 -*-

__license__ = 'GPL 3'
__copyright__ = '2010, Hiroshi Miura <miurahr@linux.com>'
__docformat__ = 'restructuredtext en'

'''
Decode unicode text to an ASCII representation of the text in Korean.
Based on unidecoder.

'''

import re
from unidecoder import Unidecoder
from krcodepoints import CODEPOINTS as HANCODES
from unicodepoints import CODEPOINTS

class Krdecoder(Unidecoder):

    codepoints = {}

    def __init__(self):
        self.codepoints = CODEPOINTS
        self.codepoints.update(HANCODES)

    def decode(self, text):
        '''
        example  convert 
        >>> h = Krdecoder()
        >>> print h.decode(u"내일은 내일 바람이 분다")
        naeileun naeil barami bunda
        >>> print h.decode(u'\u660e\u65e5\u306f\u660e\u65e5\u306e\u98a8\u304c\u5439\u304f')
        MyengIlhaMyengIlnoPhwunggaChwiku
        '''
        # Replace characters larger than 127 with their ASCII equivelent.
        return re.sub('[^\x00-\x7f]', lambda x: self.replace_point(x.group()),
            text)

    def replace_point(self, codepoint):
        '''
        Returns the replacement character or ? if none can be found.
        '''
        try:
            # Split the unicode character xABCD into parts 0xAB and 0xCD.
            # 0xAB represents the group within CODEPOINTS to query and 0xCD
            # represents the position in the list of characters for the group.
            return self.codepoints[self.code_group(codepoint)][self.grouped_point(
                codepoint)]
        except:
            return '?'

def _test():
	import doctest
	doctest.testmod()

if __name__ == "__main__":
	_test()

