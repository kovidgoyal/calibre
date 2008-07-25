#!/usr/bin/env  python
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

'''
:mod:`fontconfig` -- Query system fonts
=============================================
.. module:: fontconfig
   :platform: Unix, Windows, OS X
   :synopsis: Query system fonts
.. moduleauthor:: Kovid Goyal <kovid@kovidgoyal.net>

A ctypes based wrapper around the `fontconfig <http://fontconfig.org>`_ library.
It can be used to find all fonts available on the system as well as the closest
match to a given font specification. The main functions in this module are:

.. autofunction:: find_font_families

.. autofunction:: files_for_family

.. autofunction:: match
'''

import sys, os, locale, codecs, ctypes
from ctypes import cdll, c_void_p, Structure, c_int, POINTER, c_ubyte, c_char, util, \
                   pointer, byref, create_string_buffer, Union, c_char_p, c_double

try:
    preferred_encoding = locale.getpreferredencoding()
    codecs.lookup(preferred_encoding)
except:
    preferred_encoding = 'utf-8'

iswindows = 'win32' in sys.platform or 'win64' in sys.platform
isosx     = 'darwin' in sys.platform
DISABLED  = False 
#if isosx:
#    libc = ctypes.cdll.LoadLibrary(ctypes.util.find_library('c'))
#    size = ctypes.c_uint(0)
#    ok   = libc.sysctlbyname("hw.cpu64bit_capable", None, byref(size), None, 0)
#    if ok != 0:
#        is64bit = False
#    else:
#        buf = ctypes.c_char_p("\0" * size.value)
#        ok = libc.sysctlbyname("hw.cpu64bit_capable", buf, byref(size), None, 0)
#        if ok != 0:
#            is64bit = False
#        else:
#            is64bit = '1' in buf.value
#    DISABLED = is64bit

def load_library():
    if isosx:
        lib = os.path.join(getattr(sys, 'frameworks_dir'), 'libfontconfig.1.dylib') \
                  if hasattr(sys, 'frameworks_dir') else util.find_library('fontconfig')
        return cdll.LoadLibrary(lib)
    elif iswindows:
        return cdll.LoadLibrary('libfontconfig-1')
    else:
        try:
            return cdll.LoadLibrary(util.find_library('fontconfig'))
        except:
            try:
                return cdll.LoadLibrary('libfontconfig.so')
            except:
                return cdll.LoadLibrary('libfontconfig.so.1')

class FcPattern(Structure):
    _fields_ = [
                ('num', c_int),
                ('size', c_int),
                ('elts_offset', c_void_p),
                ('ref', c_int)
                ]
class FcFontSet(Structure):
    _fields_ = [
                ('nfont', c_int),
                ('sfont', c_int),
                ('fonts', POINTER(POINTER(FcPattern)))
                ]
(
    FcTypeVoid,
    FcTypeInteger,
    FcTypeDouble,
    FcTypeString,
    FcTypeBool,
    FcTypeMatrix,
    FcTypeCharSet,
    FcTypeFTFace,
    FcTypeLangSet
) = map(c_int, range(9))
(FcMatchPattern, FcMatchFont, FcMatchScan) = map(c_int, range(3))
(
FcResultMatch, FcResultNoMatch, FcResultTypeMismatch, FcResultNoId,
    FcResultOutOfMemory
) = map(c_int, range(5))
FcFalse, FcTrue = c_int(0), c_int(1)

class _FcValue(Union):
    _fields_ = [
                ('s', c_char_p),
                ('i', c_int),
                ('b', c_int),
                ('d', c_double),
                ]

class FcValue(Structure):
    _fields_ = [
                ('type', c_int),
                ('u', _FcValue)
                ]

lib = load_library()
lib.FcPatternCreate.restype   = c_void_p
lib.FcObjectSetCreate.restype = c_void_p
lib.FcFontSetDestroy.argtypes = [POINTER(FcFontSet)]
lib.FcFontList.restype = POINTER(FcFontSet)
lib.FcNameUnparse.argtypes = [POINTER(FcPattern)]
lib.FcNameUnparse.restype = POINTER(c_ubyte)
lib.FcPatternGetString.argtypes = [POINTER(FcPattern), POINTER(c_char), c_int, c_void_p]
lib.FcPatternGetString.restype = c_int
lib.FcPatternAdd.argtypes = [c_void_p, POINTER(c_char), FcValue, c_int]
lib.FcPatternGetInteger.argtypes = [POINTER(FcPattern), POINTER(c_char), c_int, POINTER(c_int)]
lib.FcPatternGetInteger.restype = c_int
lib.FcNameParse.argtypes = [c_char_p]
lib.FcNameParse.restype = POINTER(FcPattern)
lib.FcDefaultSubstitute.argtypes = [POINTER(FcPattern)]
lib.FcConfigSubstitute.argtypes = [c_void_p, POINTER(FcPattern), c_int]
lib.FcFontSetCreate.restype = POINTER(FcFontSet)
lib.FcFontMatch.argtypes = [c_void_p, POINTER(FcPattern), POINTER(c_int)]
lib.FcFontMatch.restype = POINTER(FcPattern)
lib.FcFontSetAdd.argtypes = [POINTER(FcFontSet), POINTER(FcPattern)]
lib.FcFontSort.argtypes = [c_void_p, POINTER(FcPattern), c_int, c_void_p, POINTER(c_int)]
lib.FcFontSort.restype = POINTER(FcFontSet)
lib.FcFontRenderPrepare.argtypes = [c_void_p, POINTER(FcPattern), POINTER(FcPattern)]
lib.FcFontRenderPrepare.restype = POINTER(FcPattern)
lib.FcConfigCreate.restype = c_void_p
lib.FcConfigSetCurrent.argtypes = [c_void_p]
lib.FcConfigSetCurrent.restype = c_int
lib.FcConfigParseAndLoad.argtypes = [c_void_p, POINTER(c_char), c_int]
lib.FcConfigParseAndLoad.restype = c_int
lib.FcConfigBuildFonts.argtypes = [c_void_p]
lib.FcConfigBuildFonts.restype  = c_int

_init_error  = None 
_initialized = False
from threading import Thread

class FontScanner(Thread):
    def run(self):
        # Initialize the fontconfig library. This has to be done manually
        # for the OS X bundle as it may have its own private fontconfig.
        if getattr(sys, 'frameworks_dir', False) and not os.path.exists('/usr/X11/lib/libfontconfig.1.dylib'):
            config_dir = os.path.join(os.path.dirname(getattr(sys, 'frameworks_dir')), 'Resources', 'fonts')
            if isinstance(config_dir, unicode):
                config_dir = config_dir.encode(sys.getfilesystemencoding())
            config = lib.FcConfigCreate()
            if not lib.FcConfigParseAndLoad(config, os.path.join(config_dir, 'fonts.conf'), 1):
                _init_error = 'Could not parse the fontconfig configuration'
                return
            if not lib.FcConfigBuildFonts(config):
                _init_error = 'Could not build fonts'
                return
            if not lib.FcConfigSetCurrent(config):
                _init_error = 'Could not set font config'
                return
        elif not lib.FcInit():
            _init_error = _('Could not initialize the fontconfig library')
            return
        global _initialized
        _initialized = True
    
if not DISABLED:
    _scanner = FontScanner()
    _scanner.start()

def join():
    _scanner.join(120)
    if _scanner.isAlive():
        raise RuntimeError('Scanning for system fonts seems to have hung. Try again in a little while.')
    if _init_error is not None:
        raise RuntimeError(_init_error)

def find_font_families(allowed_extensions=['ttf', 'otf']):
    '''
    Return an alphabetically sorted list of font families available on the system.
    
    `allowed_extensions`: A list of allowed extensions for font file types. Defaults to
    `['ttf', 'otf']`. If it is empty, it is ignored.
    '''
    if DISABLED:
        return []
    join()
    allowed_extensions = [i.lower() for i in allowed_extensions]
    
    empty_pattern = lib.FcPatternCreate()
    oset = lib.FcObjectSetCreate()
    if not lib.FcObjectSetAdd(oset, 'file'):
        raise RuntimeError('Allocation failure')
    if not lib.FcObjectSetAdd(oset, 'family'):
        raise RuntimeError('Allocation failure')
    fs = lib.FcFontList(0, empty_pattern, oset)
    font_set = fs.contents
    file = pointer(create_string_buffer(chr(0), 5000))
    family = pointer(create_string_buffer(chr(0), 200))
    font_families = []
    for i in range(font_set.nfont):
        pat = font_set.fonts[i]
        if lib.FcPatternGetString(pat, 'file', 0, byref(file)) != FcResultMatch.value:
            raise RuntimeError('Error processing pattern')
        path = str(file.contents.value)
        ext = os.path.splitext(path)[1]
        if ext:
            ext = ext[1:].lower()
        if (not allowed_extensions) or (allowed_extensions and ext in allowed_extensions):
            if lib.FcPatternGetString(pat, 'family', 0, byref(family)) != FcResultMatch.value:
                raise RuntimeError('Error processing pattern')
            font_families.append(str(family.contents.value))
         
    lib.FcObjectSetDestroy(oset)
    lib.FcPatternDestroy(empty_pattern)
    lib.FcFontSetDestroy(fs)
    font_families = list(set(font_families))
    font_families.sort()
    return font_families
    
def files_for_family(family, normalize=True):
    '''
    Find all the variants in the font family `family`. 
    Returns a dictionary of tuples. Each tuple is of the form (Full font name, path to font file).
    The keys of the dictionary depend on `normalize`. If `normalize` is `False`,
    they are a tuple (slant, weight) otherwise they are strings from the set 
    `('normal', 'bold', 'italic', 'bi', 'light', 'li')`
    '''
    if DISABLED:
        return {}
    join()
    if isinstance(family, unicode):
        family = family.encode(preferred_encoding)
    family_pattern = lib.FcPatternBuild(0, 'family', FcTypeString, family, 0)
    if not family_pattern:
        raise RuntimeError('Allocation failure')
    #lib.FcPatternPrint(family_pattern)
    oset = lib.FcObjectSetCreate()
    if not lib.FcObjectSetAdd(oset, 'file'):
        raise RuntimeError('Allocation failure')
    if not lib.FcObjectSetAdd(oset, 'weight'):
        raise RuntimeError('Allocation failure')
    if not lib.FcObjectSetAdd(oset, 'fullname'):
        raise RuntimeError('Allocation failure')
    if not lib.FcObjectSetAdd(oset, 'slant'):
        raise RuntimeError('Allocation failure')
    if not lib.FcObjectSetAdd(oset, 'style'):
        raise RuntimeError('Allocation failure')
    fonts = {}
    fs = lib.FcFontList(0, family_pattern, oset)
    font_set = fs.contents
    file  = pointer(create_string_buffer(chr(0), 5000))
    full_name  = pointer(create_string_buffer(chr(0), 200))
    weight = c_int(0)
    slant = c_int(0)
    fname = ''
    for i in range(font_set.nfont):
        pat = font_set.fonts[i]
        #lib.FcPatternPrint(pat)
        pat = font_set.fonts[i]
        if lib.FcPatternGetString(pat, 'file', 0, byref(file)) != FcResultMatch.value:
            raise RuntimeError('Error processing pattern')
        if lib.FcPatternGetInteger(pat, 'weight', 0, byref(weight)) != FcResultMatch.value:
            raise RuntimeError('Error processing pattern')
        if lib.FcPatternGetString(pat, 'fullname', 0, byref(full_name)) != FcResultMatch.value:
            if lib.FcPatternGetString(pat, 'fullname', 0, byref(full_name)) == FcResultNoMatch.value:
                if lib.FcPatternGetString(pat, 'style', 0, byref(full_name)) != FcResultMatch.value:
                    raise RuntimeError('Error processing pattern')
                fname = family + ' ' + full_name.contents.value
            else:
                raise RuntimeError('Error processing pattern')
        else:
            fname = full_name.contents.value
        if lib.FcPatternGetInteger(pat, 'slant', 0, byref(slant)) != FcResultMatch.value:
            raise RuntimeError('Error processing pattern')
        style = (slant.value, weight.value) 
        if normalize:
            italic = slant.value > 0
            normal = weight.value == 80
            bold = weight.value > 80
            if italic:
                style = 'italic' if normal else 'bi' if bold else 'li' 
            else:
                style = 'normal' if normal else 'bold' if bold else 'light'
        fonts[style] = (file.contents.value, fname)
    lib.FcObjectSetDestroy(oset)
    lib.FcPatternDestroy(family_pattern)
    if not iswindows:
        lib.FcFontSetDestroy(fs)
    
    return  fonts

def match(name, sort=False, verbose=False):
    '''
    Find the system font that most closely matches `name`, where `name` is a specification
    of the form::
      familyname-<pointsize>:<property1=value1>:<property2=value2>...
      
    For example, `verdana:weight=bold:slant=italic`
    
    Returns a list of dictionaries. Each dictionary has the keys: 'weight', 'slant', 'family', 'file'
    
    `sort`: If `True` return a sorted list of matching fonts, where the sort id in order of
    decreasing closeness of matching.
    `verbose`: If `True` print debugging information to stdout
    '''
    if DISABLED:
        return []
    join()
    if isinstance(name, unicode):
        name = name.encode(preferred_encoding)
    pat = lib.FcNameParse(name)
    if not pat:
        raise ValueError('Could not parse font name')
    if verbose:
        print 'Searching for pattern'
        lib.FcPatternPrint(pat)
    if not lib.FcConfigSubstitute(0, pat, FcMatchPattern):
        raise RuntimeError('Allocation failure')
    lib.FcDefaultSubstitute(pat)
    fs = lib.FcFontSetCreate()
    result = c_int(0)
    matches = []
    if sort:
        font_patterns = lib.FcFontSort(0, pat, FcFalse, 0, byref(result))
        if not font_patterns:
            raise RuntimeError('Allocation failed')
        fps = font_patterns.contents
        for j in range(fps.nfont):
            fpat = fps.fonts[j]
            fp = lib.FcFontRenderPrepare(0, pat, fpat)
            if fp:
                lib.FcFontSetAdd(fs, fp)
        lib.FcFontSetDestroy(font_patterns)
    else:
        match_pat = lib.FcFontMatch(0, pat, byref(result))
        if pat:
            lib.FcFontSetAdd(fs, match_pat)
        if result.value != FcResultMatch.value:
            lib.FcPatternDestroy(pat)
            return matches
    font_set = fs.contents
     
    file    = pointer(create_string_buffer(chr(0), 5000))
    family  = pointer(create_string_buffer(chr(0), 200))
    weight  = c_int(0)
    slant   = c_int(0)
    for j in range(font_set.nfont):
        fpat = font_set.fonts[j]
        #lib.FcPatternPrint(fpat)
        if lib.FcPatternGetString(fpat, 'file', 0, byref(file)) != FcResultMatch.value:
            raise RuntimeError('Error processing pattern')
        if lib.FcPatternGetString(fpat, 'family', 0, byref(family)) != FcResultMatch.value:
            raise RuntimeError('Error processing pattern')
        if lib.FcPatternGetInteger(fpat, 'weight', 0, byref(weight)) != FcResultMatch.value:
            raise RuntimeError('Error processing pattern')
        if lib.FcPatternGetInteger(fpat, 'slant', 0, byref(slant)) != FcResultMatch.value:
            raise RuntimeError('Error processing pattern')
        
        matches.append({
                        'file'    : file.contents.value,
                        'family'  : family.contents.value,
                        'weight'  : weight.value,
                        'slant'   : slant.value,
                        }
                       )
    
    lib.FcPatternDestroy(pat)
    lib.FcFontSetDestroy(fs)
    return matches

def main(args=sys.argv):
    print find_font_families()
    if len(args) > 1:
        print
        print files_for_family(args[1])
        print
        print match(args[1], verbose=True)
    return 0

if __name__ == '__main__':
    sys.exit(main())
