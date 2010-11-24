#!/usr/bin/env  python
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

import re
from calibre.utils import zipfile

def update(pathtozip, patterns, filepaths, names, compression=zipfile.ZIP_DEFLATED, verbose=True):
    '''
    Update files in the zip file at `pathtozip` matching the given
    `patterns` with the given `filepaths`. If more than
    one file matches, all of the files are replaced.

    :param patterns:    A list of compiled regular expressions
    :param filepaths:   A list of paths to the replacement files. Must have the
                        same length as `patterns`.
    :param names:       A list of archive names for each file in filepaths.
                        A name can be `None` in which case the name of the existing
                        file in the archive is used.
    :param compression: The compression to use when replacing files. Can be
                        either `zipfile.ZIP_DEFLATED` or `zipfile.ZIP_STORED`.
    '''
    assert len(patterns) == len(filepaths) == len(names)
    z = zipfile.ZipFile(pathtozip, mode='a')
    for name in z.namelist():
        for pat, fname, new_name in zip(patterns, filepaths, names):
            if pat.search(name):
                if verbose:
                    print 'Updating %s with %s' % (name, fname)
                if new_name is None:
                    z.replace(fname, arcname=name, compress_type=compression)
                else:
                    z.delete(name)
                    z.write(fname, new_name, compress_type=compression)
                break
    z.close()

def extract(filename, dir):
    """
    Extract archive C{filename} into directory C{dir}
    """
    zf = zipfile.ZipFile( filename )
    zf.extractall(dir)

def extract_member(filename, match=re.compile(r'\.(jpg|jpeg|gif|png)\s*$',
    re.I), sort_alphabetically=False):
    zf = zipfile.ZipFile(filename)
    names = list(zf.namelist())
    if sort_alphabetically:
        names.sort()
    for name in names:
        if match.search(name):
            return name, zf.read(name)
