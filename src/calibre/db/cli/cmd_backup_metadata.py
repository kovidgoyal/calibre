#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2017, Kovid Goyal <kovid at kovidgoyal.net>


from calibre import prints

readonly = True
version = 0  # change this if you change signature of implementation()
no_remote = True


def implementation(db, notify_changes, *args):
    raise NotImplementedError()


def option_parser(get_parser, args):
    parser = get_parser(
        _(
            '''\
%prog backup_metadata [options]

Backup the metadata stored in the database into individual OPF files in each
books directory. This normally happens automatically, but you can run this
command to force re-generation of the OPF files, with the --all option.

Note that there is normally no need to do this, as the OPF files are backed up
automatically, every time metadata is changed.
'''
        )
    )
    parser.add_option(
        '--all',
        default=False,
        action='store_true',
        help=_(
            'Normally, this command only operates on books that have'
            ' out of date OPF files. This option makes it operate on all'
            ' books.'
        )
    )
    return parser


class BackupProgress(object):

    def __init__(self):
        self.total = 0
        self.count = 0

    def __call__(self, book_id, mi, ok):
        if mi is True:
            self.total = book_id
        else:
            self.count += 1
            prints(
                u'%.1f%% %s - %s' % ((self.count * 100) / float(self.total), book_id,
                                     getattr(mi, 'title', 'Unknown'))
            )


def main(opts, args, dbctx):
    db = dbctx.db
    book_ids = None
    if opts.all:
        book_ids = db.all_ids()
    db.dump_metadata(book_ids=book_ids, callback=BackupProgress())
    return 0
