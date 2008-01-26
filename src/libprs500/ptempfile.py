##    Copyright (C) 2006 Kovid Goyal kovid@kovidgoyal.net
##    This program is free software; you can redistribute it and/or modify
##    it under the terms of the GNU General Public License as published by
##    the Free Software Foundation; either version 2 of the License, or
##    (at your option) any later version.
##
##    This program is distributed in the hope that it will be useful,
##    but WITHOUT ANY WARRANTY; without even the implied warranty of
##    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
##    GNU General Public License for more details.
##
##    You should have received a copy of the GNU General Public License along
##    with this program; if not, write to the Free Software Foundation, Inc.,
##    51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.Warning
""" 
Provides platform independent temporary files that persist even after 
being closed.
"""
import tempfile, os, atexit

from libprs500 import __version__, __appname__

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
