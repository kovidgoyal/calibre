#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2021, Kovid Goyal <kovid at kovidgoyal.net>


from .loader import dynamic_load
from .dbus_name_map import name_map, module_names

already_imported = {}
qt_modules = {}


def __getattr__(name):
    return dynamic_load(name, name_map, already_imported, qt_modules, module_names)
