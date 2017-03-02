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

import calibre.ebooks.metadata.sources.search_engines as builtin_search_engines
from calibre import as_unicode, prints
from calibre.constants import DEBUG, numeric_version
from calibre.ebooks.metadata.sources.base import Source
from calibre.utils.config import JSONConfig
from calibre.utils.https import get_https_resource_securely

cache = JSONConfig('metadata-sources-cache.json')

UPDATE_INTERVAL = 12 * 60 * 60

current_search_engines = builtin_search_engines


def search_engines_module():
    return current_search_engines


def debug_print(*args, **k):
    if DEBUG:
        prints(*args, **k)


def load_plugin(src):
    src = src.encode('utf-8')
    ns = {}
    exec src in ns
    for x in ns.itervalues():
        if isinstance(x, type) and issubclass(x, Source) and x is not Source:
            return x


def patch_search_engines(src):
    global current_search_engines
    src = src.encode('utf-8')
    ns = {}
    exec src in ns
    mcv = ns.get('minimum_calibre_version')
    if mcv is None or mcv > numeric_version:
        return
    cv = ns.get('current_version')
    if cv is None or cv <= builtin_search_engines.current_version:
        return
    current_search_engines = ns


def patch_plugins():
    from calibre.customize.ui import patch_metadata_plugins
    patches = {}
    for name, val in cache.iteritems():
        if name == 'hashes':
            continue
        if name == 'search_engines':
            patch_search_engines(val)
        p = load_plugin(val)
        if p is not None:
            patches[p.name] = p
    patch_metadata_plugins(patches)


def update_needed():
    needed = {}
    current_hashes = cache.get('hashes', {})
    hashes = get_https_resource_securely(
        'https://code.calibre-ebook.com/metadata-sources/hashes.json')
    hashes = bz2.decompress(hashes)
    hashes = json.loads(hashes)
    for k, v in hashes.iteritems():
        if current_hashes.get(k) != v:
            needed[k] = v
    remove = set(current_hashes) - set(hashes)
    if remove:
        with cache:
            for k in remove:
                current_hashes.pop(k, None)
                del cache[k]
            cache['hashes'] = current_hashes
    return needed


def update_plugin(name, updated, expected_hash):
    raw = get_https_resource_securely('https://code.calibre-ebook.com/metadata-sources/' + name)
    h = hashlib.sha1(raw).hexdigest()
    if h != expected_hash:
        raise ValueError('Actual hash did not match expected hash, probably an update occurred while downloading')
    plugin = bz2.decompress(raw).decode('utf-8')
    updated[name] = plugin, h


def main(report_error=prints, report_action=prints):
    try:
        if time.time() - cache.mtime() < UPDATE_INTERVAL:
            report_action('Metadata sources cache was recently updated not updating again')
            return
        try:
            report_action('Fetching metadata source hashes...')
            needed = update_needed()
        except Exception as e:
            report_error(
                'Failed to get metadata sources hashes with error: {}'.format(as_unicode(e)))
            return
        if not needed:
            cache.touch()
            return
        updated = {}
        for name, expected_hash in needed.iteritems():
            report_action('Updating metadata source {}...'.format(name))
            try:
                update_plugin(name, updated, expected_hash)
            except Exception as e:
                report_error('Failed to get plugin {} with error: {}'.format(
                    name, as_unicode(e)))
                break
        else:
            hashes = cache.get('hashes', {})
            for name in updated:
                hashes[name] = updated[name][1]
            with cache:
                cache['hashes'] = hashes
                for name in updated:
                    cache[name] = updated[name][0]
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
