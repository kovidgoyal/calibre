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
            with ZipFile(stream) as zf:
                opf_name = get_first_opf_name(stream)
                opf_stream = StringIO(zf.read(opf_name))
                mi = OPF(opf_stream).to_book_metadata()
        except:
            return mi
    return mi

def set_metadata(stream, mi):
    opf = StringIO(metadata_to_opf(mi))
    try:
        opf_name = get_first_opf_name(stream)
    except:
        opf_name = 'metadata.opf'
    safe_replace(stream, opf_name, opf)

def get_first_opf_name(stream):
    with ZipFile(stream) as zf:
        names = zf.namelist()
        opfs = []
        for n in names:
            if n.endswith('.opf') and '/' not in n:
                opfs.append(n)
        if not opfs:
            raise Exception('No OPF found')
        opfs.sort()
        return opfs[0]
