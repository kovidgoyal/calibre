#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2017, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import absolute_import, division, print_function, unicode_literals

from calibre import prints
from calibre.db.cli import integers_from_string
from calibre.srv.changes import formats_added

readonly = False
version = 0  # change this if you change signature of implementation()


def implementation(db, notify_changes, book_id, only_fmts):
    if book_id is None:
        return db.all_book_ids()
    with db.write_lock:
        if db.has_id(book_id):
            db.embed_metadata((book_id,), only_fmts=only_fmts)
            formats_added({book_id: db.formats(book_id)})
            return db.field_for('title', book_id)


def option_parser(get_parser, args):
    parser = get_parser(_(
'''
%prog embed_metadata [options] book_id

Update the metadata in the actual book files stored in the calibre library from
the metadata in the calibre database.  Normally, metadata is updated only when
exporting files from calibre, this command is useful if you want the files to
be updated in place. Note that different file formats support different amounts
of metadata. You can use the special value 'all' for book_id to update metadata
in all books. You can also specify many book ids separated by spaces and id ranges
separated by hyphens. For example: %prog embed_metadata 1 2 10-15 23'''))
    parser.add_option('-f', '--only-formats', action='append', default=[], help=_(
        'Only update metadata in files of the specified format. Specify it multiple'
        ' times for multiple formats. By default, all formats are updated.'))
    return parser


def main(opts, args, dbctx):
    ids = set()
    for arg in args:
        if arg == 'all':
            ids = None
            break
        ids |= set(integers_from_string(arg))
    only_fmts = opts.only_formats or None
    if ids is None:
        ids = dbctx.run('embed_metadata', None, None)

    def progress(i, title):
        prints(_('Processed {0} ({1} of {2})').format(title, i, len(ids)))

    for i, book_id in enumerate(ids):
        title = dbctx.run('embed_metadata', book_id, only_fmts)
        progress(i+1, title or _('No book with id: {}').format(book_id))

    return 0
