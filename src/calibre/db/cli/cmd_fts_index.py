#!/usr/bin/env python
# License: GPLv3 Copyright: 2017, Kovid Goyal <kovid at kovidgoyal.net>

import sys
from functools import lru_cache

version = 0  # change this if you change signature of implementation()


@lru_cache
def indexing_progress():
    from threading import Lock
    from calibre.db.utils import IndexingProgress
    ans = IndexingProgress()
    ans.lock = Lock()
    return ans


def update_indexing_progress(left, total):
    ip = indexing_progress()
    with ip.lock:
        ip.update(left, total)


def reset_indexing_progress():
    ip = indexing_progress()
    with ip.lock:
        ip.reset()


def indexing_progress_time_left():
    ip = indexing_progress()
    with ip.lock:
        return ip.time_left


def implementation(db, notify_changes, action, adata=None):
    if action == 'status':
        if db.is_fts_enabled():
            l, t = db.fts_indexing_progress()
            return {'enabled': True, 'left': l, 'total': t}
        return {'enabled': False, 'left': -1, 'total': -1}

    if action == 'enable':
        if not db.is_fts_enabled():
            db.enable_fts()
        l, t = db.fts_indexing_progress()
        return {'enabled': True, 'left': l, 'total': t}

    if action == 'disable':
        if db.is_fts_enabled():
            reset_indexing_progress()
            db.enable_fts(enabled=False)
        return


def option_parser(get_parser, args):
    parser = get_parser(
        _(
            '''\
%prog fts_index [options] enable/disable/status/reindex

Control the fts indexing process.
'''
    ))
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
               ' and slow for less resource intensive indexing. Note that the speed is reset to slow on every invocation.')
    )
    return parser


def local_wait_for_completion(db, indexing_speed):
    from calibre.db.listeners import EventType
    from queue import Queue

    q = Queue()

    def listen(event_type, library_id, event_data):
        if event_type is EventType.indexing_progress_changed:
            update_indexing_progress(*event_data)
            q.put(event_data)

    def show_progress(left, total):
        print('\r\x1b[K' + _('{} of {} book files indexed, {}').format(total-left, total, indexing_progress_time_left()), flush=True, end=' ...')

    db.add_listener(listen)
    if indexing_speed:
        db.set_fts_speed(slow=indexing_speed == 'slow')
    l, t = db.fts_indexing_progress()
    if l < 1:
        return
    show_progress(l, t)

    while True:
        l, t = q.get()
        if l < 1:
            return
        show_progress(l, t)


def main(opts, args, dbctx):
    if len(args) < 1:
        dbctx.option_parser.print_help()
        raise SystemExit(_('Error: You must specify the indexing action'))
    action = args[0]
    adata = {}

    def run_job(dbctx, which, **kw):
        data = adata.copy()
        data.update(kw)
        try:
            return dbctx.run('fts_index', which, data)
        except Exception as e:
            if getattr(e, 'suppress_traceback', False):
                raise SystemExit(str(e))
            raise

    if action == 'status':
        s = run_job(dbctx, 'status')
        if s['enabled']:
            print(_('FTS Indexing is enabled'))
            print(_('{0} of {1} books files indexed').format(s['total'] - s['left'], s['total']))
        else:
            print(_('FTS Indexing is disabled'))
            raise SystemExit(2)

    if action == 'enable':
        s = run_job(dbctx, 'enable')
        print(_('FTS indexing has been enabled'))
        print(_('{0} of {1} books files indexed').format(s['total'] - s['left'], s['total']))

    if action == 'disable':
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

    if opts.wait_for_completion:
        print(_('Waiting for FTS indexing to complete...'))
        try:
            if dbctx.is_remote:
                raise NotImplementedError('TODO: Implement waiting for completion via polling')
            else:
                local_wait_for_completion(dbctx.db.new_api, opts.indexing_speed)
        except KeyboardInterrupt:
            sys.excepthook = lambda *a: None
            raise
        print(_('All books indexed!'))
    return 0
