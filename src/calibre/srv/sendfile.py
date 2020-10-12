#!/usr/bin/env python
# vim:fileencoding=utf-8


__license__ = 'GPL v3'
__copyright__ = '2015, Kovid Goyal <kovid at kovidgoyal.net>'

import os, ctypes, errno, socket
from io import DEFAULT_BUFFER_SIZE
from select import select

from calibre.constants import islinux, ismacos
from calibre.srv.utils import eintr_retry_call


def file_metadata(fileobj):
    try:
        fd = fileobj.fileno()
        return os.fstat(fd)
    except Exception:
        pass


def copy_range(src_file, start, size, dest):
    total_sent = 0
    src_file.seek(start)
    while size > 0:
        data = eintr_retry_call(src_file.read, min(size, DEFAULT_BUFFER_SIZE))
        if len(data) == 0:
            break  # EOF
        dest.write(data)
        size -= len(data)
        total_sent += len(data)
        del data
    return total_sent


class CannotSendfile(Exception):
    pass


class SendfileInterrupted(Exception):
    pass


sendfile_to_socket = sendfile_to_socket_async = None

if ismacos:
    libc = ctypes.CDLL(None, use_errno=True)
    sendfile = ctypes.CFUNCTYPE(
        ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int64, ctypes.POINTER(ctypes.c_int64), ctypes.c_void_p, ctypes.c_int, use_errno=True)(
            ('sendfile', libc))
    del libc

    def sendfile_to_socket(fileobj, offset, size, socket_file):
        timeout = socket_file.gettimeout()
        if timeout == 0:
            return copy_range(fileobj, offset, size, socket_file)
        num_bytes = ctypes.c_int64(size)
        total_sent = 0
        while size > 0:
            num_bytes.value = size
            r, w, x = select([], [socket_file], [], timeout)
            if not w:
                raise socket.timeout('timed out in sendfile() waiting for socket to become writeable')
            ret = sendfile(fileobj.fileno(), socket_file.fileno(), offset, ctypes.byref(num_bytes), None, 0)
            if ret != 0:
                err = ctypes.get_errno()
                if err in (errno.EBADF, errno.ENOTSUP, errno.ENOTSOCK, errno.EOPNOTSUPP):
                    return copy_range(fileobj, offset, size, socket_file)
                if err not in (errno.EINTR, errno.EAGAIN):
                    raise IOError((err, os.strerror(err)))
            if num_bytes.value == 0:
                break  # EOF
            total_sent += num_bytes.value
            size -= num_bytes.value
            offset += num_bytes.value
        return total_sent

    def sendfile_to_socket_async(fileobj, offset, size, socket_file):
        num_bytes = ctypes.c_int64(size)
        ret = sendfile(fileobj.fileno(), socket_file.fileno(), offset, ctypes.byref(num_bytes), None, 0)
        if ret != 0:
            err = ctypes.get_errno()
            if err in (errno.EBADF, errno.ENOTSUP, errno.ENOTSOCK, errno.EOPNOTSUPP):
                raise CannotSendfile()
            if err == errno.EINTR:
                raise SendfileInterrupted()
            if err != errno.EAGAIN:
                raise IOError((err, os.strerror(err)))
        return num_bytes.value

elif islinux:
    libc = ctypes.CDLL(None, use_errno=True)
    sendfile = ctypes.CFUNCTYPE(
        ctypes.c_ssize_t, ctypes.c_int, ctypes.c_int, ctypes.POINTER(ctypes.c_int64), ctypes.c_size_t, use_errno=True)(('sendfile64', libc))
    del libc

    def sendfile_to_socket(fileobj, offset, size, socket_file):
        off = ctypes.c_int64(offset)
        timeout = socket_file.gettimeout()
        if timeout == 0:
            return copy_range(fileobj, off.value, size, socket_file)
        total_sent = 0
        while size > 0:
            r, w, x = select([], [socket_file], [], timeout)
            if not w:
                raise socket.timeout('timed out in sendfile() waiting for socket to become writeable')
            sent = sendfile(socket_file.fileno(), fileobj.fileno(), ctypes.byref(off), size)
            if sent < 0:
                err = ctypes.get_errno()
                if err in (errno.ENOSYS, errno.EINVAL):
                    return copy_range(fileobj, off.value, size, socket_file)
                if err not in (errno.EINTR, errno.EAGAIN):
                    raise IOError((err, os.strerror(err)))
            elif sent == 0:
                break  # EOF
            else:
                size -= sent
                total_sent += sent
        return total_sent

    def sendfile_to_socket_async(fileobj, offset, size, socket_file):
        off = ctypes.c_int64(offset)
        sent = sendfile(socket_file.fileno(), fileobj.fileno(), ctypes.byref(off), size)
        if sent < 0:
            err = ctypes.get_errno()
            if err in (errno.ENOSYS, errno.EINVAL):
                raise CannotSendfile()
            if err in (errno.EINTR, errno.EAGAIN):
                raise SendfileInterrupted()
            raise IOError((err, os.strerror(err)))
        return sent
