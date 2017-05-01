#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2017, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import absolute_import, division, print_function, unicode_literals

import os

from calibre import prints
from calibre.ebooks.metadata.book.base import field_from_string
from calibre.ebooks.metadata.book.serialize import read_cover
from calibre.ebooks.metadata.opf import get_metadata
from calibre.srv.changes import metadata

readonly = False
version = 0  # change this if you change signature of implementation()


def implementation(db, notify_changes, action, *args):
    is_remote = notify_changes is not None
    if action == 'field_metadata':
        return db.field_metadata
    if action == 'opf':
        book_id, mi = args
        with db.write_lock:
            if not db.has_id(book_id):
                return
            changed_ids = db.set_metadata(book_id, mi, force_changes=True, allow_case_change=False)
            if is_remote:
                notify_changes(metadata(changed_ids))
            return db.get_metadata(book_id)
    if action == 'fields':
        book_id, fvals = args
        with db.write_lock:
            if not db.has_id(book_id):
                return
            mi = db.get_metadata(book_id)
            for field, val in fvals:
                if field.endswith('_index'):
                    sname = mi.get(field[:-6])
                    if sname:
                        mi.set(field[:-6], sname, extra=val)
                        if field == 'series_index':
                            mi.series_index = val  # extra has no effect for the builtin series field
                elif field == 'cover':
                    if is_remote:
                        mi.cover_data = None, val[1]
                    else:
                        mi.cover = val
                        read_cover(mi)
                else:
                    mi.set(field, val)
            changed_ids = db.set_metadata(book_id, mi, force_changes=True, allow_case_change=True)
            if is_remote:
                notify_changes(metadata(changed_ids))
            return db.get_metadata(book_id)


def option_parser(get_parser, args):
    parser = get_parser(
        _(
            '''
%prog set_metadata [options] id [/path/to/metadata.opf]

Set the metadata stored in the calibre database for the book identified by id
from the OPF file metadata.opf. id is an id number from the search command. You
can get a quick feel for the OPF format by using the --as-opf switch to the
show_metadata command. You can also set the metadata of individual fields with
the --field option. If you use the --field option, there is no need to specify
an OPF file.
'''
        )
    )
    parser.add_option(
        '-f',
        '--field',
        action='append',
        default=[],
        help=_(
            'The field to set. Format is field_name:value, for example: '
            '{0} tags:tag1,tag2. Use {1} to get a list of all field names. You '
            'can specify this option multiple times to set multiple fields. '
            'Note: For languages you must use the ISO639 language codes (e.g. '
            'en for English, fr for French and so on). For identifiers, the '
            'syntax is {0} {2}. For boolean (yes/no) fields use true and false '
            'or yes and no.'
        ).format('--field', '--list-fields', 'identifiers:isbn:XXXX,doi:YYYYY')
    )
    parser.add_option(
        '-l',
        '--list-fields',
        action='store_true',
        default=False,
        help=_(
            'List the metadata field names that can be used'
            ' with the --field option'
        )
    )
    return parser


def get_fields(dbctx):
    fm = dbctx.run('set_metadata', 'field_metadata')
    for key in sorted(fm.all_field_keys()):
        m = fm[key]
        if (key not in {'formats', 'series_sort', 'ondevice', 'path',
            'last_modified'} and m['is_editable'] and m['name']):
            yield key, m
            if m['datatype'] == 'series':
                si = m.copy()
                si['name'] = m['name'] + ' Index'
                si['datatype'] = 'float'
                yield key + '_index', si
    c = fm['cover'].copy()
    c['datatype'] = 'text'
    yield 'cover', c


def main(opts, args, dbctx):
    if opts.list_fields:
        ans = get_fields(dbctx)
        prints('%-40s' % _('Title'), _('Field name'), '\n')
        for key, m in ans:
            prints('%-40s' % m['name'], key)
        return 0

    def verify_int(x):
        try:
            int(x)
            return True
        except:
            return False

    if len(args) < 1 or not verify_int(args[0]):
        raise SystemExit(_(
            'You must specify a record id as the '
            'first argument'
        ))
    if len(args) < 2 and not opts.field:
        raise SystemExit(_('You must specify either a field or an opf file'))
    book_id = int(args[0])

    if len(args) > 1:
        opf = os.path.abspath(args[1])
        if not os.path.exists(opf):
            raise SystemExit(_('The OPF file %s does not exist') % opf)
        with lopen(opf, 'rb') as stream:
            mi = get_metadata(stream)[0]
        if mi.cover:
            mi.cover = os.path.join(os.path.dirname(opf), os.path.relpath(mi.cover, os.getcwdu()))
        final_mi = dbctx.run('set_metadata', 'opf', book_id, read_cover(mi))
        if not final_mi:
            raise SystemExit(_('No book with id: %s in the database') % book_id)

    if opts.field:
        fields = {k: v for k, v in get_fields(dbctx)}
        fields['title_sort'] = fields['sort']
        vals = {}
        for x in opts.field:
            field, val = x.partition(':')[::2]
            if field == 'sort':
                field = 'title_sort'
            if field not in fields:
                raise SystemExit(_('%s is not a known field' % field))
            if field == 'cover':
                val = dbctx.path(os.path.abspath(os.path.expanduser(val)))
            else:
                val = field_from_string(field, val, fields[field])
            vals[field] = val
        fvals = []
        for field, val in sorted(  # ensure series_index fields are set last
                vals.iteritems(), key=lambda k: 1 if k[0].endswith('_index') else 0):
            if field.endswith('_index'):
                try:
                    val = float(val)
                except Exception:
                    raise SystemExit('The value %r is not a valid series index' % val)
            fvals.append((field, val))

        final_mi = dbctx.run('set_metadata', 'fields', book_id, fvals)
        if not final_mi:
            raise SystemExit(_('No book with id: %s in the database') % book_id)

    prints(unicode(final_mi))
    return 0
