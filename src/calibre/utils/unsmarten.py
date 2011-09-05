# -*- coding: utf-8 -*-

from __future__ import (unicode_literals, division, absolute_import, print_function)

__license__ = 'GPL 3'
__copyright__ = '2011, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

import re

from lxml import html as lhtml

from calibre import prepare_string_for_xml
from calibre.ebooks.oeb.base import barename

def unsmarten_html(html):
    def dump_text(elem):
        text = []
        tags = []
        tag = barename(elem.tag)
        attribs = elem.attrib
        tags.append(tag)
        # Turn the attributes into a string we can write with the tag.
        at = ''
        for k, v in attribs.items():
            at += ' %s="%s"' % (k, prepare_string_for_xml(v, attribute=True))
        # Write the tag.
        text.append('<%s%s>' % (tag, at))
        # Process tags that contain text.
        if hasattr(elem, 'text') and elem.text:
            # Don't modify text in pre tags.
            if tag == 'pre':
                text.append(elem.text)
            else:
                text.append(prepare_string_for_xml(unsmarten_text(elem.text)))
        # Recurse down into tags within the tag we are in.
        for item in elem:
            text += dump_text(item)
        # Close all open tags.
        tags.reverse()
        for t in tags:
            text.append('</%s>' % t)
        # Add the text that is outside of the tag.
        if hasattr(elem, 'tail') and elem.tail:
            text.append(prepare_string_for_xml(unsmarten_text(elem.tail)))
        return text
    
    content = lhtml.fromstring(html)
    html = dump_text(content)
    html = ''.join(html)
    
    return html


def unsmarten_text(txt):
    txt = re.sub(u'&#8211;|&ndash;|–', r'--', txt) # en-dash
    txt = re.sub(u'&#8212;|&mdash;|—', r'---', txt) # em-dash
    txt = re.sub(u'&#8230;|&hellip;|…', r'...', txt) # ellipsis

    txt = re.sub(u'&#8220;|&#8221;|&#8243;|&ldquo;|&rdquo;|&Prime;|“|”|″', r'"', txt)  # double quote
    txt = re.sub(u'&#8216;|&#8217;|&#8242;|&lsquo;|&rsquo;|&prime;|‘|’|′', r"'", txt)  # single quote

    return txt

