#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import json, traceback, posixpath, importlib, os
from io import BytesIO
from itertools import izip

from calibre import prints
from calibre.constants import iswindows, numeric_version
from calibre.devices.mtp.base import debug
from calibre.ptempfile import SpooledTemporaryFile, PersistentTemporaryDirectory
from calibre.utils.config import from_json, to_json
from calibre.utils.date import now, isoformat

BASE = importlib.import_module('calibre.devices.mtp.%s.driver'%(
    'windows' if iswindows else 'unix')).MTP_DEVICE

class MTP_DEVICE(BASE):

    METADATA_CACHE = 'metadata.calibre'
    DRIVEINFO = 'driveinfo.calibre'
    CAN_SET_METADATA = []
    NEWS_IN_FOLDER = True
    MAX_PATH_LEN = 230
    THUMBNAIL_HEIGHT = 160
    THUMBNAIL_WIDTH = 120
    CAN_SET_METADATA = []
    BACKLOADING_ERROR_MESSAGE = None
    MANAGES_DEVICE_PRESENCE = True
    FORMATS = ['epub', 'azw3', 'mobi', 'pdf']
    DEVICE_PLUGBOARD_NAME = 'MTP_DEVICE'

    def __init__(self, *args, **kwargs):
        BASE.__init__(self, *args, **kwargs)
        self.plugboards = self.plugboard_func = None

    def open(self, devices, library_uuid):
        self.current_library_uuid = library_uuid
        BASE.open(self, devices, library_uuid)

    # Device information {{{
    def _update_drive_info(self, storage, location_code, name=None):
        import uuid
        f = storage.find_path((self.DRIVEINFO,))
        dinfo = {}
        if f is not None:
            stream = self.get_mtp_file(f)
            try:
                dinfo = json.load(stream, object_hook=from_json)
            except:
                dinfo = None
        if dinfo.get('device_store_uuid', None) is None:
            dinfo['device_store_uuid'] = unicode(uuid.uuid4())
        if dinfo.get('device_name', None) is None:
            dinfo['device_name'] = self.current_friendly_name
        if name is not None:
            dinfo['device_name'] = name
        dinfo['location_code'] = location_code
        dinfo['last_library_uuid'] = getattr(self, 'current_library_uuid', None)
        dinfo['calibre_version'] = '.'.join([unicode(i) for i in numeric_version])
        dinfo['date_last_connected'] = isoformat(now())
        dinfo['mtp_prefix'] = storage.storage_prefix
        raw = json.dumps(dinfo, default=to_json)
        self.put_file(storage, self.DRIVEINFO, BytesIO(raw), len(raw))
        self.driveinfo = dinfo

    def get_device_information(self, end_session=True):
        self.report_progress(1.0, _('Get device information...'))
        self.driveinfo = {}
        for sid, location_code in ( (self._main_id, 'main'), (self._carda_id,
            'A'), (self._cardb_id, 'B')):
            if sid is None: continue
            self._update_drive_info(self.filesystem_cache.storage(sid), location_code)
        dinfo = self.get_basic_device_information()
        return tuple( list(dinfo) + [self.driveinfo] )

    def card_prefix(self, end_session=True):
        return (self._carda_id, self._cardb_id)

    def set_driveinfo_name(self, location_code, name):
        sid = {'main':self._main_id, 'A':self._carda_id,
                'B':self._cardb_id}.get(location_code, None)
        if sid is None:
            return
        self._update_drive_info(self.filesystem_cache.storage(sid),
                location_code, name=name)
    # }}}

    # Get list of books from device, with metadata {{{
    def books(self, oncard=None, end_session=True):
        from calibre.devices.mtp.books import JSONCodec
        from calibre.devices.mtp.books import BookList, Book
        sid = {'carda':self._carda_id, 'cardb':self._cardb_id}.get(oncard,
                self._main_id)
        if sid is None:
            return BookList(None)

        bl = BookList(sid)
        # If True then there is a mismatch between the ebooks on the device and
        # the metadata cache
        need_sync = False
        all_books = list(self.filesystem_cache.iterebooks(sid))
        steps = len(all_books) + 2
        count = 0

        self.report_progress(0, _('Reading metadata from device'))
        # Read the cache if it exists
        storage = self.filesystem_cache.storage(sid)
        cache = storage.find_path((self.METADATA_CACHE,))
        if cache is not None:
            json_codec = JSONCodec()
            try:
                stream = self.get_mtp_file(cache)
                json_codec.decode_from_file(stream, bl, Book, sid)
            except:
                need_sync = True

        relpath_cache = {b.mtp_relpath:i for i, b in enumerate(bl)}

        for mtp_file in all_books:
            count += 1
            relpath = mtp_file.mtp_relpath
            idx = relpath_cache.get(relpath, None)
            if idx is not None:
                cached_metadata = bl[idx]
                del relpath_cache[relpath]
                if cached_metadata.size == mtp_file.size:
                    cached_metadata.datetime = mtp_file.last_modified.timetuple()
                    cached_metadata.path = mtp_file.mtp_id_path
                    debug('Using cached metadata for',
                            '/'.join(mtp_file.full_path))
                    continue # No need to update metadata
                book = cached_metadata
            else:
                book = Book(sid, '/'.join(relpath))
                bl.append(book)

            need_sync = True
            self.report_progress(count/steps, _('Reading metadata from %s')%
                    ('/'.join(relpath)))
            try:
                book.smart_update(self.read_file_metadata(mtp_file))
                debug('Read metadata for', '/'.join(mtp_file.full_path))
            except:
                prints('Failed to read metadata from',
                        '/'.join(mtp_file.full_path))
                traceback.print_exc()
            book.size = mtp_file.size
            book.datetime = mtp_file.last_modified.timetuple()
            book.path = mtp_file.mtp_id_path

        # Remove books in the cache that no longer exist
        for idx in sorted(relpath_cache.itervalues(), reverse=True):
            del bl[idx]
            need_sync = True

        if need_sync:
            self.report_progress(count/steps, _('Updating metadata cache on device'))
            self.write_metadata_cache(storage, bl)
        self.report_progress(1, _('Finished reading metadata from device'))
        return bl

    def read_file_metadata(self, mtp_file):
        from calibre.ebooks.metadata.meta import get_metadata
        from calibre.customize.ui import quick_metadata
        ext = mtp_file.name.rpartition('.')[-1].lower()
        stream = self.get_mtp_file(mtp_file)
        with quick_metadata:
            return get_metadata(stream, stream_type=ext,
                    force_read_metadata=True,
                    pattern=self.build_template_regexp())

    def write_metadata_cache(self, storage, bl):
        from calibre.devices.mtp.books import JSONCodec

        if bl.storage_id != storage.storage_id:
            # Just a sanity check, should never happen
            return

        json_codec = JSONCodec()
        stream = SpooledTemporaryFile(10*(1024**2))
        json_codec.encode_to_file(stream, bl)
        size = stream.tell()
        stream.seek(0)
        self.put_file(storage, self.METADATA_CACHE, stream, size)

    def sync_booklists(self, booklists, end_session=True):
        debug('sync_booklists() called')
        for bl in booklists:
            if getattr(bl, 'storage_id', None) is None:
                continue
            storage = self.filesystem_cache.storage(bl.storage_id)
            if storage is None:
                continue
            self.write_metadata_cache(storage, bl)
        debug('sync_booklists() ended')

    # }}}

    # Get files from the device {{{
    def get_file(self, path, outfile, end_session=True):
        f = self.filesystem_cache.resolve_mtp_id_path(path)
        self.get_mtp_file(f, outfile)

    def prepare_addable_books(self, paths):
        tdir = PersistentTemporaryDirectory('_prepare_mtp')
        ans = []
        for path in paths:
            try:
                f = self.filesystem_cache.resolve_mtp_id_path(path)
            except Exception as e:
                ans.append((path, e, traceback.format_exc()))
                continue
            base = os.path.join(tdir, '%s'%f.object_id)
            os.mkdir(base)
            with open(os.path.join(base, f.name), 'wb') as out:
                try:
                    self.get_mtp_file(f, out)
                except Exception as e:
                    ans.append((path, e, traceback.format_exc()))
                else:
                    ans.append(out.name)
        return ans
    # }}}

    # Sending files to the device {{{

    def set_plugboards(self, plugboards, pb_func):
        self.plugboards = plugboards
        self.plugboard_func = pb_func

    def create_upload_path(self, path, mdata, fname):
        from calibre.devices.utils import create_upload_path
        from calibre.utils.filenames import ascii_filename as sanitize
        filepath = create_upload_path(mdata, fname, self.save_template, sanitize,
                prefix_path=path,
                path_type=posixpath,
                maxlen=self.MAX_PATH_LEN,
                use_subdirs = True,
                news_in_folder = self.NEWS_IN_FOLDER,
                )
        return tuple(x for x in filepath.split('/'))

    def prefix_for_location(self, on_card):
        # TODO: Implement this
        return 'calibre'

    def ensure_parent(self, storage, path):
        parent = storage
        pos = list(path)[:-1]
        while pos:
            name = pos[0]
            pos = pos[1:]
            parent = self.create_folder(parent, name)
        return parent

    def upload_books(self, files, names, on_card=None, end_session=True,
                     metadata=None):
        debug('upload_books() called')
        from calibre.devices.utils import sanity_check
        sanity_check(on_card, files, self.card_prefix(), self.free_space())
        prefix = self.prefix_for_location(on_card)
        sid = {'carda':self._carda_id, 'cardb':self._cardb_id}.get(on_card,
                self._main_id)
        bl_idx = {'carda':1, 'cardb':2}.get(on_card, 0)
        storage = self.filesystem_cache.storage(sid)

        ans = []
        self.report_progress(0, _('Transferring books to device...'))
        i, total = 0, len(files)

        for infile, fname, mi in izip(files, names, metadata):
            path = self.create_upload_path(prefix, mi, fname)
            parent = self.ensure_parent(storage, path)
            if hasattr(infile, 'read'):
                pos = infile.tell()
                infile.seek(0, 2)
                sz = infile.tell()
                infile.seek(pos)
                stream = infile
                close = False
            else:
                sz = os.path.getsize(infile)
                stream = lopen(infile, 'rb')
                close = True
            try:
                mtp_file = self.put_file(parent, path[-1], stream, sz)
            finally:
                if close:
                    stream.close()
            ans.append((mtp_file, bl_idx))
            i += 1
            self.report_progress(i/total, _('Transferred %s to device')%mi.title)

        self.report_progress(1, _('Transfer to device finished...'))
        debug('upload_books() ended')
        return ans

    def add_books_to_metadata(self, mtp_files, metadata, booklists):
        debug('add_books_to_metadata() called')
        from calibre.devices.mtp.books import Book

        i, total = 0, len(mtp_files)
        self.report_progress(0, _('Adding books to device metadata listing...'))
        for x, mi in izip(mtp_files, metadata):
            mtp_file, bl_idx = x
            bl = booklists[bl_idx]
            book = Book(mtp_file.storage_id, '/'.join(mtp_file.mtp_relpath),
                    other=mi)
            book = bl.add_book(book, replace_metadata=True)
            if book is not None:
                book.size = mtp_file.size
                book.datetime = mtp_file.last_modified.timetuple()
                book.path = mtp_file.mtp_id_path
            i += 1
            self.report_progress(i/total, _('Added %s')%mi.title)

        self.report_progress(1, _('Adding complete'))
        debug('add_books_to_metadata() ended')

    # }}}

    # Removing books from the device {{{
    def recursive_delete(self, obj):
        parent = self.delete_file_or_folder(obj)
        if parent.empty and parent.can_delete and not parent.is_system:
            try:
                self.recursive_delete(parent)
            except:
                prints('Failed to delete parent: %s, ignoring'%(
                    '/'.join(parent.full_path)))

    def delete_books(self, paths, end_session=True):
        self.report_progress(0, _('Deleting books from device...'))

        for i, path in enumerate(paths):
            f = self.filesystem_cache.resolve_mtp_id_path(path)
            self.recursive_delete(f)
            self.report_progress((i+1) / float(len(paths)),
                    _('Deleted %s')%path)
        self.report_progress(1, _('All books deleted'))

    def remove_books_from_metadata(self, paths, booklists):
        self.report_progress(0, _('Removing books from metadata'))
        class NextPath(Exception): pass

        for i, path in enumerate(paths):
            try:
                for bl in booklists:
                    for book in bl:
                        if book.path == path:
                            bl.remove_book(book)
                            raise NextPath('')
            except NextPath:
                pass
            self.report_progress((i+1)/len(paths), _('Removed %s')%path)

        self.report_progress(1, _('All books removed'))

    # }}}

    # Settings {{{
    @classmethod
    def settings(self):
        # TODO: Implement this
        class Opts(object):
            def __init__(s):
                s.format_map = self.FORMATS
        return Opts()

    # }}}

if __name__ == '__main__':
    dev = MTP_DEVICE(None)
    dev.startup()
    try:
        from calibre.devices.scanner import DeviceScanner
        scanner = DeviceScanner()
        scanner.scan()
        devs = scanner.devices
        cd = dev.detect_managed_devices(devs)
        if cd is None:
            raise ValueError('Failed to detect MTP device')
        dev.set_progress_reporter(prints)
        dev.open(cd, None)
        dev.books()
    finally:
        dev.shutdown()


