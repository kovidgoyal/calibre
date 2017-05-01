#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2017, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import absolute_import, division, print_function, unicode_literals

import csv
import sys

readonly = False
version = 0  # change this if you change signature of implementation()


def implementation(db, notify_changes, *args):
    is_remote = notify_changes is not None
    is_remote


def option_parser(get_parser, args):
    pass


def _print_check_library_results(checker, check, as_csv=False, out=sys.stdout):
    attr = check[0]
    list = getattr(checker, attr, None)
    if list is None:
        return

    if as_csv:
        to_output = [(check[1], i[0], i[1]) for i in list]
        csv_print = csv.writer(out)
        for line in to_output:
            csv_print.writerow(line)

    else:
        print(check[1], file=out)
        for i in list:
            print('    %-40.40s - %-40.40s' % (i[0], i[1]), file=out)


def main(opts, args, dbctx):
    raise NotImplementedError('TODO: implement this')
    return 0
