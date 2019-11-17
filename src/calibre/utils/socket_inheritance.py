#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai
from __future__ import absolute_import, division, print_function, unicode_literals

'''
Created on 29 Nov 2013

@author: charles

Code taken from https://mail.python.org/pipermail/python-dev/2007-June/073745.html
modified to make it work
'''

from calibre.constants import iswindows


def get_socket_inherit(socket):
    '''
    Returns True if the socket has been set to allow inheritance across
    forks and execs to child processes, otherwise False
    '''
    try:
        if iswindows:
            import win32api, win32con
            flags = win32api.GetHandleInformation(socket.fileno())
            return bool(flags & win32con.HANDLE_FLAG_INHERIT)
        else:
            import fcntl
            flags = fcntl.fcntl(socket.fileno(), fcntl.F_GETFD)
            return not bool(flags & fcntl.FD_CLOEXEC)
    except:
        import traceback
        traceback.print_exc()


def set_socket_inherit(sock, inherit):
    '''
    Mark a socket as inheritable or non-inheritable to child processes.

    This should be called right after socket creation if you want
    to prevent the socket from being inherited by child processes.

    Note that for sockets, a new socket returned from accept() will be
    inheritable even if the listener socket was not; so you should call
    set_socket_inherit for the new socket as well.
    '''
    try:
        if iswindows:
            import win32api, win32con

            if inherit:
                flags = win32con.HANDLE_FLAG_INHERIT
            else:
                flags = 0
            win32api.SetHandleInformation(sock.fileno(),
                                  win32con.HANDLE_FLAG_INHERIT, flags)
        else:
            import fcntl

            fd = sock.fileno()
            flags = fcntl.fcntl(fd, fcntl.F_GETFD) & ~fcntl.FD_CLOEXEC
            if not inherit:
                flags = flags | fcntl.FD_CLOEXEC
            fcntl.fcntl(fd, fcntl.F_SETFD, flags)
    except:
        import traceback
        traceback.print_exc()


def test():
    import socket
    s = socket.socket()
    orig = get_socket_inherit(s)
    set_socket_inherit(s, orig ^ True)
    if orig == get_socket_inherit(s):
        raise RuntimeError('Failed to change socket inheritance status')
    print('OK!')


if __name__ == '__main__':
    test()
