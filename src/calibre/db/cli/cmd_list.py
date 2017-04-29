#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2017, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import absolute_import, division, print_function, unicode_literals

import json
import os
import sys
import unicodedata
from textwrap import TextWrapper

from calibre import prints
from calibre.ebooks.metadata import authors_to_string
from calibre.utils.date import isoformat

readonly = True
FIELDS = {
    'title', 'authors', 'author_sort', 'publisher', 'rating', 'timestamp', 'size',
    'tags', 'comments', 'series', 'series_index', 'formats', 'isbn', 'uuid',
    'pubdate', 'cover', 'last_modified', 'identifiers', 'languages'
}


def formats(db, book_id):
    for fmt in db.formats(book_id, verify_formats=False):
        path = db.format_abspath(book_id, fmt)
        if path:
            yield path.replace(os.sep, '/')


def cover(db, book_id):
    return db.format_abspath(book_id, '__COVER_INTERNAL__')


def implementation(
    db, notify_changes, fields, sort_by, ascending, search_text, limit
):
    is_remote = notify_changes is not None
    with db.safe_read_lock:
        fm = db.field_metadata
        afields = set(FIELDS) | {'id'}
        for k in fm.custom_field_keys():
            afields.add('*' + k[1:])
        if 'all' in fields:
            fields = sorted(afields)
        sort_by = sort_by or 'id'
        if sort_by not in afields:
            return 'Unknown sort field: {}'.format(sort_by)
        if not set(fields).issubset(afields):
            return 'Unknown fields: {}'.format(', '.join(set(fields) - afields))
        if search_text:
            book_ids = db.multisort([(sort_by, ascending)],
                                    ids_to_sort=db.search(search_text))
        else:
            book_ids = db.multisort([(sort_by, ascending)])
        if limit > -1:
            book_ids = book_ids[:limit]
        data = {}
        metadata = {}
        for field in fields:
            if field in 'id':
                continue
            if field == 'isbn':
                x = db.all_field_for('identifiers', book_ids, default_value={})
                data[field] = {k: v.get('isbn') or '' for k, v in x.iteritems()}
                continue
            field = field.replace('*', '#')
            metadata[field] = fm[field]
            if not is_remote:
                if field == 'formats':
                    data[field] = {k: list(formats(db, k)) for k in book_ids}
                    continue
                if field == 'cover':
                    data[field] = {k: cover(db, k) for k in book_ids}
                    continue
            data[field] = db.all_field_for(field, book_ids)
    return {'book_ids': book_ids, "data": data, 'metadata': metadata, 'fields':fields}


def stringify(data, metadata, for_machine):
    for field, m in metadata.iteritems():
        if field == 'authors':
            data[field] = {
                k: authors_to_string(v)
                for k, v in data[field].iteritems()
            }
        else:
            dt = m['datatype']
            if dt == 'datetime':
                data[field] = {
                    k: isoformat(v, as_utc=for_machine) if v else 'None'
                    for k, v in data[field].iteritems()
                }
            elif not for_machine:
                ism = m['is_multiple']
                if ism:
                    data[field] = {
                        k: ism['list_to_ui'].join(v)
                        for k, v in data[field].iteritems()
                    }
                    if field == 'formats':
                        data[field] = {
                            k: '[' + v + ']'
                            for k, v in data[field].iteritems()
                        }


def as_machine_data(book_ids, data, metadata):
    for book_id in book_ids:
        ans = {'id': book_id}
        for field, val_map in data.iteritems():
            val = val_map.get(book_id)
            if val is not None:
                ans[field.replace('#', '*')] = val
        yield ans


def prepare_output_table(fields, book_ids, data, metadata):
    ans = []
    u = type('')
    for book_id in book_ids:
        row = []
        ans.append(row)
        for field in fields:
            if field == 'id':
                row.append(u(book_id))
                continue
            val = data.get(field.replace('*', '#'), {}).get(book_id)
            row.append(u(val).replace('\n', ' '))
    return ans


def do_list(
    dbctx,
    fields,
    afields,
    sort_by,
    ascending,
    search_text,
    line_width,
    separator,
    prefix,
    limit,
    for_machine=False
):
    if sort_by is None:
        ascending = True
    ans = dbctx.run('list', fields, sort_by, ascending, search_text, limit)
    try:
        book_ids, data, metadata = ans['book_ids'], ans['data'], ans['metadata']
    except TypeError:
        raise SystemExit(ans)
    fields = list(ans['fields'])
    try:
        fields.remove('id')
    except ValueError:
        pass
    fields = ['id'] + fields
    stringify(data, metadata, for_machine)
    if for_machine:
        json.dump(
            list(as_machine_data(book_ids, data, metadata)),
            sys.stdout,
            indent=2,
            sort_keys=True
        )
        return
    from calibre.utils.terminal import ColoredStream, geometry

    output_table = prepare_output_table(fields, book_ids, data, metadata)
    widths = list(map(lambda x: 0, fields))

    def chr_width(x):
        return 1 + unicodedata.east_asian_width(x).startswith('W')

    def str_width(x):
        return sum(map(chr_width, x))

    for record in output_table:
        for j in range(len(fields)):
            widths[j] = max(widths[j], str_width(record[j]))

    screen_width = geometry()[0] if line_width < 0 else line_width
    if not screen_width:
        screen_width = 80
    field_width = screen_width // len(fields)
    base_widths = map(lambda x: min(x + 1, field_width), widths)

    while sum(base_widths) < screen_width:
        adjusted = False
        for i in range(len(widths)):
            if base_widths[i] < widths[i]:
                base_widths[i] += min(
                    screen_width - sum(base_widths), widths[i] - base_widths[i]
                )
                adjusted = True
                break
        if not adjusted:
            break

    widths = list(base_widths)
    titles = map(
        lambda x, y: '%-*s%s' % (x - len(separator), y, separator), widths,
        fields
    )
    with ColoredStream(sys.stdout, fg='green'):
        prints(''.join(titles))

    wrappers = [TextWrapper(x - 1).wrap if x > 1 else lambda y: y for x in widths]

    for record in output_table:
        text = [
            wrappers[i](record[i]) for i, field in enumerate(fields)
        ]
        lines = max(map(len, text))
        for l in range(lines):
            for i, field in enumerate(text):
                ft = text[i][l] if l < len(text[i]) else u''
                sys.stdout.write(ft.encode('utf-8'))
                if i < len(text) - 1:
                    filler = (u'%*s' % (widths[i] - str_width(ft) - 1, u''))
                    sys.stdout.write((filler + separator).encode('utf-8'))
            print()


def option_parser(get_parser):
    parser = get_parser(
        _(
            '''\
%prog list [options]

List the books available in the calibre database.
'''
        )
    )
    parser.add_option(
        '-f',
        '--fields',
        default='title,authors',
        help=_(
            'The fields to display when listing books in the'
            ' database. Should be a comma separated list of'
            ' fields.\nAvailable fields: %s\nDefault: %%default. The'
            ' special field "all" can be used to select all fields.'
            ' In addition to the builtin fields above, custom fields are'
            ' also available as *field_name, for example, for a custom field'
            ' #rating, use the name: *rating'
        ) % ', '.join(sorted(FIELDS))
    )
    parser.add_option(
        '--sort-by',
        default=None,
        help=_(
            'The field by which to sort the results.\nAvailable fields: {0}\nDefault: {1}'
        ).format(', '.join(sorted(FIELDS)), 'id')
    )
    parser.add_option(
        '--ascending',
        default=False,
        action='store_true',
        help=_('Sort results in ascending order')
    )
    parser.add_option(
        '-s',
        '--search',
        default=None,
        help=_(
            'Filter the results by the search query. For the format of the search query,'
            ' please see the search related documentation in the User Manual. Default is to do no filtering.'
        )
    )
    parser.add_option(
        '-w',
        '--line-width',
        default=-1,
        type=int,
        help=_(
            'The maximum width of a single line in the output. Defaults to detecting screen size.'
        )
    )
    parser.add_option(
        '--separator',
        default=' ',
        help=_('The string used to separate fields. Default is a space.')
    )
    parser.add_option(
        '--prefix',
        default=None,
        help=_(
            'The prefix for all file paths. Default is the absolute path to the library folder.'
        )
    )
    parser.add_option(
        '--limit',
        default=-1,
        type=int,
        help=_('The maximum number of results to display. Default: all')
    )
    parser.add_option(
        '--for-machine',
        default=False,
        action='store_true',
        help=_(
            'Generate output in JSON format, which is more suitable for machine parsing. Causes the line width and separator options to be ignored.'
        )
    )
    return parser


def main(opts, args, dbctx):
    afields = set(FIELDS) | {'id'}
    if opts.fields.strip():
        fields = [str(f.strip().lower()) for f in opts.fields.split(',')]
    else:
        fields = []

    do_list(
        dbctx,
        fields,
        afields,
        opts.sort_by,
        opts.ascending,
        opts.search,
        opts.line_width,
        opts.separator,
        opts.prefix,
        opts.limit,
        for_machine=opts.for_machine
    )
    return 0
