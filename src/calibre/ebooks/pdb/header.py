# -*- coding: utf-8 -*-
from __future__ import with_statement
'''
Read the header data from a pdb file.
'''

__license__   = 'GPL v3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

import os, struct

class PdbHeaderReader(object):

    def __init__(self, stream):
        self.stream = stream
        self.ident = self.identity()
        self.num_sections = self.section_count()
        self.title = self.name()

    def identity(self):
        self.stream.seek(60)
        ident = self.stream.read(8)
        return ident

    def section_count(self):
        self.stream.seek(76)
        return struct.unpack('>H', self.stream.read(2))[0]

    def name(self):
        self.stream.seek(0)
        return self.stream.read(32).replace('\x00', '')

    def full_section_info(self, number):
        if number not in range(0, self.num_sections):
            raise ValueError('Not a valid section number %i' % number)

        self.stream.seek(78+number*8)
        offset, a1, a2, a3, a4 = struct.unpack('>LBBBB', self.stream.read(8))[0]
        flags, val = a1, a2<<16 | a3<<8 | a4
        return (offset, flags, val)

    def section_offset(self, number):
        if number not in range(0, self.num_sections):
            raise ValueError('Not a valid section number %i' % number)

        self.stream.seek(78+number*8)
        return struct.unpack('>LBBBB', self.stream.read(8))[0]

    def section_data(self, number):
        if number not in range(0, self.num_sections):
            raise ValueError('Not a valid section number %i' % number)

        start = self.section_offset(number)
        if number == self.num_sections -1:
            end = os.stat(self.stream.name).st_size
        else:
            end = self.section_offset(number + 1)
        self.stream.seek(start)
        return self.stream.read(end - start)


class PdbHeaderWriter(object):

    def __init__(self, identity, title):
        self.identity = identity[:8]
        self.title = title.ljust(32, '\x00')[:32]

    def build_header(self, sections):
        '''
        Sections is a list of section offsets
        '''




        return header
