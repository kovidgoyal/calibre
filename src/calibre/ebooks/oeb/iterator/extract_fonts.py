#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import re, os, logging
from functools import partial
from future_builtins import map

class FamilyMap(dict):

    def __init__(self, log):
        dict.__init__(self)
        self.replace_map = {}
        self.added_fonts = set()
        self.log = log

    def __call__(self, basedir, match):
        self.read_font_fule(basedir, match.group())
        return b''

    def finalize(self):
        if self.replace_map:
            self.pat = re.compile(br'(font-family.*?)(' +
                    b'|'.join(self.replace_map.iterkeys())+b')', re.I)

    def replace_font_families(self, raw):
        if self.replace_map:
            def sub(m):
                k = m.group(2).lower()
                for q, val in self.replace_map.iteritems():
                    if q.lower() == k.lower():
                        return m.group().replace(m.group(2), val)
                return m.group()

            return self.pat.sub(sub, raw)

    def read_font_fule(self, basedir, css):
        from PyQt4.Qt import QFontDatabase
        import cssutils
        cssutils.log.setLevel(logging.ERROR)
        try:
            sheet = cssutils.parseString(css)
        except:
            return
        for rule in sheet.cssRules:
            try:
                s = rule.style
                src = s.getProperty('src').propertyValue[0].uri
                font_family = s.getProperty('font-family').propertyValue[0].value
            except:
                continue
            if not src or not font_family:
                continue
            font_file = os.path.normcase(os.path.abspath(os.path.join(basedir,
                src)))
            if font_file not in self.added_fonts:
                self.added_fonts.add(font_file)
                if os.path.exists(font_file):
                    with open(font_file, 'rb') as f:
                        idx = QFontDatabase.addApplicationFontFromData(f.read())
                    if idx > -1:
                        family = map(unicode,
                            QFontDatabase.applicationFontFamilies(idx)).next()
                        self.log('Extracted embedded font:', family, 'from',
                                os.path.basename(font_file))
                        if (family and family != font_family and
                                family not in self.replace_map):
                            self.log('Replacing font family value:',
                                    font_family, 'with', family)
                            self.replace_map[font_family.encode('utf-8')] = \
                                    family.encode('utf-8')

def extract_fonts(opf, log):
    css_files = {}
    font_family_map = FamilyMap(log)
    pat = re.compile(br'^\s*@font-face\s*{[^}]+}', re.M)

    for item in opf.manifest:
        if item.mime_type and item.mime_type.lower() in {
                'text/css', 'text/x-oeb1-css', 'text/x-oeb-css'}:
            try:
                with open(item.path, 'rb') as f:
                    raw = f.read()
            except EnvironmentError:
                continue
            css_files[item.path] = pat.sub(partial(font_family_map,
                os.path.dirname(item.path)), raw)

    font_family_map.finalize()

    for path, raw in css_files.iteritems():
        with open(path, 'wb') as f:
            nraw = font_family_map.replace_font_families(raw)
            f.write(nraw)

