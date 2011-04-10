# -*- coding: utf-8 -*-

__license__   = 'GPL v3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

class PDBError(Exception):
    pass


from calibre.ebooks.pdb.ereader.reader import Reader as ereader_reader
from calibre.ebooks.pdb.palmdoc.reader import Reader as palmdoc_reader
from calibre.ebooks.pdb.ztxt.reader import Reader as ztxt_reader
from calibre.ebooks.pdb.pdf.reader import Reader as pdf_reader
from calibre.ebooks.pdb.plucker.reader import Reader as plucker_reader

FORMAT_READERS = {
    'PNPdPPrs': ereader_reader,
    'PNRdPPrs': ereader_reader,
    'zTXTGPlm': ztxt_reader,
    'TEXtREAd': palmdoc_reader,
    '.pdfADBE': pdf_reader,
    'DataPlkr': plucker_reader,
}

from calibre.ebooks.pdb.palmdoc.writer import Writer as palmdoc_writer
from calibre.ebooks.pdb.ztxt.writer import Writer as ztxt_writer
from calibre.ebooks.pdb.ereader.writer import Writer as ereader_writer

FORMAT_WRITERS = {
    'doc': palmdoc_writer,
    'ztxt': ztxt_writer,
    'ereader': ereader_writer,
}

IDENTITY_TO_NAME = {
    'PNPdPPrs': 'eReader',
    'PNRdPPrs': 'eReader',
    'zTXTGPlm': 'zTXT',
    'TEXtREAd': 'PalmDOC',
    '.pdfADBE': 'Adobe Reader',
    'DataPlkr': 'Plucker',

    'BVokBDIC': 'BDicty',
    'DB99DBOS': 'DB (Database program)',
    'vIMGView': 'FireViewer (ImageViewer)',
    'PmDBPmDB': 'HanDBase',
    'InfoINDB': 'InfoView',
    'ToGoToGo': 'iSilo',
    'SDocSilX': 'iSilo 3',
    'JbDbJBas': 'JFile',
    'JfDbJFil': 'JFile Pro',
    'DATALSdb': 'LIST',
    'Mdb1Mdb1': 'MobileDB',
    'BOOKMOBI': 'MobiPocket',
    'DataSprd': 'QuickSheet',
    'SM01SMem': 'SuperMemo',
    'TEXtTlDc': 'TealDoc',
    'InfoTlIf': 'TealInfo',
    'DataTlMl': 'TealMeal',
    'DataTlPt': 'TealPaint',
    'dataTDBP': 'ThinkDB',
    'TdatTide': 'Tides',
    'ToRaTRPW': 'TomeRaider',
    'BDOCWrdS': 'WordSmith',
}

def get_reader(identity):
    '''
    Returns None if no reader is found for the identity.
    '''
    return FORMAT_READERS.get(identity, None)

def get_writer(extension):
    '''
    Returns None if no writer is found for extension.
    '''
    return FORMAT_WRITERS.get(extension, None)

