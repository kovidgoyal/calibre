#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2021, Kovid Goyal <kovid at kovidgoyal.net>


from .dbus_name_map import module_names, name_map
from .loader import dynamic_load

already_imported = {}
qt_modules = {}


def __getattr__(name):
    return dynamic_load(name, name_map, already_imported, qt_modules, module_names)
