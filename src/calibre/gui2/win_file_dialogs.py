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

try:
    from calibre.constants import filesystem_encoding
    from calibre.utils.filenames import expanduser
except ImportError:
    filesystem_encoding = 'utf-8'
    expanduser = os.path.expanduser

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

def serialize_binary(key, val):
    key = key.encode('ascii') if not isinstance(key, bytes) else key
    return struct.pack(b'=B%ssB' % len(key), len(key), key, int(val))

def serialize_string(key, val):
    key = key.encode('ascii') if not isinstance(key, bytes) else key
    val = type('')(val).encode('utf-8')
    if len(val) > 2**16 - 1:
        raise ValueError('%s is too long' % key)
    return struct.pack(b'=B%dsH%ds' % (len(key), len(val)), len(key), key, len(val), val)

def serialize_file_types(file_types):
    key = b"FILE_TYPES"
    buf = [struct.pack(b'=B%dsH' % len(key), len(key), key, len(file_types))]
    def add(x):
        x = x.encode('utf-8').replace(b'\0', b'')
        buf.append(struct.pack(b'=H%ds' % len(x), len(x), x))
    for name, extensions in file_types:
        add(name or _('Files'))
        add('; '.join('*.' + ext.lower() for ext in extensions))
    return b''.join(buf)

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

def process_path(x):
    if isinstance(x, bytes):
        x = x.decode(filesystem_encoding)
    return os.path.abspath(expanduser(x))

def select_initial_dir(q):
    while q:
        c = os.path.dirname(q)
        if c == q:
            break
        if os.path.exists(c):
            return c
        q = c
    return expanduser('~')

def run_file_dialog(
        parent=None, title=None, initial_folder=None, filename=None, save_path=None,
        allow_multiple=False, only_dirs=False, confirm_overwrite=True, save_as=False, no_symlinks=False,
        file_types=()
):
    data = []
    if parent is not None:
        data.append(serialize_hwnd(get_hwnd(parent)))
    if title is not None:
        data.append(serialize_string('TITLE', title))
    if no_symlinks:
        data.append(serialize_binary('NO_SYMLINKS', no_symlinks))
    if save_as:
        data.append(serialize_binary('SAVE_AS', save_as))
        if confirm_overwrite:
            data.append(serialize_binary('CONFIRM_OVERWRITE', confirm_overwrite))
        if save_path is not None:
            save_path = process_path(save_path)
            if os.path.exists(save_path):
                data.append(serialize_string('SAVE_PATH', save_path))
            else:
                if not initial_folder:
                    initial_folder = select_initial_dir(save_path)
                if not filename:
                    filename = os.path.basename(save_path)
    else:
        if allow_multiple:
            data.append(serialize_binary('MULTISELECT', allow_multiple))
        if only_dirs:
            data.append(serialize_binary('ONLY_DIRS', only_dirs))
    if initial_folder is not None:
        initial_folder = process_path(initial_folder)
        if os.path.isdir(initial_folder):
            data.append(serialize_string('FOLDER', initial_folder))
    if filename:
        if isinstance(filename, bytes):
            filename = filename.decode(filesystem_encoding)
        data.append(serialize_string('FILENAME', filename))
    if only_dirs:
        file_types = ()  # file types not allowed for dir only dialogs
    elif not file_types:
        file_types = [(_('All files'), ('*',))]
    if file_types:
        data.append(serialize_file_types(file_types))
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
    ans = tuple((os.path.abspath(x.decode('utf-8')) for x in h.stdoutdata.split(b'\0') if x))
    return ans

if __name__ == '__main__':
    HELPER = sys.argv[-1]
    app = QApplication([])
    q = QMainWindow()
    _ = lambda x: x

    def clicked():
        print(run_file_dialog(
            b, 'Testing dialogs', only_dirs=False, allow_multiple=True, initial_folder=expanduser('~/build/calibre'),
            file_types=[('YAML files', ['yaml']), ('All files', '*')]))
        sys.stdout.flush()

    b = QPushButton('click me')
    b.clicked.connect(clicked)
    q.setCentralWidget(b)
    q.show()
    app.exec_()
