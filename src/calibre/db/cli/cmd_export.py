#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2017, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import absolute_import, division, print_function, unicode_literals

import os

from calibre.db.cli import integers_from_string
from calibre.db.errors import NoSuchFormat
from calibre.library.save_to_disk import (
    config, do_save_book_to_disk, get_formats, sanitize_args
)
from calibre.utils.formatter_functions import load_user_template_functions

readonly = True
version = 0  # change this if you change signature of implementation()


def implementation(db, notify_changes, action, *args):
    is_remote = notify_changes is not None
    if action == 'all_ids':
        return db.all_book_ids()
    if action == 'setup':
        book_id, formats = args
        mi = db.get_metadata(book_id)
        plugboards = db.pref('plugboards', {})
        formats = get_formats(db.formats(book_id), formats)
        return mi, plugboards, formats, db.library_id, db.pref(
            'user_template_functions', []
        )
    if action == 'cover':
        return db.cover(args[0])
    if action == 'fmt':
        book_id, fmt, dest = args
        if is_remote:
            return db.format(book_id, fmt)
        db.copy_format_to(book_id, fmt, dest)


def option_parser(get_parser, args):
    parser = get_parser(
        _(
            '''\
%prog export [options] ids

Export the books specified by ids (a comma separated list) to the filesystem.
The export operation saves all formats of the book, its cover and metadata (in
an opf file). You can get id numbers from the search command.
'''
        )
    )
    parser.add_option(
        '--all',
        default=False,
        action='store_true',
        help=_('Export all books in database, ignoring the list of ids.')
    )
    parser.add_option(
        '--to-dir',
        default='.',
        help=(
            _('Export books to the specified directory. Default is') + ' %default'
        )
    )
    parser.add_option(
        '--single-dir',
        default=False,
        action='store_true',
        help=_('Export all books into a single directory')
    )
    c = config()
    for pref in ['asciiize', 'update_metadata', 'write_opf', 'save_cover']:
        opt = c.get_option(pref)
        switch = '--dont-' + pref.replace('_', '-')
        parser.add_option(
            switch,
            default=True,
            action='store_false',
            help=opt.help + ' ' +
            _('Specifying this switch will turn '
              'this behavior off.'),
            dest=pref
        )

    for pref in ['timefmt', 'template', 'formats']:
        opt = c.get_option(pref)
        switch = '--' + pref
        parser.add_option(switch, default=opt.default, help=opt.help, dest=pref)

    for pref in ('replace_whitespace', 'to_lowercase'):
        opt = c.get_option(pref)
        switch = '--' + pref.replace('_', '-')
        parser.add_option(switch, default=False, action='store_true', help=opt.help)

    return parser


class DBProxy(object):

    # Proxy to allow do_save_book_to_disk() to work with remote database

    def __init__(self, dbctx):
        self.dbctx = dbctx

    def cover(self, book_id):
        return self.dbctx.run('export', 'cover', book_id)

    def copy_format_to(self, book_id, fmt, path):
        fdata = self.dbctx.run('export', 'fmt', book_id, fmt, path)
        if self.dbctx.is_remote:
            if fdata is None:
                raise NoSuchFormat(fmt)
            with lopen(path, 'wb') as f:
                f.write(fdata)


def export(opts, dbctx, book_id, dest, dbproxy, length, first):
    mi, plugboards, formats, library_id, template_funcs = dbctx.run(
        'export', 'setup', book_id, opts.formats
    )
    if dbctx.is_remote and first:
        load_user_template_functions(library_id, template_funcs)
    return do_save_book_to_disk(
        dbproxy, book_id, mi, plugboards, formats, dest, opts, length
    )


def main(opts, args, dbctx):
    if len(args) < 1 and not opts.all:
        raise SystemExit(_('You must specify some ids or the %s option') % '--all')
    if opts.all:
        book_ids = dbctx.run('export', 'all_ids')
    else:
        book_ids = set()
        for arg in args:
            book_ids |= set(integers_from_string(arg))
    dest = os.path.abspath(os.path.expanduser(opts.to_dir))
    dbproxy = DBProxy(dbctx)
    dest, opts, length = sanitize_args(dest, opts)
    for i, book_id in enumerate(book_ids):
        export(opts, dbctx, book_id, dest, dbproxy, length, i == 0)
    return 0
