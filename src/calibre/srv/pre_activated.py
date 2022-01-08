#!/usr/bin/env python


__license__ = 'GPL v3'
__copyright__ = '2015, Kovid Goyal <kovid at kovidgoyal.net>'

# Support server pre-activation, such as with systemd's socket activation

import socket, errno
from calibre.constants import islinux


def pre_activated_socket():
    return None


has_preactivated_support = False

if islinux:
    import ctypes

    class SOCKADDR_NL(ctypes.Structure):
        _fields_ = [("nl_family", ctypes.c_ushort),
                    ("nl_pad",    ctypes.c_ushort),
                    ("nl_pid",    ctypes.c_int),
                    ("nl_groups", ctypes.c_int)]

    def getsockfamily(fd):
        addr = SOCKADDR_NL(0, 0, 0, 0)
        sz = ctypes.c_int(ctypes.sizeof(addr))
        if ctypes.CDLL(None, use_errno=True).getsockname(fd, ctypes.pointer(addr), ctypes.pointer(sz)) != 0:
            raise OSError(errno.errcode[ctypes.get_errno()])
        return addr.nl_family

    try:
        systemd = ctypes.CDLL(ctypes.util.find_library('systemd'))
        systemd.sd_listen_fds
    except Exception:
        pass
    else:
        del pre_activated_socket
        has_preactivated_support = True

        def pre_activated_socket():  # noqa
            num = systemd.sd_listen_fds(1)  # Remove systemd env vars so that child processes do not inherit them
            if num > 1:
                raise OSError('Too many file descriptors received from systemd')
            if num != 1:
                return None
            fd = 3  # systemd starts activated sockets at 3
            ret = systemd.sd_is_socket(fd, socket.AF_UNSPEC, socket.SOCK_STREAM, -1)
            if ret == 0:
                raise OSError('The systemd socket file descriptor is not valid')
            if ret < 0:
                raise OSError('Failed to check the systemd socket file descriptor for validity')
            family = getsockfamily(fd)
            return socket.fromfd(fd, family, socket.SOCK_STREAM)

if __name__ == '__main__':
    # Run as:
    # /usr/lib/systemd/systemd-activate -l 8081 calibre-debug pre_activated.py
    # telnet localhost 8081
    s = pre_activated_socket()
    print(s, s.getsockname())
