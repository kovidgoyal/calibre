#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2016, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import (unicode_literals, division, absolute_import,
                        print_function)
import sys, subprocess, struct, os
from threading import Thread

from PyQt5.Qt import QMainWindow, QApplication, QPushButton, pyqtSignal, QEventLoop, Qt

is64bit = sys.maxsize > (1 << 32)
base = sys.extensions_location if hasattr(sys, 'new_app_layout') else os.path.dirname(sys.executable)
HELPER = os.path.join(base, 'calibre-file-dialogs.exe')

def get_hwnd(widget=None):
    ewid = None
    if widget is not None:
        ewid = widget.effectiveWinId()
    if ewid is None:
        return None
    return int(ewid)

def serialize_hwnd(hwnd):
    if hwnd is None:
        return b''
    return struct.pack(b'=' + (b'B4sQ' if is64bit else b'I'), 4, b'HWND', int(hwnd))

def serialize_string(key, val):
    key = key.encode('ascii') if not isinstance(key, bytes) else key
    val = type('')(val).encode('utf-8')
    if len(val) > 2**16 - 1:
        raise ValueError('%s is too long' % key)
    return struct.pack(b'=B%dsH%ds' % (len(key), len(val)), len(key), key, len(val), val)

class Helper(Thread):

    def __init__(self, process, data, callback):
        Thread.__init__(self, name='FileDialogHelper')
        self.process = process
        self.callback = callback
        self.data = data
        self.daemon = True
        self.rc = 0
        self.stdoutdata = None

    def run(self):
        self.stdoutdata, self.stderrdata = self.process.communicate(b''.join(self.data))
        self.rc = self.process.wait()
        self.callback()

class Loop(QEventLoop):

    dialog_closed = pyqtSignal()

    def __init__(self):
        QEventLoop.__init__(self)
        self.dialog_closed.connect(self.exit, type=Qt.QueuedConnection)

def run_file_dialog(parent=None, title=None):
    data = []
    if parent is not None:
        data.append(serialize_hwnd(get_hwnd(parent)))
    if title is not None:
        data.append(serialize_string('TITLE', title))
    loop = Loop()
    h = Helper(subprocess.Popen(
        [HELPER], stdout=subprocess.PIPE, stdin=subprocess.PIPE, stderr=subprocess.PIPE),
               data, loop.dialog_closed.emit)
    h.start()
    loop.exec_(QEventLoop.ExcludeUserInputEvents)
    if h.rc != 0:
        raise Exception('File dialog failed: ' + h.stderrdata.decode('utf-8'))
    if not h.stdoutdata:
        return ()
    return tuple(x.decode('utf-8') for x in h.stdoutdata.split(b'\0'))

if __name__ == '__main__':
    HELPER = sys.argv[-1]
    app = QApplication([])
    q = QMainWindow()

    def clicked():
        print(run_file_dialog(b, 'Testing dialogs')), sys.stdout.flush()

    b = QPushButton('click me')
    b.clicked.connect(clicked)
    q.setCentralWidget(b)
    q.show()
    app.exec_()
