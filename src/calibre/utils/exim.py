#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2015, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import (unicode_literals, division, absolute_import,
                        print_function)
import os, json, struct, hashlib, sys, errno, tempfile, time, shutil, uuid
from binascii import hexlify
from collections import Counter

from calibre import prints
from calibre.constants import config_dir, iswindows, filesystem_encoding
from calibre.utils.config_base import prefs, StringConfig, create_global_prefs
from calibre.utils.config import JSONConfig
from calibre.utils.filenames import samefile


# Export {{{

def send_file(from_obj, to_obj, chunksize=1<<20):
    m = hashlib.sha1()
    while True:
        raw = from_obj.read(chunksize)
        if not raw:
            break
        m.update(raw)
        to_obj.write(raw)
    return type('')(m.hexdigest())


class FileDest(object):

    def __init__(self, key, exporter, mtime=None):
        self.exporter, self.key = exporter, key
        self.hasher = hashlib.sha1()
        self.start_pos = exporter.f.tell()
        self._discard = False
        self.mtime = None

    def discard(self):
        self._discard = True

    def ensure_space(self, size):
        if size > 0:
            self.exporter.ensure_space(size)
            self.start_pos = self.exporter.f.tell()

    def write(self, data):
        self.hasher.update(data)
        self.exporter.f.write(data)

    def flush(self):
        pass

    def close(self):
        if not self._discard:
            size = self.exporter.f.tell() - self.start_pos
            digest = type('')(self.hasher.hexdigest())
            self.exporter.file_metadata[self.key] = (len(self.exporter.parts), self.start_pos, size, digest, self.mtime)
        del self.exporter, self.hasher

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


class Exporter(object):

    VERSION = 0
    TAIL_FMT = b'!II?'  # part_num, version, is_last
    MDATA_SZ_FMT = b'!Q'
    EXT = '.calibre-data'

    def __init__(self, path_to_export_dir, part_size=(1 << 30)):
        self.part_size = part_size
        self.base = os.path.abspath(path_to_export_dir)
        self.parts = []
        self.new_part()
        self.file_metadata = {}
        self.metadata = {'file_metadata': self.file_metadata}

    def set_metadata(self, key, val):
        if key in self.metadata:
            raise KeyError('The metadata already contains the key: %s' % key)
        self.metadata[key] = val

    @property
    def f(self):
        return self.parts[-1]

    def new_part(self):
        self.parts.append(open(os.path.join(
            self.base, 'part-{:04d}{}'.format(len(self.parts) + 1, self.EXT)), 'wb'))

    def commit_part(self, is_last=False):
        self.f.write(struct.pack(self.TAIL_FMT, len(self.parts), self.VERSION, is_last))
        self.f.close()
        self.parts[-1] = self.f.name

    def ensure_space(self, size):
        try:
            if size + self.f.tell() < self.part_size:
                return
        except AttributeError:
            raise RuntimeError('This exporter has already been commited, cannot add to it')
        self.commit_part()
        self.new_part()

    def commit(self):
        raw = json.dumps(self.metadata, ensure_ascii=False)
        if not isinstance(raw, bytes):
            raw = raw.encode('utf-8')
        self.ensure_space(len(raw))
        self.f.write(raw)
        self.f.write(struct.pack(self.MDATA_SZ_FMT, len(raw)))
        self.commit_part(is_last=True)

    def add_file(self, fileobj, key):
        fileobj.seek(0, os.SEEK_END)
        size = fileobj.tell()
        fileobj.seek(0)
        self.ensure_space(size)
        pos = self.f.tell()
        digest = send_file(fileobj, self.f)
        size = self.f.tell() - pos
        mtime = os.fstat(fileobj.fileno()).st_mtime
        self.file_metadata[key] = (len(self.parts), pos, size, digest, mtime)

    def start_file(self, key, mtime=None):
        return FileDest(key, self, mtime=mtime)

    def export_dir(self, path, dir_key):
        pkey = hexlify(dir_key)
        self.metadata[dir_key] = files = []
        for dirpath, dirnames, filenames in os.walk(path):
            for fname in filenames:
                fpath = os.path.join(dirpath, fname)
                rpath = os.path.relpath(fpath, path).replace(os.sep, '/')
                key = '%s:%s' % (pkey, rpath)
                try:
                    with lopen(fpath, 'rb') as f:
                        self.add_file(f, key)
                except EnvironmentError:
                    if not iswindows:
                        raise
                    time.sleep(1)
                    with lopen(fpath, 'rb') as f:
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
    from calibre.db.cache import Cache
    from calibre.db.backend import DB
    if library_paths is None:
        library_paths = all_known_libraries()
    dbmap = dbmap or {}
    dbmap = {os.path.normcase(os.path.abspath(k)):v for k, v in dbmap.iteritems()}
    exporter = Exporter(destdir)
    exporter.metadata['libraries'] = libraries = {}
    total = len(library_paths) + 1
    for i, (lpath, count) in enumerate(library_paths.iteritems()):
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


class FileSource(object):

    def __init__(self, f, size, digest, description, mtime, importer):
        self.f, self.size, self.digest, self.description = f, size, digest, description
        self.mtime = mtime
        self.end = f.tell() + size
        self.hasher = hashlib.sha1()
        self.importer = importer

    def read(self, size=None):
        if size is not None and size < 1:
            return b''
        left = self.end - self.f.tell()
        amt = min(left, size or left)
        if amt < 1:
            return b''
        ans = self.f.read(amt)
        self.hasher.update(ans)
        return ans

    def close(self):
        if self.hasher.hexdigest() != self.digest:
            self.importer.corrupted_files.append(self.description)
        self.hasher = self.f = None


class Importer(object):

    def __init__(self, path_to_export_dir):
        self.corrupted_files = []
        part_map = {}
        tail_size = struct.calcsize(Exporter.TAIL_FMT)
        for name in os.listdir(path_to_export_dir):
            if name.lower().endswith(Exporter.EXT):
                path = os.path.join(path_to_export_dir, name)
                with open(path, 'rb') as f:
                    f.seek(-tail_size, os.SEEK_END)
                    raw = f.read()
                if len(raw) != tail_size:
                    raise ValueError('The exported data in %s is not valid, tail too small' % name)
                part_num, version, is_last = struct.unpack(Exporter.TAIL_FMT, raw)
                if version > Exporter.VERSION:
                    raise ValueError('The exported data in %s is not valid,'
                                     ' version (%d) is higher than maximum supported version.'
                                     ' You might need to upgrade calibre first.' % (name, version))
                part_map[part_num] =  path, is_last
        nums = sorted(part_map)
        if not nums:
            raise ValueError('No exported data found in: %s' % path_to_export_dir)
        if nums[0] != 1:
            raise ValueError('The first part of this exported data set is missing')
        if not part_map[nums[-1]][1]:
            raise ValueError('The last part of this exported data set is missing')
        if len(nums) != nums[-1]:
            raise ValueError('There are some parts of the exported data set missing')
        self.part_map = {num:path for num, (path, is_last) in part_map.iteritems()}
        msf = struct.calcsize(Exporter.MDATA_SZ_FMT)
        offset = tail_size + msf
        with self.part(nums[-1]) as f:
            f.seek(-offset, os.SEEK_END)
            sz, = struct.unpack(Exporter.MDATA_SZ_FMT, f.read(msf))
            f.seek(- sz - offset, os.SEEK_END)
            self.metadata = json.loads(f.read(sz))
            self.file_metadata = self.metadata['file_metadata']

    def part(self, num):
        return lopen(self.part_map[num], 'rb')

    def start_file(self, key, description):
        partnum, pos, size, digest, mtime = self.file_metadata[key]
        f = self.part(partnum)
        f.seek(pos)
        return FileSource(f, size, digest, description, mtime, self)

    def export_config(self, base_dir, library_usage_stats):
        for key, relpath in self.metadata['config_dir']:
            f = self.start_file(key, relpath)
            path = os.path.join(base_dir, relpath.replace('/', os.sep))
            try:
                with lopen(path, 'wb') as dest:
                    shutil.copyfileobj(f, dest)
            except EnvironmentError:
                os.makedirs(os.path.dirname(path))
                with lopen(path, 'wb') as dest:
                    shutil.copyfileobj(f, dest)
            f.close()
        gpath = os.path.join(base_dir, 'global.py')
        try:
            with lopen(gpath, 'rb') as f:
                raw = f.read()
        except EnvironmentError:
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
        with lopen(gpath, 'wb') as f:
            f.write(raw)
        gprefs = JSONConfig('gui', base_path=base_dir)
        gprefs['library_usage_stats'] = dict(library_usage_stats)


def import_data(importer, library_path_map, config_location=None, progress1=None, progress2=None, abort=None):
    from calibre.db.cache import import_library
    config_location = config_location or config_dir
    config_location = os.path.abspath(os.path.realpath(config_location))
    total = len(library_path_map) + 1
    library_usage_stats = Counter()
    for i, (library_key, dest) in enumerate(library_path_map.iteritems()):
        if abort is not None and abort.is_set():
            return
        if progress1 is not None:
            progress1(dest, i, total)
        try:
            os.makedirs(dest)
        except EnvironmentError as err:
            if err.errno != errno.EEXIST:
                raise
        if not os.path.isdir(dest):
            raise ValueError('%s is not a directory' % dest)
        import_library(library_key, importer, dest, progress=progress2, abort=abort).close()
        library_usage_stats[dest] = importer.metadata['libraries'].get(library_key, 1)
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
                except EnvironmentError:
                    if not iswindows:
                        raise
                    time.sleep(1)
                    shutil.rmtree(config_location)
    try:
        os.rename(base_dir, config_location)
    except EnvironmentError:
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
    except EnvironmentError:
        pass


def run_exporter():
    export_dir = raw_input('Enter path to an empty folder (all exported data will be saved inside it): ').decode(filesystem_encoding)
    if not os.path.exists(export_dir):
        os.makedirs(export_dir)
    if not os.path.isdir(export_dir):
        raise SystemExit('%s is not a folder' % export_dir)
    if os.listdir(export_dir):
        raise SystemExit('%s is not empty' % export_dir)
    library_paths = {}
    for lpath, lus in all_known_libraries().iteritems():
        if raw_input('Export the library %s [y/n]: ' % lpath) == b'y':
            library_paths[lpath] = lus
    if library_paths:
        export(export_dir, progress1=cli_report, progress2=cli_report, library_paths=library_paths)
    else:
        raise SystemExit('No libraries selected for export')


def run_importer():
    export_dir = raw_input('Enter path to folder containing previously exported data: ').decode(filesystem_encoding)
    if not os.path.isdir(export_dir):
        raise SystemExit('%s is not a folder' % export_dir)
    try:
        importer = Importer(export_dir)
    except ValueError as err:
        raise SystemExit(err.message)

    import_dir = raw_input('Enter path to an empty folder (all libraries will be created inside this folder): ').decode(filesystem_encoding)
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
