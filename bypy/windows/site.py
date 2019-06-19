#!/usr/bin/env python2
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import sys
import os
import imp

class PydImporter(object):

    __slots__ = ('items', 'description')

    def __init__(self):
        self.items = None
        self.description = ('.pyd', 'rb', imp.C_EXTENSION)

    def find_module(self, fullname, path=None):
        if self.items is None:
            dlls_dir = os.path.join(sys.app_dir, 'app', 'DLLs')
            items = self.items = {}
            for x in os.listdir(dlls_dir):
                lx = x.lower()
                if lx.endswith(b'.pyd'):
                    items[lx[:-4]] = os.path.abspath(os.path.join(dlls_dir, x))
        return self if fullname.lower() in self.items else None

    def load_module(self, fullname):
        m = sys.modules.get(fullname)
        if m is not None:
            return m
        try:
            path = self.items[fullname.lower()]
        except KeyError:
            raise ImportError('The native code module %s seems to have disappeared from self.items' % fullname)
        package, name = fullname.rpartition(b'.')[::2]
        m = imp.load_module(fullname, None, path, self.description)  # This inserts the module into sys.modules itself
        m.__loader__ = self
        m.__package__ = package or None
        return m

def abs__file__():
    """Set all module __file__ attribute to an absolute path"""
    for m in sys.modules.values():
        if hasattr(m, '__loader__'):
            continue   # don't mess with a PEP 302-supplied __file__
        try:
            m.__file__ = os.path.abspath(m.__file__)
        except AttributeError:
            continue

def aliasmbcs():
    import locale, codecs
    enc = locale.getdefaultlocale()[1]
    if enc.startswith('cp'):            # "cp***" ?
        try:
            codecs.lookup(enc)
        except LookupError:
            import encodings
            encodings._cache[enc] = encodings._unknown
            encodings.aliases.aliases[enc] = 'mbcs'

def add_calibre_vars():
    sys.new_app_layout = 1
    sys.resources_location = os.path.join(sys.app_dir, 'app', 'resources')
    sys.extensions_location = os.path.join(sys.app_dir, 'app', 'DLLs')

    dv = os.environ.get('CALIBRE_DEVELOP_FROM', None)
    if dv and os.path.exists(dv):
        sys.path.insert(0, os.path.abspath(dv))

def run_entry_point():
    bname, mod, func = sys.calibre_basename, sys.calibre_module, sys.calibre_function
    sys.argv[0] = bname+'.exe'
    pmod = __import__(mod, fromlist=[1], level=0)
    return getattr(pmod, func)()

def main():
    sys.frozen = 'windows_exe'
    sys.setdefaultencoding('utf-8')
    aliasmbcs()

    sys.meta_path.insert(0, PydImporter())
    sys.path_importer_cache.clear()

    import linecache
    def fake_getline(filename, lineno, module_globals=None):
        return ''
    linecache.orig_getline = linecache.getline
    linecache.getline = fake_getline

    abs__file__()

    add_calibre_vars()

    # Needed for pywintypes to be able to load its DLL
    sys.path.append(os.path.join(sys.app_dir, 'app', 'DLLs'))

    return run_entry_point()
