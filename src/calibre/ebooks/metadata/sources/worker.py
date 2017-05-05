#!/usr/bin/env python2
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
# License: GPLv3 Copyright: 2012, Kovid Goyal <kovid at kovidgoyal.net>
from __future__ import absolute_import, division, print_function, unicode_literals

import os
from collections import Counter
from io import BytesIO
from Queue import Empty, Queue
from threading import Event, Thread

from calibre.customize.ui import metadata_plugins
from calibre.ebooks.metadata.book.base import Metadata
from calibre.ebooks.metadata.opf2 import OPF, metadata_to_opf
from calibre.ebooks.metadata.sources.base import dump_caches, load_caches
from calibre.ebooks.metadata.sources.covers import download_cover, run_download
from calibre.ebooks.metadata.sources.identify import identify, msprefs
from calibre.ebooks.metadata.sources.update import patch_plugins
from calibre.utils.date import as_utc
from calibre.utils.logging import GUILog


def merge_result(oldmi, newmi, ensure_fields=None):
    dummy = Metadata(_('Unknown'))
    for f in msprefs['ignore_fields']:
        if ':' in f or (ensure_fields and f in ensure_fields):
            continue
        setattr(newmi, f, getattr(dummy, f))
    fields = set()
    for plugin in metadata_plugins(['identify']):
        fields |= plugin.touched_fields

    def is_equal(x, y):
        if hasattr(x, 'tzinfo'):
            x = as_utc(x)
        if hasattr(y, 'tzinfo'):
            y = as_utc(y)
        return x == y

    for f in fields:
        # Optimize so that set_metadata does not have to do extra work later
        if not f.startswith('identifier:'):
            if (not newmi.is_null(f) and is_equal(getattr(newmi, f),
                    getattr(oldmi, f))):
                setattr(newmi, f, getattr(dummy, f))

    return newmi


def main(do_identify, covers, metadata, ensure_fields, tdir):
    failed_ids = set()
    failed_covers = set()
    all_failed = True
    log = GUILog()
    patch_plugins()

    for book_id, mi in metadata.iteritems():
        mi = OPF(BytesIO(mi), basedir=tdir,
                populate_spine=False).to_book_metadata()
        title, authors, identifiers = mi.title, mi.authors, mi.identifiers
        cdata = None
        log.clear()

        if do_identify:
            results = []
            try:
                results = identify(log, Event(), title=title, authors=authors,
                    identifiers=identifiers)
            except:
                pass
            if results:
                all_failed = False
                mi = merge_result(mi, results[0], ensure_fields=ensure_fields)
                identifiers = mi.identifiers
                if not mi.is_null('rating'):
                    # set_metadata expects a rating out of 10
                    mi.rating *= 2
                with open(os.path.join(tdir, '%d.mi'%book_id), 'wb') as f:
                    f.write(metadata_to_opf(mi, default_lang='und'))
            else:
                log.error('Failed to download metadata for', title)
                failed_ids.add(book_id)

        if covers:
            cdata = download_cover(log, title=title, authors=authors,
                    identifiers=identifiers)
            if cdata is None:
                failed_covers.add(book_id)
            else:
                with open(os.path.join(tdir, '%d.cover'%book_id), 'wb') as f:
                    f.write(cdata[-1])
                all_failed = False

        with open(os.path.join(tdir, '%d.log'%book_id), 'wb') as f:
            f.write(log.plain_text.encode('utf-8'))

    return failed_ids, failed_covers, all_failed


def single_identify(title, authors, identifiers):
    log = GUILog()
    patch_plugins()
    results = identify(log, Event(), title=title, authors=authors,
            identifiers=identifiers)
    return [metadata_to_opf(r) for r in results], [r.has_cached_cover_url for
        r in results], dump_caches(), log.dump()


def single_covers(title, authors, identifiers, caches, tdir):
    patch_plugins()
    load_caches(caches)
    log = GUILog()
    results = Queue()
    worker = Thread(target=run_download, args=(log, results, Event()),
            kwargs=dict(title=title, authors=authors, identifiers=identifiers))
    worker.daemon = True
    worker.start()
    c = Counter()
    while worker.is_alive():
        try:
            plugin, width, height, fmt, data = results.get(True, 1)
        except Empty:
            continue
        else:
            name = plugin.name
            if plugin.can_get_multiple_covers:
                name += '{%d}'%c[plugin.name]
                c[plugin.name] += 1
            name = '%s,,%s,,%s,,%s.cover'%(name, width, height, fmt)
            with open(os.path.join(tdir, name), 'wb') as f:
                f.write(data)
            os.mkdir(os.path.join(tdir, name+'.done'))

    return log.dump()
