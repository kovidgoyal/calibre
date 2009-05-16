# -*- coding: utf-8 -*-

'''
Read meta information from eReader pdb files.
'''

__license__   = 'GPL v3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

import re

from calibre.ebooks.metadata import MetaInformation, authors_to_string
from calibre.ebooks.pdb.header import PdbHeaderReader, PdbHeaderBuilder
from calibre.ebooks.pdb.ereader.reader import HeaderRecord

def get_metadata(stream, extract_cover=True):
    """
    Return metadata as a L{MetaInfo} object
    """
    mi = MetaInformation(None, [_('Unknown')])
    stream.seek(0)
    
    pheader = PdbHeaderReader(stream)
    hr = HeaderRecord(pheader.section_data(0))
        
    if hr.version in (2, 10) and hr.has_metadata == 1:
        try:
            mdata = pheader.section_data(hr.metadata_offset)
    
            mdata = mdata.split('\x00')
            mi.title = mdata[0]
            mi.authors = [mdata[1]]
            mi.publisher = mdata[3]
            mi.isbn = mdata[4]
        except:
            pass
        
    if not mi.title:
        mi.title = pheader.title if pheader.title else _('Unknown')

    return mi

def set_metadata(stream, mi):
    pheader = PdbHeaderReader(stream)
    sections = [pheader.section_data(x) for x in range(0, pheader.section_count())]
    hr = HeaderRecord(sections[0])
    
    if hr.version not in (2, 10):
        return
    
    # Create a metadata record for the file if one does not alreay exist
    if not hr.has_metadata:
        sections += ['', 'MeTaInFo\x00']
        last_data = len(sections) - 1
        
        for i in range(0, 132, 2):
            val, = struct.unpack('>H', sections[0][i:i+2])
            if val >= hr.last_data_offset:
                sections[0][i:i+2] = struct.pack('>H', last_data)
            
        sections[0][24:26] = struct.pack('>H', 1) # Set has metadata
        sections[0][44:46] = struct.pack('>H', last_data - 1) # Set location of metadata
        sections[0][52:54] = struct.pack('>H', last_data) # Ensure last data offset is updated
    
    # Merge the metadata into the file
    file_mi = get_metadata(stream, False)
    file_mi.smart_update(mi)
    sections[hr.metadata_offset] = '%s\x00%s\x00%s\x00%s\x00%s\x00' % \
        (file_mi.title, authors_to_string(file_mi.authors), '', file_mi.publisher, file_mi.isbn)

    # Rebuild the PDB wrapper because the offsets have changed due to the
    # new metadata.
    pheader_builder = PdbHeaderBuilder(pheader.ident, pheader.title)
    stream.seek(0)
    stream.truncate(0)
    pheader_builder.build_header([len(x) for x in sections], stream)

    # Write the data back to the file
    for item in sections:
        stream.write(item)

