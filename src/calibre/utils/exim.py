#!/usr/bin/env python
# License: GPLv3 Copyright: 2015, Kovid Goyal <kovid at kovidgoyal.net>


import errno
import hashlib
import io
import json
import os
import shutil
import struct
import sys
import tempfile
import time
import uuid
from collections import Counter
from typing import NamedTuple

from calibre import prints
from calibre.constants import config_dir, filesystem_encoding, iswindows
from calibre.utils.config import JSONConfig
from calibre.utils.config_base import StringConfig, create_global_prefs, prefs
from calibre.utils.filenames import samefile
from calibre.utils.localization import _
from polyglot.binary import as_hex_unicode
from polyglot.builtins import error_message, iteritems

# Export {{{

class FileDest:

    def __init__(self, key, exporter, mtime=None):
        self.exporter, self.key = exporter, key
        self.hasher = hashlib.sha1()
        self.start_part_number, self.start_pos = exporter.current_pos()
        self._discard = False
        self.mtime = mtime
        self.size = 0

    def discard(self):
        self._discard = True

    def write(self, data):
        self.size += len(data)
        written = self.exporter.write(data)
        if len(data) != written:
            raise RuntimeError(f'Exporter failed to write all data: {len(data)} != {written}')
        self.hasher.update(data)

    def flush(self):
        pass

    def close(self):
        if not self._discard:
            digest = str(self.hasher.hexdigest())
            self.exporter.file_metadata[self.key] = (self.start_part_number, self.start_pos, self.size, digest, self.mtime)
        del self.exporter, self.hasher

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


class Exporter:

    VERSION = 1
    TAIL_FMT = b'!II?'  # part_num, version, is_last
    MDATA_SZ_FMT = b'!Q'
    EXT = '.calibre-data'

    @classmethod
    def tail_size(cls):
        return struct.calcsize(cls.TAIL_FMT)

    def __init__(self, path_to_export_dir, part_size=None):
        # default part_size is 1 GB
        self.part_size = (1 << 30) if part_size is None else part_size
        self.base = os.path.abspath(path_to_export_dir)
        self.commited_parts = []
        self.current_part = None
        self.file_metadata = {}
        self.tail_sz = self.tail_size()
        self.metadata = {'file_metadata': self.file_metadata}

    def set_metadata(self, key, val):
        if key in self.metadata:
            raise KeyError('The metadata already contains the key: %s' % key)
        self.metadata[key] = val

    def current_pos(self):
        pos = 0
        if self.current_part is not None:
            pos = self.current_part.tell()
            if pos >= self.part_size - self.tail_sz:
                self.new_part()
                pos = 0
        return len(self.commited_parts) + 1, pos

    def write(self, data: bytes) -> int:
        written = 0
        data = memoryview(data)
        while len(data) > 0:
            if self.current_part is None:
                self.new_part()
            max_size = self.part_size - self.tail_sz - self.current_part.tell()
            if max_size <= 0:
                self.new_part()
                max_size = self.part_size - self.tail_sz
            chunk = data[:max_size]
            w = self.current_part.write(chunk)
            data = data[w:]
            written += w
        return written

    def new_part(self):
        self.commit_part()
        self.current_part = open(os.path.join(
            self.base, f'part-{len(self.commited_parts) + 1:04d}{self.EXT}'), 'wb')

    def commit_part(self, is_last=False):
        if self.current_part is not None:
            self.current_part.write(struct.pack(self.TAIL_FMT, len(self.commited_parts) + 1, self.VERSION, is_last))
            self.current_part.close()
            self.commited_parts.append(self.current_part.name)
            self.current_part = None

    def commit(self):
        raw = json.dumps(self.metadata, ensure_ascii=False)
        if not isinstance(raw, bytes):
            raw = raw.encode('utf-8')
        self.new_part()
        orig, self.part_size = self.part_size, sys.maxsize
        self.write(raw)
        self.write(struct.pack(self.MDATA_SZ_FMT, len(raw)))
        self.part_size = orig
        self.commit_part(is_last=True)

    def add_file(self, fileobj, key):
        try:
            mtime = os.fstat(fileobj.fileno()).st_mtime
        except (io.UnsupportedOperation, OSError):
            mtime = None
        with self.start_file(key, mtime=mtime) as dest:
            shutil.copyfileobj(fileobj, dest)

    def start_file(self, key, mtime=None):
        return FileDest(key, self, mtime=mtime)

    def export_dir(self, path, dir_key):
        pkey = as_hex_unicode(dir_key)
        self.metadata[dir_key] = files = []
        for dirpath, dirnames, filenames in os.walk(path):
            for fname in filenames:
                fpath = os.path.join(dirpath, fname)
                rpath = os.path.relpath(fpath, path).replace(os.sep, '/')
                key = f'{pkey}:{rpath}'
                try:
                    with open(fpath, 'rb') as f:
                        self.add_file(f, key)
                except OSError:
                    if not iswindows:
                        raise
                    time.sleep(1)
                    with open(fpath, 'rb') as f:
                        self.add_file(f, key)
                files.append((key, rpath))


def all_known_libraries():
    from calibre.gui2 import gprefs
    lus = gprefs.get('library_usage_stats', {})
    paths = set(lus)
    if prefs['library_path']:
        paths.add(prefs['library_path'])
    added = {}
    for path in paths:
        mdb = os.path.join(path, 'metadata.db')
        if os.path.exists(mdb):
            for c in added:
                if samefile(mdb, os.path.join(c, 'metadata.db')):
                    break
            else:
                added[path] = lus.get(path, 1)
    return added


def export(destdir, library_paths=None, dbmap=None, progress1=None, progress2=None, abort=None):
    from calibre.db.backend import DB
    from calibre.db.cache import Cache
    if library_paths is None:
        library_paths = all_known_libraries()
    dbmap = dbmap or {}
    dbmap = {os.path.normcase(os.path.abspath(k)):v for k, v in iteritems(dbmap)}
    exporter = Exporter(destdir)
    exporter.metadata['libraries'] = libraries = {}
    total = len(library_paths) + 1
    for i, (lpath, count) in enumerate(iteritems(library_paths)):
        if abort is not None and abort.is_set():
            return
        if progress1 is not None:
            progress1(lpath, i, total)
        key = os.path.normcase(os.path.abspath(lpath))
        db, closedb = dbmap.get(lpath), False
        if db is None:
            db = Cache(DB(lpath, load_user_formatter_functions=False))
            db.init()
            closedb = True
        else:
            db = db.new_api
        db.export_library(key, exporter, progress=progress2, abort=abort)
        if closedb:
            db.close()
        libraries[key] = count
    if progress1 is not None:
        progress1(_('Settings and plugins'), total-1, total)
    if abort is not None and abort.is_set():
        return
    exporter.export_dir(config_dir, 'config_dir')
    exporter.commit()
    if progress1 is not None:
        progress1(_('Completed'), total, total)
# }}}

# Import {{{

class Chunk(NamedTuple):
    part_num: int
    pos_in_part: int
    size: int
    pos_in_file: int


class Pos:

    def __init__(self, part, pos_in_part, size, importer):
        self.size = size
        self.pos_in_file = 0
        self.chunks = chunks = []
        self.open_part = importer.open_part
        self.currently_open_part = None
        self.currently_open_chunk_index = -1

        pos = 0
        while size > 0:
            part_size = importer.size_of_part(part)
            chunk_size = min(size, part_size - pos_in_part)
            if chunk_size > 0:
                chunks.append(Chunk(part, pos_in_part, chunk_size, pos))
                size -= chunk_size
                pos += chunk_size
            part += 1
            pos_in_part = 0

    def close(self):
        if self.currently_open_part is not None:
            self.currently_open_part.close()
            self.currently_open_part = None
        self.currently_open_chunk_index = -1

    def tell(self) -> int:
        return self.pos_in_file

    def seek(self, amt, whence=os.SEEK_SET) -> int:
        if whence == os.SEEK_SET:
            new_pos_in_file = amt
        if whence == os.SEEK_END:
            new_pos_in_file = self.size + amt
        if whence == os.SEEK_CUR:
            new_pos_in_file = self.pos_in_file + amt
        self.pos_in_file = max(0, min(new_pos_in_file, self.size))
        return self.pos_in_file

    def read(self, size=None):
        if size is None or size < 0:
            size = self.size
        size = min(size, self.size)
        amt_left = max(0, self.size - self.pos_in_file)
        amt_to_read = min(amt_left, size)
        if amt_to_read <= 0:
            return b''
        start_chunk = max(0, self.currently_open_chunk_index)
        num = len(self.chunks)
        ans = []
        chunk_idx = -1
        for i in range(num):
            chunk_idx = (start_chunk + i) % num
            chunk = self.chunks[chunk_idx]
            if chunk.pos_in_file <= self.pos_in_file < chunk.pos_in_file + chunk.size:
                break
        else:
            raise ValueError(f'No chunk found containing {self.pos_in_file=}')

        while amt_to_read > 0:
            try:
                chunk = self.chunks[chunk_idx]
            except IndexError:
                break
            ans.append(self._read_chunk(chunk, amt_to_read, chunk_idx))
            amt_to_read -= len(ans[-1])
            chunk_idx += 1
        return b''.join(ans)

    def _read_chunk(self, chunk, size, chunk_idx):
        if self.currently_open_chunk_index != chunk_idx or self.currently_open_part is None:
            self.close()
            self.currently_open_part = self.open_part(chunk.part_num)
            self.currently_open_chunk_index = chunk_idx
        offset_from_start_of_chunk = self.pos_in_file - chunk.pos_in_file
        self.currently_open_part.seek(chunk.pos_in_part + offset_from_start_of_chunk, os.SEEK_SET)
        size = min(size, chunk.size - offset_from_start_of_chunk)
        ans = self.currently_open_part.read(size)
        self.pos_in_file += len(ans)
        return ans


class FileSource:

    def __init__(self, start_partnum, start_pos, size, digest, description, mtime, importer):
        self.size, self.digest, self.description = size, digest, description
        self.mtime = mtime
        self.start = start_pos
        self.start_partnum = start_partnum
        self.pos = Pos(start_partnum, start_pos, size, importer)
        self.hasher = hashlib.sha1()
        self.importer = importer
        self.check_hash = True

    def seekable(self):
        return False

    def seek(self, amt, whence=os.SEEK_SET):
        return self.pos.seek(amt, whence)

    def tell(self):
        return self.pos.tell()

    def read(self, size=None):
        ans = self.pos.read(size)
        if self.check_hash and ans:
            self.hasher.update(ans)
        return ans

    def close(self):
        if self.check_hash and self.hasher.hexdigest() != self.digest:
            self.importer.corrupted_files.append(self.description)
        self.hasher = None
        self.pos.close()
        self.pos = None

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()


class Importer:

    def __init__(self, path_to_export_dir):
        self.corrupted_files = []
        part_map = {}
        self.tail_size = tail_size = struct.calcsize(Exporter.TAIL_FMT)
        self.version = -1
        for name in os.listdir(path_to_export_dir):
            if name.lower().endswith(Exporter.EXT):
                path = os.path.join(path_to_export_dir, name)
                with open(path, 'rb') as f:
                    f.seek(0, os.SEEK_END)
                    size_of_part = f.tell()
                    f.seek(-tail_size, os.SEEK_END)
                    raw = f.read()
                if len(raw) != tail_size:
                    raise ValueError('The exported data in %s is not valid, tail too small' % name)
                part_num, version, is_last = struct.unpack(Exporter.TAIL_FMT, raw)
                if version > Exporter.VERSION:
                    raise ValueError('The exported data in %s is not valid,'
                                     ' version (%d) is higher than maximum supported version.'
                                     ' You might need to upgrade calibre first.' % (name, version))
                part_map[part_num] = path, is_last, size_of_part
                if self.version == -1:
                    self.version = version
                if version != self.version:
                    raise ValueError(f'The exported data in {name} is not valid as it contains a mix of parts with versions: {self.version} and {version}')
        nums = sorted(part_map)
        if not nums:
            raise ValueError('No exported data found in: %s' % path_to_export_dir)
        if nums[0] != 1:
            raise ValueError('The first part of this exported data set is missing')
        if not part_map[nums[-1]][1]:
            raise ValueError('The last part of this exported data set is missing')
        if len(nums) != nums[-1]:
            raise ValueError('There are some parts of the exported data set missing')
        self.part_map, self.part_size_map = {}, {}
        for part_num, (path, is_last, size_of_part) in part_map.items():
            self.part_map[part_num] = path
            self.part_size_map[part_num] = size_of_part
        msf = struct.calcsize(Exporter.MDATA_SZ_FMT)
        offset = tail_size + msf
        with self.open_part(nums[-1]) as f:
            f.seek(-offset, os.SEEK_END)
            sz, = struct.unpack(Exporter.MDATA_SZ_FMT, f.read(msf))
            f.seek(- sz - offset, os.SEEK_END)
            self.metadata = json.loads(f.read(sz))
            self.file_metadata = self.metadata['file_metadata']

    def size_of_part(self, num):
        return self.part_size_map[num] - self.tail_size

    def open_part(self, num):
        return open(self.part_map[num], 'rb')

    def start_file(self, key, description):
        partnum, pos, size, digest, mtime = self.file_metadata[key]
        return FileSource(partnum, pos, size, digest, description, mtime, self)

    def save_file(self, key, description, output_path):
        with open(output_path, 'wb') as dest, self.start_file(key, description) as src:
            shutil.copyfileobj(src, dest)

    def export_config(self, base_dir, library_usage_stats):
        for key, relpath in self.metadata['config_dir']:
            with self.start_file(key, relpath) as f:
                path = os.path.join(base_dir, relpath.replace('/', os.sep))
                try:
                    with open(path, 'wb') as dest:
                        shutil.copyfileobj(f, dest)
                except OSError:
                    os.makedirs(os.path.dirname(path))
                    with open(path, 'wb') as dest:
                        shutil.copyfileobj(f, dest)
        gpath = os.path.join(base_dir, 'global.py')
        try:
            with open(gpath, 'rb') as f:
                raw = f.read()
        except OSError:
            raw = b''
        try:
            lpath = library_usage_stats.most_common(1)[0][0]
        except Exception:
            lpath = None
        c = create_global_prefs(StringConfig(raw, 'calibre wide preferences'))
        c.set('installation_uuid', str(uuid.uuid4()))
        c.set('library_path', lpath)
        raw = c.src
        if not isinstance(raw, bytes):
            raw = raw.encode('utf-8')
        with open(gpath, 'wb') as f:
            f.write(raw)
        gprefs = JSONConfig('gui', base_path=base_dir)
        gprefs['library_usage_stats'] = dict(library_usage_stats)


def import_data(importer, library_path_map, config_location=None, progress1=None, progress2=None, abort=None):
    from calibre.db.cache import import_library
    config_location = config_location or config_dir
    config_location = os.path.abspath(os.path.realpath(config_location))
    total = len(library_path_map) + 1
    library_usage_stats = Counter()
    for i, (library_key, dest) in enumerate(iteritems(library_path_map)):
        if abort is not None and abort.is_set():
            return
        if isinstance(dest, bytes):
            dest = dest.decode(filesystem_encoding)
        if progress1 is not None:
            progress1(dest, i, total)
        try:
            os.makedirs(dest)
        except OSError as err:
            if err.errno != errno.EEXIST:
                raise
        if not os.path.isdir(dest):
            raise ValueError('%s is not a directory' % dest)
        import_library(library_key, importer, dest, progress=progress2, abort=abort).close()
        stats_key = os.path.abspath(dest).replace(os.sep, '/')
        library_usage_stats[stats_key] = importer.metadata['libraries'].get(library_key, 1)
    if progress1 is not None:
        progress1(_('Settings and plugins'), total - 1, total)

    if abort is not None and abort.is_set():
        return
    base_dir = tempfile.mkdtemp(dir=os.path.dirname(config_location))
    importer.export_config(base_dir, library_usage_stats)
    if os.path.lexists(config_location):
        if os.path.islink(config_location) or os.path.isfile(config_location):
            os.remove(config_location)
        else:
            shutil.rmtree(config_location, ignore_errors=True)
            if os.path.exists(config_location):
                try:
                    shutil.rmtree(config_location)
                except OSError:
                    if not iswindows:
                        raise
                    time.sleep(1)
                    shutil.rmtree(config_location)
    try:
        os.rename(base_dir, config_location)
    except OSError:
        time.sleep(2)
        os.rename(base_dir, config_location)
    from calibre.gui2 import gprefs
    gprefs.refresh()

    if progress1 is not None:
        progress1(_('Completed'), total, total)


def test_import(export_dir='/t/ex', import_dir='/t/imp'):
    importer = Importer(export_dir)
    if os.path.exists(import_dir):
        shutil.rmtree(import_dir)
    os.mkdir(import_dir)
    import_data(importer, {k:os.path.join(import_dir, os.path.basename(k)) for k in importer.metadata['libraries'] if 'largelib' not in k},
                config_location=os.path.join(import_dir, 'calibre-config'), progress1=print, progress2=print)


def cli_report(*args, **kw):
    try:
        prints(*args, **kw)
    except OSError:
        pass


def input_unicode(prompt):
    ans = input(prompt)
    if isinstance(ans, bytes):
        ans = ans.decode(sys.stdin.encoding)
    return ans


def run_exporter(export_dir=None, args=None, check_known_libraries=True):
    if args:
        if len(args) < 2:
            raise SystemExit('You must specify the export folder and libraries to export')
        export_dir = args[0]
        if not os.path.exists(export_dir):
            os.makedirs(export_dir)
        if os.listdir(export_dir):
            raise SystemExit('%s is not empty' % export_dir)
        all_libraries = {os.path.normcase(os.path.abspath(path)):lus for path, lus in iteritems(all_known_libraries())}
        if 'all' in args[1:]:
            libraries = set(all_libraries)
        else:
            libraries = {os.path.normcase(os.path.abspath(os.path.expanduser(path))) for path in args[1:]}
        if check_known_libraries and libraries - set(all_libraries):
            raise SystemExit('Unknown library: ' + tuple(libraries - set(all_libraries))[0])
        libraries = {p: all_libraries[p] for p in libraries}
        print('Exporting libraries:', ', '.join(sorted(libraries)), 'to:', export_dir)
        export(export_dir, progress1=cli_report, progress2=cli_report, library_paths=libraries)
        return

    export_dir = export_dir or input_unicode(
        'Enter path to an empty folder (all exported data will be saved inside it): ').rstrip('\r')
    if not os.path.exists(export_dir):
        os.makedirs(export_dir)
    if not os.path.isdir(export_dir):
        raise SystemExit('%s is not a folder' % export_dir)
    if os.listdir(export_dir):
        raise SystemExit('%s is not empty' % export_dir)
    library_paths = {}
    for lpath, lus in iteritems(all_known_libraries()):
        if input_unicode('Export the library %s [y/n]: ' % lpath).strip().lower() == 'y':
            library_paths[lpath] = lus
    if library_paths:
        export(export_dir, progress1=cli_report, progress2=cli_report, library_paths=library_paths)
    else:
        raise SystemExit('No libraries selected for export')


def run_importer():
    export_dir = input_unicode('Enter path to folder containing previously exported data: ').rstrip('\r')
    if not os.path.isdir(export_dir):
        raise SystemExit('%s is not a folder' % export_dir)
    try:
        importer = Importer(export_dir)
    except ValueError as err:
        raise SystemExit(error_message(err))

    import_dir = input_unicode('Enter path to an empty folder (all libraries will be created inside this folder): ').rstrip('\r')
    if not os.path.exists(import_dir):
        os.makedirs(import_dir)
    if not os.path.isdir(import_dir):
        raise SystemExit('%s is not a folder' % import_dir)
    if os.listdir(import_dir):
        raise SystemExit('%s is not empty' % import_dir)
    import_data(importer, {
        k:os.path.join(import_dir, os.path.basename(k)) for k in importer.metadata['libraries']}, progress1=cli_report, progress2=cli_report)

# }}}


if __name__ == '__main__':
    export(sys.argv[-1], progress1=print, progress2=print)
