# -*- coding: utf-8 -*-

__license__ = 'GPL 3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

'''
Decode unicode text to an ASCII representation of the text. Transliterate
unicode characters to ASCII.

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

from calibre.ebooks.unidecode.unicodepoints import CODEPOINTS
from calibre.constants import preferred_encoding

class Unidecoder(object):

    def decode(self, text):
        '''
        Tranliterate the string from unicode characters to ASCII.
        '''
        # The keys for CODEPOINTS is unicode characters, we want to be sure the
        # input text is unicode.
        if not isinstance(text, unicode):
            try:
                text = unicode(text)
            except:
                try:
                    text = text.decode(preferred_encoding)
                except:
                    text = text.decode('utf-8', 'replace')
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
            return CODEPOINTS[self.code_group(codepoint)][self.grouped_point(
                codepoint)]
        except:
            return '?'

    def code_group(self, character):
        '''
        Find what group character is a part of.
        '''
        # Code groups withing CODEPOINTS take the form 'xAB'
        return u'x%02x' % (ord(unicode(character)) >> 8)

    def grouped_point(self, character):
        '''
        Return the location the replacement character is in the list for a
        the group character is a part of.
        '''
        return ord(unicode(character)) & 255

