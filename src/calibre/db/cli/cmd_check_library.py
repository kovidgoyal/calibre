#!/usr/bin/env python
# License: GPLv3 Copyright: 2017, Kovid Goyal <kovid at kovidgoyal.net>


import csv
import io
import sys

from calibre import prints
from calibre.db.legacy import LibraryDatabase
from calibre.library.check_library import CHECKS, CheckLibrary

readonly = False
version = 0  # change this if you change signature of implementation()
no_remote = True


def implementation(db, notify_changes, *args):
    raise NotImplementedError()


def option_parser(get_parser, args):
    parser = get_parser(
        _(
            '''\
%prog check_library [options]

Perform some checks on the filesystem representing a library. Reports are {0}
'''
        ).format(', '.join([c[0] for c in CHECKS]))
    )

    parser.add_option(
        '-c', '--csv', default=False, action='store_true', help=_('Output in CSV')
    )

    parser.add_option(
        '-r',
        '--report',
        default=None,
        dest='report',
        help=_("Comma-separated list of reports.\n"
               "Default: all")
    )

    parser.add_option(
        '-e',
        '--ignore_extensions',
        default=None,
        dest='exts',
        help=_("Comma-separated list of extensions to ignore.\n"
               "Default: all")
    )

    parser.add_option(
        '-n',
        '--ignore_names',
        default=None,
        dest='names',
        help=_("Comma-separated list of names to ignore.\n"
               "Default: all")
    )
    parser.add_option(
        '--vacuum-fts-db',
        default=False,
        action='store_true',
        help=_('Vacuum the full text search database. This can be very slow and memory intensive, depending on the size of the database.')
    )

    return parser


def _print_check_library_results(checker, check, as_csv=False, out=sys.stdout):
    attr = check[0]
    list = getattr(checker, attr, None)
    if list is None:
        return

    if as_csv:
        to_output = [(check[1], i[0], i[1]) for i in list]
        buf = io.StringIO(newline='')
        csv_print = csv.writer(buf)
        for line in to_output:
            csv_print.writerow(line)
        out.write(buf.getvalue())
    else:
        print(check[1], file=out)
        for i in list:
            print('    %-40.40s - %-40.40s' % (i[0], i[1]), file=out)


def main(opts, args, dbctx):
    if opts.report is None:
        checks = CHECKS
    else:
        checks = []
        for r in opts.report.split(','):
            found = False
            for c in CHECKS:
                if c[0] == r:
                    checks.append(c)
                    found = True
                    break
            if not found:
                prints(_('Unknown report check'), r)
                return 1

    if opts.names is None:
        names = []
    else:
        names = [f.strip() for f in opts.names.split(',') if f.strip()]
    if opts.exts is None:
        exts = []
    else:
        exts = [f.strip() for f in opts.exts.split(',') if f.strip()]

    if not LibraryDatabase.exists_at(dbctx.library_path):
        prints('No library found at', dbctx.library_path, file=sys.stderr)
        raise SystemExit(1)

    db = LibraryDatabase(dbctx.library_path)
    prints(_('Vacuuming database...'))
    db.new_api.vacuum(opts.vacuum_fts_db)
    checker = CheckLibrary(dbctx.library_path, db)
    checker.scan_library(names, exts)
    for check in checks:
        _print_check_library_results(checker, check, as_csv=opts.csv)

    return 0
