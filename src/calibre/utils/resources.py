#!/usr/bin/env python2
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'


import __builtin__, sys, os

from calibre import config_dir


class PathResolver(object):

    def __init__(self):
        self.locations = [sys.resources_location]
        self.cache = {}

        def suitable(path):
            try:
                return os.path.exists(path) and os.path.isdir(path) and \
                       os.listdir(path)
            except:
                pass
            return False

        self.default_path = sys.resources_location

        dev_path = os.environ.get('CALIBRE_DEVELOP_FROM', None)
        self.using_develop_from = False
        if dev_path is not None:
            dev_path = os.path.join(os.path.abspath(
                os.path.dirname(dev_path)), 'resources')
            if suitable(dev_path):
                self.locations.insert(0, dev_path)
                self.default_path = dev_path
                self.using_develop_from = True

        user_path = os.path.join(config_dir, 'resources')
        self.user_path = None
        if suitable(user_path):
            self.locations.insert(0, user_path)
            self.user_path = user_path

    def __call__(self, path, allow_user_override=True):
        path = path.replace(os.sep, '/')
        key = (path, allow_user_override)
        ans = self.cache.get(key, None)
        if ans is None:
            for base in self.locations:
                if not allow_user_override and base == self.user_path:
                    continue
                fpath = os.path.join(base, *path.split('/'))
                if os.path.exists(fpath):
                    ans = fpath
                    break

            if ans is None:
                ans = os.path.join(self.default_path, *path.split('/'))

            self.cache[key] = ans

        return ans


_resolver = PathResolver()


def get_path(path, data=False, allow_user_override=True):
    fpath = _resolver(path, allow_user_override=allow_user_override)
    if data:
        with open(fpath, 'rb') as f:
            return f.read()
    return fpath


def get_image_path(path, data=False, allow_user_override=True):
    if not path:
        return get_path('images', allow_user_override=allow_user_override)
    return get_path('images/'+path, data=data, allow_user_override=allow_user_override)


def js_name_to_path(name, ext='.coffee'):
    path = (u'/'.join(name.split('.'))) + ext
    d = os.path.dirname
    base = d(d(os.path.abspath(__file__)))
    return os.path.join(base, path)


def _compile_coffeescript(name):
    from calibre.utils.serve_coffee import compile_coffeescript
    src = js_name_to_path(name)
    with open(src, 'rb') as f:
        cs, errors = compile_coffeescript(f.read(), src)
        if errors:
            for line in errors:
                print (line)
            raise Exception('Failed to compile coffeescript'
                    ': %s'%src)
        return cs


def compiled_coffeescript(name, dynamic=False):
    import zipfile
    zipf = get_path('compiled_coffeescript.zip', allow_user_override=False)
    with zipfile.ZipFile(zipf, 'r') as zf:
        if dynamic:
            import json
            existing_hash = json.loads(zf.comment or '{}').get(name + '.js')
            if existing_hash is not None:
                import hashlib
                with open(js_name_to_path(name), 'rb') as f:
                    if existing_hash == hashlib.sha1(f.read()).hexdigest():
                        return zf.read(name + '.js')
            return _compile_coffeescript(name)
        else:
            return zf.read(name+'.js')


def load_hyphenator_dicts(hp_cache, lang, default_lang='en'):
    from calibre.utils.localization import lang_as_iso639_1
    import zipfile
    if not lang:
        lang = default_lang or 'en'

    def lang_name(l):
        l = l.lower()
        l = lang_as_iso639_1(l)
        if not l:
            l = 'en'
        l = {'en':'en-us', 'nb':'nb-no', 'el':'el-monoton'}.get(l, l)
        return l.lower().replace('_', '-')

    if not hp_cache:
        with zipfile.ZipFile(P('viewer/hyphenate/patterns.zip',
            allow_user_override=False), 'r') as zf:
            for pat in zf.namelist():
                raw = zf.read(pat).decode('utf-8')
                hp_cache[pat.partition('.')[0]] = raw

    if lang_name(lang) not in hp_cache:
        lang = lang_name(default_lang)

    lang = lang_name(lang)

    js = '\n\n'.join(hp_cache.itervalues())
    return js, lang


__builtin__.__dict__['P'] = get_path
__builtin__.__dict__['I'] = get_image_path
