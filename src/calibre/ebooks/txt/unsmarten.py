# -*- coding: utf-8 -*-

__license__ = 'GPL 3'
__copyright__ = '2011, Leigh Parry <leighparry@blueyonder.co.uk>'
__docformat__ = 'restructuredtext en'

import re

def unsmarten(txt):
    txt = re.sub(u'&#8211;|&ndash;|–', r'-', txt) # en-dash
    txt = re.sub(u'&#8212;|&mdash;|—', r'--', txt) # em-dash
    txt = re.sub(u'&#8230;|&hellip;|…', r'...', txt) # ellipsis

    txt = re.sub(u'&#8220;|&#8221;|&#8243;|&ldquo;|&rdquo;|&Prime;|“|”|″', r'"', txt)  # double quote
    txt = re.sub(u'(["\'‘“]|\s)’', r"\1{'/}", txt)  # apostrophe
    txt = re.sub(u'&#8216;|&#8217;|&#8242;|&lsquo;|&rsquo;|&prime;|‘|’|′', r"'", txt)  # single quote

    return txt
