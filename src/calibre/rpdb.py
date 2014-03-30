#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

import pdb, socket, inspect, sys, select

from calibre import prints
from calibre.utils.ipc import eintr_retry_call

PROMPT = b'(debug) '
MSG = b'\x00\x01\x02'

class RemotePdb(pdb.Pdb):

    def __init__(self, addr="127.0.0.1", port=4444, skip=None):
        try:
            prints("pdb is running on %s:%d" % (addr, port), file=sys.stderr)
        except IOError:
            pass

        # Open a reusable socket to allow for reloads
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, True)
        self.sock.bind((addr, port))
        self.sock.listen(1)
        clientsocket, address = self.sock.accept()
        self.handle = clientsocket.makefile('rw')
        pdb.Pdb.__init__(self, completekey='tab', stdin=self.handle, stdout=self.handle, skip=skip)
        self.prompt = PROMPT

    def send_message(self, *args, **kwargs):
        kwargs['file'] = self.handle
        self.handle.write(MSG)
        prints(*args, **kwargs)
        self.handle.write(PROMPT)
        self.handle.flush()

    def ask_question(self, query):
        self.send_message(query, end='')
        return self.handle.readline()

    def end_session(self, *args):
        self.clear_all_breaks()
        self.reset()
        del self.handle
        try:
            self.sock.shutdown(socket.SHUT_RDWR)
            self.sock.close()
        except socket.error:
            pass
        return pdb.Pdb.do_continue(self, None)

    def do_clear(self, arg):
        if not arg:
            ans = self.ask_question("Clear all breaks? [y/n]: ")
            if ans.strip().lower() in {b'y', b'yes'}:
                self.clear_all_breaks()
                self.send_message('All breaks cleared')
            return
        return pdb.Pdb.do_clear(self, arg)
    do_cl = do_clear

    def do_continue(self, arg):
        if not self.breaks:
            ans = self.ask_question(
                'There are no breakpoints set. Continuing will terminate this debug session. Are you sure? [y/n]: ')
            if ans.strip().lower() in {b'y', b'yes'}:
                return self.end_session()
            return
        return pdb.Pdb.do_continue(self, arg)
    do_c = do_cont = do_continue

    do_EOF = do_quit = do_exit = do_q = end_session

def set_trace(port=4444, skip=None):
    frame = inspect.currentframe().f_back

    try:
        debugger = RemotePdb(port=port, skip=skip)
        debugger.set_trace(frame)
    except KeyboardInterrupt:
        prints('Debugging aborted by keyboard interrupt')
    except Exception:
        prints('Failed to run debugger')
        import traceback
        traceback.print_exc()

def cli(port=4444):
    prints('Connecting to remote process on port %d...' % port)
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(120)
    sock.connect(('127.0.0.1', port))
    prints('Connected to remote process')
    sock.setblocking(True)
    try:
        while True:
            recvd = b''
            while not recvd.endswith(PROMPT) or select.select([sock], [], [], 0) == ([sock], [], []):
                buf = eintr_retry_call(sock.recv, 16 * 1024)
                if not buf:
                    return
                recvd += buf
            if recvd:
                if recvd.startswith(MSG):
                    recvd = recvd[len(MSG):-len(PROMPT)]
                sys.stdout.write(recvd)
            buf = []
            raw = b''
            try:
                while not raw.endswith(b'\n'):
                    raw += sys.stdin.read(1)
                    if not raw:  # EOF (Ctrl+D)
                        raw = b'quit\n'
                        break
                eintr_retry_call(sock.send, raw)
            except KeyboardInterrupt:
                eintr_retry_call(sock.send, b'quit\n')
                continue
    except KeyboardInterrupt:
        pass

