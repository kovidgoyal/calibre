'''
Created on 29 Nov 2013

@author: charles

Code taken from https://mail.python.org/pipermail/python-dev/2007-June/073745.html
modified to make it work
'''

import os, traceback

def get_socket_inherit(socket):
    '''
    Returns True if the socket has been set to allow inheritance across
    forks and execs to child processes, otherwise False
    '''
    try:
        if os.name == "nt":
            import win32api, win32con
            flags = win32api.GetHandleInformation(socket.fileno())
            return bool(flags & win32con.HANDLE_FLAG_INHERIT)
        else:
            import fcntl
            flags = fcntl.fcntl(socket.fileno(), fcntl.F_GETFD)
            return not bool(flags & fcntl.FD_CLOEXEC)
    except:
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
        if os.name == "nt":
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
        traceback.print_exc()