# -*- coding: utf-8 -*-
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

from calibre.ebooks.pdb.ereader.reader import Reader as eReader
from calibre.ebooks.pdb.ztxt.reader import Reader as zTXT
#from calibre.ebooks.pdb.palmdoc.reader import Reader as PalmDoc

FORMATS = {
    'PNPdPPrs' : eReader,
    'PNRdPPrs' : eReader,
    'zTXTGPlm' : zTXT,
#    'TEXtREAd' : PalmDoc,
}

IDENTITY_TO_NAME = {
    'PNPdPPrs' : 'eReader',
    'PNRdPPrs' : 'eReader',
    'zTXTGPlm' : 'zTXT',
    'TEXtREAd' : 'PalmDOC',
    
    '.pdfADBE' : 'Adobe Reader',
    'BVokBDIC' : 'BDicty',
    'DB99DBOS' : 'DB (Database program)',
    'vIMGView' : 'FireViewer (ImageViewer)',
    'PmDBPmDB' : 'HanDBase',
    'InfoINDB' : 'InfoView',
    'ToGoToGo' : 'iSilo',
    'SDocSilX' : 'iSilo 3',
    'JbDbJBas' : 'JFile',
    'JfDbJFil' : 'JFile Pro',
    'DATALSdb' : 'LIST',
    'Mdb1Mdb1' : 'MobileDB',
    'BOOKMOBI' : 'MobiPocket',
    'DataPlkr' : 'Plucker',
    'DataSprd' : 'QuickSheet',
    'SM01SMem' : 'SuperMemo',
    'TEXtTlDc' : 'TealDoc',
    'InfoTlIf' : 'TealInfo',
    'DataTlMl' : 'TealMeal',
    'DataTlPt' : 'TealPaint',
    'dataTDBP' : 'ThinkDB',
    'TdatTide' : 'Tides',
    'ToRaTRPW' : 'TomeRaider',
    'BDOCWrdS' : 'WordSmith',
}

class PDBError(Exception):
    pass
    

def get_reader(identity):
    '''
    Returns None if no reader is found for the identity.
    '''
    if identity in FORMATS.keys():
        return FORMATS[identity]
    else:
        return None
