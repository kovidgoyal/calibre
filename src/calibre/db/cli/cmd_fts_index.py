#!/usr/bin/env python
# License: GPLv3 Copyright: 2017, Kovid Goyal <kovid at kovidgoyal.net>

import sys

from calibre.db.listeners import EventType

version = 0  # change this if you change signature of implementation()


def implementation(db, notify_changes, action, adata=None):
    if action == 'status':
        if db.is_fts_enabled():
            l, t, r = db.fts_indexing_progress()
            return {'enabled': True, 'left': l, 'total': t, 'rate': r}
        return {'enabled': False, 'left': -1, 'total': -1}

    if action == 'enable':
        if not db.is_fts_enabled():
            db.enable_fts()
        l, t, r = db.fts_indexing_progress()
        return {'enabled': True, 'left': l, 'total': t, 'rate': r}

    if action == 'disable':
        if db.is_fts_enabled():
            db.enable_fts(enabled=False)
        return

    if action == 'reindex':
        if not db.is_fts_enabled():
            a = Exception(_('Full text indexing is not enabled on this library'))
            a.suppress_traceback = True
            raise a
        items = adata.get('items')
        if items:
            for item in items:
                db.reindex_fts_book(*item)
        else:
            db.reindex_fts()
        l, t, r = db.fts_indexing_progress()
        return {'enabled': True, 'left': l, 'total': t, 'rate': r}

    if action == 'wait':
        if not db.is_fts_enabled():
            a = Exception(_('Full text indexing is not enabled on this library'))
            a.suppress_traceback = True
            raise a
        if 'measure_state' in adata:
            db.fts_start_measuring_rate(measure=adata['measure_state'])
        if adata.get('speed'):
            db.set_fts_speed(slow=adata['speed'] == 'slow')
        l, t, r = db.fts_indexing_progress()
        return {'left': l, 'total': t, 'rate': r}


def option_parser(get_parser, args):
    parser = get_parser(
        _(
            '''\
%prog fts_index [options] {enable}/{disable}/{status}/{reindex}

Control the Full text search indexing process.

{enable}
    Turns on FTS indexing for this library
{disable}
    Turns off FTS indexing for this library
{status}
    Shows the current indexing status
{reindex}
    Can be used to re-index either particular books or
    the entire library. To re-index particular books
    specify the book ids as additional arguments after the
    {reindex} command. If no book ids are specified the
    entire library is re-indexed.
''').format(enable='enable', disable='disable', status='status', reindex='reindex')
    )
    parser.add_option(
        '--wait-for-completion',
        default=False,
        action='store_true',
        help=_('Wait till all books are indexed, showing indexing progress periodically')
    )
    parser.add_option(
        '--indexing-speed',
        default='',
        choices=('fast', 'slow', ''),
        help=_('The speed of indexing. Use fast for fast indexing using all your computers resources'
               ' and slow for less resource intensive indexing. Note that the speed is reset to slow after every invocation.')
    )
    return parser


def run_job(dbctx, which, **data):
    try:
        return dbctx.run('fts_index', which, data)
    except Exception as e:
        if getattr(e, 'suppress_traceback', False):
            raise SystemExit(str(e))
        raise


def show_progress(left, total, rate):
    from calibre.db.utils import IndexingProgress
    ip = IndexingProgress()
    ip.update(left, total, rate)
    print('\r\x1b[K' + _('{} of {} book files indexed, {}').format(total-left, total, ip.time_left), flush=True, end=' ...')


def remote_wait_for_completion(dbctx, indexing_speed):
    import time
    s = run_job(dbctx, 'wait', speed=indexing_speed, measure_state=True)
    try:
        while s['left'] > 0:
            show_progress(s['left'], s['total'], s['rate'])
            time.sleep(1)
            s = run_job(dbctx, 'wait')
    finally:
        print()
        run_job(dbctx, 'wait', speed='slow', measure_state=False)


def local_wait_for_completion(db, indexing_speed):
    from queue import Queue

    q = Queue()

    def notifier(event_type, library_id, event_data):
        if event_type is EventType.indexing_progress_changed:
            q.put(event_data)

    db.add_listener(notifier)
    if indexing_speed:
        db.set_fts_speed(slow=indexing_speed == 'slow')
    db.fts_start_measuring_rate()
    l, t, r = db.fts_indexing_progress()
    while l > 0:
        show_progress(l, t, r)
        l, t, r = q.get()
    print()


def main(opts, args, dbctx):
    if len(args) < 1:
        dbctx.option_parser.print_help()
        raise SystemExit(_('Error: You must specify the indexing action'))
    action = args[0]

    if action == 'status':
        s = run_job(dbctx, 'status')
        if s['enabled']:
            print(_('FTS Indexing is enabled'))
            print(_('{0} of {1} books files indexed').format(s['total'] - s['left'], s['total']))
        else:
            print(_('FTS Indexing is disabled'))
            raise SystemExit(2)

    elif action == 'enable':
        s = run_job(dbctx, 'enable')
        print(_('FTS indexing has been enabled'))
        print(_('{0} of {1} books files indexed').format(s['total'] - s['left'], s['total']))

    elif action == 'reindex':
        items = args[1:]
        if not items:
            print(_('Re-indexing the entire library can take a long time. Are you sure?'))
            while True:
                try:
                    q = input(_('Type {} to proceed, anything else to abort').format('"reindex"') + ': ')
                except KeyboardInterrupt:
                    sys.excepthook = lambda *a: None
                    raise
                if q.strip('"') == 'reindex':
                    break
                else:
                    return 0

        def to_spec(x):
            parts = x.split(':', 1)
            book_id = int(parts[0])
            if len(parts) == 1:
                return book_id,
            fmts = tuple(x.upper() for x in parts[1].split(','))
            return (book_id,) + fmts

        specs = tuple(map(to_spec, items))
        s = run_job(dbctx, 'reindex', items=specs)
        print(_('{0} of {1} books files indexed').format(s['total'] - s['left'], s['total']))

    elif action == 'disable':
        print(_('Disabling indexing will mean that all books will have to be re-checked when re-enabling indexing. Are you sure?'))
        while True:
            try:
                q = input(_('Type {} to proceed, anything else to abort').format('"disable"') + ': ')
            except KeyboardInterrupt:
                sys.excepthook = lambda *a: None
                raise
            if q in ('disable', '"disable"'):
                break
            else:
                return 0
        run_job(dbctx, 'disable')
        print(_('FTS indexing has been disabled'))
        return 0
    else:
        dbctx.option_parser.print_help()
        raise SystemExit(f'{action} is not a known action')

    if opts.wait_for_completion:
        print(_('Waiting for FTS indexing to complete, press Ctrl-C to abort...'))
        try:
            if dbctx.is_remote:
                remote_wait_for_completion(dbctx, opts.indexing_speed)
            else:
                local_wait_for_completion(dbctx.db.new_api, opts.indexing_speed)
        except KeyboardInterrupt:
            sys.excepthook = lambda *a: None
            raise
        print(_('All books indexed!'))
    return 0
