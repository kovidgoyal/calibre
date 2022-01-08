#!/usr/bin/env python


__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os, sys, atexit
from itertools import product

from calibre import prints, isbytestring
from calibre.constants import filesystem_encoding
from calibre.utils.fonts.utils import (is_truetype_font, get_font_names,
        get_font_characteristics)
from polyglot.builtins import iteritems


class WinFonts:

    def __init__(self, winfonts):
        self.w = winfonts
        # Windows requires font files to be executable for them to be loaded,
        # so instead we use this hack.
        self.app_font_families = {}

        for f in ('Serif', 'Sans', 'Mono'):
            base = 'fonts/liberation/Liberation%s-%s.ttf'
            self.app_font_families['Liberation %s'%f] = m = {}
            for weight, is_italic in product((self.w.FW_NORMAL, self.w.FW_BOLD), (False, True)):
                name = {(self.w.FW_NORMAL, False):'Regular',
                        (self.w.FW_NORMAL, True):'Italic',
                        (self.w.FW_BOLD, False):'Bold',
                        (self.w.FW_BOLD, True):'BoldItalic'}[(weight,
                            is_italic)]
                m[(weight, is_italic)] = base%(f, name)

        # import pprint
        # pprint.pprint(self.app_font_families)

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
        return sorted(names.union(frozenset(self.app_font_families)))

    def get_normalized_name(self, is_italic, weight):
        if is_italic:
            ft = 'bi' if weight == self.w.FW_BOLD else 'italic'
        else:
            ft = 'bold' if weight == self.w.FW_BOLD else 'normal'
        return ft

    def fonts_for_family(self, family, normalize=True):
        family = str(family)
        ans = {}
        for weight, is_italic in product((self.w.FW_NORMAL, self.w.FW_BOLD), (False, True)):
            if family in self.app_font_families:
                m = self.app_font_families[family]
                path = m.get((weight, is_italic), None)
                if path is None:
                    continue
                data = P(path, data=True)
            else:
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
                weight, is_italic, is_bold, is_regular = get_font_characteristics(data)[:4]
            except Exception as e:
                prints('Failed to get font characteristic for font: %s [%s]'
                        ' with error: %s'%(family,
                            self.get_normalized_name(is_italic, weight), e))
                continue

            try:
                family_name, sub_family_name, full_name = get_font_names(data)
            except:
                pass

            if normalize:
                ft = {(True, True):'bi', (True, False):'italic', (False,
                    True):'bold', (False, False):'normal'}[(is_italic,
                        is_bold)]
            else:
                ft = (1 if is_italic else 0, weight//10)

            if not (family_name or full_name):
                # prints('Font %s [%s] has no names'%(family,
                #     self.get_normalized_name(is_italic, weight)))
                family_name = family
            name = full_name or family + ' ' + (sub_family_name or '')

            try:
                name.encode('ascii')
            except ValueError:
                try:
                    sub_family_name.encode('ascii')
                    subf = sub_family_name
                except:
                    subf = ''

                name = family + ((' ' + subf) if subf else '')

            ans[ft] = (ext, name, data)

        return ans

    def add_system_font(self, path):
        '''
        WARNING: The file you are adding must have execute permissions or
        windows will fail to add it. (ls -l in cygwin to check)
        '''
        if isbytestring(path):
            path = path.decode(filesystem_encoding)
        path = os.path.abspath(path)
        ret = self.w.add_system_font(path)
        if ret > 0:
            atexit.register(self.remove_system_font, path)
        return ret

    def remove_system_font(self, path):
        return self.w.remove_system_font(path)


def load_winfonts():
    from calibre_extensions import winfonts
    return WinFonts(winfonts)


def test_ttf_reading():
    for arg in sys.argv[1:]:
        with open(arg, 'rb') as f:
            raw = f.read()
        print(os.path.basename(arg))
        get_font_characteristics(raw)
        print()


def test():
    base = os.path.abspath(__file__)
    d = os.path.dirname
    pluginsd = os.path.join(d(d(d(base))), 'plugins')
    if os.path.exists(os.path.join(pluginsd, 'winfonts.pyd')):
        sys.path.insert(0, pluginsd)
        import winfonts
        w = WinFonts(winfonts)
    else:
        w = load_winfonts()

    print(w.w)
    families = w.font_families()
    print(families)

    for family in families:
        prints(family + ':')
        for font, data in iteritems(w.fonts_for_family(family)):
            prints('  ', font, data[0], data[1], len(data[2]))
        print()


if __name__ == '__main__':
    test()
