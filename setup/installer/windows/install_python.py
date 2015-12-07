#!/usr/bin/env python2
# vim:fileencoding=utf-8
# Copyright: 2015, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import (unicode_literals, division, absolute_import,
                        print_function)
import sys
import re
import shutil
import os
import glob

known_extensions = {
    'bz2.pyd',
    'pyexpat.pyd',
    'select.pyd',
    'unicodedata.pyd',
    'winsound.pyd',
    '_elementtree.pyd',
    '_bsddb.pyd',
    '_socket.pyd',
    '_ssl.pyd',
    '_testcapi.pyd',
    '_tkinter.pyd',
    '_msi.pyd',
    '_ctypes.pyd',
    '_ctypes_test.pyd',
    '_sqlite3.pyd',
    '_hashlib.pyd',
    '_multiprocessing.pyd'
}


def main():
    if len(sys.argv) != 2:
        raise SystemExit('Usage: python %s install_dir' % sys.argv[0])
    install_dir = os.path.abspath(os.path.join(os.path.expanduser(
        sys.argv[-1]), 'python'))
    exedir = os.path.dirname(os.path.abspath(sys.executable))
    cwd = exedir
    while not cwd.lower().endswith('pcbuild'):
        b = cwd
        cwd = os.path.dirname(cwd)
        if b == cwd or not cwd:
            raise SystemExit(
                'python not running form the build directory')
    os.chdir(os.path.dirname(cwd))

    # Clear out install_dir, preserving site-packages
    has_sp = False
    if os.path.exists(install_dir):
        sp_dir = os.path.join(install_dir, 'Lib', 'site-packages')
        has_sp = os.path.exists(sp_dir)
        if has_sp:
            sp_temp = os.path.join(install_dir, 'site-packages')
            os.rename(sp_dir, sp_temp)
        for x in os.listdir(install_dir):
            if x != 'site-packages':
                path = os.path.join(install_dir, x)
                (shutil.rmtree if os.path.isdir(path) else os.remove)(path)
    else:
        os.mkdir(install_dir)

    # Copy executables
    for exe in (os.path.join(exedir, x + '.exe')
                for x in 'python pythonw'.split()):
        shutil.copy2(exe, install_dir)

    # Copy extensions
    dll_dir = os.path.join(install_dir, 'DLLs')
    os.mkdir(dll_dir)
    found_extensions = set()
    for pyd in glob.glob(os.path.join(exedir, '*.pyd')):
        found_extensions.add(os.path.basename(pyd))
        shutil.copy2(pyd, dll_dir)
    for pyd in known_extensions - found_extensions:
        print('WARNING: Extension %s not found, ignoring' % pyd)
    have_tcl = '_tkinter.pyd' in found_extensions

    # Copy dlls
    for dll in glob.glob(os.path.join(exedir, '*.dll')):
        if os.path.basename(dll).startswith('python'):
            shutil.copy2(dll, install_dir)
        else:
            shutil.copy2(dll, dll_dir)

    # Copy import libraries
    lib_dir = os.path.join(install_dir, 'libs')
    os.mkdir(lib_dir)
    for lib in glob.glob(os.path.join(exedir, '*.lib')):
        shutil.copy2(lib, lib_dir)

    # Copy the headers
    include_dir = os.path.join(install_dir, 'include')
    os.mkdir(include_dir)
    shutil.copy2(os.path.join('PC', 'pyconfig.h'), include_dir)
    for x in glob.glob(os.path.join('Include', '*.h')):
        shutil.copy2(x, include_dir)

    # Make the Scripts dir
    os.mkdir(os.path.join(install_dir, 'Scripts'))

    # Copy the python modules in Lib
    ignored_dirs = frozenset('pydoc_data test tests lib2to3 ensurepip'.split())
    if not have_tcl:
        ignored_dirs |= frozenset(('lib-tk', 'idlelib', 'Icons'))

    def ignore_in_lib(basedir, items):
        ignored = set()
        for item in items:
            is_dir = os.path.isdir(os.path.join(basedir, item))
            if (is_dir and (
                    item in ignored_dirs or item.startswith('plat-'))) or \
               (not is_dir and item.rpartition('.')[-1].lower() != 'py'):
                ignored.add(item)
        return ignored

    shutil.copytree('Lib', os.path.join(install_dir, 'Lib'),
                    ignore=ignore_in_lib)
    if has_sp:
        shutil.rmtree(sp_dir)
        os.rename(sp_temp, sp_dir)

    with open(os.path.join(install_dir, 'Lib', 'mimetypes.py'), 'r+b') as f:
        raw = f.read()
        f.seek(0), f.truncate(0)
        raw, num = re.subn(br'try:.*?import\s+_winreg.*?None', br'_winreg = None', raw, count=1, flags=re.DOTALL)
        if num != 1:
            raise SystemExit('Failed to patch mimetypes.py')
        f.write(raw)

    print('python installed to:', install_dir)

if __name__ == '__main__':
    main()
