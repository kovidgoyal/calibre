#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2017, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import absolute_import, division, print_function, unicode_literals

import importlib


def module_for_cmd(cmd):
    return importlib.import_module('calibre.db.cli.cmd_' + cmd)
