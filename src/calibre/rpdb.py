#!/usr/bin/env python


__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

import pdb, socket, inspect, sys, select, os, atexit, time
from contextlib import suppress

from calibre.constants import cache_dir

PROMPT = '(debug) '
QUESTION = '\x00\x01\x02'


class RemotePdb(pdb.Pdb):

    def __init__(self, addr="127.0.0.1", port=4444, skip=None):
        # Open a reusable socket to allow for reloads
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, True)
        self.sock.bind((addr, port))
        self.sock.listen(1)
        with suppress(OSError):
            print("pdb is running on %s:%d" % (addr, port), file=sys.stderr)
        clientsocket, address = self.sock.accept()
        clientsocket.setblocking(True)
        self.clientsocket = clientsocket
        self.handle = clientsocket.makefile('rw')
        pdb.Pdb.__init__(self, completekey='tab', stdin=self.handle, stdout=self.handle, skip=skip)
        self.prompt = PROMPT

    def prints(self, *args, **kwargs):
        kwargs['file'] = self.handle
        kwargs['flush'] = True
        print(*args, **kwargs)

    def ask_question(self, query):
        self.handle.write(QUESTION)
        self.prints(query, end='')
        self.handle.write(PROMPT)
        self.handle.flush()
        return self.handle.readline()

    def end_session(self, *args):
        self.clear_all_breaks()
        self.reset()
        self.handle.close()
        self.clientsocket.shutdown(socket.SHUT_RDWR)
        self.clientsocket.close()
        try:
            self.sock.shutdown(socket.SHUT_RDWR)
            self.sock.close()
        except OSError:
            pass
        return pdb.Pdb.do_continue(self, None)

    def do_clear(self, arg):
        if not arg:
            ans = self.ask_question("Clear all breaks? [y/n]: ")
            if ans.strip().lower() in {'y', 'yes'}:
                self.clear_all_breaks()
                self.prints('All breaks cleared')
            return
        return pdb.Pdb.do_clear(self, arg)
    do_cl = do_clear

    def do_continue(self, arg):
        if not self.breaks:
            ans = self.ask_question(
                'There are no breakpoints set. Continuing will terminate this debug session. Are you sure? [y/n]: ')
            if ans.strip().lower() in {'y', 'yes'}:
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
        print('Debugging aborted by keyboard interrupt')
    except Exception:
        print('Failed to run debugger')
        import traceback
        traceback.print_exc()


def cli(port=4444):
    print('Connecting to remote debugger on port %d...' % port)
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    for i in range(20):
        try:
            sock.connect(('127.0.0.1', port))
            break
        except OSError:
            pass
        time.sleep(0.1)
    else:
        try:
            sock.connect(('127.0.0.1', port))
        except OSError as err:
            print('Failed to connect to remote debugger:', err, file=sys.stderr)
            raise SystemExit(1)
    print('Connected to remote process', flush=True)
    try:
        import readline
    except ImportError:
        pass
    else:
        histfile = os.path.join(cache_dir(), 'rpdb.history')
        try:
            readline.read_history_file(histfile)
        except OSError:
            pass
        atexit.register(readline.write_history_file, histfile)
        p = pdb.Pdb()
        readline.set_completer(p.complete)
        readline.parse_and_bind("tab: complete")

    sock.setblocking(True)
    with suppress(KeyboardInterrupt):
        end_of_input = PROMPT.encode('utf-8')
        while True:
            recvd = b''
            while select.select([sock], [], [], 0)[0] or not recvd.endswith(end_of_input):
                buf = sock.recv(4096)
                if not buf:
                    return
                recvd += buf
            recvd = recvd.decode('utf-8', 'replace')
            recvd = recvd[:-len(PROMPT)]
            raw = ''
            if recvd.startswith(QUESTION):
                recvd = recvd[len(QUESTION):]
                print(recvd, end='', flush=True)
                raw = sys.stdin.readline() or 'n'
            else:
                print(recvd, end='', flush=True)
                try:
                    raw = input(PROMPT)
                except (EOFError, KeyboardInterrupt):
                    pass
                else:
                    raw += '\n'
                if not raw:
                    raw = 'quit\n'
            if raw:
                sock.sendall(raw.encode('utf-8'))


if __name__ == '__main__':
    cli()
