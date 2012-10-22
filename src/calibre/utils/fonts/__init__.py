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
            f, name = val
            ext = f.rpartition('.')[-1].lower()
            ans[ft] = (ext, name, open(f, 'rb').read())
        return ans

    def find_font_for_text(self, text, allowed_families={'serif', 'sans-serif'},
            preferred_families=('serif', 'sans-serif', 'monospace', 'cursive', 'fantasy')):
        '''
        Find a font on the system capable of rendering the given text.

        Returns a font family (as given by fonts_for_family()) that has a
        "normal" font and that can render the supplied text. If no such font
        exists, returns None.

        :return: (family name, faces) or None, None
        '''
        from calibre.utils.fonts.free_type import FreeType, get_printable_characters, FreeTypeError
        from calibre.utils.fonts.utils import panose_to_css_generic_family, get_font_characteristics
        ft = FreeType()
        found = {}
        if not isinstance(text, unicode):
            raise TypeError(u'%r is not unicode'%text)
        text = get_printable_characters(text)

        def filter_faces(faces):
            ans = {}
            for k, v in faces.iteritems():
                try:
                    font = ft.load_font(v[2])
                except FreeTypeError:
                    continue
                if font.supports_text(text, has_non_printable_chars=False):
                    ans[k] = v
            return ans

        for family in sorted(self.find_font_families()):
            faces = filter_faces(self.fonts_for_family(family))
            if 'normal' not in faces:
                continue
            panose = get_font_characteristics(faces['normal'][2])[5]
            generic_family = panose_to_css_generic_family(panose)
            if generic_family in allowed_families or generic_family == preferred_families[0]:
                return (family, faces)
            elif generic_family not in found:
                found[generic_family] = (family, faces)

        for f in preferred_families:
            if f in found:
                return found[f]
        return None, None

fontconfig = Fonts()

def test():
    import os
    print(fontconfig.find_font_families())
    m = 'Liberation Serif'
    for ft, val in fontconfig.files_for_family(m).iteritems():
        print val[0], ft, val[1], os.path.getsize(val[0])

if __name__ == '__main__':
    test()
