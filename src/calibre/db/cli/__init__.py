#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2017, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import absolute_import, division, print_function, unicode_literals

import importlib


def module_for_cmd(cmd):
    return importlib.import_module('calibre.db.cli.cmd_' + cmd)


def integers_from_string(arg, include_last_inrange=False):
    for x in arg.split(','):
        y = tuple(map(int, x.split('-')))
        if len(y) > 1:
            for y in range(y[0], y[1] + int(bool(include_last_inrange))):
                yield y
        else:
            yield y[0]
