# -*- coding: utf-8 -*-

'''
Read meta information from pdb files.
'''

__license__   = 'GPL v3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

import re

from calibre.ebooks.metadata import MetaInformation
from calibre.ebooks.pdb.header import PdbHeaderReader
from calibre.ebooks.metadata.ereader import get_metadata as get_eReader
from calibre.ebooks.metadata.plucker import get_metadata as get_plucker
from calibre.ebooks.metadata.haodoo import get_metadata as get_Haodoo

MREADER = {
    'PNPdPPrs' : get_eReader,
    'PNRdPPrs' : get_eReader,
    'DataPlkr' : get_plucker,
    'BOOKMTIT' : get_Haodoo,
    'BOOKMTIU' : get_Haodoo,
}

from calibre.ebooks.metadata.ereader import set_metadata as set_eReader

MWRITER = {
    'PNPdPPrs' : set_eReader,
    'PNRdPPrs' : set_eReader,
}

def get_metadata(stream, extract_cover=True):
    """
    Return metadata as a L{MetaInfo} object
    """
    
    pheader = PdbHeaderReader(stream)
    
    MetadataReader = MREADER.get(pheader.ident, None)

    if MetadataReader is None:
        return MetaInformation(pheader.title, [_('Unknown')])

    return MetadataReader(stream, extract_cover)
    
def set_metadata(stream, mi):
    stream.seek(0)
    
    pheader = PdbHeaderReader(stream)
    
    MetadataWriter = MWRITER.get(pheader.ident, None)
    
    if MetadataWriter:
        MetadataWriter(stream, mi)

    stream.seek(0)
    stream.write('%s\x00' % re.sub('[^-A-Za-z0-9 ]+', '_', mi.title).ljust(31, '\x00')[:31].encode('ascii', 'replace'))

