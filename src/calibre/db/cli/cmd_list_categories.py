#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2017, Kovid Goyal <kovid at kovidgoyal.net>


import csv
import sys
from textwrap import TextWrapper

from calibre import prints
from polyglot.builtins import as_bytes, map, unicode_type

readonly = True
version = 0  # change this if you change signature of implementation()


def implementation(db, notify_changes):
    return db.get_categories(), db.field_metadata


def option_parser(get_parser, args):
    parser = get_parser(
        _(
            '''\
%prog list_categories [options]

Produce a report of the category information in the database. The
information is the equivalent of what is shown in the Tag browser.
'''
        )
    )

    parser.add_option(
        '-i',
        '--item_count',
        default=False,
        action='store_true',
        help=_(
            'Output only the number of items in a category instead of the '
            'counts per item within the category'
        )
    )
    parser.add_option(
        '-c', '--csv', default=False, action='store_true', help=_('Output in CSV')
    )
    parser.add_option(
        '--dialect',
        default='excel',
        choices=csv.list_dialects(),
        help=_('The type of CSV file to produce. Choices: {}')
        .format(', '.join(sorted(csv.list_dialects())))
    )
    parser.add_option(
        '-r',
        '--categories',
        default='',
        dest='report',
        help=_("Comma-separated list of category lookup names. "
               "Default: all")
    )
    parser.add_option(
        '-w',
        '--width',
        default=-1,
        type=int,
        help=_(
            'The maximum width of a single line in the output. '
            'Defaults to detecting screen size.'
        )
    )
    return parser


def do_list(fields, data, opts):
    from calibre.utils.terminal import geometry, ColoredStream

    separator = ' '
    widths = list(map(lambda x: 0, fields))
    for i in data:
        for j, field in enumerate(fields):
            widths[j] = max(widths[j], max(len(field), len(unicode_type(i[field]))))

    screen_width = geometry()[0]
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
        lambda x, y: '%-*s%s' % (x - len(separator), y, separator), widths, fields
    )
    with ColoredStream(sys.stdout, fg='green'):
        prints(''.join(titles))

    wrappers = list(map(lambda x: TextWrapper(x - 1), widths))

    for record in data:
        text = [
            wrappers[i].wrap(unicode_type(record[field]))
            for i, field in enumerate(fields)
        ]
        lines = max(map(len, text))
        for l in range(lines):
            for i, field in enumerate(text):
                ft = text[i][l] if l < len(text[i]) else ''
                filler = '%*s' % (widths[i] - len(ft) - 1, '')
                print(ft.encode('utf-8') + filler.encode('utf-8'), end=separator)
            print()


class StdoutWriter:

    def __init__(self):
        self.do_write = getattr(sys.stdout, 'buffer', sys.stdout).write

    def write(self, x):
        x = as_bytes(x)
        self.do_write(x)


def do_csv(fields, data, opts):
    csv_print = csv.writer(StdoutWriter(), opts.dialect)
    csv_print.writerow(fields)
    for d in data:
        row = [d[f] for f in fields]
        csv_print.writerow(row)


def main(opts, args, dbctx):
    category_data, field_metadata = dbctx.run('list_categories')
    data = []
    report_on = [c.strip() for c in opts.report.split(',') if c.strip()]

    def category_metadata(k):
        return field_metadata.get(k)

    categories = [
        k for k in category_data.keys()
        if category_metadata(k)['kind'] not in ['user', 'search'] and
        (not report_on or k in report_on)
    ]

    categories.sort(key=lambda x: x if x[0] != '#' else x[1:])

    def fmtr(v):
        v = v or 0
        ans = '%.1f' % v
        if ans.endswith('.0'):
            ans = ans[:-2]
        return ans

    if not opts.item_count:
        for category in categories:
            is_rating = category_metadata(category)['datatype'] == 'rating'
            for tag in category_data[category]:
                if is_rating:
                    tag.name = unicode_type(len(tag.name))
                data.append({
                    'category': category,
                    'tag_name': tag.name,
                    'count': unicode_type(tag.count),
                    'rating': fmtr(tag.avg_rating),
                })
    else:
        for category in categories:
            data.append({
                'category': category,
                'tag_name': _('CATEGORY ITEMS'),
                'count': unicode_type(len(category_data[category])),
                'rating': ''
            })

    fields = ['category', 'tag_name', 'count', 'rating']

    func = do_csv if opts.csv else do_list
    func(fields, data, opts)

    return 0
