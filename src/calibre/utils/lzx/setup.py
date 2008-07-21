#!/usr/bin/env  python
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

'''
Build the lzx decompressor extension
'''
from distutils.core import setup, Extension

setup(name="lzx", version="1.0", 
      ext_modules=[Extension('lzx',
                             sources=['lzxmodule.c', 'lzxd.c'],
                             include_dirs=['.'])])

