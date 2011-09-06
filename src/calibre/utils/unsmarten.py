# -*- coding: utf-8 -*-

from __future__ import (unicode_literals, division, absolute_import, print_function)

__license__ = 'GPL 3'
__copyright__ = '2011, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

import re

def unsmarten_text(txt):
    txt = re.sub(u'&#8211;|&ndash;|–', r'--', txt) # en-dash
    txt = re.sub(u'&#8212;|&mdash;|—', r'---', txt) # em-dash
    txt = re.sub(u'&#8230;|&hellip;|…', r'...', txt) # ellipsis

    txt = re.sub(u'&#8220;|&#8221;|&#8243;|&ldquo;|&rdquo;|&Prime;|“|”|″', r'"', txt)  # double quote
    txt = re.sub(u'&#8216;|&#8217;|&#8242;|&lsquo;|&rsquo;|&prime;|‘|’|′', r"'", txt)  # single quote

    return txt

