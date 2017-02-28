#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2017, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import absolute_import, division, print_function, unicode_literals

import bz2
import hashlib
import json
import sys
import time
from threading import Thread

from calibre import as_unicode, prints
from calibre.constants import DEBUG
from calibre.utils.config import JSONConfig
from calibre.utils.https import get_https_resource_securely

cache = JSONConfig('metadata-sources-cache.json')

UPDATE_INTERVAL = 24 * 60 * 60


def debug_print(*args, **k):
    if DEBUG:
        prints(*args, **k)


def update_needed():
    needed = set()
    current_hashes = cache.get('hashes', {})
    hashes = get_https_resource_securely(
        'https://code.calibre-ebook.com/metadata-sources/hashes.json')
    hashes = bz2.decompress(hashes)
    hashes = json.loads(hashes)
    for k, v in hashes.iteritems():
        if current_hashes.get(k) != v:
            needed.add(k)
    remove = set(current_hashes) - set(hashes)
    if remove:
        for k in remove:
            current_hashes.pop(k, None)
        cache['hashes'] = current_hashes
    return needed


def update_plugin(name):
    raw = get_https_resource_securely('https://code.calibre-ebook.com/metadata-sources/' + name)
    h = hashlib.sha1(raw).hexdigest()
    plugin = bz2.decompress(raw)
    hashes = cache.get('hashes', {})
    hashes[name] = h
    with cache:
        cache['hashes'] = hashes
        cache[name] = plugin


def main(report_error, report_action=prints):
    try:
        if time.time() - cache.mtime() < UPDATE_INTERVAL:
            return
        try:
            report_action('Fetching metadata source hashes...')
            needed = update_needed()
        except Exception as e:
            report_error(
                'Failed to get metadata sources hashes with error: {}'.format(as_unicode(e)))
            return
        for name in needed:
            report_action('Updating metadata source {}...'.format(name))
            try:
                update_plugin(name)
            except Exception as e:
                report_error('Failed to get plugin {} with error: {}'.format(
                    name, as_unicode(e)))
    finally:
        update_sources.worker = None


def update_sources(wait_for_completion=False):
    if update_sources.worker is not None:
        return False
    update_sources.errors = errs = []
    update_sources.worker = t = Thread(
        target=main, args=(errs.append, debug_print), name='MSourcesUpdater')
    t.daemon = True
    t.start()
    if wait_for_completion:
        t.join()
    return True


update_sources.worker = None

if __name__ == '__main__':
    def re(x):
        prints(x, file=sys.stderr)
        re.ok = False
    re.ok = True
    main(re)
    if not re.ok:
        raise SystemExit(1)
