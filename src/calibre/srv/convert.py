#!/usr/bin/env python
# License: GPLv3 Copyright: 2018, Kovid Goyal <kovid at kovidgoyal.net>


import os
import shutil
import tempfile
from threading import Lock

from calibre.customize.ui import input_profiles, output_profiles
from calibre.db.errors import NoSuchBook
from calibre.srv.changes import formats_added
from calibre.srv.errors import BookNotFound, HTTPNotFound
from calibre.srv.routes import endpoint, json
from calibre.srv.utils import get_library_data
from calibre.utils.monotonic import monotonic
from calibre.utils.shared_file import share_open
from polyglot.builtins import iteritems

receive_data_methods = {'GET', 'POST'}
conversion_jobs = {}
cache_lock = Lock()


class JobStatus:

    def __init__(self, job_id, book_id, tdir, library_id, pathtoebook, conversion_data):
        self.job_id = job_id
        self.log = self.traceback = ''
        self.book_id = book_id
        self.output_path = os.path.join(
            tdir, 'output.' + conversion_data['output_fmt'].lower())
        self.tdir = tdir
        self.library_id, self.pathtoebook = library_id, pathtoebook
        self.conversion_data = conversion_data
        self.running = self.ok = True
        self.last_check_at = monotonic()
        self.was_aborted = False

    def cleanup(self):
        safe_delete_tree(self.tdir)
        self.log = self.traceback = ''

    @property
    def current_status(self):
        try:
            with share_open(os.path.join(self.tdir, 'status'), 'rb') as f:
                lines = f.read().decode('utf-8').splitlines()
        except Exception:
            lines = ()
        for line in reversed(lines):
            if line.endswith('|||'):
                p, msg = line.partition(':')[::2]
                percent = float(p)
                msg = msg[:-3]
                return percent, msg
        return 0, ''


def expire_old_jobs():
    now = monotonic()
    with cache_lock:
        remove = [job_id for job_id, job_status in iteritems(conversion_jobs) if now - job_status.last_check_at >= 360]
        for job_id in remove:
            job_status = conversion_jobs.pop(job_id)
            job_status.cleanup()


def safe_delete_file(path):
    try:
        os.remove(path)
    except OSError:
        pass


def safe_delete_tree(path):
    try:
        shutil.rmtree(path, ignore_errors=True)
    except OSError:
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
            job_status.log = job.read_log()
            job_status.was_aborted = job.was_aborted
            job_status.traceback = job.traceback
    safe_delete_file(job_status.pathtoebook)


def convert_book(path_to_ebook, opf_path, cover_path, output_fmt, recs):
    from calibre.customize.conversion import OptionRecommendation
    from calibre.ebooks.conversion.plumber import Plumber
    from calibre.utils.logging import Log
    recs.append(('verbose', 2, OptionRecommendation.HIGH))
    recs.append(('read_metadata_from_opf', opf_path,
                OptionRecommendation.HIGH))
    if cover_path:
        recs.append(('cover', cover_path, OptionRecommendation.HIGH))
    log = Log()
    os.chdir(os.path.dirname(path_to_ebook))
    status_file = share_open('status', 'wb')

    def notification(percent, msg=''):
        status_file.write(f'{percent}:{msg}|||\n'.encode())
        status_file.flush()

    output_path = os.path.abspath('output.' + output_fmt.lower())
    plumber = Plumber(path_to_ebook, output_path, log,
                      report_progress=notification, override_input_metadata=True)
    plumber.merge_ui_recommendations(recs)
    plumber.run()


def queue_job(ctx, rd, library_id, db, fmt, book_id, conversion_data):
    from calibre.ebooks.metadata.opf2 import metadata_to_opf
    from calibre.ebooks.conversion.config import GuiRecommendations, save_specifics
    from calibre.customize.conversion import OptionRecommendation
    tdir = tempfile.mkdtemp(dir=rd.tdir)
    with tempfile.NamedTemporaryFile(prefix='', suffix=('.' + fmt.lower()), dir=tdir, delete=False) as src_file:
        db.copy_format_to(book_id, fmt, src_file)
    with tempfile.NamedTemporaryFile(prefix='', suffix='.jpg', dir=tdir, delete=False) as cover_file:
        cover_copied = db.copy_cover_to(book_id, cover_file)
    cover_path = cover_file.name if cover_copied else None
    mi = db.get_metadata(book_id)
    mi.application_id = mi.uuid
    raw = metadata_to_opf(mi)
    with tempfile.NamedTemporaryFile(prefix='', suffix='.opf', dir=tdir, delete=False) as opf_file:
        opf_file.write(raw)
    recs = GuiRecommendations()
    recs.update(conversion_data['options'])
    recs['gui_preferred_input_format'] = conversion_data['input_fmt'].lower()
    save_specifics(db, book_id, recs)
    recs = [(k, v, OptionRecommendation.HIGH) for k, v in iteritems(recs)]

    job_id = ctx.start_job(
        f'Convert book {book_id} ({fmt})', 'calibre.srv.convert',
        'convert_book', args=(
            src_file.name, opf_file.name, cover_path, conversion_data['output_fmt'], recs),
        job_done_callback=job_done
    )
    expire_old_jobs()
    with cache_lock:
        conversion_jobs[job_id] = JobStatus(
            job_id, book_id, tdir, library_id, src_file.name, conversion_data)
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


@endpoint('/conversion/status/{job_id}', postprocess=json, needs_db_write=True, types={'job_id': int}, methods=receive_data_methods)
def conversion_status(ctx, rd, job_id):
    with cache_lock:
        job_status = conversion_jobs.get(job_id)
        if job_status is None:
            raise HTTPNotFound(f'No job with id: {job_id}')
        job_status.last_check_at = monotonic()
        if job_status.running:
            percent, msg = job_status.current_status
            if rd.query.get('abort_job'):
                ctx.abort_job(job_id)
            return {'running': True, 'percent': percent, 'msg': msg}

        del conversion_jobs[job_id]

    try:
        ans = {'running': False, 'ok': job_status.ok, 'was_aborted':
               job_status.was_aborted, 'traceback': job_status.traceback,
               'log': job_status.log}
        if job_status.ok:
            db, library_id = get_library_data(ctx, rd)[:2]
            if library_id != job_status.library_id:
                raise HTTPNotFound('job library_id does not match')
            fmt = job_status.output_path.rpartition('.')[-1]
            try:
                db.add_format(job_status.book_id, fmt, job_status.output_path)
            except NoSuchBook:
                raise HTTPNotFound(
                    f'book_id {job_status.book_id} not found in library')
            formats_added({job_status.book_id: (fmt,)})
            ans['size'] = os.path.getsize(job_status.output_path)
            ans['fmt'] = fmt
        return ans
    finally:
        job_status.cleanup()


def get_conversion_options(input_fmt, output_fmt, book_id, db):
    from calibre.ebooks.conversion.plumber import create_dummy_plumber
    from calibre.ebooks.conversion.config import (
        load_specifics, load_defaults, OPTIONS, options_for_input_fmt, options_for_output_fmt)
    from calibre.customize.conversion import OptionRecommendation
    plumber = create_dummy_plumber(input_fmt, output_fmt)
    specifics = load_specifics(db, book_id)
    ans = {'options': {}, 'disabled': set(), 'defaults': {}, 'help': {}}
    ans['input_plugin_name'] = plumber.input_plugin.commit_name
    ans['output_plugin_name'] = plumber.output_plugin.commit_name
    ans['input_ui_data'] = plumber.input_plugin.ui_data
    ans['output_ui_data'] = plumber.output_plugin.ui_data

    def merge_group(group_name, option_names):
        if not group_name or group_name in ('debug', 'metadata'):
            return
        defs = load_defaults(group_name)
        defs.merge_recommendations(
            plumber.get_option_by_name, OptionRecommendation.LOW, option_names)
        specifics.merge_recommendations(
            plumber.get_option_by_name, OptionRecommendation.HIGH, option_names, only_existing=True)
        defaults = defs.as_dict()['options']
        for k in defs:
            if k in specifics:
                defs[k] = specifics[k]
        defs = defs.as_dict()
        ans['options'].update(defs['options'])
        ans['disabled'] |= set(defs['disabled'])
        ans['defaults'].update(defaults)
        ans['help'] = plumber.get_all_help()

    for group_name, option_names in iteritems(OPTIONS['pipe']):
        merge_group(group_name, option_names)

    group_name, option_names = options_for_input_fmt(input_fmt)
    merge_group(group_name, option_names)
    group_name, option_names = options_for_output_fmt(output_fmt)
    merge_group(group_name, option_names)

    ans['disabled'] = tuple(ans['disabled'])
    return ans


def profiles():
    ans = getattr(profiles, 'ans', None)
    if ans is None:
        def desc(profile):
            w, h = profile.screen_size
            if w >= 10000:
                ss = _('unlimited')
            else:
                ss = _('%(width)d x %(height)d pixels') % dict(width=w, height=h)
            ss = _('Screen size: %s') % ss
            return {'name': profile.name, 'description': (f'{profile.description} [{ss}]')}

        ans = profiles.ans = {}
        ans['input'] = {p.short_name: desc(p) for p in input_profiles()}
        ans['output'] = {p.short_name: desc(p) for p in output_profiles()}
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
        'profiles': profiles(),
        'conversion_options': get_conversion_options(input_fmt, output_formats[0], book_id, db),
        'title': db.field_for('title', book_id),
        'authors': db.field_for('authors', book_id),
        'book_id': book_id
    }
    return ans
