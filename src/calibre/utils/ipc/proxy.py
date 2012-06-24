#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os, cPickle, struct
from threading import Thread
from Queue import Queue, Empty
from multiprocessing.connection import arbitrary_address, Listener
from functools import partial

from calibre import as_unicode, prints
from calibre.constants import iswindows, DEBUG
from calibre.utils.ipc import eintr_retry_call

def _encode(msg):
    raw = cPickle.dumps(msg, -1)
    size = len(raw)
    header = struct.pack('!Q', size)
    return header + raw

def _decode(raw):
    sz = struct.calcsize('!Q')
    if len(raw) < sz:
        return 'invalid', None
    header, = struct.unpack('!Q', raw[:sz])
    if len(raw) != sz + header or header == 0:
        return 'invalid', None
    return cPickle.loads(raw[sz:])


class Writer(Thread):

    TIMEOUT = 60 #seconds

    def __init__(self, conn):
        Thread.__init__(self)
        self.daemon = True
        self.dataq, self.resultq = Queue(), Queue()
        self.conn = conn
        self.start()
        self.data_written = False

    def close(self):
        self.dataq.put(None)

    def flush(self):
        pass

    def write(self, raw_data):
        self.dataq.put(raw_data)

        try:
            ex = self.resultq.get(True, self.TIMEOUT)
        except Empty:
            raise IOError('Writing to socket timed out')
        else:
            if ex is not None:
                raise IOError('Writing to socket failed with error: %s' % ex)

    def run(self):
        while True:
            x = self.dataq.get()
            if x is None:
                break
            try:
                self.data_written = True
                eintr_retry_call(self.conn.send_bytes, x)
            except Exception as e:
                self.resultq.put(as_unicode(e))
            else:
                self.resultq.put(None)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

class Server(Thread):

    def __init__(self, dispatcher):
        Thread.__init__(self)
        self.daemon = True

        self.auth_key = os.urandom(32)
        self.address = arbitrary_address('AF_PIPE' if iswindows else 'AF_UNIX')
        if iswindows and self.address[1] == ':':
            self.address = self.address[2:]
        self.listener = Listener(address=self.address,
                authkey=self.auth_key, backlog=4)

        self.keep_going = True
        self.dispatcher = dispatcher

    @property
    def connection_information(self):
        if not self.is_alive():
            self.start()
        return (self.address, self.auth_key)

    def stop(self):
        self.keep_going = False
        try:
            self.listener.close()
        except:
            pass

    def run(self):
        while self.keep_going:
            try:
                conn = eintr_retry_call(self.listener.accept)
                self.handle_client(conn)
            except:
                pass

    def handle_client(self, conn):
        t = Thread(target=partial(self._handle_client, conn))
        t.daemon = True
        t.start()

    def _handle_client(self, conn):
        while True:
            try:
                func_name, args, kwargs = eintr_retry_call(conn.recv)
            except EOFError:
                try:
                    conn.close()
                except:
                    pass
                return
            else:
                try:
                    self.call_func(func_name, args, kwargs, conn)
                except:
                    try:
                        conn.close()
                    except:
                        pass
                    prints('Proxy function: %s with args: %r and'
                            ' kwargs: %r failed')
                    if DEBUG:
                        import traceback
                        traceback.print_exc()
                    break

    def call_func(self, func_name, args, kwargs, conn):
        with Writer(conn) as f:
            try:
                self.dispatcher(f, func_name, args, kwargs)
            except Exception as e:
                if not f.data_written:
                    import traceback
                    # Try to tell the client process what error happened
                    try:
                        eintr_retry_call(conn.send_bytes, (_encode(('failed', (unicode(e),
                            as_unicode(traceback.format_exc()))))))
                    except:
                        pass
                raise


