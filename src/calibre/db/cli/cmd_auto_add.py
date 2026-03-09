#!/usr/bin/env python
# License: GPLv3 Copyright: 2024, Kovid Goyal <kovid at kovidgoyal.net>

import os
import signal

from calibre import prints

readonly = True
version = 0  # change this if you change signature of implementation()


def implementation(db, notify_changes, *args):
    raise NotImplementedError('The auto_add command is not supported in remote mode')


no_remote = True


def option_parser(get_parser, args):
    parser = get_parser(
        _(
            '''\
%prog auto_add [options] /path/to/watch/folder

Watch a folder for new ebook files and automatically add them to the calibre
library. Files are removed from the watch folder after being successfully added.
'''
        )
    )
    parser.add_option(
        '--poll-interval',
        type=int,
        default=5,
        help=_('Interval in seconds between directory scans. Default: %default')
    )
    parser.add_option(
        '-d',
        '--duplicates',
        action='store_true',
        default=False,
        help=_('Add books even if they already exist in the database')
    )
    parser.add_option(
        '--blocked-formats',
        default='',
        help=_('Comma-separated list of file extensions to ignore (e.g. pdf,mobi)')
    )
    return parser


def main(opts, args, dbctx):
    if len(args) < 1:
        raise SystemExit(_('You must specify a folder to watch'))

    watch_dir = os.path.abspath(args[0])
    if not os.path.isdir(watch_dir):
        raise SystemExit(_('{} is not a valid directory').format(watch_dir))

    from calibre.db.auto_add import HeadlessAutoAdder

    blocked = frozenset(
        x.strip().lower() for x in opts.blocked_formats.split(',') if x.strip()
    )

    adder = HeadlessAutoAdder(
        watch_dir=watch_dir,
        db=dbctx.db.new_api,
        poll_interval=opts.poll_interval,
        add_duplicates=opts.duplicates,
        blocked_formats=blocked,
    )

    prints(_('Watching {} for new ebooks...').format(watch_dir))
    prints(_('Press Ctrl+C to stop'))

    def handle_signal(signum, frame):
        prints(_('\nStopping...'))
        adder.stop()

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    try:
        adder.start(blocking=True)
    except KeyboardInterrupt:
        adder.stop()

    return 0
