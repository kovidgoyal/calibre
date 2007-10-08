##    Copyright (C) 2007 Kovid Goyal kovid@kovidgoyal.net
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
##    51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
import ctypes, os, sys

from libprs500 import iswindows, isosx

class WandException(Exception):
    pass

_lib_name = 'CORE_RL_wand_.dll' if iswindows else 'libWand.dylib' if isosx else 'libWand.so'
if iswindows and hasattr(sys, 'frozen'):
    im_dir = os.path.join(os.path.dirname(sys.executable), 'ImageMagick')
    os.putenv('PATH', im_dir + ';' + os.environ['PATH'])
_libwand = None
try:
    _libwand = ctypes.cdll.LoadLibrary(_lib_name)
except:
    pass



class Severity(ctypes.c_long):
    pass

class String(ctypes.c_char_p):
    
    def __del__(self):
        _libwand.MagickRelinquishMemory(self)
        
    def __str__(self):
        return self.value

if _libwand is not None:
    _libwand.MagickGetException.argtypes = [ctypes.c_void_p, ctypes.POINTER(Severity)]
    _libwand.MagickGetException.restype  = String 

def get_exception(wand):
    severity = Severity()
    desc = _libwand.MagickGetException(wand, ctypes.byref(severity))
    return str(desc)

def convert(source, dest):
    if _libwand is None:
        raise WandException('Could not find ImageMagick library')
    if not _libwand.MagickWandGenesis():
        raise WandException('Unable to initialize Image Magick')
    wand = _libwand.NewMagickWand()
    if wand <= 0:
        raise WandException('Unable to initialize Image Magick. Cannot create wand.')
    if not _libwand.MagickReadImage(wand, source):
        raise WandException('Cannot read image %s: %s'%(source, get_exception(wand)))
    if not _libwand.MagickWriteImage(wand, dest):
        raise WandException('Cannot write image to file %s: %s'%(source, get_exception(wand)))
    _libwand.DestroyMagickWand(wand)
    _libwand.MagickWandTerminus()