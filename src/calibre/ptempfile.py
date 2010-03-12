from __future__ import with_statement
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
"""
Provides platform independent temporary files that persist even after
being closed.
"""
import tempfile, os, atexit, shutil

from calibre import __version__, __appname__

def cleanup(path):
    try:
        import os
        if os.path.exists(path):
            os.remove(path)
    except:
        pass

class PersistentTemporaryFile(object):
    """
    A file-like object that is a temporary file that is available even after being closed on
    all platforms. It is automatically deleted on normal program termination.
    """
    _file = None

    def __init__(self, suffix="", prefix="", dir=None, mode='w+b'):
        if prefix == None:
            prefix = ""
        fd, name = tempfile.mkstemp(suffix, __appname__+"_"+ __version__+"_" + prefix,
                                    dir=dir)
        self._file = os.fdopen(fd, mode)
        self._name = name
        self._fd = fd
        atexit.register(cleanup, name)

    def __getattr__(self, name):
        if name == 'name':
            return self.__dict__['_name']
        return getattr(self.__dict__['_file'], name)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def __del__(self):
        try:
            self.close()
        except:
            pass

    def startswith(self,*args):
        if len(args):
            str = args[0]
            beg = 0
            end = len(str)
        else:
            return False

        if len(args) > 1:
            begin = args[1]
        if len(args) > 2:
            end = args[2]
        if self._name[beg:end].startswith(str):
            return True
        return False

    def split(self,*args):
        if len(args):
            sep = args[0]
        if len(args) > 1:
            maxsplit = args[1]
            return self._name.split(sep,maxsplit)
        else:
            return self._name.split(sep)


def PersistentTemporaryDirectory(suffix='', prefix='', dir=None):
    '''
    Return the path to a newly created temporary directory that will
    be automatically deleted on application exit.
    '''
    tdir = tempfile.mkdtemp(suffix, __appname__+"_"+ __version__+"_" +prefix, dir)
    atexit.register(shutil.rmtree, tdir, True)
    return tdir

class TemporaryDirectory(object):
    '''
    A temporary directory to be used in a with statement.
    '''
    def __init__(self, suffix='', prefix='', dir=None, keep=False):
        self.suffix = suffix
        self.prefix = prefix
        self.dir = dir
        self.keep = keep

    def __enter__(self):
        self.tdir = tempfile.mkdtemp(self.suffix, __appname__+"_"+ __version__+"_" +self.prefix, self.dir)
        return self.tdir

    def __exit__(self, *args):
        if not self.keep and os.path.exists(self.tdir):
            shutil.rmtree(self.tdir, ignore_errors=True)

class TemporaryFile(object):

    def __init__(self, suffix="", prefix="", dir=None, mode='w+b'):
        if prefix == None:
            prefix = ''
        if suffix is None:
            suffix = ''
        self.prefix, self.suffix, self.dir, self.mode = prefix, suffix, dir, mode
        self._file = None

    def __enter__(self):
        fd, name = tempfile.mkstemp(self.suffix,
                __appname__+"_"+ __version__+"_" + self.prefix,
                                    dir=self.dir)
        self._file = os.fdopen(fd, self.mode)
        self._name = name
        self._file.close()
        return name

    def __exit__(self, *args):
        cleanup(self._name)




