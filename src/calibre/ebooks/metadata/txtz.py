# -*- coding: utf-8 -*-

__license__   = 'GPL v3'
__copyright__ = '2011, John Schember <john@nachtimwald.com>'

'''
Read meta information from TXT files
'''

import os

from calibre.ebooks.metadata import MetaInformation
from calibre.ptempfile import TemporaryDirectory
from calibre.utils.zipfile import ZipFile

def get_metadata(stream, extract_cover=True):
    '''
    Return metadata as a L{MetaInfo} object
    '''
    mi = MetaInformation(_('Unknown'), [_('Unknown')])
    stream.seek(0)

    with TemporaryDirectory('_untxtz_mdata') as tdir:
        try:
            zf = ZipFile(stream)
            zf.extract('metadata.opf', tdir)
            
            from calibre.ebooks.metadata.opf2 import OPF
            with open(os.path.join(tdir, 'metadata.opf'), 'rb') as opff:
                mi = OPF(opff).to_book_metadata()
        except:
            return mi

    return mi
