#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2016, Kovid Goyal <kovid at kovidgoyal.net>


import errno
import json as jsonlib
import os
import tempfile
import time
from functools import partial
from hashlib import sha1
from threading import Lock, RLock

from calibre.constants import cache_dir, iswindows
from calibre.customize.ui import plugin_for_input_format
from calibre.srv.errors import BookNotFound, HTTPNotFound
from calibre.srv.metadata import book_as_json
from calibre.srv.render_book import RENDER_VERSION
from calibre.srv.routes import endpoint, json
from calibre.srv.utils import get_db, get_library_data
from calibre.utils.filenames import rmtree
from calibre.utils.serialize import json_dumps
from polyglot.builtins import as_unicode, itervalues, map

cache_lock = RLock()
queued_jobs = {}
failed_jobs = {}


def abspath(x):
    x = os.path.abspath(x)
    if iswindows and not x.startswith('\\\\?\\'):
        x = '\\\\?\\' + os.path.abspath(x)
    return x


_books_cache_dir = None


def books_cache_dir():
    global _books_cache_dir
    if _books_cache_dir:
        return _books_cache_dir
    base = abspath(os.path.join(cache_dir(), 'srvb'))
    for d in 'sf':
        try:
            os.makedirs(os.path.join(base, d))
        except EnvironmentError as e:
            if e.errno != errno.EEXIST:
                raise
    _books_cache_dir = base
    return base


def book_hash(library_uuid, book_id, fmt, size, mtime):
    raw = json_dumps((library_uuid, book_id, fmt.upper(), size, mtime, RENDER_VERSION))
    return as_unicode(sha1(raw).hexdigest())


staging_cleaned = False


def safe_remove(x, is_file=None):
    if is_file is None:
        is_file = os.path.isfile(x)
    try:
        os.remove(x) if is_file else rmtree(x, ignore_errors=True)
    except EnvironmentError:
        pass


def queue_job(ctx, copy_format_to, bhash, fmt, book_id, size, mtime):
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
    job_id = ctx.start_job('Render book %s (%s)' % (book_id, fmt), 'calibre.srv.render_book', 'render', args=(
        pathtoebook, tdir, {'size':size, 'mtime':mtime, 'hash':bhash}),
        job_done_callback=job_done, job_data=(bhash, pathtoebook, tdir))
    queued_jobs[bhash] = job_id
    return job_id


last_final_clean_time = 0


def clean_final(interval=24 * 60 * 60):
    global last_final_clean_time
    now = time.time()
    if now - last_final_clean_time < interval:
        return
    last_final_clean_time = now
    fdir = os.path.join(books_cache_dir(), 'f')
    for x in os.listdir(fdir):
        try:
            tm = os.path.getmtime(os.path.join(fdir, x,  'calibre-book-manifest.json'))
        except EnvironmentError:
            continue
        if now - tm >= interval:
            # This book has not been accessed for a long time, delete it
            safe_remove(x)


def job_done(job):
    with cache_lock:
        bhash, pathtoebook, tdir = job.data
        queued_jobs.pop(bhash, None)
        safe_remove(pathtoebook)
        if job.failed:
            failed_jobs[bhash] = (job.was_aborted, job.traceback)
            safe_remove(tdir, False)
        else:
            try:
                clean_final()
                dest = os.path.join(books_cache_dir(), 'f', bhash)
                safe_remove(dest, False)
                os.rename(tdir, dest)
            except Exception:
                import traceback
                failed_jobs[bhash] = (False, traceback.format_exc())


@endpoint('/book-manifest/{book_id}/{fmt}', postprocess=json, types={'book_id':int})
def book_manifest(ctx, rd, book_id, fmt):
    db, library_id = get_library_data(ctx, rd)[:2]
    force_reload = rd.query.get('force_reload') == '1'
    if plugin_for_input_format(fmt) is None:
        raise HTTPNotFound('The format %s cannot be viewed' % fmt.upper())
    if not ctx.has_id(rd, db, book_id):
        raise BookNotFound(book_id, db)
    with db.safe_read_lock:
        fm = db.format_metadata(book_id, fmt, allow_cache=False)
        if not fm:
            raise HTTPNotFound('No %s format for the book (id:%s) in the library: %s' % (fmt, book_id, library_id))
        size, mtime = map(int, (fm['size'], time.mktime(fm['mtime'].utctimetuple())*10))
        bhash = book_hash(db.library_id, book_id, fmt, size, mtime)
        with cache_lock:
            mpath = abspath(os.path.join(books_cache_dir(), 'f', bhash, 'calibre-book-manifest.json'))
            if force_reload:
                safe_remove(mpath, True)
            try:
                os.utime(mpath, None)
                with lopen(mpath, 'rb') as f:
                    ans = jsonlib.load(f)
                ans['metadata'] = book_as_json(db, book_id)
                user = rd.username or None
                ans['last_read_positions'] = db.get_last_read_positions(book_id, fmt, user) if user else []
                ans['annotations_map'] = db.annotations_map_for_book(book_id, fmt, user_type='web', user=user or '*')
                return ans
            except EnvironmentError as e:
                if e.errno != errno.ENOENT:
                    raise
            x = failed_jobs.pop(bhash, None)
            if x is not None:
                return {'aborted':x[0], 'traceback':x[1], 'job_status':'finished'}
            job_id = queued_jobs.get(bhash)
            if job_id is None:
                job_id = queue_job(ctx, partial(db.copy_format_to, book_id, fmt), bhash, fmt, book_id, size, mtime)
    status, result, tb, aborted = ctx.job_status(job_id)
    return {'aborted': aborted, 'traceback':tb, 'job_status':status, 'job_id':job_id}


@endpoint('/book-file/{book_id}/{fmt}/{size}/{mtime}/{+name}', types={'book_id':int, 'size':int, 'mtime':int})
def book_file(ctx, rd, book_id, fmt, size, mtime, name):
    db, library_id = get_library_data(ctx, rd)[:2]
    if not ctx.has_id(rd, db, book_id):
        raise BookNotFound(book_id, db)
    bhash = book_hash(db.library_id, book_id, fmt, size, mtime)
    base = abspath(os.path.join(books_cache_dir(), 'f'))
    mpath = abspath(os.path.join(base, bhash, name))
    if not mpath.startswith(base):
        raise HTTPNotFound('No book file with hash: %s and name: %s' % (bhash, name))
    try:
        return rd.filesystem_file_with_custom_etag(lopen(mpath, 'rb'), bhash, name)
    except EnvironmentError as e:
        if e.errno != errno.ENOENT:
            raise
        raise HTTPNotFound('No book file with hash: %s and name: %s' % (bhash, name))


@endpoint('/book-get-last-read-position/{library_id}/{+which}', postprocess=json)
def get_last_read_position(ctx, rd, library_id, which):
    '''
    Get last read position data for the specified books, where which is of the form:
    book_id1-fmt1_book_id2-fmt2,...
    '''
    db = get_db(ctx, rd, library_id)
    user = rd.username or None
    if not user:
        raise HTTPNotFound('login required for sync')
    ans = {}
    allowed_book_ids = ctx.allowed_book_ids(rd, db)
    for item in which.split('_'):
        book_id, fmt = item.partition('-')[::2]
        try:
            book_id = int(book_id)
        except Exception:
            continue
        if book_id not in allowed_book_ids:
            continue
        key = '{}:{}'.format(book_id, fmt)
        ans[key] = db.get_last_read_positions(book_id, fmt, user)
    return ans


@endpoint('/book-set-last-read-position/{library_id}/{book_id}/{+fmt}', types={'book_id': int}, methods=('POST',))
def set_last_read_position(ctx, rd, library_id, book_id, fmt):
    db = get_db(ctx, rd, library_id)
    user = rd.username or None
    if not ctx.has_id(rd, db, book_id):
        raise BookNotFound(book_id, db)
    try:
        data = jsonlib.load(rd.request_body_file)
        device, cfi, pos_frac = data['device'], data['cfi'], data['pos_frac']
    except Exception:
        raise HTTPNotFound('Invalid data')
    db.set_last_read_position(
        book_id, fmt, user=user, device=device, cfi=cfi or None, pos_frac=pos_frac)
    rd.outheaders['Content-type'] = 'text/plain'
    return b''


@endpoint('/book-get-annotations/{library_id}/{+which}', postprocess=json)
def get_annotations(ctx, rd, library_id, which):
    '''
    Get annotations and last read position data for the specified books, where which is of the form:
    book_id1-fmt1_book_id2-fmt2,...
    '''
    db = get_db(ctx, rd, library_id)
    user = rd.username or '*'
    ans = {}
    allowed_book_ids = ctx.allowed_book_ids(rd, db)
    for item in which.split('_'):
        book_id, fmt = item.partition('-')[::2]
        try:
            book_id = int(book_id)
        except Exception:
            continue
        if book_id not in allowed_book_ids:
            continue
        key = '{}:{}'.format(book_id, fmt)
        ans[key] = {
            'last_read_positions': db.get_last_read_positions(book_id, fmt, user),
            'annotations_map': db.annotations_map_for_book(book_id, fmt, user_type='web', user=user) if user else {}
        }
    return ans


@endpoint('/book-update-annotations/{library_id}/{book_id}/{+fmt}', types={'book_id': int}, methods=('POST',))
def update_annotations(ctx, rd, library_id, book_id, fmt):
    db = get_db(ctx, rd, library_id)
    user = rd.username or '*'
    if not ctx.has_id(rd, db, book_id):
        raise BookNotFound(book_id, db)
    try:
        amap = jsonlib.load(rd.request_body_file)
    except Exception:
        raise HTTPNotFound('Invalid data')
    alist = []
    for val in itervalues(amap):
        if val:
            alist.extend(val)
    db.merge_annotations_for_book(book_id, fmt, alist, user_type='web', user=user)
    return b''


mathjax_lock = Lock()
mathjax_manifest = None


def manifest_as_json():
    return P('mathjax/manifest.json', data=True, allow_user_override=False)


def get_mathjax_manifest():
    global mathjax_manifest
    with mathjax_lock:
        if mathjax_manifest is None:
            mathjax_manifest = jsonlib.loads(manifest_as_json())
    return mathjax_manifest


@endpoint('/mathjax/{+which=""}', auth_required=False)
def mathjax(ctx, rd, which):
    manifest = get_mathjax_manifest()
    if not which:
        return rd.etagged_dynamic_response(manifest['etag'], manifest_as_json, content_type='application/json; charset=UTF-8')
    if which not in manifest['files']:
        raise HTTPNotFound('No MathJax file named: %s' % which)
    path = os.path.abspath(P('mathjax/' + which, allow_user_override=False))
    if not path.startswith(P('mathjax', allow_user_override=False)):
        raise HTTPNotFound('No MathJax file named: %s' % which)
    return rd.filesystem_file_with_constant_etag(lopen(path, 'rb'), manifest['etag'])
