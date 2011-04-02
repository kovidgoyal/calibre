# -*- coding: utf-8 -*-

__license__   = 'GPL v3'
__copyright__ = '2011, John Schember <john@nachtimwald.com>'

'''
Read meta information from extZ (TXTZ, HTMLZ...) files.
'''

import os

from cStringIO import StringIO

from calibre.ebooks.metadata import MetaInformation
from calibre.ebooks.metadata.opf2 import OPF, metadata_to_opf
from calibre.ptempfile import TemporaryDirectory
from calibre.utils.zipfile import ZipFile, safe_replace

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
            with open(os.path.join(tdir, 'metadata.opf'), 'rb') as opff:
                mi = OPF(opff).to_book_metadata()
        except:
            return mi
    return mi

def set_metadata(stream, mi):
    opf = StringIO(metadata_to_opf(mi))
    safe_replace(stream, 'metadata.opf', opf)
