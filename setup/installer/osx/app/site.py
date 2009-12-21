"""
Append module search paths for third-party packages to sys.path.

This is stripped down and customized for use in py2app applications
"""

import sys
import os

def makepath(*paths):
    dir = os.path.abspath(os.path.join(*paths))
    return dir, os.path.normcase(dir)

def abs__file__():
    """Set all module __file__ attribute to an absolute path"""
    for m in sys.modules.values():
        if hasattr(m, '__loader__'):
            continue   # don't mess with a PEP 302-supplied __file__
        try:
            m.__file__ = os.path.abspath(m.__file__)
        except AttributeError:
            continue

# This ensures that the initial path provided by the interpreter contains
# only absolute pathnames, even if we're running from the build directory.
L = []
_dirs_in_sys_path = {}
dir = dircase = None  # sys.path may be empty at this point
for dir in sys.path:
    # Filter out duplicate paths (on case-insensitive file systems also
    # if they only differ in case); turn relative paths into absolute
    # paths.
    dir, dircase = makepath(dir)
    if not dircase in _dirs_in_sys_path:
        L.append(dir)
        _dirs_in_sys_path[dircase] = 1
sys.path[:] = L
del dir, dircase, L
_dirs_in_sys_path = None

def _init_pathinfo():
    global _dirs_in_sys_path
    _dirs_in_sys_path = d = {}
    for dir in sys.path:
        if dir and not os.path.isdir(dir):
            continue
        dir, dircase = makepath(dir)
        d[dircase] = 1

def addsitedir(sitedir):
    global _dirs_in_sys_path
    if _dirs_in_sys_path is None:
        _init_pathinfo()
        reset = 1
    else:
        reset = 0
    sitedir, sitedircase = makepath(sitedir)
    if not sitedircase in _dirs_in_sys_path:
        sys.path.append(sitedir)        # Add path component
    try:
        names = os.listdir(sitedir)
    except os.error:
        return
    names.sort()
    for name in names:
        if name[-4:] == os.extsep + "pth":
            addpackage(sitedir, name)
    if reset:
        _dirs_in_sys_path = None

def addpackage(sitedir, name):
    global _dirs_in_sys_path
    if _dirs_in_sys_path is None:
        _init_pathinfo()
        reset = 1
    else:
        reset = 0
    fullname = os.path.join(sitedir, name)
    try:
        f = open(fullname)
    except IOError:
        return
    while 1:
        dir = f.readline()
        if not dir:
            break
        if dir[0] == '#':
            continue
        if dir.startswith("import"):
            exec dir
            continue
        if dir[-1] == '\n':
            dir = dir[:-1]
        dir, dircase = makepath(sitedir, dir)
        if not dircase in _dirs_in_sys_path and os.path.exists(dir):
            sys.path.append(dir)
            _dirs_in_sys_path[dircase] = 1
    if reset:
        _dirs_in_sys_path = None


sys.setdefaultencoding('utf-8')

#
# Remove sys.setdefaultencoding() so that users cannot change the
# encoding after initialization.  The test for presence is needed when
# this module is run as a script, because this code is executed twice.
#
if hasattr(sys, "setdefaultencoding"):
    del sys.setdefaultencoding

def run_entry_point():
    bname, mod, func = sys.calibre_basename, sys.calibre_module, sys.calibre_function
    sys.argv[0] = bname
    pmod = __import__(mod, fromlist=[1], level=0)
    return getattr(pmod, func)()

def add_calibre_vars(base):
    sys.frameworks_dir = os.path.join(os.path.dirname(base), 'Frameworks')
    sys.resources_location = os.path.abspath(os.path.join(base, 'resources'))
    sys.extensions_location = os.path.join(sys.frameworks_dir, 'plugins')
    sys.binaries_path = os.path.join(os.path.dirname(base), 'MacOS')
    sys.console_binaries_path = os.path.join(os.path.dirname(base),
        'console.app', 'Contents', 'MacOS')

    dv = os.environ.get('CALIBRE_DEVELOP_FROM', None)
    if dv and os.path.exists(dv):
        sys.path.insert(0, os.path.abspath(dv))


def main():
    global __file__
    base = sys.resourcepath

    sys.frozen = 'macosx_app'
    sys.new_app_bundle = True
    abs__file__()

    add_calibre_vars(base)
    addsitedir(sys.site_packages)


    for arg in list(sys.argv[1:]):
        if arg.startswith('-psn'):
            sys.argv.remove(arg)

    return run_entry_point()


