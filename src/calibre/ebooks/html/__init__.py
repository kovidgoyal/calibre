#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import re


def tostring(root, strip_comments=False, pretty_print=False):
    '''
    Serialize processed XHTML.
    '''
    from lxml.etree import tostring as _tostring

    root.set('xmlns', 'http://www.w3.org/1999/xhtml')
    root.set('{http://www.w3.org/1999/xhtml}xlink', 'http://www.w3.org/1999/xlink')
    for x in root.iter():
        if hasattr(x.tag, 'rpartition') and x.tag.rpartition('}')[-1].lower() == 'svg':
            x.set('xmlns', 'http://www.w3.org/2000/svg')

    ans = _tostring(root, encoding='utf-8', pretty_print=pretty_print)
    if strip_comments:
        ans = re.compile(r'<!--.*?-->', re.DOTALL).sub('', ans)
    ans = '<?xml version="1.0" encoding="utf-8" ?>\n'+ans

    return ans


