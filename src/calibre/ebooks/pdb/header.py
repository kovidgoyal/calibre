'''
Read the header data from a pdb file.
'''

__license__   = 'GPL v3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

import re
import struct
import time
from polyglot.builtins import long_type


class PdbHeaderReader:

    def __init__(self, stream):
        self.stream = stream
        self.ident = self.identity()
        self.num_sections = self.section_count()
        self.title = self.name()

    def identity(self):
        self.stream.seek(60)
        ident = self.stream.read(8)
        return ident.decode('utf-8')

    def section_count(self):
        self.stream.seek(76)
        return struct.unpack('>H', self.stream.read(2))[0]

    def name(self):
        self.stream.seek(0)
        return re.sub(b'[^-A-Za-z0-9 ]+', b'_', self.stream.read(32).replace(b'\x00', b''))

    def full_section_info(self, number):
        if not (0 <= number < self.num_sections):
            raise ValueError('Not a valid section number %i' % number)

        self.stream.seek(78 + number * 8)
        offset, a1, a2, a3, a4 = struct.unpack('>LBBBB', self.stream.read(8))[0]
        flags, val = a1, a2 << 16 | a3 << 8 | a4
        return (offset, flags, val)

    def section_offset(self, number):
        if not (0 <= number < self.num_sections):
            raise ValueError('Not a valid section number %i' % number)

        self.stream.seek(78 + number * 8)
        return struct.unpack('>LBBBB', self.stream.read(8))[0]

    def section_data(self, number):
        if not (0 <= number < self.num_sections):
            raise ValueError('Not a valid section number %i' % number)

        start = self.section_offset(number)
        if number == self.num_sections -1:
            self.stream.seek(0, 2)
            end = self.stream.tell()
        else:
            end = self.section_offset(number + 1)
        self.stream.seek(start)
        return self.stream.read(end - start)


class PdbHeaderBuilder:

    def __init__(self, identity, title):
        self.identity = identity.ljust(3, '\x00')[:8].encode('utf-8')
        if isinstance(title, str):
            title = title.encode('ascii', 'replace')
        self.title = b'%s\x00' % re.sub(b'[^-A-Za-z0-9 ]+', b'_', title).ljust(31, b'\x00')[:31]

    def build_header(self, section_lengths, out_stream):
        '''
        section_lengths = Length of each section in file.
        '''

        now = int(time.time())
        nrecords = len(section_lengths)

        out_stream.write(self.title + struct.pack('>HHIIIIII', 0, 0, now, now, 0, 0, 0, 0))
        out_stream.write(self.identity + struct.pack('>IIH', nrecords, 0, nrecords))

        offset = 78 + (8 * nrecords) + 2
        for id, record in enumerate(section_lengths):
            out_stream.write(struct.pack('>LBBBB', long_type(offset), 0, 0, 0, 0))
            offset += record
        out_stream.write(b'\x00\x00')
