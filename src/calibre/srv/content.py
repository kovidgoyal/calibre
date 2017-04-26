#!/usr/bin/env python2
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2015, Kovid Goyal <kovid at kovidgoyal.net>'

import os, errno
from binascii import hexlify
from io import BytesIO
from threading import Lock
from future_builtins import map
from functools import partial

from calibre import fit_image
from calibre.constants import config_dir, iswindows
from calibre.db.errors import NoSuchFormat
from calibre.ebooks.covers import cprefs, override_prefs, scale_cover, generate_cover, set_use_roman
from calibre.ebooks.metadata import authors_to_string
from calibre.ebooks.metadata.meta import set_metadata
from calibre.ebooks.metadata.opf2 import metadata_to_opf
from calibre.library.save_to_disk import find_plugboard
from calibre.srv.errors import HTTPNotFound
from calibre.srv.routes import endpoint, json
from calibre.srv.utils import http_date, get_db, get_use_roman
from calibre.utils.config_base import tweaks
from calibre.utils.date import timestampfromdt
from calibre.utils.img import scale_image, image_from_data
from calibre.utils.filenames import ascii_filename, atomic_rename
from calibre.utils.shared_file import share_open

plugboard_content_server_value = 'content_server'
plugboard_content_server_formats = ['epub', 'mobi', 'azw3']
update_metadata_in_fmts = frozenset(plugboard_content_server_formats)
lock = Lock()

# Get book formats/cover as a cached filesystem file {{{

# We cannot store mtimes in the filesystem since some operating systems (OS X)
# have only one second precision for mtimes
mtimes = {}
rename_counter = 0


def open_for_write(fname):
    try:
        return share_open(fname, 'w+b')
    except EnvironmentError:
        try:
            os.makedirs(os.path.dirname(fname))
        except EnvironmentError:
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

    bname = '%s-%s-%x.%s' % (prefix, library_id, book_id, ext)
    if '\\' in bname or '/' in bname:
        raise ValueError('File components must not contain path separators')
    fname = os.path.join(base, bname)
    used_cache = 'no'

    with lock:
        previous_mtime = mtimes.get(bname)
        if previous_mtime is None or previous_mtime < mtime:
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
            mtimes[bname] = mtime
            copy_func(ans)
            ans.seek(0)
        else:
            try:
                ans = share_open(fname, 'rb')
                used_cache = 'yes'
            except EnvironmentError as err:
                if err.errno != errno.ENOENT:
                    raise
                ans = open_for_write(fname)
                mtimes[bname] = mtime
                copy_func(ans)
                ans.seek(0)
        if ctx.testing:
            rd.outheaders['Used-Cache'] = used_cache
            rd.outheaders['Tempfile'] = hexlify(fname.encode('utf-8'))
        return rd.filesystem_file_with_custom_etag(ans, prefix, library_id, book_id, mtime, extra_etag_data)


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
        prefix += '-%sx%s' % (width, height)

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
        prefix += '-%sx%s' % (width, height)

        def copy_func(dest):
            buf = BytesIO()
            db.copy_cover_to(book_id, buf)
            quality = min(99, max(50, tweaks['content_server_thumbnail_compression_quality']))
            data = scale_image(buf.getvalue(), width=width, height=height, compression_quality=quality)[-1]
            dest.write(data)
    return create_file_copy(ctx, rd, prefix, library_id, book_id, 'jpg', mtime, copy_func)


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
            set_metadata(dest, mi, fmt)
            dest.seek(0)

    au = authors_to_string(mi.authors or [_('Unknown')])
    title = mi.title or _('Unknown')
    ext = fmt
    if ext == 'kepub' and 'Kobo Touch' in rd.inheaders.get('User-Agent', ''):
        ext = 'kepub.epub'
    fname = '%s - %s_%s.%s' % (title[:30], au[:30], book_id, ext)
    fname = ascii_filename(fname).replace('"', '_')
    rd.outheaders['Content-Disposition'] = 'attachment; filename="%s"' % fname

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
    except EnvironmentError:
        raise HTTPNotFound()


@endpoint('/favicon.png', auth_required=False, cache_control=24)
def favicon(ctx, rd):
    return share_open(I('lt.png'), 'rb')


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
        except EnvironmentError:
            raise HTTPNotFound()
    with lock:
        cached = os.path.join(rd.tdir, 'icons', '%d-%s.png' % (sz, which))
        try:
            return share_open(cached, 'rb')
        except EnvironmentError:
            pass
        try:
            src = share_open(path, 'rb')
        except EnvironmentError:
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


@endpoint('/get/{what}/{book_id}/{library_id=None}')
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
        if not db.has_id(book_id):
            raise HTTPNotFound('Book with id %r does not exist' % book_id)
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
                raise HTTPNotFound('No %s format for the book %r' % (what.lower(), book_id))
