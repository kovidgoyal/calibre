#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2017, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import absolute_import, division, print_function, unicode_literals

import csv
import sys
from textwrap import TextWrapper
from io import BytesIO

from calibre import prints

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
information is the equivalent of what is shown in the tags pane.
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
        .format(', '.join(csv.list_dialects()))
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
            widths[j] = max(widths[j], max(len(field), len(unicode(i[field]))))

    screen_width = geometry()[0]
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
        lambda x, y: '%-*s%s' % (x - len(separator), y, separator), widths, fields
    )
    with ColoredStream(sys.stdout, fg='green'):
        prints(''.join(titles))

    wrappers = map(lambda x: TextWrapper(x - 1), widths)

    for record in data:
        text = [
            wrappers[i].wrap(unicode(record[field]))
            for i, field in enumerate(fields)
        ]
        lines = max(map(len, text))
        for l in range(lines):
            for i, field in enumerate(text):
                ft = text[i][l] if l < len(text[i]) else ''
                filler = '%*s' % (widths[i] - len(ft) - 1, '')
                print(ft.encode('utf-8') + filler.encode('utf-8'), end=separator)
            print()


def do_csv(fields, data, opts):
    buf = BytesIO()
    csv_print = csv.writer(buf, opts.dialect)
    csv_print.writerow(fields)
    for d in data:
        row = [d[f] for f in fields]
        csv_print.writerow([
            x if isinstance(x, bytes) else unicode(x).encode('utf-8') for x in row
        ])
    print(buf.getvalue())


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

    categories.sort(
        cmp=lambda x, y: cmp(x if x[0] != '#' else x[1:], y if y[0] != '#' else y[1:])
    )

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
                    tag.name = unicode(len(tag.name))
                data.append({
                    'category': category,
                    'tag_name': tag.name,
                    'count': unicode(tag.count),
                    'rating': fmtr(tag.avg_rating),
                })
    else:
        for category in categories:
            data.append({
                'category': category,
                'tag_name': _('CATEGORY ITEMS'),
                'count': unicode(len(category_data[category])),
                'rating': ''
            })

    fields = ['category', 'tag_name', 'count', 'rating']

    func = do_csv if opts.csv else do_list
    func(fields, data, opts)

    return 0
