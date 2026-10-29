#!/usr/bin/env python
# License: GPLv3 Copyright: 2008, Kovid Goyal kovid@kovidgoyal.net

"""
Miscelleaneous utilities.
"""

import os
from time import time
from typing import IO

from polyglot.builtins import as_bytes


def join_with_timeout(q, timeout=2):
    """Join the queue q with a specified timeout. Blocks until all tasks on
    the queue are done or times out with a runtime error."""
    q.all_tasks_done.acquire()
    try:
        endtime = time() + timeout
        while q.unfinished_tasks:
            remaining = endtime - time()
            if remaining <= 0.0:
                raise RuntimeError('Waiting for queue to clear timed out')
            q.all_tasks_done.wait(remaining)
    finally:
        q.all_tasks_done.release()


def unpickle_binary_string(data):
    # Maintains compatibility with python's pickle module protocol version 2
    import struct

    PROTO, SHORT_BINSTRING, BINSTRING = b'\x80', b'U', b'T'
    if data.startswith(PROTO + b'\x02'):
        offset = 2
        which = data[offset : offset + 1]
        offset += 1
        if which == BINSTRING:
            (sz,) = struct.unpack_from('<i', data, offset)
            offset += struct.calcsize('<i')
        elif which == SHORT_BINSTRING:
            sz = ord(data[offset : offset + 1])
            offset += 1
        else:
            return
        return data[offset : offset + sz]


def pickle_binary_string(data):
    # Maintains compatibility with python's pickle module protocol version 2
    import struct

    PROTO, STOP, BINSTRING = b'\x80', b'.', b'T'
    data = as_bytes(data)
    return PROTO + b'\x02' + BINSTRING + struct.pack(b'<i', len(data)) + data + STOP


def kill_parent_if_needed(parent_process_handle: int, timeout: float = 1.0, exit_code: int = 0) -> None:
    import ctypes

    WAIT_TIMEOUT = 0x00000102

    kernel32 = ctypes.windll.kernel32
    try:
        if kernel32.WaitForSingleObject(parent_process_handle, int(timeout * 1000)) == WAIT_TIMEOUT:
            kernel32.TerminateProcess(parent_process_handle, exit_code)
    finally:
        kernel32.CloseHandle(parent_process_handle)


class StreamOrPath:
    """
    Open a stream if a path is given, or wrap the stream object.

    When used in a with statement, returns the underlying stream and closes it
    on exit only if it was opened from a path, a source stream is left open
    and unchanged.
    """

    def __init__(self, stream_or_path: str | bytes | IO, mode: str, makedirs: bool = False, **kwargs):
        if hasattr(stream_or_path, 'read') or hasattr(stream_or_path, 'write'):
            self.stream: IO = stream_or_path  # ty: ignore[invalid-assignment]
            self.needs_close = False
        else:
            if makedirs and any(m in mode for m in 'wxa'):
                dirname = os.path.dirname(stream_or_path)
                if dirname and not os.path.exists(dirname):
                    os.makedirs(dirname)
            self.stream = open(stream_or_path, mode, **kwargs)  # ruff: ignore[open-file-with-context-handler]
            self.needs_close = True

    def __enter__(self) -> IO:
        return self.stream

    def __exit__(self, *args) -> None:
        if self.needs_close:
            self.stream.close()
