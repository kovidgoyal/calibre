#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2016, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import (unicode_literals, division, absolute_import,
                        print_function)
from hashlib import sha1
from functools import partial
from threading import RLock
from cPickle import dumps
import errno, os, tempfile, shutil

from calibre.constants import cache_dir, iswindows
from calibre.customize.ui import plugin_for_input_format
from calibre.srv.render_book import RENDER_VERSION
from calibre.srv.errors import HTTPNotFound
from calibre.srv.routes import endpoint, json
from calibre.srv.utils import get_library_data

cache_lock = RLock()
queued_jobs = {}
failed_jobs = {}

_books_cache_dir = None
def books_cache_dir():
    global _books_cache_dir
    if _books_cache_dir:
        return _books_cache_dir
    base = os.path.abspath(os.path.join(cache_dir(), 'srvb'))
    for d in 'sf':
        try:
            os.makedirs(os.path.join(base, d))
        except EnvironmentError as e:
            if e.errno != errno.EEXIST:
                raise
    _books_cache_dir = base
    return base


def book_hash(library_uuid, book_id, fmt, fmt_metadata):
    raw = dumps((library_uuid, book_id, fmt.upper(), fmt_metadata['size']), RENDER_VERSION)
    return sha1(raw).hexdigest().decode('ascii')

staging_cleaned = False

def safe_remove(x, is_file=None):
    if is_file is None:
        is_file = os.path.isfile(x)
    try:
        os.remove(x) if is_file else shutil.rmtree(x, ignore_errors=True)
    except EnvironmentError:
        pass


def queue_job(ctx, copy_format_to, bhash, fmt, book_id):
    global staging_cleaned
    tdir = os.path.join(books_cache_dir(), 's')
    if not staging_cleaned:
        staging_cleaned = True
        for x in os.listdir(tdir):
            safe_remove(os.path.join(tdir, x))
    fd, pathtoebook = tempfile.mkstemp(prefix='', suffix=('.' + fmt.lower()), dir=tdir)
    with os.fdopen(fd, 'wb') as f:
        copy_format_to(f)
    tdir = tempfile.mkdtemp('', '', tdir)
    job_id = ctx.start_job('Render book %s (%s)' % (book_id, fmt), 'calibre.srv.render_book', 'render', args=(pathtoebook, tdir, bhash),
                           job_done_callback=job_done, job_data=(bhash, pathtoebook, tdir))
    queued_jobs[bhash] = job_id
    return job_id

def job_done(job):
    with cache_lock:
        book_hash, pathtoebook, tdir = job.data
        queued_jobs.pop(book_hash, None)
        safe_remove(pathtoebook)
        if job.failed:
            failed_jobs[book_hash] = (job.was_aborted, job.traceback)
            safe_remove(tdir, False)
        else:
            try:
                dest = os.path.join(books_cache_dir(), 'f', book_hash)
                safe_remove(dest, False)
                os.rename(tdir, dest)
            except Exception:
                import traceback
                failed_jobs[book_hash] = (False, traceback.format_exc())

@endpoint('/book-manifest/{book_id}/{fmt}', postprocess=json, types={'book_id':int})
def book_manifest(ctx, rd, book_id, fmt):
    db, library_id = get_library_data(ctx, rd)[:2]
    if plugin_for_input_format(fmt) is None:
        raise HTTPNotFound('The format %s cannot be viewed' % fmt.upper())
    with db.safe_read_lock:
        fm = db.format_metadata(book_id, fmt)
        if not fm:
            raise HTTPNotFound('No %s format for the book %s in the library: %s' % (fm, book_id, library_id))
        bhash = book_hash(db.library_id, book_id, fmt, fm)
        with cache_lock:
            mpath = os.path.join(books_cache_dir(), 'f', bhash, 'calibre-book-manifest.json')
            if iswindows:
                mpath = '\\\\?\\' + os.path.abspath(mpath)
            try:
                os.utime(mpath, None)
                return lopen(mpath, 'rb')
            except EnvironmentError as e:
                if e.errno != errno.ENOENT:
                    raise
            x = failed_jobs.pop(bhash, None)
            if x is not None:
                return {'aborted':x[0], 'traceback':x[1], 'job_status':'finished'}
            job_id = queued_jobs.get(bhash)
            if job_id is None:
                job_id = queue_job(ctx, partial(db.copy_format_to, book_id, fmt), bhash, fmt, book_id)
    status, result, tb, aborted = ctx.job_status(job_id)
    return {'aborted': aborted, 'traceback':tb, 'job_status':status, 'job_id':job_id}

@endpoint('/book-file/{book_hash}/{name}')
def book_file(ctx, rd, book_hash, name):
    base = os.path.join(books_cache_dir, 'f')
    mpath = os.path.abspath(os.path.join(book_hash, name))
    if not mpath.startswith(base):
        raise HTTPNotFound('No book file with hash: %s and name: %s' % (book_hash, name))
    try:
        return rd.filesystem_file_with_custom_etag(lopen(mpath, 'rb'), book_hash, name)
    except EnvironmentError as e:
        if e.errno != errno.ENOENT:
            raise
        raise HTTPNotFound('No book file with hash: %s and name: %s' % (book_hash, name))
