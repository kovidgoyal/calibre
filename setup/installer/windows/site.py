#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import sys
import os
import zipimport
import _memimporter

DEBUG_ZIPIMPORT = False

class ZipExtensionImporter(zipimport.zipimporter):
    '''
    Taken, with thanks, from the py2exe source code
    '''

    def __init__(self, *args, **kwargs):
        zipimport.zipimporter.__init__(self, *args, **kwargs)
        # We know there are no dlls in the zip file, so dont set findproc
        # (performance optimization)
        #_memimporter.set_find_proc(self.locate_dll_image)

    def find_module(self, fullname, path=None):
        result = zipimport.zipimporter.find_module(self, fullname, path)
        if result:
            return result
        fullname = fullname.replace(".", "\\")
        if (fullname + '.pyd') in self._files:
            return self
        return None

    def locate_dll_image(self, name):
        # A callback function for_memimporter.import_module.  Tries to
        # locate additional dlls.  Returns the image as Python string,
        # or None if not found.
        if name in self._files:
            return self.get_data(name)
        return None

    def load_module(self, fullname):
        if sys.modules.has_key(fullname):
            mod = sys.modules[fullname]
            if DEBUG_ZIPIMPORT:
                sys.stderr.write("import %s # previously loaded from zipfile %s\n" % (fullname, self.archive))
            return mod
        try:
            return zipimport.zipimporter.load_module(self, fullname)
        except zipimport.ZipImportError:
            pass
        initname = "init" + fullname.split(".")[-1] # name of initfunction
        filename = fullname.replace(".", "\\")
        path = filename + '.pyd'
        if path in self._files:
            if DEBUG_ZIPIMPORT:
                sys.stderr.write("# found %s in zipfile %s\n" % (path, self.archive))
            code = self.get_data(path)
            mod = _memimporter.import_module(code, initname, fullname, path)
            mod.__file__ = "%s\\%s" % (self.archive, path)
            mod.__loader__ = self
            if DEBUG_ZIPIMPORT:
                sys.stderr.write("import %s # loaded from zipfile %s\n" % (fullname, mod.__file__))
            return mod
        raise zipimport.ZipImportError, "can't find module %s" % fullname

    def __repr__(self):
        return "<%s object %r>" % (self.__class__.__name__, self.archive)


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
    sys.resources_location = os.path.join(sys.app_dir, 'resources')
    sys.extensions_location = os.path.join(sys.app_dir, 'plugins2')

    dv = os.environ.get('CALIBRE_DEVELOP_FROM', None)
    if dv and os.path.exists(dv):
        sys.path.insert(0, os.path.abspath(dv))

def makepath(*paths):
    dir = os.path.abspath(os.path.join(*paths))
    return dir, os.path.normcase(dir)

def run_entry_point():
    bname, mod, func = sys.calibre_basename, sys.calibre_module, sys.calibre_function
    sys.argv[0] = bname+'.exe'
    pmod = __import__(mod, fromlist=[1], level=0)
    return getattr(pmod, func)()

def main():
    sys.frozen = 'windows_exe'
    sys.setdefaultencoding('utf-8')
    aliasmbcs()

    sys.path_hooks.insert(0, ZipExtensionImporter)
    sys.path_importer_cache.clear()

    import linecache
    def fake_getline(filename, lineno, module_globals=None):
        return ''
    linecache.orig_getline = linecache.getline
    linecache.getline = fake_getline

    abs__file__()

    add_calibre_vars()

    # Needed for pywintypes to be able to load its DLL
    sys.path.append(os.path.join(sys.app_dir, 'DLLs'))

    return run_entry_point()


