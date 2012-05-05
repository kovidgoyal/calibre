#!/usr/bin/env python
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
        if dev_path is not None:
            dev_path = os.path.join(os.path.abspath(
                os.path.dirname(dev_path)), 'resources')
            if suitable(dev_path):
                self.locations.insert(0, dev_path)
                self.default_path = dev_path

        user_path = os.path.join(config_dir, 'resources')
        self.user_path = None
        if suitable(user_path):
            self.locations.insert(0, user_path)
            self.user_path = user_path

    def __call__(self, path, allow_user_override=True):
        path = path.replace(os.sep, '/')
        ans = self.cache.get(path, None)
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

            self.cache[path] = ans

        return ans

_resolver = PathResolver()

def get_path(path, data=False, allow_user_override=True):
    fpath = _resolver(path, allow_user_override=allow_user_override)
    if data:
        with open(fpath, 'rb') as f:
            return f.read()
    return fpath

def get_image_path(path, data=False, allow_user_override=True):
    return get_path('images/'+path, data=data)

def _compile_coffeescript(name):
    from calibre.utils.serve_coffee import compile_coffeescript
    path = (u'/'.join(name.split('.'))) + '.coffee'
    d = os.path.dirname
    base = d(d(os.path.abspath(__file__)))
    src = os.path.join(base, path)
    with open(src, 'rb') as f:
        cs, errors = compile_coffeescript(f.read(), src)
        if errors:
            for line in errors:
                print (line)
            raise Exception('Failed to compile coffeescript'
                    ': %s'%src)
        return cs

def compiled_coffeescript(name, dynamic=False):
    if dynamic:
        return _compile_coffeescript(name)
    else:
        import zipfile
        zipf = get_path('compiled_coffeescript.zip', allow_user_override=False)
        try:
            with zipfile.ZipFile(zipf, 'r') as zf:
                return zf.read(name+'.js')
        except EnvironmentError:
            # zipfile does not exist, probably someone running with
            # CALIBRE_DEVELOP_FROM and an outdated binary install, so try to
            # compile from source
            if os.path.exists(zipf): raise
            return _compile_coffeescript(name)


__builtin__.__dict__['P'] = get_path
__builtin__.__dict__['I'] = get_image_path
