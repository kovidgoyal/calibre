#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

import os, subprocess, time, struct, sys, errno
from threading import Thread
from Queue import Queue
from functools import partial

from PyQt5.Qt import QApplication, QSplashScreen, pyqtSignal, QBrush, QColor, Qt, QPixmap

from calibre.constants import iswindows, isosx
from calibre.utils.ipc import eintr_retry_call

class SplashScreen(Thread):

    daemon = True

    def __init__(self, debug_executable):
        Thread.__init__(self)
        self.queue = Queue()
        try:
            self.launch_process(debug_executable)
        except Exception:
            import traceback
            traceback.print_exc()
            self.process = None
        self.keep_going = True
        if self.process is not None:
            self.start()
        self.show_message = partial(self._rpc, 'show_message')
        self.hide = partial(self._rpc, 'hide')

    def launch_process(self, debug_executable):
        kwargs = {'stdin':subprocess.PIPE}
        if iswindows:
            import win32process
            kwargs['creationflags'] = win32process.CREATE_NO_WINDOW
            kwargs['stdout'] = open(os.devnull, 'wb')
            kwargs['stderr'] = subprocess.STDOUT
        self.process = subprocess.Popen([debug_executable, '-c', 'from calibre.gui2.splash import main; main()'], **kwargs)

    def _rpc(self, name, *args):
        self.queue.put(('_' + name, args))

    def run(self):
        while self.keep_going:
            try:
                func, args = self.queue.get()
                if func == '_hide':
                    self.keep_going = False
                getattr(self, func)(*args)
            except Exception:
                import traceback
                traceback.print_exc()
        self.terminate_worker()

    def terminate_worker(self):
        if self.process is None:
            return
        self.process.stdin.close()
        # Give the worker two seconds to exit naturally
        c = 20
        while self.process.poll() is None and c > 0:
            time.sleep(0.1)
            c -= 1
        if self.process.poll() is None:
            try:
                self.process.terminate()
            except EnvironmentError as e:
                if getattr(e, 'errno', None) != errno.ESRCH:  # ESRCH ==> process does not exist anymore
                    import traceback
                    traceback.print_exc()
        self.process.wait()

    def send(self, msg):
        if self.process is not None and not self.process.stdin.closed:
            if not isinstance(msg, bytes):
                msg = msg.encode('utf-8')
            eintr_retry_call(self.process.stdin.write, struct.pack(b'>L', len(msg)) + msg)

    def _show_message(self, msg):
        self.send(msg)

    def _hide(self):
        if self.process is not None:
            self.process.stdin.close()

def read(amount):
    ans = b''
    left = amount
    while left > 0:
        raw = eintr_retry_call(sys.stdin.read, left)
        if len(raw) == 0:
            raise EOFError('')
        left -= len(raw)
        ans += raw
    return ans

def run_loop(splash_screen):
    shutdown = splash_screen.shutdown.emit
    try:
        while True:
            raw = read(4)
            mlen = struct.unpack(b'>L', raw)[0]
            msg = read(mlen).decode('utf-8')
            if not msg:
                return shutdown()
            splash_screen.show_message.emit(msg)
    except EOFError:
        pass
    except:
        import traceback
        traceback.print_exc()
    return shutdown()

class CalibreSplashScreen(QSplashScreen):

    shutdown = pyqtSignal()
    show_message = pyqtSignal(object)

    def __init__(self):
        QSplashScreen.__init__(self, QPixmap(I('library.png')))

    def drawContents(self, painter):
        painter.setBackgroundMode(Qt.OpaqueMode)
        painter.setBackground(QBrush(QColor(0xee, 0xee, 0xee)))
        painter.setPen(Qt.black)
        painter.setRenderHint(painter.TextAntialiasing, True)
        painter.drawText(self.rect().adjusted(5, 5, -5, -5), Qt.AlignLeft, self.message())


def main():
    os.closerange(3, 256)
    from calibre.gui2 import Application
    app = Application([])
    s = CalibreSplashScreen()
    s.show_message.connect(s.showMessage, type=Qt.QueuedConnection)
    s.shutdown.connect(app.quit, type=Qt.QueuedConnection)
    s.show()
    Thread(target=run_loop, args=(s,)).start()
    app.exec_()

if isosx:
    # Showing the splash screen in a separate process doesn't work on OS X and
    # I can't be bothered to figure out why
    del SplashScreen

    class SplashScreen(CalibreSplashScreen):

        def __init__(self, *args):
            CalibreSplashScreen.__init__(self)
            self.show()

        def show(self):
            CalibreSplashScreen.show(self)
            QApplication.instance().processEvents()
            QApplication.instance().flush()

        def show_message(self, msg):
            CalibreSplashScreen.showMessage(self, msg)
