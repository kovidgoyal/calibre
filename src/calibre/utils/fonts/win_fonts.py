#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os, sys
from itertools import product

from calibre import prints
from calibre.constants import plugins
from calibre.utils.fonts.utils import (is_truetype_font,
        get_font_characteristics)

class WinFonts(object):

    def __init__(self, winfonts):
        self.w = winfonts

    def font_families(self):
        names = set()
        for font in self.w.enum_font_families():
            if (
                    font['is_truetype'] and
                    # Fonts with names starting with @ are designed for
                    # vertical text
                    not font['name'].startswith('@')
                ):
                names.add(font['name'])
        return sorted(names)

    def get_normalized_name(self, is_italic, weight):
        if is_italic:
            ft = 'bi' if weight == self.w.FW_BOLD else 'italic'
        else:
            ft = 'bold' if weight == self.w.FW_BOLD else 'normal'
        return ft

    def fonts_for_family(self, family, normalize=True):
        family = type(u'')(family)
        ans = {}
        for weight, is_italic in product( (self.w.FW_NORMAL, self.w.FW_BOLD), (False, True) ):
            try:
                data = self.w.font_data(family, is_italic, weight)
            except Exception as e:
                prints('Failed to get font data for font: %s [%s] with error: %s'%
                        (family, self.get_normalized_name(is_italic, weight), e))
                continue

            ok, sig = is_truetype_font(data)
            if not ok:
                prints('Not a supported font, sfnt_version: %r'%sig)
                continue
            ext = 'otf' if sig == b'OTTO' else 'ttf'

            try:
                weight, is_italic, is_bold, is_regular = get_font_characteristics(data)
            except Exception as e:
                prints('Failed to get font characteristic for font: %s [%s]'
                        ' with error: %s'%(family,
                            self.get_normalized_name(is_italic, weight), e))
                continue

            if normalize:
                ft = {(True, True):'bi', (True, False):'italic', (False,
                    True):'bold', (False, False):'normal'}[(is_italic,
                        is_bold)]
            else:
                ft = (1 if is_italic else 0, weight//10)

            ans[ft] = (ext, data)

        return ans


def load_winfonts():
    w, err = plugins['winfonts']
    if w is None:
        raise RuntimeError('Failed to load the winfonts module: %s'%err)
    return WinFonts(w)

def test_ttf_reading():
    for f in sys.argv[1:]:
        raw = open(f).read()
        print (os.path.basename(f))
        get_font_characteristics(raw)
        print()

if __name__ == '__main__':
    base = os.path.abspath(__file__)
    d = os.path.dirname
    pluginsd = os.path.join(d(d(d(base))), 'plugins')
    if os.path.exists(os.path.join(pluginsd, 'winfonts.pyd')):
        sys.path.insert(0, pluginsd)
        import winfonts
        w = WinFonts(winfonts)
    else:
        w = load_winfonts()

    print (w.w)
    families = w.font_families()
    print (families)

    for family in families:
        print (family + ':')
        for font, data in w.fonts_for_family(family).iteritems():
            print ('  ', font, data[0], len(data[1]))
        print ()

