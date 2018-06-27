#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2018, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import absolute_import, division, print_function, unicode_literals

import os
import shutil
import tempfile
from threading import Lock

from calibre.srv.errors import BookNotFound, HTTPNotFound
from calibre.srv.routes import endpoint, json
from calibre.srv.utils import get_library_data
from calibre.utils.monotonic import monotonic

receive_data_methods = {'GET', 'POST'}
conversion_jobs = {}
cache_lock = Lock()


class JobStatus(object):

    def __init__(self, job_id, tdir, library_id, pathtoebook, conversion_data):
        self.job_id = job_id
        self.tdir = tdir
        self.library_id, self.pathtoebook = library_id, pathtoebook
        self.conversion_data = conversion_data
        self.running = self.ok = True
        self.last_check_at = monotonic()

    def cleanup(self):
        safe_delete_tree(self.tdir)


def expire_old_jobs():
    now = monotonic()
    with cache_lock:
        remove = [job_id for job_id, job_status in conversion_jobs.iteritems() if now - job_status.last_check_at >= 360]
        for job_id in remove:
            conversion_jobs.pop(job_id)


def safe_delete_file(path):
    try:
        os.remove(path)
    except EnvironmentError:
        pass


def safe_delete_tree(path):
    try:
        shutil.rmtree(path, ignore_errors=True)
    except EnvironmentError:
        pass


def job_done(job):
    with cache_lock:
        try:
            job_status = conversion_jobs[job.job_id]
        except KeyError:
            return
        job_status.running = False
        if job.failed:
            job_status.ok = False
            job_status.was_aborted = job.was_aborted
            job_status.traceback = job.traceback
    safe_delete_file(job_status.pathtoebook)


def convert_book(path_to_ebook, opf_path, cover_path, output_fmt, recs):
    pass


def queue_job(ctx, rd, library_id, db, fmt, book_id, conversion_data):
    from calibre.ebooks.metadata.opf2 import metadata_to_opf
    from calibre.ebooks.conversion.config import GuiRecommendations, save_specifics
    from calibre.customize.conversion import OptionRecommendation
    tdir = tempfile.mkdtemp(dir=rd.tdir)
    fd, pathtoebook = tempfile.mkstemp(prefix='', suffix=('.' + fmt.lower()), dir=tdir)
    with os.fdopen(fd, 'wb') as f:
        db.copy_format_to(book_id, fmt, f)
    fd, pathtocover = tempfile.mkstemp(prefix='', suffix=('.jpg'), dir=tdir)
    with os.fdopen(fd, 'wb') as f:
        cover_copied = db.copy_cover_to(book_id, f)
    cover_path = f.name if cover_copied else None
    mi = db.get_metadata(book_id)
    mi.application_id = mi.uuid
    raw = metadata_to_opf(mi)
    fd, pathtocover = tempfile.mkstemp(prefix='', suffix=('.opf'), dir=tdir)
    with os.fdopen(fd, 'wb') as metadata_file:
        metadata_file.write(raw)

    recs = GuiRecommendations()
    recs.update(conversion_data['options'])
    recs['gui_preferred_input_format'] = conversion_data.input_fmt.lower()
    save_specifics(db, book_id, recs)
    recs = [(k, v, OptionRecommendation.HIGH) for k, v in recs.iteritems()]

    job_id = ctx.start_job(
        'Convert book %s (%s)' % (book_id, fmt), 'calibre.srv.convert_book',
        'convert_book', args=(
            pathtoebook, metadata_file.name, cover_path, conversion_data['output_fmt'], recs),
        job_done_callback=job_done
    )
    expire_old_jobs()
    with cache_lock:
        conversion_jobs[job_id] = JobStatus(job_id, tdir, library_id, pathtoebook, conversion_data)
    return job_id


@endpoint('/conversion/start/{book_id}', postprocess=json, needs_db_write=True, types={'book_id': int}, methods=receive_data_methods)
def start_conversion(ctx, rd, book_id):
    db, library_id = get_library_data(ctx, rd)[:2]
    if not ctx.has_id(rd, db, book_id):
        raise BookNotFound(book_id, db)
    data = json.loads(rd.request_body_file.read())
    input_fmt = data['input_fmt']
    job_id = queue_job(ctx, rd, library_id, db, input_fmt, book_id, data)
    return job_id


@endpoint('/conversion/status/{job_id}', postprocess=json, needs_db_write=True, types={'job_id': int})
def conversion_status(ctx, rd, job_id):
    with cache_lock:
        job_status = conversion_jobs.get(job_id)
        if job_status is None:
            raise HTTPNotFound('No job with id: {}'.format(job_id))
        job_status.last_check_at = monotonic()
        if job_status.running:
            pass
        else:
            del conversion_jobs[job_id]
            job_status.cleanup()


def get_conversion_options(input_fmt, output_fmt, book_id, db):
    from calibre.ebooks.conversion.plumber import create_dummy_plumber
    from calibre.ebooks.conversion.config import (
        load_specifics, load_defaults, OPTIONS, options_for_input_fmt, options_for_output_fmt)
    from calibre.customize.conversion import OptionRecommendation
    plumber = create_dummy_plumber(input_fmt, output_fmt)
    specifics = load_specifics(db, book_id)
    ans = {'options': {}, 'disabled': set()}

    def merge_group(group_name, option_names):
        if not group_name or group_name == 'debug':
            return
        defs = load_defaults(group_name)
        defs.merge_recommendations(plumber.get_option_by_name, OptionRecommendation.LOW, option_names)
        specifics.merge_recommendations(plumber.get_option_by_name, OptionRecommendation.HIGH, option_names, only_existing=True)
        for k in defs:
            if k in specifics:
                defs[k] = specifics[k]
        defs = defs.as_dict()
        ans['options'].update(defs['options'])
        ans['disabled'] |= set(defs['disabled'])

    for group_name, option_names in OPTIONS['pipe'].iteritems():
        merge_group(group_name, option_names)

    group_name, option_names = options_for_input_fmt(input_fmt)
    merge_group(group_name, option_names)
    group_name, option_names = options_for_output_fmt(output_fmt)
    merge_group(group_name, option_names)

    ans['disabled'] = tuple(ans['disabled'])
    return ans


@endpoint('/conversion/book-data/{book_id}', postprocess=json, types={'book_id': int})
def conversion_data(ctx, rd, book_id):
    from calibre.ebooks.conversion.config import (
        NoSupportedInputFormats, get_input_format_for_book, get_sorted_output_formats)
    db = get_library_data(ctx, rd)[0]
    if not ctx.has_id(rd, db, book_id):
        raise BookNotFound(book_id, db)
    try:
        input_format, input_formats = get_input_format_for_book(db, book_id)
    except NoSupportedInputFormats:
        input_formats = []
    else:
        if rd.query.get('input_fmt') and rd.query.get('input_fmt').lower() in input_formats:
            input_format = rd.query.get('input_fmt').lower()
        if input_format in input_formats:
            input_formats.remove(input_format)
            input_formats.insert(0, input_format)
    input_fmt = input_formats[0] if input_formats else 'epub'
    output_formats = get_sorted_output_formats(rd.query.get('output_fmt'))
    ans = {
        'input_formats': [x.upper() for x in input_formats],
        'output_formats': output_formats,
        'conversion_options': get_conversion_options(input_fmt, output_formats[0], book_id, db),
        'title': db.field_for('title', book_id),
        'authors': db.field_for('authors', book_id),
        'book_id': book_id
    }
    return ans
