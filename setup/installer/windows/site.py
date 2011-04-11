#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import sys, os, linecache


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
    sys.extensions_location = os.path.join(sys.app_dir, 'plugins')

    dv = os.environ.get('CALIBRE_DEVELOP_FROM', None)
    if dv and os.path.exists(dv):
        sys.path.insert(0, os.path.abspath(dv))

def makepath(*paths):
    dir = os.path.abspath(os.path.join(*paths))
    return dir, os.path.normcase(dir)

def addpackage(sitedir, name):
    """Process a .pth file within the site-packages directory:
       For each line in the file, either combine it with sitedir to a path,
       or execute it if it starts with 'import '.
    """
    fullname = os.path.join(sitedir, name)
    try:
        f = open(fullname, "rU")
    except IOError:
        return
    with f:
        for line in f:
            if line.startswith("#"):
                continue
            if line.startswith(("import ", "import\t")):
                exec line
                continue
            line = line.rstrip()
            dir, dircase = makepath(sitedir, line)
            if os.path.exists(dir):
                sys.path.append(dir)


def addsitedir(sitedir):
    """Add 'sitedir' argument to sys.path if missing and handle .pth files in
    'sitedir'"""
    sitedir, sitedircase = makepath(sitedir)
    try:
        names = os.listdir(sitedir)
    except os.error:
        return
    dotpth = os.extsep + "pth"
    names = [name for name in names if name.endswith(dotpth)]
    for name in sorted(names):
        addpackage(sitedir, name)

def run_entry_point():
    bname, mod, func = sys.calibre_basename, sys.calibre_module, sys.calibre_function
    sys.argv[0] = bname+'.exe'
    pmod = __import__(mod, fromlist=[1], level=0)
    return getattr(pmod, func)()

def main():
    sys.frozen = 'windows_exe'
    sys.setdefaultencoding('utf-8')
    aliasmbcs()

    def fake_getline(filename, lineno, module_globals=None):
        return ''
    linecache.orig_getline = linecache.getline
    linecache.getline = fake_getline

    abs__file__()

    addsitedir(os.path.join(sys.app_dir, 'pydlib'))

    add_calibre_vars()

    return run_entry_point()


