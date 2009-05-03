# -*- coding: utf-8 -*-

'''
Read meta information from eReader pdb files.
'''

__license__   = 'GPL v3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

import re

from calibre.ebooks.metadata import MetaInformation
from calibre.ebooks.pdb.header import PdbHeaderReader
from calibre.ebooks.pdb.ereader.reader import HeaderRecord

def get_metadata(stream, extract_cover=True):
    """
    Return metadata as a L{MetaInfo} object
    """
    mi = MetaInformation(None, [_('Unknown')])
    stream.seek(0)
    
    pheader = PdbHeaderReader(stream)
    hr = HeaderRecord(pheader.section_data(0))
        
    if hr.version in (2, 10):
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

