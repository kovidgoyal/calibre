#!/usr/bin/env python
# vim:fileencoding=utf-8


__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

import pdb, socket, inspect, sys, select, os, atexit, time

from calibre import prints
from calibre.constants import cache_dir
from polyglot.builtins import range, raw_input as rinput

PROMPT = '(debug) '
QUESTION = '\x00\x01\x02'


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

    def prints(self, *args, **kwargs):
        kwargs['file'] = self.handle
        prints(*args, **kwargs)

    def ask_question(self, query):
        self.handle.write(QUESTION)
        self.prints(query, end='')
        self.handle.write(PROMPT)
        self.handle.flush()
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
        prints('Debugging aborted by keyboard interrupt')
    except Exception:
        prints('Failed to run debugger')
        import traceback
        traceback.print_exc()


def cli(port=4444):
    prints('Connecting to remote debugger on port %d...' % port)
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    for i in range(20):
        try:
            sock.connect(('127.0.0.1', port))
            break
        except socket.error:
            pass
        time.sleep(0.1)
    else:
        try:
            sock.connect(('127.0.0.1', port))
        except socket.error as err:
            prints('Failed to connect to remote debugger:', err, file=sys.stderr)
            raise SystemExit(1)
    prints('Connected to remote process')
    import readline
    histfile = os.path.join(cache_dir(), 'rpdb.history')
    try:
        readline.read_history_file(histfile)
    except IOError:
        pass
    atexit.register(readline.write_history_file, histfile)
    p = pdb.Pdb()
    readline.set_completer(p.complete)
    readline.parse_and_bind("tab: complete")
    sockf = sock.makefile('rw')

    try:
        while True:
            recvd = ''
            while not recvd.endswith(PROMPT) or select.select([sock], [], [], 0) == ([sock], [], []):
                buf = sockf.read()
                if not buf:
                    return
                recvd += buf
            recvd = recvd[:-len(PROMPT)]
            if recvd.startswith(QUESTION):
                recvd = recvd[len(QUESTION):]
                sys.stdout.write(recvd)
                raw = sys.stdin.readline() or 'n'
            else:
                sys.stdout.write(recvd)
                raw = ''
                try:
                    raw = rinput(PROMPT.decode('utf-8'))
                except (EOFError, KeyboardInterrupt):
                    pass
                else:
                    raw += '\n'
                if not raw:
                    raw = 'quit\n'
            sockf.write(raw)
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    cli()
