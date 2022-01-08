__license__ = 'GPL 3'
__copyright__ = '2010, Hiroshi Miura <miurahr@linux.com>'
__docformat__ = 'restructuredtext en'

'''
Decode unicode text to an ASCII representation of the text in Chinese.
Transliterate unicode characters to ASCII based on chinese pronounce.

Derived from John Schember's unidecode library. Which was created
as part of calibre.

Copyright(c) 2009, John Schember <john@nachtimwald.com>

Based on the ruby unidecode gem (http://rubyforge.org/projects/unidecode/) which
is based on the perl module Text::Unidecode
(http://search.cpan.org/~sburke/Text-Unidecode-0.04/). More information about
unidecode can be found at
http://interglacial.com/~sburke/tpj/as_html/tpj22.html.

The major differences between this implementation and others is it's written in
python and it uses a single dictionary instead of loading the code group files
as needed.


Copyright (c) 2007 Russell Norris

Permission is hereby granted, free of charge, to any person
obtaining a copy of this software and associated documentation
files (the "Software"), to deal in the Software without
restriction, including without limitation the rights to use,
copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the
Software is furnished to do so, subject to the following
conditions:

The above copyright notice and this permission notice shall be
included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES
OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
OTHER DEALINGS IN THE SOFTWARE.


Copyright 2001, Sean M. Burke <sburke@cpan.org>, all rights reserved.

The programs and documentation in this dist are distributed in the
hope that they will be useful, but without any warranty; without even
the implied warranty of merchantability or fitness for a particular
purpose.

This library is free software; you can redistribute it and/or modify
it under the same terms as Perl itself.
'''

import re
from calibre.ebooks.unihandecode.unicodepoints import CODEPOINTS
from calibre.ebooks.unihandecode.zhcodepoints import CODEPOINTS as HANCODES


class Unidecoder:

    codepoints = {}

    def __init__(self):
        self.codepoints = CODEPOINTS
        self.codepoints.update(HANCODES)

    def decode(self, text):
        # Replace characters larger than 127 with their ASCII equivalent.
        return re.sub('[^\x00-\x7f]',lambda x: self.replace_point(x.group()), text)

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

    def code_group(self, character):
        '''
        Find what group character is a part of.
        '''
        # Code groups within CODEPOINTS take the form 'xAB'
        if not isinstance(character, str):
            character = str(character, "utf-8")
        return 'x%02x' % (ord(character) >> 8)

    def grouped_point(self, character):
        '''
        Return the location the replacement character is in the list for a
        the group character is a part of.
        '''
        if not isinstance(character, str):
            character = str(character, "utf-8")
        return ord(character) & 255
