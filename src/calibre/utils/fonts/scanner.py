#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai


__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os
from collections import defaultdict
from threading import Thread

from calibre import walk, prints, as_unicode
from calibre.constants import (config_dir, iswindows, ismacos, DEBUG,
        isworker, filesystem_encoding)
from calibre.utils.fonts.metadata import FontMetadata, UnsupportedFont
from calibre.utils.icu import sort_key
from polyglot.builtins import itervalues, unicode_type, filter


class NoFonts(ValueError):
    pass

# Font dirs {{{


def default_font_dirs():
    return [
        '/opt/share/fonts',
        '/usr/share/fonts',
        '/usr/local/share/fonts',
        os.path.expanduser('~/.local/share/fonts'),
        os.path.expanduser('~/.fonts')
    ]


def fc_list():
    import ctypes
    from ctypes.util import find_library

    lib = find_library('fontconfig')
    if lib is None:
        return default_font_dirs()
    try:
        lib = ctypes.CDLL(lib)
    except:
        return default_font_dirs()

    prototype = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p)
    try:
        get_font_dirs = prototype(('FcConfigGetFontDirs', lib))
    except (AttributeError):
        return default_font_dirs()
    prototype = ctypes.CFUNCTYPE(ctypes.c_char_p, ctypes.c_void_p)
    try:
        next_dir = prototype(('FcStrListNext', lib))
    except (AttributeError):
        return default_font_dirs()

    prototype = ctypes.CFUNCTYPE(None, ctypes.c_void_p)
    try:
        end = prototype(('FcStrListDone', lib))
    except (AttributeError):
        return default_font_dirs()

    str_list = get_font_dirs(ctypes.c_void_p())
    if not str_list:
        return default_font_dirs()

    ans = []
    while True:
        d = next_dir(str_list)
        if not d:
            break
        if d:
            try:
                ans.append(d.decode(filesystem_encoding))
            except ValueError:
                prints('Ignoring undecodeable font path: %r' % d)
                continue
    end(str_list)
    if len(ans) < 3:
        return default_font_dirs()

    parents, visited = [], set()
    for f in ans:
        path = os.path.normpath(os.path.abspath(os.path.realpath(f)))
        if path == '/':
            continue
        head, tail = os.path.split(path)
        while head and tail:
            if head in visited:
                break
            head, tail = os.path.split(head)
        else:
            parents.append(path)
            visited.add(path)
    return parents


def font_dirs():
    if iswindows:
        from calibre_extensions import winutil
        paths = {os.path.normcase(r'C:\Windows\Fonts')}
        for which in (winutil.CSIDL_FONTS, winutil.CSIDL_LOCAL_APPDATA, winutil.CSIDL_APPDATA):
            try:
                path = winutil.special_folder_path(which)
            except ValueError:
                continue
            if which != winutil.CSIDL_FONTS:
                path = os.path.join(path, r'Microsoft\Windows\Fonts')
            paths.add(os.path.normcase(path))
        return list(paths)
    if ismacos:
        return [
                '/Library/Fonts',
                '/System/Library/Fonts',
                '/usr/share/fonts',
                '/var/root/Library/Fonts',
                os.path.expanduser('~/.fonts'),
                os.path.expanduser('~/Library/Fonts'),
                ]
    return fc_list()
# }}}

# Build font family maps {{{


def font_priority(font):
    '''
    Try to ensure that  the "Regular" face is the first font for a given
    family.
    '''
    style_normal = font['font-style'] == 'normal'
    width_normal = font['font-stretch'] == 'normal'
    weight_normal = font['font-weight'] == 'normal'
    num_normal = sum(filter(None, (style_normal, width_normal,
        weight_normal)))
    subfamily_name = (font['wws_subfamily_name'] or
            font['preferred_subfamily_name'] or font['subfamily_name'])
    if num_normal == 3 and subfamily_name == 'Regular':
        return 0
    if num_normal == 3:
        return 1
    if subfamily_name == 'Regular':
        return 2
    return 3 + (3 - num_normal)


def path_significance(path, folders):
    path = os.path.normcase(os.path.abspath(path))
    for i, q in enumerate(folders):
        if path.startswith(q):
            return i
    return -1


def build_families(cached_fonts, folders, family_attr='font-family'):
    families = defaultdict(list)
    for f in itervalues(cached_fonts):
        if not f:
            continue
        lf = icu_lower(f.get(family_attr) or '')
        if lf:
            families[lf].append(f)

    for fonts in itervalues(families):
        # Look for duplicate font files and choose the copy that is from a
        # more significant font directory (prefer user directories over
        # system directories).
        fmap = {}
        remove = []
        for f in fonts:
            fingerprint = (icu_lower(f['font-family']), f['font-weight'],
                    f['font-stretch'], f['font-style'])
            if fingerprint in fmap:
                opath = fmap[fingerprint]['path']
                npath = f['path']
                if path_significance(npath, folders) >= path_significance(opath, folders):
                    remove.append(fmap[fingerprint])
                    fmap[fingerprint] = f
                else:
                    remove.append(f)
            else:
                fmap[fingerprint] = f
        for font in remove:
            fonts.remove(font)
        fonts.sort(key=font_priority)

    font_family_map = dict.copy(families)
    font_families = tuple(sorted((f[0]['font-family'] for f in
            itervalues(font_family_map)), key=sort_key))
    return font_family_map, font_families
# }}}


class FontScanner(Thread):

    CACHE_VERSION = 2

    def __init__(self, folders=[], allowed_extensions={'ttf', 'otf'}):
        Thread.__init__(self)
        self.folders = folders + font_dirs() + [os.path.join(config_dir, 'fonts'),
                P('fonts/liberation')]
        self.folders = [os.path.normcase(os.path.abspath(f)) for f in
                self.folders]
        self.font_families = ()
        self.allowed_extensions = allowed_extensions

    # API {{{
    def find_font_families(self):
        self.join()
        return self.font_families

    def fonts_for_family(self, family):
        '''
        Return a list of the faces belonging to the specified family. The first
        face is the "Regular" face of family. Each face is a dictionary with
        many keys, the most important of which are: path, font-family,
        font-weight, font-style, font-stretch. The font-* properties follow the
        CSS 3 Fonts specification.
        '''
        self.join()
        try:
            return self.font_family_map[icu_lower(family)]
        except KeyError:
            raise NoFonts('No fonts found for the family: %r'%family)

    def legacy_fonts_for_family(self, family):
        '''
        Return a simple set of regular, bold, italic and bold-italic faces for
        the specified family. Returns a dictionary with each element being a
        2-tuple of (path to font, full font name) and the keys being: normal,
        bold, italic, bi.
        '''
        ans = {}
        try:
            faces = self.fonts_for_family(family)
        except NoFonts:
            return ans
        for i, face in enumerate(faces):
            if i == 0:
                key = 'normal'
            elif face['font-style'] in {'italic', 'oblique'}:
                key = 'bi' if face['font-weight'] == 'bold' else 'italic'
            elif face['font-weight'] == 'bold':
                key = 'bold'
            else:
                continue
            ans[key] = (face['path'], face['full_name'])
        return ans

    def get_font_data(self, font_or_path):
        path = font_or_path
        if isinstance(font_or_path, dict):
            path = font_or_path['path']
        with lopen(path, 'rb') as f:
            return f.read()

    def find_font_for_text(self, text, allowed_families={'serif', 'sans-serif'},
            preferred_families=('serif', 'sans-serif', 'monospace', 'cursive', 'fantasy')):
        '''
        Find a font on the system capable of rendering the given text.

        Returns a font family (as given by fonts_for_family()) that has a
        "normal" font and that can render the supplied text. If no such font
        exists, returns None.

        :return: (family name, faces) or None, None
        '''
        from calibre.utils.fonts.utils import (supports_text,
                panose_to_css_generic_family, get_printable_characters)
        if not isinstance(text, unicode_type):
            raise TypeError(u'%r is not unicode'%text)
        text = get_printable_characters(text)
        found = {}

        def filter_faces(font):
            try:
                raw = self.get_font_data(font)
                return supports_text(raw, text)
            except:
                pass
            return False

        for family in self.find_font_families():
            faces = list(filter(filter_faces, self.fonts_for_family(family)))
            if not faces:
                continue
            generic_family = panose_to_css_generic_family(faces[0]['panose'])
            if generic_family in allowed_families or generic_family == preferred_families[0]:
                return (family, faces)
            elif generic_family not in found:
                found[generic_family] = (family, faces)

        for f in preferred_families:
            if f in found:
                return found[f]
        return None, None
    # }}}

    def reload_cache(self):
        if not hasattr(self, 'cache'):
            from calibre.utils.config import JSONConfig
            self.cache = JSONConfig('fonts/scanner_cache')
        else:
            self.cache.refresh()
        if self.cache.get('version', None) != self.CACHE_VERSION:
            self.cache.clear()
        self.cached_fonts = self.cache.get('fonts', {})

    def run(self):
        self.do_scan()

    def do_scan(self):
        self.reload_cache()

        if isworker:
            # Dont scan font files in worker processes, use whatever is
            # cached. Font files typically dont change frequently enough to
            # justify a rescan in a worker process.
            self.build_families()
            return

        cached_fonts = self.cached_fonts.copy()
        self.cached_fonts.clear()
        for folder in self.folders:
            if not os.path.isdir(folder):
                continue
            try:
                files = tuple(walk(folder))
            except EnvironmentError as e:
                if DEBUG:
                    prints('Failed to walk font folder:', folder,
                            as_unicode(e))
                continue
            for candidate in files:
                if (candidate.rpartition('.')[-1].lower() not in self.allowed_extensions or not os.path.isfile(candidate)):
                    continue
                candidate = os.path.normcase(os.path.abspath(candidate))
                try:
                    s = os.stat(candidate)
                except EnvironmentError:
                    continue
                fileid = '{0}||{1}:{2}'.format(candidate, s.st_size, s.st_mtime)
                if fileid in cached_fonts:
                    # Use previously cached metadata, since the file size and
                    # last modified timestamp have not changed.
                    self.cached_fonts[fileid] = cached_fonts[fileid]
                    continue
                try:
                    self.read_font_metadata(candidate, fileid)
                except Exception as e:
                    if DEBUG:
                        prints('Failed to read metadata from font file:',
                                candidate, as_unicode(e))
                    continue

        if frozenset(cached_fonts) != frozenset(self.cached_fonts):
            # Write out the cache only if some font files have changed
            self.write_cache()

        self.build_families()

    def build_families(self):
        self.font_family_map, self.font_families = build_families(self.cached_fonts, self.folders)

    def write_cache(self):
        with self.cache:
            self.cache['version'] = self.CACHE_VERSION
            self.cache['fonts'] = self.cached_fonts

    def force_rescan(self):
        self.cached_fonts = {}
        self.write_cache()

    def read_font_metadata(self, path, fileid):
        with lopen(path, 'rb') as f:
            try:
                fm = FontMetadata(f)
            except UnsupportedFont:
                self.cached_fonts[fileid] = {}
            else:
                data = fm.to_dict()
                data['path'] = path
                self.cached_fonts[fileid] = data

    def dump_fonts(self):
        self.join()
        for family in self.font_families:
            prints(family)
            for font in self.fonts_for_family(family):
                prints('\t%s: %s'%(font['full_name'], font['path']))
                prints(end='\t')
                for key in ('font-stretch', 'font-weight', 'font-style'):
                    prints('%s: %s'%(key, font[key]), end=' ')
                prints()
                prints('\tSub-family:', font['wws_subfamily_name'] or
                        font['preferred_subfamily_name'] or
                        font['subfamily_name'])
                prints()
            prints()


font_scanner = FontScanner()
font_scanner.start()


def force_rescan():
    font_scanner.join()
    font_scanner.force_rescan()
    font_scanner.run()


if __name__ == '__main__':
    font_scanner.dump_fonts()
