# -*- coding: utf-8 -*-

__license__   = 'GPL v3'
__copyright__ = '2011, John Schember <john@nachtimwald.com>'

'''
Read meta information from extZ (TXTZ, HTMLZ...) files.
'''

from cStringIO import StringIO

from calibre.ebooks.metadata import MetaInformation
from calibre.ebooks.metadata.opf2 import OPF
from calibre.utils.zipfile import ZipFile, safe_replace

def get_metadata(stream, extract_cover=True):
    '''
    Return metadata as a L{MetaInfo} object
    '''
    mi = MetaInformation(_('Unknown'), [_('Unknown')])
    stream.seek(0)

    try:
        with ZipFile(stream) as zf:
            opf_name = get_first_opf_name(stream)
            opf_stream = StringIO(zf.read(opf_name))
            opf = OPF(opf_stream)
            mi = opf.to_book_metadata()
            if extract_cover:
                cover_name = opf.raster_cover
                if cover_name:
                    mi.cover_data = ('jpg', zf.read(cover_name))
    except:
        return mi
    return mi

def set_metadata(stream, mi):
    try:
        opf_name = get_first_opf_name(stream)
        with ZipFile(stream) as zf:
            opf_stream = StringIO(zf.read(opf_name))
        opf = OPF(opf_stream)
    except:
        opf_name = 'metadata.opf'
        opf = OPF(StringIO())
    opf.smart_update(mi, replace_metadata=True)
    newopf = StringIO(opf.render())
    safe_replace(stream, opf_name, newopf)

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
