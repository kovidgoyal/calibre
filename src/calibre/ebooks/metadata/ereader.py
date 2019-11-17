# -*- coding: utf-8 -*-


'''
Read meta information from eReader pdb files.
'''

__license__   = 'GPL v3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

import re
import struct

from calibre.ebooks.metadata import MetaInformation
from calibre.ebooks.metadata import authors_to_string
from calibre.ebooks.pdb.ereader.reader132 import HeaderRecord
from calibre.ebooks.pdb.header import PdbHeaderBuilder
from calibre.ebooks.pdb.header import PdbHeaderReader


def get_cover(pheader, eheader):
    cover_data = None

    for i in range(eheader.image_count):
        raw = pheader.section_data(eheader.image_data_offset + i)

        if raw[4:4 + 32].strip(b'\x00') == b'cover.png':
            cover_data = raw[62:]
            break

    return ('png', cover_data)


def get_metadata(stream, extract_cover=True):
    """
    Return metadata as a L{MetaInfo} object
    """
    mi = MetaInformation(None, [_('Unknown')])
    stream.seek(0)

    pheader = PdbHeaderReader(stream)

    # Only Dropbook produced 132 byte record0 files are supported
    if len(pheader.section_data(0)) == 132:
        hr = HeaderRecord(pheader.section_data(0))

        if hr.compression in (2, 10) and hr.has_metadata == 1:
            try:
                mdata = pheader.section_data(hr.metadata_offset)

                mdata = mdata.decode('cp1252', 'replace').split('\x00')
                mi.title = re.sub(r'[^a-zA-Z0-9 \._=\+\-!\?,\'\"]', '', mdata[0])
                mi.authors = [re.sub(r'[^a-zA-Z0-9 \._=\+\-!\?,\'\"]', '', mdata[1])]
                mi.publisher = re.sub(r'[^a-zA-Z0-9 \._=\+\-!\?,\'\"]', '', mdata[3])
                mi.isbn = re.sub(r'[^a-zA-Z0-9 \._=\+\-!\?,\'\"]', '', mdata[4])
            except Exception:
                pass

            if extract_cover:
                mi.cover_data = get_cover(pheader, hr)

    if not mi.title:
        mi.title = pheader.title if pheader.title else _('Unknown')

    return mi


def set_metadata(stream, mi):
    pheader = PdbHeaderReader(stream)

    # Only Dropbook produced 132 byte record0 files are supported
    if pheader.section_data(0) != 132:
        return

    sections = [pheader.section_data(x) for x in range(0, pheader.section_count())]
    hr = HeaderRecord(sections[0])

    if hr.compression not in (2, 10):
        return

    # Create a metadata record for the file if one does not alreay exist
    if not hr.has_metadata:
        sections += [b'', b'MeTaInFo\x00']
        last_data = len(sections) - 1

        for i in range(0, 132, 2):
            val, = struct.unpack('>H', sections[0][i:i + 2])
            if val >= hr.last_data_offset:
                sections[0][i:i + 2] = struct.pack('>H', last_data)

        sections[0][24:26] = struct.pack('>H', 1)  # Set has metadata
        sections[0][44:46] = struct.pack('>H', last_data - 1)  # Set location of metadata
        sections[0][52:54] = struct.pack('>H', last_data)  # Ensure last data offset is updated

    # Merge the metadata into the file
    file_mi = get_metadata(stream, False)
    file_mi.smart_update(mi)
    sections[hr.metadata_offset] = ('%s\x00%s\x00%s\x00%s\x00%s\x00' % (
        file_mi.title, authors_to_string(file_mi.authors), '', file_mi.publisher, file_mi.isbn)).encode('cp1252', 'replace')

    # Rebuild the PDB wrapper because the offsets have changed due to the
    # new metadata.
    pheader_builder = PdbHeaderBuilder(pheader.ident, pheader.title)
    stream.seek(0)
    stream.truncate(0)
    pheader_builder.build_header([len(x) for x in sections], stream)

    # Write the data back to the file
    for item in sections:
        stream.write(item)
