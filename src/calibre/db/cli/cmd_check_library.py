#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2017, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import absolute_import, division, print_function, unicode_literals

readonly = False
version = 0  # change this if you change signature of implementation()


def implementation(db, notify_changes, *args):
    is_remote = notify_changes is not None
    is_remote


def option_parser(get_parser, args):
    pass


def main(opts, args, dbctx):
    raise NotImplementedError('TODO: implement this')
    return 0
