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
from calibre.ebooks.metadata.ereader import get_metadata as eReader

MREADER = {    
    'PNPdPPrs' : eReader,
    'PNRdPPrs' : eReader,
}

def get_metadata(stream, extract_cover=True):
    """
    Return metadata as a L{MetaInfo} object
    """
    
    pheader = PdbHeaderReader(stream)
    
    MetadataReader = MREADER.get(pheader.ident, None)

    if MetadataReader is None:
        return MetaInformation(_('Unknown'), [_('Unknown')])

    
    return MetadataReader(stream, extract_cover)
    
