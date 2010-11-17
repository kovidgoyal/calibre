from __future__ import with_statement
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
"""
This module provides a thin ctypes based wrapper around libunrar.

See  ftp://ftp.rarlabs.com/rar/unrarsrc-3.7.5.tar.gz
"""
import os, ctypes, sys, re
from ctypes import Structure as _Structure, c_char_p, c_uint, c_void_p, POINTER, \
                    byref, c_wchar_p, c_int, c_char, c_wchar
from tempfile import NamedTemporaryFile
from StringIO import StringIO

from calibre import iswindows, load_library, CurrentDir
from calibre.ptempfile import TemporaryDirectory

_librar_name = 'libunrar'
cdll = ctypes.cdll
if iswindows:
    class Structure(_Structure):
        _pack_ = 1
    _librar_name = 'unrar'
    cdll = ctypes.windll
else:
    Structure = _Structure
if hasattr(sys, 'frozen') and iswindows:
    lp = os.path.join(os.path.dirname(sys.executable), 'DLLs', 'unrar.dll')
    _libunrar = cdll.LoadLibrary(lp)
elif hasattr(sys, 'frozen_path'):
    lp = os.path.join(sys.frozen_path, 'libunrar.so')
    _libunrar = cdll.LoadLibrary(lp)
else:
    _libunrar = load_library(_librar_name, cdll)

RAR_OM_LIST    = 0
RAR_OM_EXTRACT = 1

ERAR_END_ARCHIVE      =  10
ERAR_NO_MEMORY        =  11
ERAR_BAD_DATA         =  12
ERAR_BAD_ARCHIVE      =  13
ERAR_UNKNOWN_FORMAT   =  14
ERAR_EOPEN            =  15
ERAR_ECREATE          =  16
ERAR_ECLOSE           =  17
ERAR_EREAD            =  18
ERAR_EWRITE           =  19
ERAR_SMALL_BUF        =  20
ERAR_UNKNOWN          =  21
ERAR_MISSING_PASSWORD =  22

RAR_VOL_ASK           = 0
RAR_VOL_NOTIFY        = 1

RAR_SKIP              = 0
RAR_TEST              = 1
RAR_EXTRACT           = 2

class UnRARException(Exception):
    pass

class RAROpenArchiveDataEx(Structure):
    _fields_ = [
                ('ArcName', c_char_p),
                ('ArcNameW', c_wchar_p),
                ('OpenMode', c_uint),
                ('OpenResult', c_uint),
                ('CmtBuf', c_char_p),
                ('CmtBufSize', c_uint),
                ('CmtSize', c_uint),
                ('CmtState', c_uint),
                ('Flags', c_uint),
                ('Reserved', c_uint * 32)
               ]

class RARHeaderDataEx(Structure):
    _fields_ = [
                ('ArcName', c_char*1024),
                ('ArcNameW', c_wchar*1024),
                ('FileName', c_char*1024),
                ('FileNameW', c_wchar*1024),
                ('Flags', c_uint),
                ('PackSize', c_uint),
                ('PackSizeHigh', c_uint),
                ('UnpSize', c_uint),
                ('UnpSizeHigh', c_uint),
                ('HostOS', c_uint),
                ('FileCRC', c_uint),
                ('FileTime', c_uint),
                ('UnpVer', c_uint),
                ('Method', c_uint),
                ('FileAttr', c_uint),
                ('CmtBuf', c_char_p),
                ('CmtBufSize', c_uint),
                ('CmtSize', c_uint),
                ('CmtState', c_uint),
                ('Reserved', c_uint*1024)
                ]

# Define a callback function
#CALLBACK_FUNC = CFUNCTYPE(c_int, c_uint, c_long, c_char_p, c_long)
#def py_callback_func(msg, user_data, p1, p2):
#    return 0

#callback_func = CALLBACK_FUNC(py_callback_func)

_libunrar.RAROpenArchiveEx.argtypes = [POINTER(RAROpenArchiveDataEx)]
_libunrar.RAROpenArchiveEx.restype  = c_void_p
_libunrar.RARReadHeaderEx.argtypes  = [c_void_p, POINTER(RARHeaderDataEx)]
_libunrar.RARReadHeaderEx.restype   = c_int
_libunrar.RARProcessFileW.argtypes  = [c_void_p, c_int, c_wchar_p, c_wchar_p]
_libunrar.RARProcessFileW.restype   = c_int
_libunrar.RARCloseArchive.argtypes  = [c_void_p]
_libunrar.RARCloseArchive.restype   = c_int
_libunrar.RARSetPassword.argtypes   = [c_void_p, c_char_p]
#_libunrar.RARSetCallback.argtypes   = [c_void_p,  CALLBACK_FUNC, c_long]


def _interpret_open_error(code, path):
    msg = 'Unknown error.'
    if code == ERAR_NO_MEMORY:
        msg = "Not enough memory to process " + path
    elif code == ERAR_BAD_DATA:
        msg = "Archive header broken: " + path
    elif code == ERAR_BAD_ARCHIVE:
        msg = path + ' is not a RAR archive.'
    elif code == ERAR_EOPEN:
        msg = 'Cannot open ' + path
    return msg

def _interpret_process_file_error(code):
    msg = 'Unknown Error'
    if code == ERAR_UNKNOWN_FORMAT:
        msg = 'Unknown archive format'
    elif  code == ERAR_BAD_ARCHIVE:
        msg = 'Bad volume'
    elif  code == ERAR_ECREATE:
        msg = 'File create error'
    elif  code == ERAR_EOPEN:
        msg = 'Volume open error'
    elif  code == ERAR_ECLOSE:
        msg = 'File close error'
    elif  code == ERAR_EREAD:
        msg = 'Read error'
    elif  code == ERAR_EWRITE:
        msg = 'Write error'
    elif  code == ERAR_BAD_DATA:
        msg = 'CRC error'
    elif  code == ERAR_MISSING_PASSWORD:
        msg = 'Password is required.'
    return msg

def get_archive_info(flags):
    ios = StringIO()
    print >>ios, 'Volume:\t\t', 'yes' if (flags & 1) else 'no'
    print >>ios, 'Comment:\t', 'yes' if (flags & 2) else 'no'
    print >>ios, 'Locked:\t\t', 'yes' if (flags & 4) else 'no'
    print >>ios, 'Solid:\t\t', 'yes' if (flags & 8) else 'no'
    print >>ios, 'New naming:\t', 'yes' if (flags & 16) else 'no'
    print >>ios, 'Authenticity:\t', 'yes' if (flags & 32) else 'no'
    print >>ios, 'Recovery:\t', 'yes' if (flags & 64) else 'no'
    print >>ios, 'Encr.headers:\t', 'yes' if (flags & 128) else 'no'
    print >>ios, 'First Volume:\t', 'yes' if (flags & 256) else 'no or older than 3.0'
    return ios.getvalue()

def extract(path, dir):
    """
    Extract archive C{filename} into directory C{dir}
    """
    open_archive_data = RAROpenArchiveDataEx(ArcName=path, OpenMode=RAR_OM_EXTRACT, CmtBuf=None)
    arc_data = _libunrar.RAROpenArchiveEx(byref(open_archive_data))
    cwd = os.getcwd()
    if not os.path.isdir( dir ):
        os.mkdir( dir )
    os.chdir( dir )
    try:
        if open_archive_data.OpenResult != 0:
            raise UnRARException(_interpret_open_error(open_archive_data.OpenResult, path))
        #prints('Archive:', path)
        #print get_archive_info(open_archive_data.Flags)
        header_data = RARHeaderDataEx(CmtBuf=None)
        #_libunrar.RARSetCallback(arc_data, callback_func, mode)
        while True:
            RHCode = _libunrar.RARReadHeaderEx(arc_data, byref(header_data))
            if RHCode != 0:
                break
            PFCode = _libunrar.RARProcessFileW(arc_data, RAR_EXTRACT, None, None)
            if PFCode != 0:
                raise UnRARException(_interpret_process_file_error(PFCode))
        if RHCode == ERAR_BAD_DATA:
            raise UnRARException('File header broken')
    finally:
        os.chdir(cwd)
        _libunrar.RARCloseArchive(arc_data)

def names(path):
    if hasattr(path, 'read'):
        data = path.read()
        f = NamedTemporaryFile(suffix='.rar')
        f.write(data)
        f.flush()
        path = f.name
    open_archive_data = RAROpenArchiveDataEx(ArcName=path, OpenMode=RAR_OM_LIST, CmtBuf=None)
    arc_data = _libunrar.RAROpenArchiveEx(byref(open_archive_data))
    try:
        if open_archive_data.OpenResult != 0:
            raise UnRARException(_interpret_open_error(open_archive_data.OpenResult, path))
        header_data = RARHeaderDataEx(CmtBuf=None)
        while True:
            if _libunrar.RARReadHeaderEx(arc_data, byref(header_data)) != 0:
                break
            PFCode = _libunrar.RARProcessFileW(arc_data, RAR_SKIP, None, None)
            if PFCode != 0:
                raise UnRARException(_interpret_process_file_error(PFCode))
            yield header_data.FileNameW
    finally:
        _libunrar.RARCloseArchive(arc_data)

def _extract_member(path, match, name):

    def is_match(fname):
        return (name is not None and fname == name) or \
               (match is not None and match.search(fname) is not None)

    open_archive_data = RAROpenArchiveDataEx(ArcName=path, OpenMode=RAR_OM_EXTRACT, CmtBuf=None)
    arc_data = _libunrar.RAROpenArchiveEx(byref(open_archive_data))
    try:
        if open_archive_data.OpenResult != 0:
            raise UnRARException(_interpret_open_error(open_archive_data.OpenResult, path))
        header_data = RARHeaderDataEx(CmtBuf=None)
        first = True
        while True:
            if _libunrar.RARReadHeaderEx(arc_data, byref(header_data)) != 0:
                raise UnRARException('%s has no files'%path if first
                        else 'No match found in %s'%path)
            file_name = header_data.FileNameW
            if is_match(file_name):
                PFCode = _libunrar.RARProcessFileW(arc_data, RAR_EXTRACT, None, None)
                if PFCode != 0:
                    raise UnRARException(_interpret_process_file_error(PFCode))
                abspath = os.path.abspath(os.path.join(*file_name.split('/')))
                return abspath
            else:
                PFCode = _libunrar.RARProcessFileW(arc_data, RAR_SKIP, None, None)
                if PFCode != 0:
                    raise UnRARException(_interpret_process_file_error(PFCode))
            first = False

    finally:
        _libunrar.RARCloseArchive(arc_data)

def extract_member(path, match=re.compile(r'\.(jpg|jpeg|gif|png)\s*$', re.I),
        name=None, as_file=False):
    if hasattr(path, 'read'):
        data = path.read()
        f = NamedTemporaryFile(suffix='.rar')
        f.write(data)
        f.flush()
        path = f.name

    path = os.path.abspath(path)
    if as_file:
        path = _extract_member(path, match, name)
        return path, open(path, 'rb')
    else:
        with TemporaryDirectory('_libunrar') as tdir:
            with CurrentDir(tdir):
                path = _extract_member(path, match, name)
                return path, open(path, 'rb').read()

def extract_first_alphabetically(path):
    if hasattr(path, 'read'):
        data = path.read()
        f = NamedTemporaryFile(suffix='.rar')
        f.write(data)
        f.flush()
        path = f.name

    names_ = [x for x in names(path) if os.path.splitext(x)[1][1:].lower() in
            ('png', 'jpg', 'jpeg', 'gif')]
    names_.sort()
    return extract_member(path, name=names_[0], match=None)

