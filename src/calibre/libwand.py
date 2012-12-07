__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
import ctypes, os, sys

from calibre import iswindows, isosx

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
