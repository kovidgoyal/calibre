#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import sys, cPickle, os, binascii
from code import InteractiveInterpreter
from Queue import Queue, Empty
from threading import Thread
from binascii import unhexlify
from multiprocessing.connection import Client
from repr import repr as safe_repr

from calibre.utils.pyconsole import preferred_encoding, isbytestring, \
        POLL_TIMEOUT

'''
Messages sent by client:

    (stdout, unicode)
    (stderr, unicode)
    (syntaxerror, unicode)
    (traceback, unicode)
    (done, True iff incomplete command)

Messages that can be received by client:
    (quit, return code)
    (run, unicode)

'''

def tounicode(raw): # {{{
    if isbytestring(raw):
        try:
            raw = raw.decode(preferred_encoding, 'replace')
        except:
            raw = safe_repr(raw)

        if isbytestring(raw):
            try:
                raw.decode('utf-8', 'replace')
            except:
                raw = u'Undecodable bytestring'
        return raw
# }}}

class DummyFile(object): # {{{

    def __init__(self, what, out_queue):
        self.closed = False
        self.name = 'console'
        self.softspace = 0
        self.what = what
        self.out_queue = out_queue

    def flush(self):
        pass

    def close(self):
        pass

    def write(self, raw):
        self.out_queue.put((self.what, tounicode(raw)))
# }}}

class Comm(Thread): # {{{

    def __init__(self, conn, out_queue, in_queue):
        Thread.__init__(self)
        self.daemon = True
        self.conn = conn
        self.out_queue = out_queue
        self.in_queue = in_queue
        self.keep_going = True

    def run(self):
        while self.keep_going:
            try:
                self.communicate()
            except KeyboardInterrupt:
                pass
            except EOFError:
                pass

    def communicate(self):
        if self.conn.poll(POLL_TIMEOUT):
            try:
                obj = self.conn.recv()
            except:
                pass
            else:
                self.in_queue.put(obj)
        try:
            obj = self.out_queue.get_nowait()
        except Empty:
            pass
        else:
            try:
                self.conn.send(obj)
            except:
                raise EOFError('interpreter failed to send')
# }}}

class Interpreter(InteractiveInterpreter): # {{{

    def __init__(self, queue, local={}):
        if '__name__' not in local:
            local['__name__'] = '__console__'
        if '__doc__' not in local:
            local['__doc__'] = None
        self.out_queue = queue
        sys.stdout = DummyFile('stdout', queue)
        sys.stderr = DummyFile('sdterr', queue)
        InteractiveInterpreter.__init__(self, locals=local)

    def showtraceback(self, *args, **kwargs):
        self.is_syntax_error = False
        InteractiveInterpreter.showtraceback(self, *args, **kwargs)

    def showsyntaxerror(self, *args, **kwargs):
        self.is_syntax_error = True
        InteractiveInterpreter.showsyntaxerror(self, *args, **kwargs)

    def write(self, raw):
        what = 'syntaxerror' if self.is_syntax_error else 'traceback'
        self.out_queue.put((what, tounicode(raw)))

# }}}

def connect():
    os.chdir(cPickle.loads(binascii.unhexlify(os.environ['ORIGWD'])))
    address = cPickle.loads(unhexlify(os.environ['CALIBRE_WORKER_ADDRESS']))
    key     = unhexlify(os.environ['CALIBRE_WORKER_KEY'])
    return Client(address, authkey=key)

def main():
    out_queue = Queue()
    in_queue = Queue()
    conn = connect()
    comm = Comm(conn, out_queue, in_queue)
    comm.start()
    interpreter = Interpreter(out_queue)

    ret = 0

    while True:
        try:
            try:
                cmd, data = in_queue.get(1)
            except Empty:
                pass
            else:
                if cmd == 'quit':
                    ret = data
                    comm.keep_going = False
                    comm.join()
                    break
                elif cmd == 'run':
                    if not comm.is_alive():
                        ret = 1
                        break
                    ret = False
                    try:
                        ret = interpreter.runsource(data)
                    except KeyboardInterrupt:
                        pass
                    except SystemExit:
                        out_queue.put(('stderr', 'SystemExit ignored\n'))
                    out_queue.put(('done', ret))
        except KeyboardInterrupt:
            pass

    return ret

if __name__ == '__main__':
    main()
