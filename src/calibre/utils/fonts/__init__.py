#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from calibre.constants import iswindows

class Fonts(object):

    def __init__(self):
        if iswindows:
            from calibre.utils.fonts.win_fonts import load_winfonts
            self.backend = load_winfonts()
        else:
            from calibre.utils.fonts.fc import fontconfig
            self.backend = fontconfig

    def find_font_families(self, allowed_extensions={'ttf', 'otf'}):
        if iswindows:
            return self.backend.font_families()
        return self.backend.find_font_families(allowed_extensions=allowed_extensions)

    def files_for_family(self, family, normalize=True):
        '''
        Find all the variants in the font family `family`.
        Returns a dictionary of tuples. Each tuple is of the form (path to font
        file, Full font name).
        The keys of the dictionary depend on `normalize`. If `normalize` is `False`,
        they are a tuple (slant, weight) otherwise they are strings from the set
        `('normal', 'bold', 'italic', 'bi', 'light', 'li')`
        '''
        if iswindows:
            from calibre.ptempfile import PersistentTemporaryFile
            fonts = self.backend.fonts_for_family(family, normalize=normalize)
            ans = {}
            for ft, val in fonts.iteritems():
                ext, name, data = val
                pt = PersistentTemporaryFile('.'+ext)
                pt.write(data)
                pt.close()
                ans[ft] = (pt.name, name)
            return ans
        return self.backend.files_for_family(family, normalize=normalize)

    def fonts_for_family(self, family, normalize=True):
        '''
        Just like files for family, except that it returns 3-tuples of the form
        (extension, full name, font data).
        '''
        if iswindows:
            return self.backend.fonts_for_family(family, normalize=normalize)
        files = self.backend.files_for_family(family, normalize=normalize)
        ans = {}
        for ft, val in files.iteritems():
            name, f = val
            ext = f.rpartition('.')[-1].lower()
            ans[ft] = (ext, name, open(f, 'rb').read())
        return ans

fontconfig = Fonts()

def test():
    import os
    print(fontconfig.find_font_families())
    m = 'times new roman' if iswindows else 'liberation serif'
    for ft, val in fontconfig.files_for_family(m).iteritems():
        print val[0], ft, val[1], os.path.getsize(val[1])

if __name__ == '__main__':
    test()
