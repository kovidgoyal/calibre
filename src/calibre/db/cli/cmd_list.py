#!/usr/bin/env python
# License: GPLv3 Copyright: 2017, Kovid Goyal <kovid at kovidgoyal.net>


import json
import os
import sys
from textwrap import TextWrapper

from calibre.db.cli.utils import str_width
from calibre.ebooks.metadata import authors_to_string
from calibre.utils.date import isoformat
from polyglot.builtins import as_bytes, iteritems

readonly = True
version = 0  # change this if you change signature of implementation()
FIELDS = {
    'title', 'authors', 'author_sort', 'publisher', 'rating', 'timestamp', 'size',
    'tags', 'comments', 'series', 'series_index', 'formats', 'isbn', 'uuid',
    'pubdate', 'cover', 'last_modified', 'identifiers', 'languages', 'template'
}


def formats(db, book_id):
    for fmt in db.formats(book_id, verify_formats=False):
        path = db.format_abspath(book_id, fmt)
        if path:
            yield path.replace(os.sep, '/')


def cover(db, book_id):
    return db.format_abspath(book_id, '__COVER_INTERNAL__')


def implementation(
    db, notify_changes, fields, sort_by, ascending, search_text, limit, template=None
):
    is_remote = notify_changes is not None
    formatter = None
    with db.safe_read_lock:
        fm = db.field_metadata
        afields = set(FIELDS) | {'id'}
        for k in fm.custom_field_keys():
            afields.add('*' + k[1:])
        if 'all' in fields:
            if template:
                fields = sorted(afields - {'template'})
            else:
                fields = sorted(afields)
        sort_by = sort_by or 'id'
        if sort_by not in afields:
            return f'Unknown sort field: {sort_by}'
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
                data[field] = {k: v.get('isbn') or '' for k, v in iteritems(x)}
                continue
            if field == 'template':
                vals = {}
                global_vars = {}
                if formatter is None:
                    from calibre.ebooks.metadata.book.formatter import SafeFormat
                    formatter = SafeFormat()
                for book_id in book_ids:
                    mi = db.get_proxy_metadata(book_id)
                    vals[book_id] = formatter.safe_format(template, {}, 'TEMPLATE ERROR', mi, global_vars=global_vars)
                data['template'] = vals
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
    for field, m in iteritems(metadata):
        if field == 'authors':
            data[field] = {
                k: authors_to_string(v)
                for k, v in iteritems(data[field])
            }
        else:
            dt = m['datatype']
            if dt == 'datetime':
                data[field] = {
                    k: isoformat(v, as_utc=for_machine) if v else 'None'
                    for k, v in iteritems(data[field])
                }
            elif not for_machine:
                ism = m['is_multiple']
                if ism:
                    data[field] = {
                        k: ism['list_to_ui'].join(v)
                        for k, v in iteritems(data[field])
                    }
                    if field == 'formats':
                        data[field] = {
                            k: '[' + v + ']'
                            for k, v in iteritems(data[field])
                        }


def as_machine_data(book_ids, data, metadata):
    for book_id in book_ids:
        ans = {'id': book_id}
        for field, val_map in iteritems(data):
            val = val_map.get(book_id)
            if val is not None:
                ans[field.replace('#', '*')] = val
        yield ans


def prepare_output_table(fields, book_ids, data, metadata):
    ans = []
    for book_id in book_ids:
        row = []
        ans.append(row)
        for field in fields:
            if field == 'id':
                row.append(str(book_id))
                continue
            val = data.get(field.replace('*', '#'), {}).get(book_id)
            row.append(str(val).replace('\n', ' '))
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
    template,
    template_file,
    template_title,
    for_machine=False
):
    if sort_by is None:
        ascending = True
    if 'template' in (f.strip() for f in fields):
        if template_file:
            with lopen(template_file, 'rb') as f:
                template = f.read().decode('utf-8')
        if not template:
            raise SystemExit(_('You must provide a template'))
        ans = dbctx.run('list', fields, sort_by, ascending, search_text, limit, template)
    else:
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
        raw = json.dumps(
            list(as_machine_data(book_ids, data, metadata)),
            indent=2,
            sort_keys=True
        )
        if not isinstance(raw, bytes):
            raw = raw.encode('utf-8')
        getattr(sys.stdout, 'buffer', sys.stdout).write(raw)
        return
    from calibre.utils.terminal import ColoredStream, geometry

    output_table = prepare_output_table(fields, book_ids, data, metadata)
    widths = list(map(lambda x: 0, fields))

    for record in output_table:
        for j in range(len(fields)):
            widths[j] = max(widths[j], str_width(record[j]))

    screen_width = geometry()[0] if line_width < 0 else line_width
    if not screen_width:
        screen_width = 80
    field_width = screen_width // len(fields)
    base_widths = list(map(lambda x: min(x + 1, field_width), widths))

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
        [template_title if v == 'template' else v for v in fields]
    )
    with ColoredStream(sys.stdout, fg='green'):
        print(''.join(titles), flush=True)
    stdout = getattr(sys.stdout, 'buffer', sys.stdout)
    linesep = as_bytes(os.linesep)

    wrappers = [TextWrapper(x - 1).wrap if x > 1 else lambda y: y for x in widths]

    for record in output_table:
        text = [
            wrappers[i](record[i]) for i in range(len(fields))
        ]
        lines = max(map(len, text))
        for l in range(lines):
            for i in range(len(text)):
                ft = text[i][l] if l < len(text[i]) else ''
                stdout.write(ft.encode('utf-8'))
                if i < len(text) - 1:
                    filler = ('%*s' % (widths[i] - str_width(ft) - 1, ''))
                    stdout.write((filler + separator).encode('utf-8'))
            stdout.write(linesep)


def option_parser(get_parser, args):
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
            'Filter the results by the search query. For the format of the search '
            'query, please see the search related documentation in the User '
            'Manual. Default is to do no filtering.'
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
            'Generate output in JSON format, which is more suitable for machine '
            'parsing. Causes the line width and separator options to be ignored.'
        )
    )
    parser.add_option(
        '--template',
        default=None,
        help=_('The template to run if "{}" is in the field list. Default: None').format('template')
    )
    parser.add_option(
        '--template_file',
        '-t',
        default=None,
        help=_('Path to a file containing the template to run if "{}" is in '
               'the field list. Default: None').format('template')
    )
    parser.add_option(
        '--template_heading',
        default='template',
        help=_('Heading for the template column. Default: %default. This option '
               'is ignored if the option {} is set').format('--for-machine')
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
        opts.template,
        opts.template_file,
        opts.template_heading,
        for_machine=opts.for_machine
    )
    return 0
