#!/usr/bin/env python


__license__ = 'GPL v3'
__copyright__ = '2015, Kovid Goyal <kovid at kovidgoyal.net>'

import base64
import errno
import os
import re
from contextlib import suppress
from functools import partial
from io import BytesIO
from json import load as load_json_file
from threading import Lock

from calibre import fit_image, guess_type, sanitize_file_name
from calibre.constants import config_dir, iswindows
from calibre.db.constants import RESOURCE_URL_SCHEME
from calibre.db.errors import NoSuchFormat
from calibre.ebooks.covers import (
    cprefs, generate_cover, override_prefs, scale_cover, set_use_roman,
)
from calibre.ebooks.metadata import authors_to_string
from calibre.ebooks.metadata.meta import set_metadata
from calibre.ebooks.metadata.opf2 import metadata_to_opf
from calibre.library.save_to_disk import find_plugboard
from calibre.srv.errors import BookNotFound, HTTPBadRequest, HTTPNotFound
from calibre.srv.routes import endpoint, json
from calibre.srv.utils import get_db, get_use_roman, http_date
from calibre.utils.config_base import tweaks
from calibre.utils.date import timestampfromdt
from calibre.utils.filenames import (
    ascii_filename, atomic_rename, make_long_path_useable,
)
from calibre.utils.img import image_from_data, scale_image
from calibre.utils.localization import _
from calibre.utils.resources import get_image_path as I, get_path as P
from calibre.utils.shared_file import share_open
from polyglot.binary import as_hex_unicode
from polyglot.urllib import quote

plugboard_content_server_value = 'content_server'
plugboard_content_server_formats = ['epub', 'mobi', 'azw3']
update_metadata_in_fmts = frozenset(plugboard_content_server_formats)
lock = Lock()

# Get book formats/cover as a cached filesystem file {{{

rename_counter = 0


def reset_caches():
    pass


def open_for_write(fname):
    try:
        return share_open(fname, 'w+b')
    except OSError:
        try:
            os.makedirs(os.path.dirname(fname))
        except OSError:
            pass
    return share_open(fname, 'w+b')


def create_file_copy(ctx, rd, prefix, library_id, book_id, ext, mtime, copy_func, extra_etag_data=''):
    ''' We cannot copy files directly from the library folder to the output
    socket, as this can potentially lock the library for an extended period. So
    instead we copy out the data from the library folder into a temp folder. We
    make sure to only do this copy once, using the previous copy, if there have
    been no changes to the data for the file since the last copy. '''
    global rename_counter

    # Avoid too many items in a single directory for performance
    base = os.path.join(rd.tdir, 'fcache', (('%x' % book_id)[-3:]))
    if iswindows:
        base = '\\\\?\\' + os.path.abspath(base)  # Ensure fname is not too long for windows' API

    bname = f'{prefix}-{library_id}-{book_id:x}.{ext}'
    if '\\' in bname or '/' in bname:
        raise ValueError('File components must not contain path separators')
    fname = os.path.join(base, bname)
    used_cache = 'no'

    def safe_mtime():
        with suppress(OSError):
            return os.path.getmtime(fname)

    mt = mtime if isinstance(mtime, (int, float)) else timestampfromdt(mtime)
    with lock:
        previous_mtime = safe_mtime()
        if previous_mtime is None or previous_mtime < mt:
            if previous_mtime is not None:
                # File exists and may be open, so we cannot change its
                # contents, as that would lead to corrupted downloads in any
                # clients that are currently downloading the file.
                if iswindows:
                    # On windows in order to re-use bname, we have to rename it
                    # before deleting it
                    rename_counter += 1
                    dname = os.path.join(base, '_%x' % rename_counter)
                    atomic_rename(fname, dname)
                    os.remove(dname)
                else:
                    os.remove(fname)
            ans = open_for_write(fname)
            copy_func(ans)
            ans.seek(0)
        else:
            try:
                ans = share_open(fname, 'rb')
                used_cache = 'yes'
            except OSError as err:
                if err.errno != errno.ENOENT:
                    raise
                ans = open_for_write(fname)
                copy_func(ans)
                ans.seek(0)
        if ctx.testing:
            rd.outheaders['Used-Cache'] = used_cache
            rd.outheaders['Tempfile'] = as_hex_unicode(fname)
        return rd.filesystem_file_with_custom_etag(ans, prefix, library_id, book_id, mt, extra_etag_data)


def write_generated_cover(db, book_id, width, height, destf):
    mi = db.get_metadata(book_id)
    set_use_roman(get_use_roman())
    if height is None:
        prefs = cprefs
    else:
        ratio = height / float(cprefs['cover_height'])
        prefs = override_prefs(cprefs)
        scale_cover(prefs, ratio)
    cdata = generate_cover(mi, prefs=prefs)
    destf.write(cdata)


def generated_cover(ctx, rd, library_id, db, book_id, width=None, height=None):
    prefix = 'generated-cover'
    if height is not None:
        prefix += f'-{width}x{height}'

    mtime = timestampfromdt(db.field_for('last_modified', book_id))
    return create_file_copy(ctx, rd, prefix, library_id, book_id, 'jpg', mtime, partial(write_generated_cover, db, book_id, width, height))


def cover(ctx, rd, library_id, db, book_id, width=None, height=None):
    mtime = db.cover_last_modified(book_id)
    if mtime is None:
        return generated_cover(ctx, rd, library_id, db, book_id, width, height)
    prefix = 'cover'
    if width is None and height is None:
        def copy_func(dest):
            db.copy_cover_to(book_id, dest)
    else:
        prefix += f'-{width}x{height}'

        def copy_func(dest):
            buf = BytesIO()
            db.copy_cover_to(book_id, buf)
            quality = min(99, max(50, tweaks['content_server_thumbnail_compression_quality']))
            data = scale_image(buf.getvalue(), width=width, height=height, compression_quality=quality)[-1]
            dest.write(data)
    return create_file_copy(ctx, rd, prefix, library_id, book_id, 'jpg', mtime, copy_func)


def fname_for_content_disposition(fname, as_encoded_unicode=False):
    if as_encoded_unicode:
        # See https://tools.ietf.org/html/rfc6266
        fname = sanitize_file_name(fname).encode('utf-8')
        fname = str(quote(fname))
    else:
        fname = ascii_filename(fname).replace('"', '_')
    return fname


def book_filename(rd, book_id, mi, fmt, as_encoded_unicode=False):
    au = authors_to_string(mi.authors or [_('Unknown')])
    title = mi.title or _('Unknown')
    ext = (fmt or '').lower()
    fname = f'{title[:30]} - {au[:30]}_{book_id}.{ext}'
    fname = fname_for_content_disposition(fname, as_encoded_unicode)
    if ext == 'kepub' and 'Kobo Touch' in rd.inheaders.get('User-Agent', ''):
        fname = fname.replace('!', '_')
        fname += '.epub'
    return fname


def book_fmt(ctx, rd, library_id, db, book_id, fmt):
    mdata = db.format_metadata(book_id, fmt)
    if not mdata:
        raise NoSuchFormat()
    mtime = mdata['mtime']
    update_metadata = fmt in update_metadata_in_fmts
    extra_etag_data = ''

    if update_metadata:
        mi = db.get_metadata(book_id)
        mtime = max(mtime, mi.last_modified)
        # Get any plugboards for the Content server
        plugboards = db.pref('plugboards')
        if plugboards:
            cpb = find_plugboard(plugboard_content_server_value, fmt, plugboards)
            if cpb:
                # Transform the metadata via the plugboard
                newmi = mi.deepcopy_metadata()
                newmi.template_to_attribute(mi, cpb)
                mi = newmi
                extra_etag_data = repr(cpb)
    else:
        mi = db.get_proxy_metadata(book_id)

    def copy_func(dest):
        db.copy_format_to(book_id, fmt, dest)
        if update_metadata:
            if not mi.cover_data or not mi.cover_data[-1]:
                cdata = db.cover(book_id)
                if cdata:
                    mi.cover_data = ('jpeg', cdata)
            set_metadata(dest, mi, fmt)
            dest.seek(0)

    cd = rd.query.get('content_disposition', 'attachment')
    rd.outheaders['Content-Disposition'] = '''{}; filename="{}"; filename*=utf-8''{}'''.format(
        cd, book_filename(rd, book_id, mi, fmt), book_filename(rd, book_id, mi, fmt, as_encoded_unicode=True))

    return create_file_copy(ctx, rd, 'fmt', library_id, book_id, fmt, mtime, copy_func, extra_etag_data=extra_etag_data)
# }}}


@endpoint('/static/{+what}', auth_required=False, cache_control=24)
def static(ctx, rd, what):
    if not what:
        raise HTTPNotFound()
    base = P('content-server', allow_user_override=False)
    path = os.path.abspath(os.path.join(base, *what.split('/')))
    if not path.startswith(base) or ':' in what:
        raise HTTPNotFound('Naughty, naughty!')
    path = os.path.relpath(path, base).replace(os.sep, '/')
    path = P('content-server/' + path)
    try:
        return share_open(path, 'rb')
    except OSError:
        raise HTTPNotFound()


@endpoint('/favicon.png', auth_required=False, cache_control=24)
def favicon(ctx, rd):
    return share_open(I('lt.png'), 'rb')


@endpoint('/apple-touch-icon.png', auth_required=False, cache_control=24)
def apple_touch_icon(ctx, rd):
    return share_open(I('apple-touch-icon.png'), 'rb')


@endpoint('/icon/{+which}', auth_required=False, cache_control=24)
def icon(ctx, rd, which):
    sz = rd.query.get('sz')
    if sz != 'full':
        try:
            sz = int(rd.query.get('sz', 48))
        except Exception:
            sz = 48
    if which in {'', '_'}:
        raise HTTPNotFound()
    if which.startswith('_'):
        base = os.path.join(config_dir, 'tb_icons')
        path = os.path.abspath(os.path.join(base, *which[1:].split('/')))
        if not path.startswith(base) or ':' in which:
            raise HTTPNotFound('Naughty, naughty!')
    else:
        base = P('images', allow_user_override=False)
        path = os.path.abspath(os.path.join(base, *which.split('/')))
        if not path.startswith(base) or ':' in which:
            raise HTTPNotFound('Naughty, naughty!')
        path = os.path.relpath(path, base).replace(os.sep, '/')
        path = P('images/' + path)
    if sz == 'full':
        try:
            return share_open(path, 'rb')
        except OSError:
            raise HTTPNotFound()
    with lock:
        cached = os.path.join(rd.tdir, 'icons', '%d-%s.png' % (sz, which))
        try:
            return share_open(cached, 'rb')
        except OSError:
            pass
        try:
            src = share_open(path, 'rb')
        except OSError:
            raise HTTPNotFound()
        with src:
            idata = src.read()
            img = image_from_data(idata)
        scaled, width, height = fit_image(img.width(), img.height(), sz, sz)
        if scaled:
            idata = scale_image(img, width, height, as_png=True)[-1]
        ans = open_for_write(cached)
        ans.write(idata)
        ans.seek(0)
        return ans


@endpoint('/reader-background/{encoded_fname}', android_workaround=True)
def reader_background(ctx, rd, encoded_fname):
    base = os.path.abspath(os.path.normapth(os.path.join(config_dir, 'viewer', 'background-images')))
    fname = bytes.fromhex(encoded_fname)
    q = os.path.abspath(os.path.normpath(os.path.join(base, fname)))
    if not q.startswith(base):
        raise HTTPNotFound(f'Reader background {encoded_fname} not found')
    try:
        return share_open(make_long_path_useable(q), 'rb')
    except FileNotFoundError:
        raise HTTPNotFound(f'Reader background {encoded_fname} not found')


@endpoint('/reader-profiles/get-all', postprocess=json)
def get_all_reader_profiles(ctx, rd):
    from calibre.gui2.viewer.config import load_viewer_profiles
    which = 'user:'
    if rd.username:
        which += rd.username
    return load_viewer_profiles(which)


@endpoint('/reader-profiles/save', methods={'POST'}, postprocess=json)
def save_reader_profile(ctx, rd):
    try:
        data = load_json_file(rd.request_body_file)
        name, profile = data['name'], data['profile']
        if not isinstance(profile, dict) and profile is not None:
            raise TypeError(f'profile must be a dict not {type(profile)}')
    except Exception as err:
        raise HTTPBadRequest(f'Invalid query: {err}')
    from calibre.gui2.viewer.config import save_viewer_profile
    which = 'user:'
    if rd.username:
        which += rd.username
    save_viewer_profile(name, profile, which)
    return True


@endpoint('/get/{what}/{book_id}/{library_id=None}', android_workaround=True)
def get(ctx, rd, what, book_id, library_id):
    book_id, rest = book_id.partition('_')[::2]
    try:
        book_id = int(book_id)
    except Exception:
        raise HTTPNotFound('Book with id %r does not exist' % book_id)
    db = get_db(ctx, rd, library_id)
    if db is None:
        raise HTTPNotFound('Library %r not found' % library_id)
    with db.safe_read_lock:
        if not ctx.has_id(rd, db, book_id):
            raise BookNotFound(book_id, db)
        library_id = db.server_library_id  # in case library_id was None
        if what == 'thumb':
            sz = rd.query.get('sz')
            w, h = 60, 80
            if sz is None:
                if rest:
                    try:
                        w, h = map(int, rest.split('_'))
                    except Exception:
                        pass
            elif sz == 'full':
                w = h = None
            elif 'x' in sz:
                try:
                    w, h = map(int, sz.partition('x')[::2])
                except Exception:
                    pass
            else:
                try:
                    w = h = int(sz)
                except Exception:
                    pass
            return cover(ctx, rd, library_id, db, book_id, width=w, height=h)
        elif what == 'cover':
            return cover(ctx, rd, library_id, db, book_id)
        elif what == 'opf':
            mi = db.get_metadata(book_id, get_cover=False)
            rd.outheaders['Content-Type'] = 'application/oebps-package+xml; charset=UTF-8'
            rd.outheaders['Last-Modified'] = http_date(timestampfromdt(mi.last_modified))
            return metadata_to_opf(mi)
        elif what == 'json':
            from calibre.srv.ajax import book_to_json
            data, last_modified = book_to_json(ctx, rd, db, book_id)
            rd.outheaders['Last-Modified'] = http_date(timestampfromdt(last_modified))
            return json(ctx, rd, get, data)
        else:
            try:
                return book_fmt(ctx, rd, library_id, db, book_id, what.lower())
            except NoSuchFormat:
                raise HTTPNotFound(f'No {what.lower()} format for the book {book_id!r}')


def resource_hash_to_url(ctx, scheme, digest, library_id):
    kw = {'scheme': scheme, 'digest': digest}
    if library_id:
        kw['library_id'] = library_id
    return ctx.url_for('/get-note-resource', **kw)


def _get_note(ctx, rd, db, field, item_id, library_id):
    note_data = db.notes_data_for(field, item_id)
    if not note_data:
        if db.get_item_name(field, item_id):
            return ''
        raise HTTPNotFound(f'Item {field!r}:{item_id!r} not found')
    note_data.pop('searchable_text', None)
    resources = note_data.pop('resource_hashes', None)
    if resources:
        import re
        html = note_data['doc']
        def r(x):
            scheme, digest = x.split(':', 1)
            return f'{scheme}/{digest}'
        pat = re.compile(rf'{RESOURCE_URL_SCHEME}://({{}})'.format('|'.join(map(r, resources))))
        def sub(m):
            s, d = m.group(1).split('/', 1)
            return resource_hash_to_url(ctx, s, d, library_id)
        note_data['doc'] = pat.sub(sub, html)
    rd.outheaders['Last-Modified'] = http_date(note_data['mtime'])
    return note_data['doc']


@endpoint('/get-note/{field}/{item_id}/{library_id=None}', types={'item_id': int})
def get_note(ctx, rd, field, item_id, library_id):
    '''
    Get the note as text/html for the specified field and item id.
    '''
    db = get_db(ctx, rd, library_id)
    if db is None:
        raise HTTPNotFound(f'Library {library_id} not found')
    html = _get_note(ctx, rd, db, field, item_id, library_id)
    rd.outheaders['Content-Type'] = 'text/html; charset=UTF-8'
    return html


@endpoint('/get-note-from-item-val/{field}/{item}/{library_id=None}', postprocess=json)
def get_note_from_val(ctx, rd, field, item, library_id):
    db = get_db(ctx, rd, library_id)
    if db is None:
        raise HTTPNotFound(f'Library {library_id} not found')
    item_id = db.get_item_id(field, item)
    if not item_id:
        raise HTTPNotFound(f'Item {field!r}:{item!r} not found')
    html = _get_note(ctx, rd, db, field, item_id, library_id)
    return {'item_id': item_id, 'html': html}


@endpoint('/get-note-resource/{scheme}/{digest}/{library_id=None}')
def get_note_resource(ctx, rd, scheme, digest, library_id):
    '''
    Get the data for a resource in a field note, such as an image.
    '''
    db = get_db(ctx, rd, library_id)
    if db is None:
        raise HTTPNotFound(f'Library {library_id} not found')
    d = db.get_notes_resource(f'{scheme}:{digest}')
    if not d:
        raise HTTPNotFound(f'Notes resource {scheme}:{digest} not found')
    name = d['name']
    rd.outheaders['Content-Type'] = guess_type(name)[0] or 'application/octet-stream'
    rd.outheaders['Content-Disposition'] = '''inline; filename="{}"; filename*=utf-8''{}'''.format(
        fname_for_content_disposition(name), fname_for_content_disposition(name, as_encoded_unicode=True))
    rd.outheaders['Last-Modified'] = http_date(d['mtime'])
    return d['data']


@endpoint('/set-note/{field}/{item_id}/{library_id=None}', needs_db_write=True, methods={'POST'}, types={'item_id': int})
def set_note(ctx, rd, field, item_id, library_id):
    '''
    Set the note for a field  as HTML + text + resources.
    '''
    db = get_db(ctx, rd, library_id)
    if db is None:
        raise HTTPNotFound(f'Library {library_id} not found')
    try:
        data = load_json_file(rd.request_body_file)
        if not isinstance(data, dict):
            raise Exception('note data must be a dict')
        html, searchable_text, images = data['html'], data['searchable_text'], data['images']
    except Exception as err:
        raise HTTPBadRequest(f'Invalid query: {err}')
    srv_replacements = {}
    db_replacements = {}
    resources = []
    res_pat = re.compile(r'get-note-resource/([a-zA-Z0-9]+)/([a-zA-Z0-9]+)')
    for key, img in images.items():
        try:
            is_new_image = img['data'].startswith('data:')
            if is_new_image:
                d = img['data'].encode('ascii')
                idx = d.index(b',')
                d = memoryview(d)[idx:]
                img_data = base64.standard_b64decode(d)
                fname = img['filename']
            else:
                m = res_pat.search(img['data'])
                scheme, digest = m.group(1), m.group(2)
                resources.append(f'{scheme}:{digest}')
        except Exception as err:
            raise HTTPBadRequest(f'Invalid query: {err}')
        if is_new_image:
            chash = db.add_notes_resource(img_data, fname)
            scheme, digest = chash.split(':', 1)
            resources.append(chash)
        srv_replacements[key] = resource_hash_to_url(ctx, scheme, digest, library_id)
        db_replacements[key] = f'{RESOURCE_URL_SCHEME}://{scheme}/{digest}'
    db_html = srv_html = html
    if db_replacements:
        db_html = re.sub('|'.join(map(re.escape, db_replacements)), lambda m: db_replacements[m.group()], html)
    if srv_replacements:
        srv_html = re.sub('|'.join(map(re.escape, srv_replacements)), lambda m: srv_replacements[m.group()], html)
    db.set_notes_for(field, item_id, db_html, searchable_text, resources)
    rd.outheaders['Content-Type'] = 'text/html; charset=UTF-8'
    return srv_html
