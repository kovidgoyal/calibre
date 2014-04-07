#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

import sys, glob, os, shutil, tempfile

from lxml import etree

from calibre.constants import config_dir
from calibre.utils.zipfile import ZipFile

NS_MAP = {
    'oor': "http://openoffice.org/2001/registry",
    'xs': "http://www.w3.org/2001/XMLSchema",
    'manifest': 'http://openoffice.org/2001/manifest',
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

def import_from_oxt(source_path, name, dest_dir=None, prefix='dic-'):
    dest_dir = dest_dir or os.path.join(config_dir, 'dictionaries')
    if not os.path.exists(dest_dir):
        os.makedirs(dest_dir)
    num = 0
    with ZipFile(source_path) as zf:
        root = etree.fromstring(zf.open('META-INF/manifest.xml').read())
        xcu = XPath('//manifest:file-entry[@manifest:media-type="application/vnd.sun.star.configuration-data"]')(root)[0].get(
            '{%s}full-path' % NS_MAP['manifest'])
        for (dic, aff), locales in parse_xcu(zf.open(xcu).read(), origin='').iteritems():
            dic, aff = dic.lstrip('/'), aff.lstrip('/')
            d = tempfile.mkdtemp(prefix=prefix, dir=dest_dir)
            metadata = [name] + locales
            with open(os.path.join(d, 'locales'), 'wb') as f:
                f.write(('\n'.join(metadata)).encode('utf-8'))
            with open(os.path.join(d, '%s.dic' % locales[0]), 'wb') as f:
                shutil.copyfileobj(zf.open(dic), f)
            with open(os.path.join(d, '%s.aff' % locales[0]), 'wb') as f:
                shutil.copyfileobj(zf.open(aff), f)
            num += 1
    return num

if __name__ == '__main__':
    import_from_libreoffice_source_tree(sys.argv[-1])
