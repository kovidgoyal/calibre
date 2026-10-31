#!/usr/bin/env python

"""
Created on 29 Nov 2013

@author: charles

Code taken from https://mail.python.org/pipermail/python-dev/2007-June/073745.html
modified to make it work
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import socket


def get_socket_inherit(s: socket.socket) -> bool | None:
    """
    Returns True if the socket has been set to allow inheritance across
    forks and execs to child processes, otherwise False
    """
    try:
        return s.get_inheritable()
    except Exception:
        import traceback

        traceback.print_exc()


def set_socket_inherit(s: socket.socket, inherit: bool = False) -> None:
    """
    Mark a socket as inheritable or non-inheritable to child processes.

    This should be called right after socket creation if you want
    to prevent the socket from being inherited by child processes.

    Note that for sockets, a new socket returned from accept() will be
    inheritable even if the listener socket was not; so you should call
    set_socket_inherit for the new socket as well.
    """
    try:
        s.set_inheritable(inherit)
    except Exception:
        import traceback

        traceback.print_exc()


def test() -> None:
    import socket

    s = socket.socket()
    orig = get_socket_inherit(s)
    set_socket_inherit(s, not orig)
    if orig == get_socket_inherit(s):
        raise RuntimeError('Failed to change socket inheritance status')
    print('OK!')


if __name__ == '__main__':
    test()
