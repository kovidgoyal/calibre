#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

import sys, glob, os, shutil

from lxml import etree

NS_MAP = {
    'oor': "http://openoffice.org/2001/registry",
    'xs': "http://www.w3.org/2001/XMLSchema",
}

XPath = lambda x: etree.XPath(x, namespaces=NS_MAP)
BUILTIN_LOCALES = {'en-US'}

def parse_xcu(raw, origin='%origin%'):
    ' Get the dictionary and affix file names as well as supported locales for each dictionary '
    ans = {}
    root = etree.fromstring(raw)

    for node in XPath('//prop[@oor:name="Format"]/value[text()="DICT_SPELL"]/../..')(root):
        paths = ''.join(XPath('descendant::prop[@oor:name="Locations"]/value/text()')(node)).replace('%origin%', origin).split()
        aff, dic = paths if paths[0].endswith('.aff') else reversed(paths)
        locales = ''.join(XPath('descendant::prop[@oor:name="Locales"]/value/text()')(node)).split()
        ans[(dic, aff)] = locales
    return ans

def import_from_libreoffice_source_tree(source_path):
    dictionaries = {}
    for x in glob.glob(os.path.join(source_path, '*', 'dictionaries.xcu')):
        origin = os.path.dirname(x)
        with open(x, 'rb') as f:
            dictionaries.update(parse_xcu(f.read(), origin))

    base = P('dictionaries', allow_user_override=False)
    want_locales = set(BUILTIN_LOCALES)

    for (dic, aff), locales in dictionaries.iteritems():
        c = set(locales) & want_locales
        if c:
            locale = tuple(c)[0]
            want_locales.discard(locale)
            dest = os.path.join(base, locale)
            if not os.path.exists(dest):
                os.makedirs(dest)
            for src in (dic, aff):
                df = os.path.join(dest, locale + os.path.splitext(src)[1])
                shutil.copyfile(src, df)
            with open(os.path.join(dest, 'locales'), 'wb') as f:
                f.write(('\n'.join(locales)).encode('utf-8'))

    if want_locales:
        raise Exception('Failed to find dictionaries for some wanted locales: %s' % want_locales)

if __name__ == '__main__':
    import_from_libreoffice_source_tree(sys.argv[-1])
