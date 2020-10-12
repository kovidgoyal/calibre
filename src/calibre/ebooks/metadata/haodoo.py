# -*- coding: utf-8 -*-


'''
Read meta information from Haodoo.net pdb files.
'''

__license__   = 'GPL v3'
__copyright__ = '2012, Kan-Ru Chen <kanru@kanru.info>'
__docformat__ = 'restructuredtext en'

from calibre.ebooks.pdb.header import PdbHeaderReader
from calibre.ebooks.pdb.haodoo.reader import Reader


def get_metadata(stream, extract_cover=True):
    '''
    Return metadata as a L{MetaInfo} object
    '''
    stream.seek(0)

    pheader = PdbHeaderReader(stream)
    reader = Reader(pheader, stream, None, None)

    return reader.get_metadata()
