__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
""" 
Provides platform independent temporary files that persist even after 
being closed.
"""
import tempfile, os, atexit, shutil

from calibre import __version__, __appname__

class _TemporaryFileWrapper(object):
    """
    Temporary file wrapper

    This class provides a wrapper around files opened for
    temporary use.  In particular, it seeks to automatically
    remove the file when the object is deleted.
    """

    def __init__(self, _file, name):
        self.file = _file
        self.name = name
        atexit.register(cleanup, name)        

    def __getattr__(self, name):
        _file = self.__dict__['file']
        a = getattr(_file, name)
        if type(a) != type(0):
            setattr(self, name, a)
        return a
        
    def __del__(self):
        self.close()
        
def cleanup(path):
    try:
        import os
        if os.path.exists(path):
            os.remove(path)            
    except:
        pass   
    
def PersistentTemporaryFile(suffix="", prefix="", dir=None):
    """ 
    Return a temporary file that is available even after being closed on
    all platforms. It is automatically deleted on normal program termination.
    Uses tempfile.mkstemp to create the file. The file is opened in mode 'wb'.
    """
    if prefix == None: 
        prefix = ""
    fd, name = tempfile.mkstemp(suffix, __appname__+"_"+ __version__+"_" + prefix,
                                dir=dir)
    _file = os.fdopen(fd, 'w+b')
    return _TemporaryFileWrapper(_file, name)  

def PersistentTemporaryDirectory(suffix='', prefix='', dir=None):
    '''
    Return the path to a newly created temporary directory that will
    be automatically deleted on application exit.
    '''
    tdir = tempfile.mkdtemp(suffix, __appname__+"_"+ __version__+"_" +prefix, dir)
    atexit.register(shutil.rmtree, tdir, True)
    return tdir
      
