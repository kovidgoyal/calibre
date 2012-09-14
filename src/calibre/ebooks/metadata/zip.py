from __future__ import with_statement
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'

import os

from calibre.utils.zipfile import ZipFile
from calibre.ptempfile import TemporaryDirectory
from calibre import CurrentDir

def get_metadata(stream):
    from calibre.ebooks.metadata.meta import get_metadata
    from calibre.ebooks.metadata.archive import is_comic
    stream_type = None
    zf = ZipFile(stream, 'r')
    names = zf.namelist()
    if is_comic(names):
        # Is probably a comic
        return get_metadata(stream, 'cbz')

    for f in names:
        stream_type = os.path.splitext(f)[1].lower()
        if stream_type:
            stream_type = stream_type[1:]
            if stream_type in ('lit', 'opf', 'prc', 'mobi', 'fb2', 'epub',
                               'rb', 'imp', 'pdf', 'lrf', 'azw', 'azw1', 'azw3'):
                with TemporaryDirectory() as tdir:
                    with CurrentDir(tdir):
                        path = zf.extract(f)
                        mi = get_metadata(open(path,'rb'), stream_type)
                        if stream_type == 'opf' and mi.application_id == None:
                            try:
                                # zip archive opf files without an application_id were assumed not to have a cover
                                # reparse the opf and if cover exists read its data from zip archive for the metadata
                                nmi = zip_opf_metadata(path, zf)
                                return nmi
                            except:
                                pass
                        return mi
    raise ValueError('No ebook found in ZIP archive')


def zip_opf_metadata(opfpath, zf):
    from calibre.ebooks.metadata.opf2 import OPF
    if hasattr(opfpath, 'read'):
        f = opfpath
        opfpath = getattr(f, 'name', os.getcwdu())
    else:
        f = open(opfpath, 'rb')
    opf = OPF(f, os.path.dirname(opfpath))
    mi = opf.to_book_metadata()
    # This is broken, in that it only works for
    # when both the OPF file and the cover file are in the root of the
    # zip file and the cover is an actual raster image, but I don't care
    # enough to make it more robust
    if getattr(mi, 'cover', None):
        covername = os.path.basename(mi.cover)
        mi.cover = None
        names = zf.namelist()
        if covername in names:
            fmt = covername.rpartition('.')[-1]
            data = zf.read(covername)
            mi.cover_data = (fmt, data)
    return mi

