#!/usr/bin/env python2
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2015, Kovid Goyal <kovid at kovidgoyal.net>'

import os, hashlib, shutil, httplib, zlib, struct, time
from io import DEFAULT_BUFFER_SIZE, BytesIO

from calibre import force_unicode
from calibre.srv.errors import IfNoneMatch

def acceptable_encoding(val, allowed=frozenset({'gzip'})):
    def enc(x):
        e, r = x.partition(';')[::2]
        p, v = r.partition('=')[::2]
        q = 1.0
        if p == 'q' and v:
            try:
                q = float(v)
            except Exception:
                pass
        return e.lower(), q

    emap = dict(enc(x.strip()) for x in val.split(','))
    acceptable = sorted(set(emap) & allowed, key=emap.__getitem__, reverse=True)
    if acceptable:
        return acceptable[0]

def gzip_prefix(mtime):
    # See http://www.gzip.org/zlib/rfc-gzip.html
    return b''.join((
        b'\x1f\x8b',       # ID1 and ID2: gzip marker
        b'\x08',           # CM: compression method
        b'\x00',           # FLG: none set
        # MTIME: 4 bytes
        struct.pack(b"<L", int(mtime) & 0xFFFFFFFF),
        b'\x02',           # XFL: max compression, slowest algo
        b'\xff',           # OS: unknown
    ))

def write_chunked_data(dest, data):
    dest.write(('%X\r\n' % len(data)).encode('ascii'))
    dest.write(data)
    dest.write(b'\r\n')

def write_compressed_file_obj(input_file, dest, compress_level=6):
    crc = zlib.crc32(b"")
    size = 0
    zobj = zlib.compressobj(compress_level,
                            zlib.DEFLATED, -zlib.MAX_WBITS,
                            zlib.DEF_MEM_LEVEL, 0)
    prefix_written = False
    while True:
        data = input_file.read(DEFAULT_BUFFER_SIZE)
        if not data:
            break
        size += len(data)
        crc = zlib.crc32(data, crc)
        data = zobj.compress(data)
        if not prefix_written:
            prefix_written = True
            data = gzip_prefix(time.time()) + data
        write_chunked_data(dest, data)
    data = zobj.flush() + struct.pack(b"<L", crc & 0xFFFFFFFF) + struct.pack(b"<L", size & 0xFFFFFFFF)
    write_chunked_data(dest, data)
    write_chunked_data(dest, b'')


class FileSystemOutputFile(object):

    def __init__(self, output, outheaders):
        self.output_file = output
        pos = output.tell()
        output.seek(0, os.SEEK_END)
        self.content_length = output.tell() - pos
        self.etag = '"%s"' % hashlib.sha1(type('')(os.fstat(output.fileno()).st_mtime) + force_unicode(output.name or '')).hexdigest()
        output.seek(pos)
        self.accept_ranges = True

    def write(self, dest):
        shutil.copyfileobj(self.output_file, dest)
        self.output_file = None

    def write_compressed(self, dest):
        write_compressed_file_obj(self.output_file, dest)

class DynamicOutput(object):

    def __init__(self, output, outheaders):
        if isinstance(output, bytes):
            self.data = output
        else:
            self.data = output.encode('utf-8')
            ct = outheaders.get('Content-Type', 'text/plain')
            if 'charset=' not in ct:
                ct += '; charset=UTF-8'
            outheaders.set('Content-Type', ct, replace=True)
        self.content_length = len(self.data)
        self.etag = None
        self.accept_ranges = False

    def write(self, dest):
        dest.write(self.data)
        self.data = None

    def write_compressed(self, dest):
        write_compressed_file_obj(BytesIO(self.data), dest)

class GeneratedOutput(object):

    def __init__(self, output, outheaders):
        self.output = output
        self.content_length = self.etag = None
        self.accept_ranges = False

    def write(self, dest):
        for line in self.output:
            if line:
                write_chunked_data(dest, line)

class StaticGeneratedOutput(object):

    def __init__(self, data):
        self.data = data
        self.etag = '"%s"' % hashlib.sha1(data).hexdigest()
        self.content_length = len(data)
        self.accept_ranges = False

    def write(self, dest):
        dest.write(self.data)

    def write_compressed(self, dest):
        write_compressed_file_obj(BytesIO(self.data), dest)

def generate_static_output(cache, gso_lock, name, generator):
    with gso_lock:
        ans = cache.get(name)
        if ans is None:
            ans = cache[name] = StaticGeneratedOutput(generator())
        return ans

def parse_if_none_match(val):
    return {x.strip() for x in val.split(',')}

def finalize_output(output, inheaders, outheaders, status_code, is_http1, method):
    ct = outheaders.get('Content-Type', '')
    compressible = not ct or ct.startswith('text/') or ct.startswith('image/svg') or ct.startswith('application/json')
    if isinstance(output, file):
        output = FileSystemOutputFile(output, outheaders)
    elif isinstance(output, (bytes, type(''))):
        output = DynamicOutput(output, outheaders)
    elif isinstance(output, StaticGeneratedOutput):
        pass
    else:
        output = GeneratedOutput(output, outheaders)
    compressible = (status_code == httplib.OK and compressible and output.content_length > 1024 and
                    acceptable_encoding(inheaders.get('Accept-Encoding', '')) and not is_http1)
    accept_ranges = (not compressible and output.accept_ranges is not None and status_code == httplib.OK and
                     not is_http1)
    ranges = None

    for header in ('Accept-Ranges', 'Content-Encoding', 'Transfer-Encoding', 'ETag', 'Content-Length'):
        outheaders.pop('header', all=True)

    none_match = parse_if_none_match(inheaders.get('If-None-Match', ''))
    matched = '*' in none_match or (output.etag and output.etag in none_match)
    if matched:
        raise IfNoneMatch(output.etag)

    # TODO: Ranges, If-Range

    if output.etag and method in ('GET', 'HEAD'):
        outheaders.set('ETag', output.etag, replace=True)
    if accept_ranges:
        outheaders.set('Accept-Ranges', 'bytes', replace=True)
    elif compressible:
        outheaders.set('Content-Encoding', 'gzip', replace=True)
    if output.content_length is not None and not compressible and not ranges:
        outheaders.set('Content-Length', '%d' % output.content_length, replace=True)

    if compressible or output.content_length is None:
        outheaders.set('Transfer-Encoding', 'chunked', replace=True)

    output.commit = output.write_compressed if compressible else output.write

    return status_code, output
