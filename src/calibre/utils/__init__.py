#!/usr/bin/env  python2
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

'''
Miscelleaneous utilities.
'''

from time import time


def join_with_timeout(q, timeout=2):
    ''' Join the queue q with a specified timeout. Blocks until all tasks on
    the queue are done or times out with a runtime error. '''
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
    from pickle import PROTO, SHORT_BINSTRING, BINSTRING
    if data.startswith(PROTO + b'\x02'):
        offset = 2
        which = data[offset]
        offset += 1
        if which == BINSTRING:
            sz, = struct.unpack_from(b'<i', data, offset)
            offset += struct.calcsize(b'<i')
        elif which == SHORT_BINSTRING:
            sz = ord(data[offset])
            offset += 1
        else:
            return
        return data[offset:offset + sz]


def pickle_binary_string(data):
    # Maintains compatibility with python's pickle module protocol version 2
    import struct
    from pickle import PROTO, BINSTRING, STOP
    data = bytes(data)
    return PROTO + b'\x02' + BINSTRING + struct.pack(b'<i', len(data)) + data + STOP
