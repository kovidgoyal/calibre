#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, Kovid Goyal <kovid at kovidgoyal.net>

# Download metadata and covers for a book from the online metadata sources, for
# the metadata editor in the browser. Downloads take tens of seconds, so they
# run as jobs in worker processes and the browser polls for the results.

import json as stdlib_json
import os
import shutil
import tempfile
from collections import Counter
from threading import Lock
from typing import IO, TYPE_CHECKING, NamedTuple, TypedDict, cast

from calibre.srv.errors import BookNotFound, HTTPBadRequest, HTTPForbidden, HTTPNotFound, HTTPSimpleResponse
from calibre.srv.routes import endpoint, json
from calibre.srv.utils import get_db
from calibre.utils.localization import calibre_langcode_to_name
from calibre.utils.monotonic import monotonic
from calibre.utils.serialize import json_loads
from calibre.utils.shared_file import share_open

if TYPE_CHECKING:
    from calibre.db.cache import Cache
    from calibre.ebooks.metadata.book.base import Metadata
    from calibre.ebooks.metadata.sources.base import CachesDump
    from calibre.srv.handler import Context
    from calibre.srv.http_response import RequestData
    from calibre.srv.jobs import Job


class DownloadedMetadata(TypedDict, total=False):
    title: str
    authors: list[str]
    publisher: str
    pubdate: str
    series: str
    series_index: float
    rating: int
    tags: list[str]
    identifiers: dict[str, str]
    languages: list[str]
    comments: str
    merged_comments: str


class DownloadResult(TypedDict):
    results: list[DownloadedMetadata]
    # Fields the user has chosen to never set from downloaded metadata
    ignore_fields: list[str]
    log: str
    # The caches of the metadata sources, which have the URLs of the covers of
    # the results, for downloading covers. They are never sent to the browser,
    # as the sources download whatever URLs are in them.
    caches: dict[str, CachesDump]


class DownloadedCover(TypedDict):
    num: int
    source: str
    width: int
    height: int


class DownloadRequest(NamedTuple):
    title: str | None
    authors: list[str] | None
    identifiers: dict[str, str]
    comments: str
    # The id of the metadata download whose result the covers are for
    metadata_download_id: int | None


class IdentifyCaches(NamedTuple):
    username: str | None
    library_id: str
    caches: dict[str, CachesDump]
    created_at: float


# A user can only have this many downloads that have not finished, so that
# they cannot fill up the queue of worker processes
MAX_DOWNLOADS_PER_USER = 3
# Downloads whose results the browser has stopped asking for, because the
# editor was closed, are aborted or forgotten after this many seconds. Browsers
# poll at least once a minute even in background tabs.
ABANDONED_AFTER = 300
# The caches from metadata downloads are used to download covers for their
# results for this many seconds
CACHES_KEPT_FOR = 1800

receive_data_methods = {'POST'}
# Never call ctx.abort_job() with this held, as the jobs manager calls
# job_done() with its own lock held
lock = Lock()


class DownloadJob:
    def __init__(self, job_id: int, username: str | None, library_id: str, book_id: int, covers_dir: str | None = None) -> None:
        self.job_id = job_id
        self.username = username
        self.library_id = library_id
        self.book_id = book_id
        # Set for cover downloads, the worker puts the covers in it, and they
        # are kept after the download has finished, until the browser is done
        # with them
        self.covers_dir = covers_dir
        self.running = True
        # Aborted jobs that had started are remembered until they finish, so
        # that they count towards the limit on downloads per user
        self.abort_requested = False
        self.ok = False
        self.was_aborted = False
        self.result: DownloadResult | None = None
        self.log = ''
        self.traceback = ''
        self.last_check_at = monotonic()

    def remove_covers(self) -> None:
        if self.covers_dir:
            remove_covers_dir(self.covers_dir)


download_jobs: dict[int, DownloadJob] = {}
# The number of downloads being started by each user
starting_downloads: Counter[str | None] = Counter()
# Jobs that finished before they could be added to download_jobs
finished_too_soon: dict[int, Job] = {}
# By the id of the metadata download they are from
identify_caches: dict[int, IdentifyCaches] = {}
# Directories of aborted cover downloads that could not be removed, because
# the worker was still writing to them while it was being killed
leftover_covers_dirs: set[str] = set()


def remove_covers_dir(path: str) -> None:
    shutil.rmtree(path, ignore_errors=True)
    with lock:
        if os.path.exists(path):
            leftover_covers_dirs.add(path)
        else:
            leftover_covers_dirs.discard(path)


# Worker process {{{


def serialize_result(mi: Metadata, current_comments: str) -> DownloadedMetadata:
    from calibre.library.comments import comments_to_html, merge_comments
    from calibre.utils.date import is_date_undefined
    from calibre.utils.localization import canonicalize_lang

    ans: DownloadedMetadata = {}
    if not mi.is_null('title'):
        ans['title'] = mi.title
    if not mi.is_null('authors'):
        ans['authors'] = list(mi.authors)
    if mi.publisher and mi.publisher.strip():
        ans['publisher'] = mi.publisher
    if (pd := mi.pubdate) is not None and not is_date_undefined(pd):
        # Only the date is meaningful, the browser chooses the time so that the
        # date is the same in all timezones, as it does when editing dates
        ans['pubdate'] = f'{pd.year:04d}-{pd.month:02d}-{pd.day:02d}'
    if mi.series and mi.series.strip():
        ans['series'] = mi.series
        ans['series_index'] = 1.0 if mi.series_index is None else float(mi.series_index)
    if mi.rating is not None and mi.rating > 0:
        # Metadata sources rate out of 5, calibre out of 10. Truncated, as in
        # the Edit metadata dialog.
        ans['rating'] = int(min(mi.rating, 5) * 2)
    if not mi.is_null('tags'):
        ans['tags'] = list(mi.tags)
    if mi.identifiers:
        ans['identifiers'] = dict(mi.identifiers)
    if mi.languages:
        langs = [lc for lc in map(canonicalize_lang, mi.languages) if lc is not None]
        if langs:
            ans['languages'] = langs
    if mi.comments and mi.comments.strip():
        # Some sources, and the option to download comments as plain text,
        # produce plain text, which the Edit metadata dialog converts to HTML
        ans['comments'] = comments_to_html(mi.comments)
        if current_comments.strip():
            ans['merged_comments'] = merge_comments(current_comments, mi.comments)
    return ans


def download_metadata(title: str | None, authors: list[str] | None, identifiers: dict[str, str], current_comments: str) -> DownloadResult:
    """Runs in a worker process. current_comments are the comments of the book
    being edited, used to produce the comments to set when the user has chosen
    to append downloaded comments to the existing comments."""
    from io import StringIO
    from threading import Event

    from calibre.ebooks.metadata.sources.base import create_log, dump_caches
    from calibre.ebooks.metadata.sources.identify import identify, msprefs
    from calibre.ebooks.metadata.sources.update import patch_plugins
    from calibre.scraper.simple import cleanup_overseers

    buf = StringIO()
    log = create_log(buf)
    try:
        patch_plugins()
        # The worker process is killed to abort the download, so the abort
        # event is never set
        results = identify(log, Event(), title=title, authors=authors, identifiers=identifiers)
        if not msprefs['append_comments']:
            current_comments = ''
        return {
            'results': [serialize_result(mi, current_comments) for mi in results],
            # As in the Edit metadata dialog, entries for individual identifiers,
            # of the form identifier:type, are not used
            'ignore_fields': [f for f in msprefs['ignore_fields'] if ':' not in f],
            'log': buf.getvalue(),
            'caches': dump_caches(),
        }
    finally:
        cleanup_overseers()()


def write_atomically(path: str, data: bytes) -> None:
    # The server process lists the covers while they are being downloaded,
    # so it must never see partially written files
    with open(path + '.tmp', 'wb') as f:
        f.write(data)
    os.replace(path + '.tmp', path)


def download_covers(title: str | None, authors: list[str] | None, identifiers: dict[str, str], caches: dict[str, CachesDump], covers_dir: str) -> str:
    """Runs in a worker process. Puts the downloaded covers in covers_dir as they
    are downloaded, as NUM.jpg with their details in NUM.json. Returns the log."""
    from io import StringIO
    from queue import Empty, Queue
    from threading import Event, Thread

    from calibre.ebooks.metadata.sources.base import create_log, load_caches
    from calibre.ebooks.metadata.sources.covers import run_download
    from calibre.ebooks.metadata.sources.update import patch_plugins
    from calibre.scraper.simple import cleanup_overseers
    from calibre.utils.imghdr import what

    if TYPE_CHECKING:
        from calibre.ebooks.metadata.sources.covers import CoverResult

    buf = StringIO()
    log = create_log(buf)
    try:
        patch_plugins()
        load_caches(caches)
        results: Queue[CoverResult] = Queue()
        # The worker process is killed to abort the download, so the abort
        # event is never set
        downloader = Thread(
            target=run_download, args=(log, results, Event()), kwargs={'title': title, 'authors': authors, 'identifiers': identifiers}, daemon=True
        )
        downloader.start()
        num = 0
        while downloader.is_alive() or not results.empty():
            try:
                plugin, width, height, fmt, data = results.get(timeout=0.2)
            except Empty:
                continue
            # run_download() converts covers to JPEG, which is also a format
            # that can be set as the cover of a book
            if what(None, data) != 'jpeg':
                log.error('Ignoring cover from', plugin.name, 'as it is not a JPEG image')
                continue
            write_atomically(os.path.join(covers_dir, f'{num}.jpg'), data)
            details = {'source': plugin.name, 'width': width, 'height': height}
            write_atomically(os.path.join(covers_dir, f'{num}.json'), stdlib_json.dumps(details).encode())
            num += 1
        return buf.getvalue()
    finally:
        cleanup_overseers()()


# }}}


def list_covers(covers_dir: str) -> list[DownloadedCover]:
    ans: list[DownloadedCover] = []
    try:
        names = os.listdir(covers_dir)
    except FileNotFoundError:  # the download was aborted and its covers removed
        return ans
    for name in names:
        num, ext = os.path.splitext(name)
        if ext != '.json' or not num.isdigit():
            continue
        try:
            with open(os.path.join(covers_dir, name), 'rb') as f:
                details = stdlib_json.loads(f.read())
        except FileNotFoundError:
            continue
        ans.append({'num': int(num), 'source': details['source'], 'width': details['width'], 'height': details['height']})
    ans.sort(key=lambda c: c['num'])
    return ans


def record_job_result(dj: DownloadJob, job: Job) -> None:
    dj.running = False
    dj.last_check_at = monotonic()  # so that the results are kept for ABANDONED_AFTER
    dj.was_aborted = job.was_aborted
    if job.failed:
        dj.traceback = job.traceback or ''
    else:
        dj.ok = True
        if dj.covers_dir is None:
            dj.result = cast('DownloadResult', job.result)  # the return value of download_metadata()
        else:
            dj.log = cast('str', job.result)  # the return value of download_covers()


def job_done(job: Job) -> None:
    with lock:
        dj = download_jobs.get(job.job_id)
        if dj is None:
            finished_too_soon[job.job_id] = job
            return
        if not dj.abort_requested:
            record_job_result(dj, job)
            return
        del download_jobs[job.job_id]
    dj.remove_covers()


def abort_downloads(ctx: Context, to_abort: list[DownloadJob]) -> None:
    # Must be called without lock held, after setting abort_requested
    for dj in to_abort:
        if ctx.abort_job(dj.job_id):
            # The job had not started, so it will never finish
            with lock:
                download_jobs.pop(dj.job_id, None)
            dj.remove_covers()


def expire_abandoned_jobs(ctx: Context) -> None:
    now = monotonic()
    to_abort: list[DownloadJob] = []
    to_remove: list[DownloadJob] = []
    with lock:
        for job_id, dj in tuple(download_jobs.items()):
            if not dj.abort_requested and now - dj.last_check_at > ABANDONED_AFTER:
                if dj.running:
                    dj.abort_requested = True
                    to_abort.append(dj)
                else:
                    del download_jobs[job_id]
                    to_remove.append(dj)
        for job_id, ic in tuple(identify_caches.items()):
            if now - ic.created_at > CACHES_KEPT_FOR:
                del identify_caches[job_id]
        leftovers = tuple(leftover_covers_dirs)
    for path in leftovers:
        remove_covers_dir(path)
    for dj in to_remove:
        dj.remove_covers()
    abort_downloads(ctx, to_abort)


def parse_download_request(rd: RequestData) -> DownloadRequest:
    try:
        data = json_loads(rd.read())
    except Exception:
        raise HTTPBadRequest('The request must be a JSON object')
    if not isinstance(data, dict):
        raise HTTPBadRequest('The request must be a JSON object')
    title, authors, identifiers, comments = data.get('title'), data.get('authors'), data.get('identifiers') or {}, data.get('comments') or ''
    metadata_download_id = data.get('metadata_download_id')
    if title is not None and not isinstance(title, str):
        raise HTTPBadRequest('title must be a string')
    if authors is not None and not (isinstance(authors, list) and all(isinstance(a, str) for a in authors)):
        raise HTTPBadRequest('authors must be a list of strings')
    if not isinstance(identifiers, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in identifiers.items()):
        raise HTTPBadRequest('identifiers must be an object mapping strings to strings')
    if not isinstance(comments, str):
        raise HTTPBadRequest('comments must be a string')
    if metadata_download_id is not None and (isinstance(metadata_download_id, bool) or not isinstance(metadata_download_id, int)):
        raise HTTPBadRequest('metadata_download_id must be an integer')
    if not title and not authors and not identifiers:
        raise HTTPBadRequest('At least one of title, authors or identifiers is needed to download metadata or covers')
    return DownloadRequest(title or None, authors or None, identifiers, comments, metadata_download_id)


def db_for_download(ctx: Context, rd: RequestData, book_id: int, library_id: str | None) -> Cache:
    db = get_db(ctx, rd, library_id)
    # Matches cdb_set_fields(), as what is downloaded is only useful for
    # changing the metadata of the book
    if ctx.restriction_for(rd, db):
        raise HTTPForbidden('Cannot download metadata with a user who has per library restrictions')
    if not ctx.has_id(rd, db, book_id):
        raise BookNotFound(book_id, db)
    return db


def start_download(
    ctx: Context, rd: RequestData, db: Cache, book_id: int, func: str, args: tuple[object, ...], covers_dir: str | None = None
) -> dict[str, int]:
    expire_abandoned_jobs(ctx)
    with lock:
        # Anonymous users, which are allowed to make changes only from trusted
        # IP addresses, share a limit
        running = sum(1 for dj in download_jobs.values() if dj.running and dj.username == rd.username)
        if running + starting_downloads[rd.username] >= MAX_DOWNLOADS_PER_USER:
            raise HTTPSimpleResponse(429, 'Too many downloads of metadata or covers are in progress, wait for them to finish')
        starting_downloads[rd.username] += 1
    job_id = None
    try:
        from calibre.ebooks.metadata.sources.update import update_sources

        # Get the latest versions of the metadata sources, as calibre does before
        # downloading. Does nothing if they were updated recently.
        update_sources()
        what = 'covers' if covers_dir else 'metadata'
        job_id = ctx.start_job(f'Download {what} for book: {book_id}', 'calibre.srv.metadata_download', func, args=args, job_done_callback=job_done)
    finally:
        with lock:
            starting_downloads[rd.username] -= 1
            if starting_downloads[rd.username] <= 0:
                del starting_downloads[rd.username]
            if job_id is not None:
                download_jobs[job_id] = dj = DownloadJob(job_id, rd.username, db.server_library_id, book_id, covers_dir)
                if (job := finished_too_soon.pop(job_id, None)) is not None:
                    record_job_result(dj, job)
    if job_id is None:
        raise HTTPSimpleResponse(503, 'The server is shutting down')
    return {'job_id': job_id}


@endpoint(
    '/metadata-download/start/{book_id}/{library_id=None}',
    types={'book_id': int},
    needs_db_write=True,
    postprocess=json,
    methods=receive_data_methods,
    cache_control='no-cache',
)
def start_metadata_download(ctx: Context, rd: RequestData, book_id: int, library_id: str | None) -> dict[str, int]:
    """Start downloading metadata matching the title, authors and identifiers
    in the request, which are those in the editor, as they may not have been
    saved yet. Returns the id to use to get the results."""
    db = db_for_download(ctx, rd, book_id, library_id)
    q = parse_download_request(rd)
    return start_download(ctx, rd, db, book_id, 'download_metadata', (q.title, q.authors, q.identifiers, q.comments))


@endpoint(
    '/metadata-download/start-covers/{book_id}/{library_id=None}',
    types={'book_id': int},
    needs_db_write=True,
    postprocess=json,
    methods=receive_data_methods,
    cache_control='no-cache',
)
def start_cover_download(ctx: Context, rd: RequestData, book_id: int, library_id: str | None) -> dict[str, int]:
    """Start downloading covers matching the title, authors and identifiers in
    the request. When the request has the id of a metadata download, the
    covers found by that download are used. Returns the id to use to get the
    covers."""
    db = db_for_download(ctx, rd, book_id, library_id)
    q = parse_download_request(rd)
    caches: dict[str, CachesDump] = {}
    if q.metadata_download_id is not None:
        with lock:
            ic = identify_caches.get(q.metadata_download_id)
            # Only the user that did the metadata download, in the same
            # library, can use its caches
            if ic is not None and ic.username == rd.username and ic.library_id == db.server_library_id:
                caches = ic.caches
    covers_dir = tempfile.mkdtemp(prefix='covers-', dir=rd.tdir)
    try:
        return start_download(ctx, rd, db, book_id, 'download_covers', (q.title, q.authors, q.identifiers, caches, covers_dir), covers_dir)
    except BaseException:
        shutil.rmtree(covers_dir, ignore_errors=True)
        raise


def owned_download(rd: RequestData, db: Cache, job_id: int) -> DownloadJob:
    # Must be called with lock held. Job ids are sequential, so only the user
    # that started the download, in the library it was started in, may get
    # its results or abort it
    dj = download_jobs.get(job_id)
    if dj is None or dj.abort_requested or dj.username != rd.username or dj.library_id != db.server_library_id:
        raise HTTPNotFound(f'No metadata download with id: {job_id}')
    dj.last_check_at = monotonic()
    return dj


@endpoint(
    '/metadata-download/status/{job_id}/{library_id=None}',
    types={'job_id': int},
    needs_db_write=True,
    postprocess=json,
    methods=receive_data_methods,
    cache_control='no-cache',
)
def metadata_download_status(ctx: Context, rd: RequestData, job_id: int, library_id: str | None) -> dict[str, object]:
    """Get the results of a download, or abort it with the query parameter
    abort=1. Metadata downloads are forgotten once their results are returned.
    Cover downloads are kept until they are aborted, which the browser does
    when it no longer needs the covers, as the covers are fetched separately."""
    db = get_db(ctx, rd, library_id)
    abort = rd.query.get('abort') == '1'
    expire_abandoned_jobs(ctx)
    to_abort: list[DownloadJob] = []
    with lock:
        dj = owned_download(rd, db, job_id)
        running = dj.running
        if running:
            if abort:
                dj.abort_requested = True
                to_abort.append(dj)
        elif abort or dj.covers_dir is None:
            del download_jobs[job_id]
    if running and not abort:
        # The covers found so far, so that they can be shown while waiting
        return {'running': True, 'covers': list_covers(dj.covers_dir)} if dj.covers_dir else {'running': True}
    if to_abort:
        abort_downloads(ctx, to_abort)
        return {'running': False, 'ok': False, 'was_aborted': True}
    if abort:
        dj.remove_covers()
        return {'running': False, 'ok': False, 'was_aborted': True}
    # Access to the book may have been revoked during the download
    if not ctx.has_id(rd, db, dj.book_id):
        raise BookNotFound(dj.book_id, db)
    ans: dict[str, object] = {'running': False, 'ok': dj.ok, 'was_aborted': dj.was_aborted}
    if not dj.ok:
        ans['traceback'] = dj.traceback
        return ans
    if dj.covers_dir:
        covers = list_covers(dj.covers_dir)
        # The biggest first, as in the Edit metadata dialog
        covers.sort(key=lambda c: c['width'] * c['height'], reverse=True)
        ans.update({'covers': covers, 'log': dj.log})
        return ans
    assert dj.result is not None  # set by record_job_result() for successful metadata downloads
    with lock:
        identify_caches[job_id] = IdentifyCaches(dj.username, dj.library_id, dj.result['caches'], monotonic())
    results = dj.result['results']
    for r in results:
        if 'languages' in r:
            # The editor uses the names of languages, which are localized,
            # so they must be generated in the server process
            r['languages'] = [calibre_langcode_to_name(lc) for lc in r['languages']]
    ans.update({'results': results, 'ignore_fields': dj.result['ignore_fields'], 'log': dj.result['log']})
    return ans


@endpoint(
    '/metadata-download/cover/{job_id}/{num}/{library_id=None}',
    types={'job_id': int, 'num': int},
    needs_db_write=True,
    cache_control='no-cache',
)
def downloaded_cover(ctx: Context, rd: RequestData, job_id: int, num: int, library_id: str | None) -> IO[bytes]:
    "Get a cover from a cover download, as a JPEG image"
    db = get_db(ctx, rd, library_id)
    with lock:
        dj = owned_download(rd, db, job_id)
        covers_dir = dj.covers_dir
    if covers_dir is None or num < 0:
        raise HTTPNotFound(f'No cover number {num} in download: {job_id}')
    try:
        ans = share_open(os.path.join(covers_dir, f'{num}.jpg'), 'rb')
    except FileNotFoundError:
        raise HTTPNotFound(f'No cover number {num} in download: {job_id}')
    rd.outheaders['Content-Type'] = 'image/jpeg'
    rd.outheaders['X-Content-Type-Options'] = 'nosniff'
    return ans
