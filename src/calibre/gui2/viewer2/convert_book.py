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
from calibre.constants import cache_dir
from calibre.srv.render_book import RENDER_VERSION
from calibre.utils.ipc.simple_worker import fork_job
from calibre.utils.lock import ExclusiveFile

DAY = 24 * 3600


def book_cache_dir():
    return os.path.join(cache_dir(), 'ev2')


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


def clear_temp(temp_path):
    now = time.time()
    for x in os.listdir(temp_path):
        x = os.path.join(temp_path, x)
        st = os.stat(x)
        if now - st.st_mtime > DAY:
            try:
                shutil.rmtree(x)
            except EnvironmentError:
                pass


def expire_cache(path, instances):
    now = time.time()
    remove = [x for x in instances if now - instances['atime'] > 30 * DAY]
    for instance in remove:
        instances.remove(instance)
        if instances['status'] == 'finished':
            try:
                shutil.rmtree(os.path.join(path, instances['path']))
            except Exception:
                pass


def expire_cache_and_temp(temp_path, finished_path, metadata):
    now = time.time()
    if now - metadata['last_clear_at'] < DAY:
        return
    clear_temp(temp_path)
    entries = metadata['entries']
    for key, instances in tuple(entries.items()):
        expire_cache(finished_path, instances)
        if not instances:
            del entries[key]
    metadata['last_clear_at'] = now


def prepare_convert(temp_path, key, st):
    tdir = tempfile.mkdtemp(dir=temp_path)
    now = time.time()
    return {
        'path': os.path.basename(tdir),
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


def prepare_book(path):
    st = os.stat(path)
    key = book_hash(path, st.st_size, st.st_mtime)
    finished_path = safe_makedirs(os.path.join(book_cache_dir(), 'f'))
    temp_path = safe_makedirs(os.path.join(book_cache_dir(), 't'))
    with cache_lock() as f:
        try:
            metadata = json.loads(f.read())
        except ValueError:
            metadata = {'entries': [], 'last_clear_at': 0}
        entries = metadata['entries']
        instances = entries.setdefault(key, [])
        for instance in instances:
            if instance['status'] == 'finished':
                instance['atime'] = time.time()
                f.seek(0), f.write(json.dumps(metadata))
                return os.path.join(finished_path, instance['path'])
        instance = prepare_convert(temp_path, key, st)
        instances.append(instance)
        f.seek(0), f.write(json.dumps(metadata))
    do_convert(path, temp_path, key, instance)
    src_path = os.path.join(temp_path, instance['path'])
    with cache_lock() as f:
        ans = tempfile.mkdtemp(dir=finished_path)
        instance['path'] = os.path.basename(ans)
        try:
            metadata = json.loads(f.read())
        except ValueError:
            metadata = {'entries': [], 'last_cleat_at': 0}
        entries = metadata['entries']
        instances = entries.setdefault(key, [])
        os.rmdir(ans)
        os.rename(src_path, ans)
        for q in instances:
            if q['id'] == instance['id']:
                q.update(instance)
                break
        expire_cache_and_temp(temp_path, finished_path, metadata)
        f.seek(0), f.write(json.dumps(metadata))
    return ans
