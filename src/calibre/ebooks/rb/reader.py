# -*- coding: utf-8 -*-


__license__ = 'GPL 3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

import os
import struct
import zlib

from calibre import CurrentDir
from calibre.ebooks.rb import HEADER
from calibre.ebooks.rb import RocketBookError
from calibre.ebooks.metadata.rb import get_metadata
from calibre.ebooks.metadata.opf2 import OPFCreator
from polyglot.builtins import range, as_unicode
from polyglot.urllib import unquote


class RBToc(list):

    class Item(object):

        def __init__(self, name='', size=0, offset=0, flags=0):
            self.name = name
            self.size = size
            self.offset = offset
            self.flags = flags


class Reader(object):

    def __init__(self, stream, log, encoding=None):
        self.stream = stream
        self.log = log
        self.encoding = encoding

        self.verify_file()

        self.mi = get_metadata(self.stream)
        self.toc = self.get_toc()

    def read_i32(self):
        return struct.unpack('<I', self.stream.read(4))[0]

    def verify_file(self):
        self.stream.seek(0)
        if self.stream.read(14) != HEADER:
            raise RocketBookError('Could not read file: %s. Does not contain a valid RocketBook Header.' % self.stream.name)

        self.stream.seek(28)
        size = self.read_i32()
        self.stream.seek(0, os.SEEK_END)
        real_size = self.stream.tell()
        if size != real_size:
            raise RocketBookError('File is corrupt. The file size recorded in the header does not match the actual file size.')

    def get_toc(self):
        self.stream.seek(24)
        toc_offset = self.read_i32()

        self.stream.seek(toc_offset)
        pages = self.read_i32()

        toc = RBToc()
        for i in range(pages):
            name = unquote(self.stream.read(32).strip(b'\x00'))
            size, offset, flags = self.read_i32(), self.read_i32(), self.read_i32()
            toc.append(RBToc.Item(name=name, size=size, offset=offset, flags=flags))

        return toc

    def get_text(self, toc_item, output_dir):
        if toc_item.flags in (1, 2):
            return

        output = ''
        self.stream.seek(toc_item.offset)

        if toc_item.flags == 8:
            count = self.read_i32()
            self.read_i32()  # Uncompressed size.
            chunck_sizes = []
            for i in range(count):
                chunck_sizes.append(self.read_i32())

            for size in chunck_sizes:
                cm_chunck = self.stream.read(size)
                output += zlib.decompress(cm_chunck).decode('cp1252' if self.encoding is None else self.encoding, 'replace')
        else:
            output += self.stream.read(toc_item.size).decode('cp1252' if self.encoding is None else self.encoding, 'replace')

        with open(os.path.join(output_dir, toc_item.name.decode('utf-8')), 'wb') as html:
            html.write(output.replace('<TITLE>', '<TITLE> ').encode('utf-8'))

    def get_image(self, toc_item, output_dir):
        if toc_item.flags != 0:
            return

        self.stream.seek(toc_item.offset)
        data = self.stream.read(toc_item.size)

        with open(os.path.join(output_dir, toc_item.name.decode('utf-8')), 'wb') as img:
            img.write(data)

    def extract_content(self, output_dir):
        self.log.debug('Extracting content from file...')
        html = []
        images = []

        for item in self.toc:
            iname = as_unicode(item.name)
            if iname.lower().endswith('html'):
                self.log.debug('HTML item %s found...' % iname)
                html.append(iname)
                self.get_text(item, output_dir)
            if iname.lower().endswith('png'):
                self.log.debug('PNG item %s found...' % iname)
                images.append(iname)
                self.get_image(item, output_dir)

        opf_path = self.create_opf(output_dir, html, images)

        return opf_path

    def create_opf(self, output_dir, pages, images):
        with CurrentDir(output_dir):
            opf = OPFCreator(output_dir, self.mi)

            manifest = []
            for page in pages+images:
                manifest.append((page, None))

            opf.create_manifest(manifest)
            opf.create_spine(pages)
            with open('metadata.opf', 'wb') as opffile:
                opf.render(opffile)

        return os.path.join(output_dir, 'metadata.opf')
