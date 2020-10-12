#!/usr/bin/env python
# vim:fileencoding=utf-8


__license__ = 'GPL v3'
__copyright__ = '2015, Kovid Goyal <kovid at kovidgoyal.net>'

import os, sys

from polyglot.builtins import reraise

from calibre.constants import iswindows

'''
This module defines a share_open() function which is a replacement for
python's builtin open() function.

This replacement, opens 'shareable' files on all platforms. That is files that
can be read from and written to and deleted at the same time by multiple
processes. All file handles are non-inheritable, as in Python 3, but unlike,
Python 2. Non-inheritance is atomic.

Caveats on windows: On windows sharing is co-operative, i.e. it only works if
all processes involved open the file with share_open(). Also while you can
delete a file that is open, you cannot open a new file with the same filename
until all open file handles are closed. You also cannot delete the containing
directory until all file handles are closed. To get around this, rename the
file before deleting it.
'''

if iswindows:
    from numbers import Integral
    import msvcrt
    import win32file, pywintypes
    CREATE_NEW                  = win32file.CREATE_NEW
    CREATE_ALWAYS               = win32file.CREATE_ALWAYS
    OPEN_EXISTING               = win32file.OPEN_EXISTING
    OPEN_ALWAYS                 = win32file.OPEN_ALWAYS
    TRUNCATE_EXISTING           = win32file.TRUNCATE_EXISTING
    FILE_SHARE_READ             = win32file.FILE_SHARE_READ
    FILE_SHARE_WRITE            = win32file.FILE_SHARE_WRITE
    FILE_SHARE_DELETE           = win32file.FILE_SHARE_DELETE
    FILE_SHARE_VALID_FLAGS      = FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE
    FILE_ATTRIBUTE_READONLY     = win32file.FILE_ATTRIBUTE_READONLY
    FILE_ATTRIBUTE_NORMAL       = win32file.FILE_ATTRIBUTE_NORMAL
    FILE_ATTRIBUTE_TEMPORARY    = win32file.FILE_ATTRIBUTE_TEMPORARY
    FILE_FLAG_DELETE_ON_CLOSE   = win32file.FILE_FLAG_DELETE_ON_CLOSE
    FILE_FLAG_SEQUENTIAL_SCAN   = win32file.FILE_FLAG_SEQUENTIAL_SCAN
    FILE_FLAG_RANDOM_ACCESS     = win32file.FILE_FLAG_RANDOM_ACCESS
    GENERIC_READ                = win32file.GENERIC_READ & 0xffffffff
    GENERIC_WRITE               = win32file.GENERIC_WRITE & 0xffffffff
    DELETE                      = 0x00010000

    _ACCESS_MASK = os.O_RDONLY | os.O_WRONLY | os.O_RDWR
    _ACCESS_MAP  = {
        os.O_RDONLY : GENERIC_READ,
        os.O_WRONLY : GENERIC_WRITE,
        os.O_RDWR   : GENERIC_READ | GENERIC_WRITE
    }

    _CREATE_MASK = os.O_CREAT | os.O_EXCL | os.O_TRUNC
    _CREATE_MAP  = {
        0                                   : OPEN_EXISTING,
        os.O_EXCL                           : OPEN_EXISTING,
        os.O_CREAT                          : OPEN_ALWAYS,
        os.O_CREAT | os.O_EXCL              : CREATE_NEW,
        os.O_CREAT | os.O_TRUNC | os.O_EXCL : CREATE_NEW,
        os.O_TRUNC                          : TRUNCATE_EXISTING,
        os.O_TRUNC | os.O_EXCL              : TRUNCATE_EXISTING,
        os.O_CREAT | os.O_TRUNC             : CREATE_ALWAYS
    }

    def raise_winerror(pywinerr, path=None):
        exc = OSError(
            pywinerr.winerror,
            (pywinerr.funcname or '') + ': ' + (pywinerr.strerror or ''),
            path,
            pywinerr.winerror
        )
        reraise(type(exc), exc, sys.exc_info()[2])

    def os_open(path, flags, mode=0o777, share_flags=FILE_SHARE_VALID_FLAGS):
        '''
        Replacement for os.open() allowing moving or unlinking before closing
        '''
        if not isinstance(flags, Integral):
            raise TypeError('flags must be an integer')
        if not isinstance(mode, Integral):
            raise TypeError('mode must be an integer')

        if share_flags & ~FILE_SHARE_VALID_FLAGS:
            raise ValueError('bad share_flags: %r' % share_flags)

        access_flags = _ACCESS_MAP[flags & _ACCESS_MASK]
        create_flags = _CREATE_MAP[flags & _CREATE_MASK]
        attrib_flags = FILE_ATTRIBUTE_NORMAL

        if flags & os.O_CREAT and mode & ~0o444 == 0:
            attrib_flags = FILE_ATTRIBUTE_READONLY

        if flags & os.O_TEMPORARY:
            share_flags |= FILE_SHARE_DELETE
            attrib_flags |= FILE_FLAG_DELETE_ON_CLOSE
            access_flags |= DELETE

        if flags & os.O_SHORT_LIVED:
            attrib_flags |= FILE_ATTRIBUTE_TEMPORARY

        if flags & os.O_SEQUENTIAL:
            attrib_flags |= FILE_FLAG_SEQUENTIAL_SCAN

        if flags & os.O_RANDOM:
            attrib_flags |= FILE_FLAG_RANDOM_ACCESS

        try:
            h = win32file.CreateFileW(
                path, access_flags, share_flags, None, create_flags, attrib_flags, None)
        except pywintypes.error as e:
            raise_winerror(e, path)
        ans = msvcrt.open_osfhandle(h.Detach(), flags | os.O_NOINHERIT)
        return ans

    def share_open(*a, **kw):
        kw['opener'] = os_open
        return open(*a, **kw)

else:
    share_open = open

    def raise_winerror(x):
        reraise(NotImplementedError, None, sys.exc_info()[2])


def find_tests():
    import unittest
    from calibre.ptempfile import TemporaryDirectory

    class SharedFileTest(unittest.TestCase):

        def test_shared_file(self):
            eq = self.assertEqual

            with TemporaryDirectory() as tdir:
                fname = os.path.join(tdir, 'test.txt')
                with share_open(fname, 'wb') as f:
                    f.write(b'a' * 20 * 1024)
                    eq(fname, f.name)
                f = share_open(fname, 'rb')
                eq(f.read(1), b'a')
                if iswindows:
                    os.rename(fname, fname+'.moved')
                    os.remove(fname+'.moved')
                else:
                    os.remove(fname)
                eq(f.read(1), b'a')
                f2 = share_open(fname, 'w+b')
                f2.write(b'b' * 10 * 1024)
                f2.seek(0)
                eq(f.read(10000), b'a'*10000)
                eq(f2.read(100), b'b' * 100)
                f3 = share_open(fname, 'rb')
                eq(f3.read(100), b'b' * 100)

    return unittest.defaultTestLoader.loadTestsFromTestCase(SharedFileTest)


def run_tests():
    from calibre.utils.run_tests import run_tests
    run_tests(find_tests)
