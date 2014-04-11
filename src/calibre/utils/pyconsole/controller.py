#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os, cPickle, signal, time
from Queue import Queue, Empty
from multiprocessing.connection import Listener, arbitrary_address
from binascii import hexlify

from PyQt5.Qt import QThread, pyqtSignal

from calibre.utils.pyconsole import Process, iswindows, POLL_TIMEOUT

class Controller(QThread):

    # show_error(is_syntax_error, traceback, self)
    show_error = pyqtSignal(object, object, object)
    # write_output(unicode_object, stdout or stderr, self)
    write_output = pyqtSignal(object, object, object)
    # Indicates interpreter has finished evaluating current command
    interpreter_done = pyqtSignal(object, object)
    # interpreter_died(self, returncode or None if no return code available)
    interpreter_died = pyqtSignal(object, object)

    def __init__(self, parent):
        QThread.__init__(self, parent)
        self.keep_going = True
        self.current_command = None

        self.out_queue = Queue()
        self.address = arbitrary_address('AF_PIPE' if iswindows else 'AF_UNIX')
        self.auth_key = os.urandom(32)
        if iswindows and self.address[1] == ':':
            self.address = self.address[2:]
        self.listener = Listener(address=self.address,
                authkey=self.auth_key, backlog=4)

        self.env = {
            'CALIBRE_SIMPLE_WORKER':
                'calibre.utils.pyconsole.interpreter:main',
            'CALIBRE_WORKER_ADDRESS':
                    hexlify(cPickle.dumps(self.listener.address, -1)),
            'CALIBRE_WORKER_KEY': hexlify(self.auth_key)
        }
        self.process = Process(self.env)
        self.output_file_buf = self.process(redirect_output=False)
        self.conn = self.listener.accept()
        self.start()

    def run(self):
        while self.keep_going and self.is_alive:
            try:
                self.communicate()
            except KeyboardInterrupt:
                pass
            except EOFError:
                break
        self.interpreter_died.emit(self, self.returncode)
        try:
            self.listener.close()
        except:
            pass

    def communicate(self):
        if self.conn.poll(POLL_TIMEOUT):
            self.dispatch_incoming_message(self.conn.recv())
        try:
            obj = self.out_queue.get_nowait()
        except Empty:
            pass
        else:
            try:
                self.conn.send(obj)
            except:
                raise EOFError('controller failed to send')

    def dispatch_incoming_message(self, obj):
        try:
            cmd, data = obj
        except:
            print 'Controller received invalid message'
            print repr(obj)
            return
        if cmd in ('stdout', 'stderr'):
            self.write_output.emit(data, cmd, self)
        elif cmd == 'syntaxerror':
            self.show_error.emit(True, data, self)
        elif cmd == 'traceback':
            self.show_error.emit(False, data, self)
        elif cmd == 'done':
            self.current_command = None
            self.interpreter_done.emit(self, data)

    def runsource(self, cmd):
        self.current_command = cmd
        self.out_queue.put(('run', cmd))

    def __nonzero__(self):
        return self.process.is_alive

    @property
    def returncode(self):
        return self.process.returncode

    def interrupt(self):
        if hasattr(signal, 'SIGINT'):
            os.kill(self.process.pid, signal.SIGINT)
        elif hasattr(signal, 'CTRL_C_EVENT'):
            os.kill(self.process.pid, signal.CTRL_C_EVENT)

    @property
    def is_alive(self):
        return self.process.is_alive

    def kill(self):
        self.out_queue.put(('quit', 0))
        t = 0
        while self.is_alive and t < 10:
            time.sleep(0.1)
        self.process.kill()
        self.keep_going = False

