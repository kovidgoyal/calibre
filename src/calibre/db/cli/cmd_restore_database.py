#!/usr/bin/env python
# License: GPLv3 Copyright: 2017, Kovid Goyal <kovid at kovidgoyal.net>


from calibre import prints
from calibre.db.restore import Restore

readonly = False
version = 0  # change this if you change signature of implementation()
no_remote = True


def implementation(db, notify_changes, *args):
    raise NotImplementedError()


def option_parser(get_parser, args):
    parser = get_parser(
        _(
            '''\
%prog restore_database [options]

Restore this database from the metadata stored in OPF files in each
folder of the calibre library. This is useful if your metadata.db file
has been corrupted.

WARNING: This command completely regenerates your database. You will lose
all saved searches, user categories, plugboards, stored per-book conversion
settings, and custom recipes. Restored metadata will only be as accurate as
what is found in the OPF files.
    '''
        )
    )

    parser.add_option(
        '-r',
        '--really-do-it',
        default=False,
        action='store_true',
        help=_(
            'Really do the recovery. The command will not run '
            'unless this option is specified.'
        )
    )
    return parser


class Progress:

    def __init__(self):
        self.total = 1

    def __call__(self, msg, step):
        if msg is None:
            self.total = float(step)
        else:
            prints(msg, '...', '%d%%' % int(100 * (step / self.total)))


def main(opts, args, dbctx):
    if not opts.really_do_it:
        raise SystemExit(
            _('You must provide the %s option to do a'
              ' recovery') % '--really-do-it'
        )

    r = Restore(dbctx.library_path, progress_callback=Progress())
    r.start()
    r.join()

    if r.tb is not None:
        prints('Restoring database failed with error:')
        prints(r.tb)
    else:
        prints('Restoring database succeeded')
        prints('old database saved as', r.olddb)
        if r.errors_occurred:
            name = 'calibre_db_restore_report.txt'
            lopen('calibre_db_restore_report.txt',
                  'wb').write(r.report.encode('utf-8'))
            prints('Some errors occurred. A detailed report was ' 'saved to', name)

    return 0
