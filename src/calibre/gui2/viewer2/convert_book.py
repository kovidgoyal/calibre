#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2018, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import absolute_import, division, print_function, unicode_literals

import errno
import json
import os
import shutil
import tempfile
import time
from cPickle import dumps
from hashlib import sha1

from calibre import walk
from calibre.constants import cache_dir, iswindows
from calibre.srv.render_book import RENDER_VERSION
from calibre.utils.ipc.simple_worker import fork_job
from calibre.utils.lock import ExclusiveFile
from calibre.utils.short_uuid import uuid4

DAY = 24 * 3600


def book_cache_dir():
    return getattr(book_cache_dir, 'override', os.path.join(cache_dir(), 'ev2'))


def cache_lock():
    return ExclusiveFile(os.path.join(book_cache_dir(), 'metadata.json'))


def book_hash(path, size, mtime):
    path = os.path.normcase(os.path.abspath(path))
    raw = dumps((path, size, mtime, RENDER_VERSION))
    return sha1(raw).hexdigest().decode('ascii')


def safe_makedirs(path):
    try:
        os.makedirs(path)
    except EnvironmentError as err:
        if err.errno != errno.EEXIST:
            raise
    return path


def robust_rmtree(x):
    retries = 2 if iswindows else 1  # retry on windows to get around the idiotic mandatory file locking
    for i in range(retries):
        try:
            return shutil.rmtree(x)
        except EnvironmentError:
            time.sleep(0.1)


def clear_temp(temp_path):
    now = time.time()
    for x in os.listdir(temp_path):
        x = os.path.join(temp_path, x)
        mtime = os.path.getmtime(x)
        if now - mtime > DAY:
            robust_rmtree(x)


def expire_cache(path, instances, max_age):
    now = time.time()
    remove = [x for x in instances if now - x['atime'] > max_age]
    for instance in remove:
        if instance['status'] == 'finished':
            instances.remove(instance)
            robust_rmtree(os.path.join(path, instance['path']))


def expire_cache_and_temp(temp_path, finished_path, metadata, max_age):
    now = time.time()
    if now - metadata['last_clear_at'] < DAY and max_age >= 0:
        return
    clear_temp(temp_path)
    entries = metadata['entries']
    for key, instances in tuple(entries.items()):
        if instances:
            expire_cache(finished_path, instances, max_age)
            if not instances:
                del entries[key]
    metadata['last_clear_at'] = now


def prepare_convert(temp_path, key, st):
    tdir = tempfile.mkdtemp(dir=temp_path)
    now = time.time()
    return {
        'path': os.path.basename(tdir),
        'id': uuid4(),
        'status': 'working',
        'mtime': now,
        'atime': now,
        'key': key,
        'file_mtime': st.st_mtime,
        'file_size': st.st_size,
        'cache_size': 0,
    }


def do_convert(path, temp_path, key, instance):
    tdir = os.path.join(temp_path, instance['path'])
    fork_job('calibre.srv.render_book', 'render', args=(
        path, tdir, {'size': instance['file_size'], 'mtime': instance['file_mtime'], 'hash': key}
        ), timeout=3000, no_output=True
    )
    size = 0
    for f in walk(tdir):
        size += os.path.getsize(f)
    instance['cache_size'] = size


def prepare_book(path, convert_func=do_convert, max_age=30 * DAY):
    st = os.stat(path)
    key = book_hash(path, st.st_size, st.st_mtime)
    finished_path = safe_makedirs(os.path.join(book_cache_dir(), 'f'))
    temp_path = safe_makedirs(os.path.join(book_cache_dir(), 't'))
    with cache_lock() as f:
        try:
            metadata = json.loads(f.read())
        except ValueError:
            metadata = {'entries': {}, 'last_clear_at': 0}
        entries = metadata['entries']
        instances = entries.setdefault(key, [])
        for instance in instances:
            if instance['status'] == 'finished':
                instance['atime'] = time.time()
                f.seek(0), f.write(json.dumps(metadata))
                return os.path.join(finished_path, instance['path'])
        instance = prepare_convert(temp_path, key, st)
        instances.append(instance)
        f.seek(0), f.truncate(), f.write(json.dumps(metadata))
    convert_func(path, temp_path, key, instance)
    src_path = os.path.join(temp_path, instance['path'])
    with cache_lock() as f:
        ans = tempfile.mkdtemp(dir=finished_path)
        instance['path'] = os.path.basename(ans)
        try:
            metadata = json.loads(f.read())
        except ValueError:
            metadata = {'entries': {}, 'last_clear_at': 0}
        entries = metadata['entries']
        instances = entries.setdefault(key, [])
        os.rmdir(ans)
        os.rename(src_path, ans)
        instance['status'] = 'finished'
        for q in instances:
            if q['id'] == instance['id']:
                q.update(instance)
                break
        expire_cache_and_temp(temp_path, finished_path, metadata, max_age)
        f.seek(0), f.truncate(), f.write(json.dumps(metadata))
    return ans


def find_tests():
    import unittest

    class TestViewerCache(unittest.TestCase):
        ae = unittest.TestCase.assertEqual

        def setUp(self):
            self.tdir = tempfile.mkdtemp()
            book_cache_dir.override = os.path.join(self.tdir, 'ev2')

        def tearDown(self):
            shutil.rmtree(self.tdir)
            del book_cache_dir.override

        def test_viewer_cache(self):

            def convert_mock(path, temp_path, key, instance):
                self.ae(instance['status'], 'working')
                self.ae(instance['key'], key)
                open(os.path.join(temp_path, instance['path'], 'sentinel'), 'wb').write(b'test')

            book_src = os.path.join(self.tdir, 'book.epub')
            open(book_src, 'wb').write(b'a')
            path = prepare_book(book_src, convert_func=convert_mock)
            self.ae(open(os.path.join(path, 'sentinel'), 'rb').read(), b'test')

            # Test that opening the same book uses the cache
            second_path = prepare_book(book_src, convert_func=convert_mock)
            self.ae(path, second_path)

            # Test that changing the book updates the cache
            open(book_src, 'wb').write(b'bc')
            third_path = prepare_book(book_src, convert_func=convert_mock)
            self.assertNotEqual(path, third_path)

            # Test cache expiry
            open(book_src, 'wb').write(b'bcd')
            prepare_book(book_src, convert_func=convert_mock, max_age=-1000)
            self.ae([], os.listdir(os.path.join(book_cache_dir(), 'f')))

    return unittest.defaultTestLoader.loadTestsFromTestCase(TestViewerCache)
