#!/usr/bin/env python


__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import importlib
import json
import os
import posixpath
import sys
import traceback
from io import BytesIO
from typing import Sequence

from calibre import prints
from calibre.constants import iswindows, numeric_version
from calibre.devices.errors import PathError
from calibre.devices.mtp.base import debug
from calibre.devices.mtp.defaults import DeviceDefaults
from calibre.devices.mtp.filesystem_cache import FileOrFolder
from calibre.ptempfile import PersistentTemporaryDirectory, SpooledTemporaryFile
from calibre.utils.filenames import shorten_components_to
from calibre.utils.icu import lower as icu_lower
from polyglot.builtins import as_bytes, iteritems, itervalues

BASE = importlib.import_module('calibre.devices.mtp.%s.driver'%(
    'windows' if iswindows else 'unix')).MTP_DEVICE
DEFAULT_THUMBNAIL_HEIGHT = 320


class MTPInvalidSendPathError(PathError):

    def __init__(self, folder):
        PathError.__init__(self, 'Trying to send to ignored folder: %s'%folder)
        self.folder = folder


class MTP_DEVICE(BASE):

    METADATA_CACHE = 'metadata.calibre'
    DRIVEINFO = 'driveinfo.calibre'
    CAN_SET_METADATA = []
    NEWS_IN_FOLDER = True
    MAX_PATH_LEN = 230
    THUMBNAIL_HEIGHT = DEFAULT_THUMBNAIL_HEIGHT
    CAN_SET_METADATA = []
    BACKLOADING_ERROR_MESSAGE = None
    MANAGES_DEVICE_PRESENCE = True
    FORMATS = ['epub', 'azw3', 'mobi', 'pdf']
    DEVICE_PLUGBOARD_NAME = 'MTP_DEVICE'
    SLOW_DRIVEINFO = True
    ASK_TO_ALLOW_CONNECT = True

    def __init__(self, *args, **kwargs):
        BASE.__init__(self, *args, **kwargs)
        self.plugboards = self.plugboard_func = None
        self._prefs = None
        self.device_defaults = DeviceDefaults()
        self.current_device_defaults = {}
        self.current_vid = self.current_pid = -1
        self.calibre_file_paths = {'metadata':self.METADATA_CACHE, 'driveinfo':self.DRIVEINFO}
        self.highlight_ignored_folders = False

    @property
    def prefs(self):
        from calibre.utils.config import JSONConfig
        if self._prefs is None:
            self._prefs = p = JSONConfig('mtp_devices')
            p.defaults['format_map'] = self.FORMATS
            p.defaults['send_to'] = [
                'Calibre_Companion', 'Books', 'eBooks/import', 'eBooks',
                'wordplayer/calibretransfer', 'sdcard/ebooks',
                'Android/data/com.amazon.kindle/files', 'kindle', 'NOOK', 'Documents',
            ]
            p.defaults['send_template'] = '{title} - {authors}'
            p.defaults['blacklist'] = []
            p.defaults['history'] = {}
            p.defaults['rules'] = []
            p.defaults['ignored_folders'] = {}

        return self._prefs

    @property
    def is_kindle(self) -> bool:
        return self.current_vid == 0x1949

    def is_folder_ignored(self, storage_or_storage_id, path,
                          ignored_folders=None):
        storage_id = str(getattr(storage_or_storage_id, 'object_id',
                             storage_or_storage_id))
        lpath = tuple(icu_lower(name) for name in path)
        if ignored_folders is None:
            ignored_folders = self.get_pref('ignored_folders')
        if storage_id in ignored_folders:
            # Use the users ignored folders settings
            return '/'.join(lpath) in {icu_lower(x) for x in ignored_folders[storage_id]}

        # Implement the default ignore policy

        # Top level ignores
        if lpath[0] in {
            'alarms', 'dcim', 'movies', 'music', 'notifications',
            'pictures', 'ringtones', 'samsung', 'sony', 'htc', 'bluetooth', 'fonts',
            'games', 'lost.dir', 'video', 'whatsapp', 'image', 'com.zinio.mobile.android.reader'}:
            return True
        if lpath[0].startswith('.') and lpath[0] not in {'.tolino', '.notebooks'}:
            # apparently the Tolino for some reason uses a hidden folder for its library, sigh.
            # Kindle Scribe stores user notebooks in subfolders of '.notebooks'
            return True
        if lpath[0] == 'system' and not self.is_kindle:
            # on Kindles we need the system folder for the amazon cover bug workaround
            return True

        if len(lpath) > 1 and lpath[0] == 'android':
            # Ignore everything in Android apart from a few select folders
            if lpath[1] != 'data':
                return True
            if len(lpath) > 2 and lpath[2] != 'com.amazon.kindle':
                return True

        return False

    def configure_for_kindle_app(self):
        proxy = self.prefs
        with proxy:
            proxy['format_map'] = ['azw3', 'mobi', 'azw', 'azw1', 'azw4', 'pdf']
            proxy['send_template'] = '{title} - {authors}'
            orig = list(proxy['send_to'])
            for folder in ('kindle', 'Android/data/com.amazon.kindle/files'):
                if folder in orig:
                    orig.remove(folder)
                orig.insert(0, folder)
            proxy['send_to'] = orig

    def configure_for_generic_epub_app(self):
        with self.prefs:
            for x in ('format_map', 'send_template', 'send_to'):
                del self.prefs[x]

    def open(self, device, library_uuid):
        from calibre.utils.date import isoformat, utcnow
        self.current_library_uuid = library_uuid
        self.location_paths = None
        self.driveinfo = {}
        BASE.open(self, device, library_uuid)
        h = self.prefs['history']
        if self.current_serial_num:
            h[self.current_serial_num] = (self.current_friendly_name,
                    isoformat(utcnow()))
            self.prefs['history'] = h

        self.current_device_defaults, self.current_vid, self.current_pid = self.device_defaults(device, self)
        self.calibre_file_paths = self.current_device_defaults.get(
            'calibre_file_paths', {'metadata':self.METADATA_CACHE, 'driveinfo':self.DRIVEINFO})
        self.THUMBNAIL_HEIGHT = DEFAULT_THUMBNAIL_HEIGHT
        if self.is_kindle:
            self.THUMBNAIL_HEIGHT = 500  # see kindle/driver.py
            try:
                self.sync_kindle_thumbnails()
            except Exception:
                import traceback
                traceback.print_exc()

    def list(self, path, recurse=False):
        if path.startswith('/'):
            q = self._main_id
            path = path[1:]
        elif path.startswith('card:/'):
            q = self._carda_id
            path = path[6:]
        for storage in self.filesystem_cache.entries:
            if storage.storage_id == q:
                if path:
                    path = path.replace(os.sep, '/')
                    parts = path.split('/')
                    if parts:
                        storage = storage.find_path(parts)
                        if storage is None:
                            return []
                return list(storage.list(recurse))
        return []

    def get_device_uid(self):
        return self.current_serial_num

    def ignore_connected_device(self, uid):
        bl = self.prefs['blacklist']
        if uid not in bl:
            bl.append(uid)
            self.prefs['blacklist'] = bl
        if self.is_mtp_device_connected:
            self.eject()

    def put_calibre_file(self, storage, key, stream, size):
        path = self.calibre_file_paths[key].split('/')
        parent = self.ensure_parent(storage, path)
        self.put_file(parent, path[-1], stream, size)

    # Device information {{{
    def _update_drive_info(self, storage, location_code, name=None):
        import uuid

        from calibre.utils.config import from_json, to_json
        from calibre.utils.date import isoformat, now
        f = storage.find_path(self.calibre_file_paths['driveinfo'].split('/'))
        dinfo = {}
        if f is not None:
            try:
                stream = self.get_mtp_file(f)
                dinfo = json.load(stream, object_hook=from_json)
            except:
                prints('Failed to load existing driveinfo.calibre file, with error:')
                traceback.print_exc()
                dinfo = {}
        if dinfo.get('device_store_uuid', None) is None:
            dinfo['device_store_uuid'] = str(uuid.uuid4())
        if dinfo.get('device_name', None) is None:
            dinfo['device_name'] = self.current_friendly_name
        if name is not None:
            dinfo['device_name'] = name
        dinfo['location_code'] = location_code
        dinfo['last_library_uuid'] = getattr(self, 'current_library_uuid', None)
        dinfo['calibre_version'] = '.'.join(str(i) for i in numeric_version)
        dinfo['date_last_connected'] = isoformat(now())
        dinfo['mtp_prefix'] = storage.storage_prefix
        raw = as_bytes(json.dumps(dinfo, default=to_json))
        self.put_calibre_file(storage, 'driveinfo', BytesIO(raw), len(raw))
        self.driveinfo[location_code] = dinfo

    def get_driveinfo(self):
        if not self.driveinfo:
            self.driveinfo = {}
            for sid, location_code in ((self._main_id, 'main'), (self._carda_id,
                'A'), (self._cardb_id, 'B')):
                if sid is None:
                    continue
                self._update_drive_info(self.filesystem_cache.storage(sid), location_code)
        return self.driveinfo

    def get_device_information(self, end_session=True):
        self.report_progress(1.0, _('Get device information...'))
        dinfo = self.get_basic_device_information()
        return tuple(list(dinfo) + [self.driveinfo])

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
    def filesystem_callback(self, msg):
        self.report_progress(0, msg)

    def books(self, oncard=None, end_session=True):
        from calibre.devices.mtp.books import Book, BookList, JSONCodec
        self.report_progress(0, _('Listing files, this can take a while'))
        self.get_driveinfo()  # Ensure driveinfo is loaded
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

        self.report_progress(0, _('Reading e-book metadata'))
        # Read the cache if it exists
        storage = self.filesystem_cache.storage(sid)
        cache = storage.find_path(self.calibre_file_paths['metadata'].split('/'))
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
                    continue  # No need to update metadata
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
        for idx in sorted(itervalues(relpath_cache), reverse=True):
            del bl[idx]
            need_sync = True

        if need_sync:
            self.report_progress(count/steps, _('Updating metadata cache on device'))
            self.write_metadata_cache(storage, bl)
        self.report_progress(1, _('Finished reading metadata from device'))
        return bl

    def read_file_metadata(self, mtp_file):
        from calibre.customize.ui import quick_metadata
        from calibre.ebooks.metadata.meta import get_metadata
        ext = mtp_file.name.rpartition('.')[-1].lower()

        if self.is_kindle and ext == 'kfx' and mtp_file.name != 'metadata.kfx':
            # locate the actual file containing KFX book metadata
            metadata_file = mtp_file.parent.find_path((mtp_file.name[:-4] + '.sdr', 'assets', 'metadata.kfx'))
            if metadata_file is not None:
                metadata = self.read_file_metadata(metadata_file)
                # failure to process metadata.kfx will result in a title of 'metadata'
                if metadata.title != 'metadata':
                    return metadata

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
        self.put_calibre_file(storage, 'metadata', stream, size)

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
            name = f.name
            if iswindows:
                plen = len(base)
                name = ''.join(shorten_components_to(245-plen, [name]))
            with open(os.path.join(base, name), 'wb') as out:
                try:
                    self.get_mtp_file(f, out)
                except Exception as e:
                    ans.append((path, e, traceback.format_exc()))
                else:
                    ans.append(out.name)

        # copy additional files needed for KFX books found in the associated .sdr folder
        if self.is_kindle:
            for path, new_path in zip(paths, ans):
                if path.endswith('.kfx') and isinstance(new_path, str):
                    try:
                        mtp_file = self.filesystem_cache.resolve_mtp_id_path(path)
                        sdr_folder_name = mtp_file.name[:-4] + '.sdr'
                        sdr_folder = mtp_file.parent.folder_named(sdr_folder_name)

                        if sdr_folder is not None:
                            new_base = os.path.join(os.path.split(new_path)[0], sdr_folder_name)
                            os.mkdir(new_base)

                            def scan_for_kfx(mtp_folder):
                                for f in mtp_folder.files:
                                    if f.full_path:
                                        fn = f.full_path[-1].lower()
                                        if fn.endswith('.kfx') or fn == 'voucher':
                                            name = ''.join(shorten_components_to(245 - len(new_base), [f.name])) if iswindows else f.name
                                            with open(os.path.join(new_base, name), 'wb') as out:
                                                self.get_mtp_file(f, out)

                                for folder in mtp_folder.folders:
                                    scan_for_kfx(folder)

                            scan_for_kfx(sdr_folder)
                    except Exception:
                        traceback.print_exc()

        return ans
    # }}}

    # Sending files to the device {{{

    def set_plugboards(self, plugboards, pb_func):
        self.plugboards = plugboards
        self.plugboard_func = pb_func

    def create_upload_path(self, path, mdata, fname, routing):
        from calibre.devices.utils import create_upload_path
        from calibre.utils.filenames import ascii_filename as sanitize
        ext = fname.rpartition('.')[-1].lower()
        path = routing.get(ext, path)

        filepath = create_upload_path(mdata, fname, self.save_template, sanitize,
                prefix_path=path,
                path_type=posixpath,
                maxlen=self.MAX_PATH_LEN,
                use_subdirs='/' in self.save_template,
                news_in_folder=self.NEWS_IN_FOLDER,
                )
        return tuple(x for x in filepath.split('/'))

    def prefix_for_location(self, on_card):
        if self.location_paths is None:
            self.location_paths = {}
            for sid, loc in ((self._main_id, None), (self._carda_id, 'carda'),
                    (self._cardb_id, 'cardb')):
                if sid is not None:
                    storage = self.filesystem_cache.storage(sid)
                    prefixes = self.get_pref('send_to')
                    p = None
                    for path in prefixes:
                        path = path.replace(os.sep, '/')
                        if storage.find_path(path.split('/')) is not None:
                            p = path
                            break
                    if p is None:
                        p = 'Books'
                    self.location_paths[loc] = p

        return self.location_paths[on_card]

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

        routing = {fmt:dest for fmt,dest in self.get_pref('rules')}

        for infile, fname, mi in zip(files, names, metadata):
            path = self.create_upload_path(prefix, mi, fname, routing)
            if path and self.is_folder_ignored(storage, path):
                raise MTPInvalidSendPathError('/'.join(path))
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
                stream = open(infile, 'rb')
                close = True
            relpath = parent.mtp_relpath + (path[-1].lower(),)
            try:
                mtp_file = self.put_file(parent, path[-1], stream, sz)
                try:
                    self.upload_cover(parent, relpath, storage, mi, stream)
                except Exception:
                    import traceback
                    traceback.print_exc()
            finally:
                if close:
                    stream.close()
            ans.append((mtp_file, bl_idx))
            i += 1
            self.report_progress(i/total, _('Transferred %s to device')%mi.title)

        self.report_progress(1, _('Transfer to device finished...'))
        debug('upload_books() ended')
        return ans

    def upload_cover(self, parent_folder: FileOrFolder, relpath_of_ebook_on_device: Sequence[str], storage: FileOrFolder, mi, ebook_file_as_stream):
        if self.is_kindle:
            self.upload_kindle_thumbnail(parent_folder, relpath_of_ebook_on_device, storage, mi, ebook_file_as_stream)

    # Kindle cover thumbnail handling {{{

    def upload_kindle_thumbnail(self, parent_folder: FileOrFolder, relpath_of_ebook_on_device: Sequence[str], storage: FileOrFolder, mi, ebook_file_as_stream):
        coverdata = getattr(mi, 'thumbnail', None)
        if not coverdata or not coverdata[2]:
            return
        from calibre.devices.kindle.driver import thumbnail_filename
        tfname = thumbnail_filename(ebook_file_as_stream)
        if not tfname:
            return
        thumbpath = 'system', 'thumbnails', tfname
        cover_stream = BytesIO(coverdata[2])
        sz = len(coverdata[2])
        try:
            parent = self.ensure_parent(storage, thumbpath)
        except Exception as err:
            print(f'Failed to upload cover thumbnail to system/thumbnails with error: {err}', file=sys.stderr)
            return
        self.put_file(parent, tfname, cover_stream, sz)
        cover_stream.seek(0)
        cache_path = 'amazon-cover-bug', tfname
        parent = self.ensure_parent(storage, cache_path)
        self.put_file(parent, tfname, cover_stream, sz)
        # mapping from ebook relpath to thumbnail filename
        from hashlib import sha1
        index_name = sha1('/'.join(relpath_of_ebook_on_device).encode()).hexdigest()
        data = tfname.encode()
        self.put_file(parent, index_name, BytesIO(data), len(data))

    def delete_kindle_cover_thumbnail_for(self, storage: FileOrFolder, mtp_relpath: Sequence[str]) -> None:
        from hashlib import sha1
        index_name = sha1('/'.join(mtp_relpath).encode()).hexdigest()
        index = storage.find_path(('amazon-cover-bug', index_name))
        if index is not None:
            data = BytesIO()
            self.get_mtp_file(index, data)
            tfname = data.getvalue().decode().strip()
            if tfname:
                thumbnail = storage.find_path(('system', 'thumbnails', tfname))
                if thumbnail is not None:
                    self.delete_file_or_folder(thumbnail)
                cache = storage.find_path(('amazon-cover-bug', tfname))
                if cache is not None:
                    self.delete_file_or_folder(cache)
                self.delete_file_or_folder(index)

    def sync_kindle_thumbnails(self):
        for storage in self.filesystem_cache.entries:
            self._sync_kindle_thumbnails(storage)

    def _sync_kindle_thumbnails(self, storage):
        system_thumbnails_dir = storage.find_path(('system', 'thumbnails'))
        amazon_cover_bug_cache_dir = storage.find_path(('amazon-cover-bug',))
        if system_thumbnails_dir is None or amazon_cover_bug_cache_dir is None:
            return
        debug('Syncing cover thumbnails to workaround amazon cover bug')
        system_thumbnails = {x.name: x for x in system_thumbnails_dir.files}
        count = 0
        for f in amazon_cover_bug_cache_dir.files:
            s = system_thumbnails.get(f.name)
            if s is not None and s.size != f.size:
                count += 1
                data = BytesIO()
                self.get_mtp_file(f, data)
                data.seek(0)
                sz = len(data.getvalue())
                self.put_file(system_thumbnails_dir, f.name, data, sz)
        debug(f'Restored {count} cover thumbnails that were destroyed by Amazon')
    # }}}

    def add_books_to_metadata(self, mtp_files, metadata, booklists):
        debug('add_books_to_metadata() called')
        from calibre.devices.mtp.books import Book

        i, total = 0, len(mtp_files)
        self.report_progress(0, _('Adding books to device metadata listing...'))
        for x, mi in zip(mtp_files, metadata):
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
            fpath = f.mtp_relpath
            storage = f.storage
            self.recursive_delete(f)
            if self.is_kindle:
                self.delete_kindle_cover_thumbnail_for(storage, fpath)
            self.report_progress((i+1) / float(len(paths)),
                    _('Deleted %s')%path)
        self.report_progress(1, _('All books deleted'))

    def remove_books_from_metadata(self, paths, booklists):
        self.report_progress(0, _('Removing books from metadata'))

        class NextPath(Exception):
            pass

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

    def get_pref(self, key):
        ''' Get the setting named key. First looks for a device specific setting.
        If that is not found looks for a device default and if that is not
        found uses the global default.'''
        dd = self.current_device_defaults if self.is_mtp_device_connected else {}
        dev_settings = self.prefs.get('device-%s'%self.current_serial_num, {})
        default_value = dd.get(key, self.prefs[key])
        return dev_settings.get(key, default_value)

    def config_widget(self):
        from calibre.gui2.device_drivers.mtp_config import MTPConfig
        return MTPConfig(self, highlight_ignored_folders=self.highlight_ignored_folders)

    def save_settings(self, cw):
        cw.commit()

    def settings(self):
        class Opts:

            def __init__(s):
                s.format_map = self.get_pref('format_map')
        return Opts()

    @property
    def save_template(self):
        return self.get_pref('send_template')

    def get_user_blacklisted_devices(self):
        bl = frozenset(self.prefs['blacklist'])
        ans = {}
        for dev, x in iteritems(self.prefs['history']):
            name = x[0]
            if dev in bl:
                ans[dev] = name
        return ans

    def set_user_blacklisted_devices(self, devs):
        self.prefs['blacklist'] = list(devs)

    # }}}


def main():
    import io
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
        dev.filesystem_cache.dump()
        print('Prefix for main mem:', dev.prefix_for_location(None), flush=True)
        raw = os.urandom(32 * 1024)
        folder = dev.create_folder(dev.filesystem_cache.entries[0], 'developing-mtp-driver')
        f = dev.put_file(folder, 'developing-mtp-driver.bin', io.BytesIO(raw), len(raw))
        print('Put file:', f, flush=True)
        buf = io.BytesIO()
        dev.get_file(f.mtp_id_path, buf)
        if buf.getvalue() != raw:
            raise ValueError('Getting previously put file did not return expected data')
        print('Successfully got previously put file', flush=True)
        dev.recursive_delete(f)
    finally:
        dev.shutdown()


if __name__ == '__main__':
    main()
