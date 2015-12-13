#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2015, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import (unicode_literals, division, absolute_import,
                        print_function)
import os, json, struct, hashlib

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

    def __init__(self, key, exporter):
        self.exporter, self.key = exporter, key
        self.hasher = hashlib.sha1()
        self.start_pos = exporter.f.tell()
        self._discard = False

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
            self.exporter.file_metadata[self.key] = (len(self.exporter.parts), self.start_pos, size, digest)
        del self.exporter, self.hasher

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


class Exporter(object):

    VERSION = 1
    TAIL_FMT = b'!II?'  # part_num, version, is_last
    MDATA_SZ_FMT = b'!Q'

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
            self.base, 'part-{:04d}.calibre-data'.format(len(self.parts) + 1)), 'wb'))

    def commit_part(self, is_last=False):
        self.f.write(struct.pack(self.TAIL_FMT, len(self.parts), self.VERSION, is_last))
        self.f.close()
        self.parts[-1] = self.f.name

    def ensure_space(self, size):
        if size + self.f.tell() < self.part_size:
            return
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
        self.file_metadata[key] = (len(self.parts), pos, size, digest)

    def start_file(self, key):
        return FileDest(key, self)
