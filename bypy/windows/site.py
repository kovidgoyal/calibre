#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
# License: GPLv3 Copyright: 2015, Kovid Goyal <kovid at kovidgoyal.net>

import builtins
import os
import sys
from importlib import import_module
from importlib.util import spec_from_file_location
from importlib.machinery import EXTENSION_SUFFIXES

import _sitebuiltins

pyd_items = None
extension_suffixes = sorted(EXTENSION_SUFFIXES, key=len, reverse=True)
USER_SITE = None


def remove_extension_suffix(name):
    for q in extension_suffixes:
        if name.endswith(q):
            return name[:-len(q)]


class PydImporter:

    def find_spec(self, fullname, path, target=None):
        global pyd_items
        if pyd_items is None:
            pyd_items = {}
            dlls_dir = os.path.join(sys.app_dir, 'app', 'bin')
            for x in os.listdir(dlls_dir):
                lx = x.lower()
                if lx.endswith('.pyd'):
                    pyd_items[remove_extension_suffix(lx)] = os.path.abspath(os.path.join(dlls_dir, x))
        q = fullname.lower()
        path = pyd_items.get(q)
        if path is not None:
            return spec_from_file_location(fullname, path)

    def invalidate_caches(self):
        global pyd_items
        pyd_items = None


def run_entry_point():
    bname, mod, func = sys.calibre_basename, sys.calibre_module, sys.calibre_function
    sys.argv[0] = bname + '.exe'
    pmod = import_module(mod)
    return getattr(pmod, func)()


def set_helper():
    builtins.help = _sitebuiltins._Helper()


def set_quit():
    eof = 'Ctrl-Z plus Return'
    builtins.quit = _sitebuiltins.Quitter('quit', eof)
    builtins.exit = _sitebuiltins.Quitter('exit', eof)


def main():
    sys.meta_path.insert(0, PydImporter())
    os.add_dll_directory(os.path.abspath(os.path.join(sys.app_dir, 'app', 'bin')))

    import linecache

    def fake_getline(filename, lineno, module_globals=None):
        return ''

    linecache.orig_getline = linecache.getline
    linecache.getline = fake_getline

    set_helper()
    set_quit()

    return run_entry_point()


if __name__ == '__main__':
    try:
        main()
    except Exception:
        if sys.gui_app and sys.excepthook == sys.__excepthook__:
            import traceback
            import calibre_os_module
            calibre_os_module.gui_error_message(
                f"Unhandled exception running {sys.calibre_basename}",
                traceback.format_exc())
        raise
