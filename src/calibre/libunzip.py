#!/usr/bin/env  python
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

import os
from cStringIO import StringIO
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
    namelist = zf.namelist()
    dirlist = filter( lambda x: x.endswith( '/' ), namelist )
    filelist = filter( lambda x: not x.endswith( '/' ), namelist )
    # make base
    pushd = os.getcwd()
    if not os.path.isdir( dir ):
        os.mkdir( dir )
    os.chdir( dir )
    # create directory structure
    dirlist.sort()
    for dirs in dirlist:
        dirs = dirs.split( '/' )
        prefix = ''
        for dir in dirs:
            dirname = os.path.join( prefix, dir )
            if dir and not os.path.isdir( dirname ):
                os.mkdir( dirname )
            prefix = dirname
    # extract files
    for fn in filelist:
        if os.path.dirname(fn) and not os.path.exists(os.path.dirname(fn)):
            os.makedirs(os.path.dirname(fn))
        out = open( fn, 'wb' )
        buffer = StringIO( zf.read( fn ))
        buflen = 2 ** 20
        datum = buffer.read( buflen )
        while datum:
            out.write( datum )
            datum = buffer.read( buflen )
        out.close()
    os.chdir( pushd )