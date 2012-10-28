#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os, sys

from calibre.constants import plugins, islinux, isbsd, isosx, preferred_encoding

_fc, _fc_err = plugins['fontconfig']

if _fc is None:
    raise RuntimeError('Failed to load fontconfig with error:'+_fc_err)

if islinux or isbsd:
    Thread = object
else:
    from threading import Thread

class FontConfig(Thread):

    def __init__(self):
        Thread.__init__(self)
        self.daemon = True
        self.failed = False
        self.css_weight_map = {
            _fc.FC_WEIGHT_THIN : u'100',
            _fc.FC_WEIGHT_EXTRALIGHT : u'200', _fc.FC_WEIGHT_ULTRALIGHT : u'200',
            _fc.FC_WEIGHT_LIGHT : u'300',
            _fc.FC_WEIGHT_BOOK : u'normal', _fc.FC_WEIGHT_BOOK : u'normal', _fc.FC_WEIGHT_REGULAR : u'normal',
            _fc.FC_WEIGHT_MEDIUM : u'500',
            _fc.FC_WEIGHT_DEMIBOLD : u'600', _fc.FC_WEIGHT_SEMIBOLD : u'600',
            _fc.FC_WEIGHT_BOLD : u'bold',
            _fc.FC_WEIGHT_EXTRABOLD : u'800', _fc.FC_WEIGHT_ULTRABOLD : u'800',
            _fc.FC_WEIGHT_HEAVY : u'900', _fc.FC_WEIGHT_BLACK : u'900', _fc.FC_WEIGHT_EXTRABLACK : u'900', _fc.FC_WEIGHT_ULTRABLACK : u'900'
        }
        self.css_slant_map = {
            _fc.FC_SLANT_ROMAN : u'normal',
            _fc.FC_SLANT_ITALIC : u'italic',
            _fc.FC_SLANT_OBLIQUE : u'oblique'
        }
        self.css_stretch_map = {
                _fc.FC_WIDTH_ULTRACONDENSED: u'ultra-condensed',
                _fc.FC_WIDTH_EXTRACONDENSED : u'extra-condensed',
                _fc.FC_WIDTH_CONDENSED: u'condensed',
                _fc.FC_WIDTH_SEMICONDENSED: u'semi-condensed',
                _fc.FC_WIDTH_NORMAL: u'normal',
                _fc.FC_WIDTH_SEMIEXPANDED: u'semi-expanded',
                _fc.FC_WIDTH_EXPANDED: u'expanded',
                _fc.FC_WIDTH_EXTRAEXPANDED: u'extra-expanded',
                _fc.FC_WIDTH_ULTRAEXPANDED: u'ultra-expanded',
        }

    def run(self):
        config = None
        if getattr(sys, 'frameworks_dir', False):
            config_dir = os.path.join(os.path.dirname(
                getattr(sys, 'frameworks_dir')), 'Resources', 'fonts')
            if isinstance(config_dir, unicode):
                config_dir = config_dir.encode(sys.getfilesystemencoding())
            config = os.path.join(config_dir, 'fonts.conf')
        try:
            _fc.initialize(config)
        except:
            import traceback
            traceback.print_exc()
            self.failed = True
        if not self.failed and hasattr(_fc, 'add_font_dir'):
            _fc.add_font_dir(P('fonts/liberation'))

    def is_scanning(self):
        if isosx:
            return self.is_alive()
        return False

    def wait(self):
        if not (islinux or isbsd):
            self.join()
        if self.failed:
            raise RuntimeError('Failed to initialize fontconfig')

    def find_font_families(self, allowed_extensions={'ttf', 'otf'}):
        '''
        Return an alphabetically sorted list of font families available on the system.

        `allowed_extensions`: A list of allowed extensions for font file types. Defaults to
        `['ttf', 'otf']`. If it is empty, it is ignored.
        '''
        self.wait()
        ans = _fc.find_font_families([bytes('.'+x) for x in allowed_extensions])
        ans = sorted(set(ans), cmp=lambda x,y:cmp(x.lower(), y.lower()))
        ans2 = []
        for x in ans:
            try:
                ans2.append(x.decode('utf-8'))
            except UnicodeDecodeError:
                continue
        return ans2

    def files_for_family(self, family, normalize=True):
        '''
        Find all the variants in the font family `family`.
        Returns a dictionary of tuples. Each tuple is of the form (path to font
        file, Full font name).
        The keys of the dictionary depend on `normalize`. If `normalize` is `False`,
        they are a tuple (slant, weight) otherwise they are strings from the set
        `('normal', 'bold', 'italic', 'bi', 'light', 'li')`
        '''
        self.wait()
        if not isinstance(family, unicode):
            family = family.decode(preferred_encoding)
        fonts = {}
        for entry in _fc.files_for_family(family):
            slant, weight = entry['slant'], entry['weight']
            fullname, path = entry['fullname'], entry['path']
            nfamily = entry['family']
            style = (slant, weight)
            if normalize:
                italic = slant > 0
                normal = weight == 80
                bold = weight > 80
                if italic:
                    style = 'italic' if normal else 'bi' if bold else 'li'
                else:
                    style = 'normal' if normal else 'bold' if bold else 'light'
            try:
                fullname, path = fullname.decode('utf-8'), path.decode('utf-8')
                nfamily = nfamily.decode('utf-8')
            except UnicodeDecodeError:
                continue
            if style in fonts:
                if nfamily.lower().strip() == family.lower().strip() \
                and 'Condensed' not in fullname and 'ExtraLight' not in fullname:
                    fonts[style] = (path, fullname)
            else:
                fonts[style] = (path, fullname)

        return fonts

    def faces_for_family(self, family):
        '''
        Return all the faces in a font family in a manner suitable for CSS 3.
        '''
        self.wait()
        if not isinstance(family, unicode):
            family = family.decode(preferred_encoding)
        seen = set()
        for entry in _fc.files_for_family(family):
            slant, weight = entry['slant'], entry['weight']
            fullname, path = entry['fullname'], entry['path']
            nfamily, width = entry['family'], entry['width']
            fingerprint = (slant, weight, width, nfamily)
            if fingerprint in seen:
                # Fontconfig returns the same font multiple times if it is
                # present in multiple locations
                continue
            seen.add(fingerprint)

            try:
                nfamily = nfamily.decode('UTF-8')
                fullname = fullname.decode('utf-8')
                path = path.decode('utf-8')
            except UnicodeDecodeError:
                continue

            face = {
                    'font-weight': self.css_weight_map[weight],
                    'font-style': self.css_slant_map[slant],
                    'font-stretch': self.css_stretch_map[width],
                    'font-family': nfamily,
                    'fullname': fullname, 'path':path
                    }
            yield face

    def match(self, name, all=False, verbose=False):
        '''
        Find the system font that most closely matches `name`, where `name` is a specification
        of the form::
        familyname-<pointsize>:<property1=value1>:<property2=value2>...

        For example, `verdana:weight=bold:slant=italic`

        Returns a list of dictionaries, or a single dictionary.
        Each dictionary has the keys:
        'weight', 'slant', 'family', 'file', 'fullname', 'style'

        `all`: If `True` return a sorted list of matching fonts, where the sort
        is in order of decreasing closeness of matching. If `False` only the
        best match is returned.        '''
        self.wait()
        if isinstance(name, unicode):
            name = name.encode('utf-8')
        fonts = []
        for fullname, path, style, family, weight, slant in \
            _fc.match(str(name), bool(all), bool(verbose)):
            try:
                fullname = fullname.decode('utf-8')
                path = path.decode('utf-8')
                style = style.decode('utf-8')
                family = family.decode('utf-8')
                fonts.append({
                    'fullname' : fullname,
                    'path'     : path,
                    'style'    : style,
                    'family'   : family,
                    'weight'   : weight,
                    'slant'    : slant
                    })
            except UnicodeDecodeError:
                continue
        return fonts if all else (fonts[0] if fonts else None)

fontconfig = FontConfig()
if islinux or isbsd:
    # On X11 Qt also uses fontconfig, so initialization must happen in the
    # main thread. In any case on X11 initializing fontconfig should be very
    # fast
    fontconfig.run()
else:
    fontconfig.start()

def test():
    from pprint import pprint;
    pprint(fontconfig.find_font_families())
    pprint(tuple(fontconfig.faces_for_family('liberation serif')))
    m = 'liberation serif'
    pprint(fontconfig.match(m+':slant=italic:weight=bold', verbose=True))

if __name__ == '__main__':
    test()
