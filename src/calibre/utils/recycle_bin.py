#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os, shutil, time

from calibre import isbytestring, force_unicode
from calibre.constants import (iswindows, isosx, plugins, filesystem_encoding,
        islinux)

recycle = None

if iswindows:
    import ctypes, subprocess, sys
    from ctypes import POINTER, Structure
    from ctypes.wintypes import HANDLE, LPVOID, WORD, DWORD, BOOL, ULONG, LPCWSTR
    RECYCLE = force_unicode(os.path.join(os.path.dirname(sys.executable), 'calibre-recycle.exe'), filesystem_encoding)
    LPDWORD = POINTER(DWORD)
    LPHANDLE = POINTER(HANDLE)
    ULONG_PTR = POINTER(ULONG)
    CREATE_NO_WINDOW = 0x08000000
    INFINITE = 0xFFFFFFFF
    WAIT_FAILED = 0xFFFFFFFF

    class SECURITY_ATTRIBUTES(Structure):
        _fields_ = [("nLength", DWORD),
                    ("lpSecurityDescriptor", LPVOID),
                    ("bInheritHandle", BOOL)]
    LPSECURITY_ATTRIBUTES = POINTER(SECURITY_ATTRIBUTES)

    class STARTUPINFO(Structure):
        _fields_ = [("cb", DWORD),
                    ("lpReserved", LPCWSTR),
                    ("lpDesktop", LPCWSTR),
                    ("lpTitle", LPCWSTR),
                    ("dwX", DWORD),
                    ("dwY", DWORD),
                    ("dwXSize", DWORD),
                    ("dwYSize", DWORD),
                    ("dwXCountChars", DWORD),
                    ("dwYCountChars", DWORD),
                    ("dwFillAttribute", DWORD),
                    ("dwFlags", DWORD),
                    ("wShowWindow", WORD),
                    ("cbReserved2", WORD),
                    ("lpReserved2", LPVOID),
                    ("hStdInput", HANDLE),
                    ("hStdOutput", HANDLE),
                    ("hStdError", HANDLE)]
    LPSTARTUPINFO = POINTER(STARTUPINFO)

    class PROCESS_INFORMATION(Structure):
        _fields_ = [("hProcess", HANDLE),
                    ("hThread", HANDLE),
                    ("dwProcessId", DWORD),
                    ("dwThreadId", DWORD)]
    LPPROCESS_INFORMATION = POINTER(PROCESS_INFORMATION)

    CreateProcess = ctypes.windll.kernel32.CreateProcessW
    CreateProcess.argtypes = [LPCWSTR, LPCWSTR, LPSECURITY_ATTRIBUTES,
        LPSECURITY_ATTRIBUTES, BOOL, DWORD, LPVOID, LPCWSTR, LPSTARTUPINFO,
        LPPROCESS_INFORMATION]
    CreateProcess.restype = BOOL

    WaitForSingleObject = ctypes.windll.kernel32.WaitForSingleObject
    WaitForSingleObject.argtypes = [HANDLE, DWORD]
    WaitForSingleObject.restype = DWORD

    GetExitCodeProcess = ctypes.windll.kernel32.GetExitCodeProcess
    GetExitCodeProcess.argtypes = [HANDLE, LPDWORD]
    GetExitCodeProcess.restype = BOOL

    CloseHandle = ctypes.windll.kernel32.CloseHandle
    CloseHandle.argtypes = [HANDLE]
    CloseHandle.restype = BOOL

    def recycle(path):
        # We have to run the delete to recycle bin in a separate process as the
        # morons who wrote SHFileOperation designed it to spin the event loop
        # even when no UI is created. And there is no other way to send files
        # to the recycle bin on windows. Le Sigh. We dont use subprocess since
        # there is no way to pass unicode arguments with subprocess in 2.7 and
        # the twit that maintains subprocess believes that this is not an
        # bug but a request for a new feature.
        if isinstance(path, bytes):
            path = path.decode(filesystem_encoding)
        si = STARTUPINFO()
        si.cb = ctypes.sizeof(si)
        pi = PROCESS_INFORMATION()
        exit_code = DWORD()
        cmd = subprocess.list2cmdline([RECYCLE, path])
        dwCreationFlags = CREATE_NO_WINDOW
        if not CreateProcess(None, cmd, None, None, False, dwCreationFlags,
                None, None, ctypes.byref(si), ctypes.byref(pi)):
            raise ctypes.WinError()
        try:
            if WaitForSingleObject(pi.hProcess, INFINITE) == WAIT_FAILED:
                raise ctypes.WinError()
            if not GetExitCodeProcess(pi.hProcess, ctypes.byref(exit_code)):
                raise ctypes.WinError()

        finally:
            CloseHandle(pi.hThread)
            CloseHandle(pi.hProcess)
        exit_code = exit_code.value
        if exit_code != 0:
            raise ctypes.WinError(exit_code)

elif isosx:
    u = plugins['usbobserver'][0]
    if hasattr(u, 'send2trash'):
        def osx_recycle(path):
            if isbytestring(path):
                path = path.decode(filesystem_encoding)
            u.send2trash(path)
        recycle = osx_recycle
elif islinux:
    from calibre.utils.linux_trash import send2trash
    def fdo_recycle(path):
        if isbytestring(path):
            path = path.decode(filesystem_encoding)
        path = os.path.abspath(path)
        send2trash(path)
    recycle = fdo_recycle

can_recycle = callable(recycle)

def nuke_recycle():
    global can_recycle
    can_recycle = False

def restore_recyle():
    global can_recycle
    can_recycle = callable(recycle)

def delete_file(path, permanent=False):
    if not permanent and can_recycle:
        try:
            recycle(path)
            return
        except:
            import traceback
            traceback.print_exc()
    os.remove(path)

def delete_tree(path, permanent=False):
    if permanent:
        try:
            # For completely mysterious reasons, sometimes a file is left open
            # leading to access errors. If we get an exception, wait and hope
            # that whatever has the file (Antivirus, DropBox?) lets go of it.
            shutil.rmtree(path)
        except:
            import traceback
            traceback.print_exc()
            time.sleep(1)
            shutil.rmtree(path)
    else:
        if can_recycle:
            try:
                recycle(path)
                return
            except:
                import traceback
                traceback.print_exc()
        delete_tree(path, permanent=True)

