# vim:fileencoding=utf-8

from __future__ import division, absolute_import

try:
    try:
        # >=python-3.3, Unix
        from time import clock_gettime
        try:
            # >={kernel}-sources-2.6.28
            from time import CLOCK_MONOTONIC_RAW as CLOCK_ID
        except ImportError:
            from time import CLOCK_MONOTONIC as CLOCK_ID  # NOQA

        monotonic = lambda: clock_gettime(CLOCK_ID)

    except ImportError:
        # >=python-3.3
        from time import monotonic  # NOQA

except ImportError:
    import ctypes
    import sys

    try:
        if sys.platform == 'win32':
            # Windows only
            GetTickCount64 = ctypes.windll.kernel32.GetTickCount64
            GetTickCount64.restype = ctypes.c_ulonglong

            def monotonic():  # NOQA
                return GetTickCount64() / 1000

        elif sys.platform == 'darwin':
            # Mac OS X
            from ctypes.util import find_library

            libc_name = find_library('c')
            if not libc_name:
                raise OSError

            libc = ctypes.CDLL(libc_name, use_errno=True)

            mach_absolute_time = libc.mach_absolute_time
            mach_absolute_time.argtypes = ()
            mach_absolute_time.restype = ctypes.c_uint64

            class mach_timebase_info_data_t(ctypes.Structure):
                _fields_ = (
                    ('numer', ctypes.c_uint32),
                    ('denom', ctypes.c_uint32),
                )
            mach_timebase_info_data_p = ctypes.POINTER(mach_timebase_info_data_t)

            _mach_timebase_info = libc.mach_timebase_info
            _mach_timebase_info.argtypes = (mach_timebase_info_data_p,)
            _mach_timebase_info.restype = ctypes.c_int

            def mach_timebase_info():
                timebase = mach_timebase_info_data_t()
                _mach_timebase_info(ctypes.byref(timebase))
                return (timebase.numer, timebase.denom)

            timebase = mach_timebase_info()
            factor = timebase[0] / timebase[1] * 1e-9

            def monotonic():  # NOQA
                return mach_absolute_time() * factor
        else:
            # linux only (no librt on OS X)
            import os

            # See <bits/time.h>
            CLOCK_MONOTONIC = 1
            CLOCK_MONOTONIC_RAW = 4

            class timespec(ctypes.Structure):
                _fields_ = (
                    ('tv_sec', ctypes.c_long),
                    ('tv_nsec', ctypes.c_long)
                )
            tspec = timespec()

            librt = ctypes.CDLL('librt.so.1', use_errno=True)
            clock_gettime = librt.clock_gettime
            clock_gettime.argtypes = [ctypes.c_int, ctypes.POINTER(timespec)]

            if clock_gettime(CLOCK_MONOTONIC_RAW, ctypes.pointer(tspec)) == 0:
                # >={kernel}-sources-2.6.28
                clock_id = CLOCK_MONOTONIC_RAW
            elif clock_gettime(CLOCK_MONOTONIC, ctypes.pointer(tspec)) == 0:
                clock_id = CLOCK_MONOTONIC
            else:
                raise OSError

            def monotonic():  # NOQA
                if clock_gettime(CLOCK_MONOTONIC, ctypes.pointer(tspec)) != 0:
                    errno_ = ctypes.get_errno()
                    raise OSError(errno_, os.strerror(errno_))
                return tspec.tv_sec + tspec.tv_nsec / 1e9

    except:
        from time import time as monotonic  # NOQA
        monotonic
