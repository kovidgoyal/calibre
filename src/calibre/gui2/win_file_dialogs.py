#!/usr/bin/env python
# License: GPLv3 Copyright: 2016, Kovid Goyal <kovid at kovidgoyal.net>


import os
import struct
import subprocess
import sys
from threading import Thread
from uuid import uuid4
from contextlib import suppress


from polyglot.builtins import string_or_bytes

base = sys.extensions_location if hasattr(sys, 'new_app_layout') else os.path.dirname(sys.executable)
HELPER = os.path.join(base, 'calibre-file-dialog.exe')
current_app_uid = None


def set_app_uid(val=None):
    global current_app_uid
    current_app_uid = val


def is_ok():
    return os.path.exists(HELPER)


try:
    from calibre.utils.config import dynamic
except ImportError:
    dynamic = {}


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
    return struct.pack('=B4sQ', 4, b'HWND', int(hwnd))


def serialize_secret(secret):
    return struct.pack('=B6s32s', 6, b'SECRET', secret)


def serialize_binary(key, val):
    key = key.encode('ascii') if not isinstance(key, bytes) else key
    return struct.pack('=B%ssB' % len(key), len(key), key, int(val))


def serialize_string(key, val):
    key = key.encode('ascii') if not isinstance(key, bytes) else key
    val = str(val).encode('utf-8')
    if len(val) > 2**16 - 1:
        raise ValueError('%s is too long' % key)
    return struct.pack('=B%dsH%ds' % (len(key), len(val)), len(key), key, len(val), val)


def serialize_file_types(file_types):
    key = b"FILE_TYPES"
    buf = [struct.pack('=B%dsH' % len(key), len(key), key, len(file_types))]

    def add(x):
        x = x.encode('utf-8').replace(b'\0', b'')
        buf.append(struct.pack('=H%ds' % len(x), len(x), x))
    for name, extensions in file_types:
        add(name or _('Files'))
        if isinstance(extensions, string_or_bytes):
            extensions = extensions.split()
        add('; '.join('*.' + ext.lower() for ext in extensions))
    return b''.join(buf)


class Helper(Thread):

    def __init__(self, process, data, callback):
        Thread.__init__(self, name='FileDialogHelper')
        self.process = process
        self.callback = callback
        self.data = data
        self.daemon = True
        self.rc = 1
        self.stdoutdata = self.stderrdata = b''

    def run(self):
        try:
            self.stdoutdata, self.stderrdata = self.process.communicate(b''.join(self.data))
            self.rc = self.process.wait()
        finally:
            self.callback()


def process_path(x):
    if isinstance(x, bytes):
        x = os.fsdecode(x)
    return os.path.abspath(os.path.expanduser(x))


def select_initial_dir(q):
    while q:
        c = os.path.dirname(q)
        if c == q:
            break
        if os.path.exists(c):
            return c
        q = c
    return os.path.expanduser('~')


def run_file_dialog(
        parent=None, title=None, initial_folder=None, filename=None, save_path=None,
        allow_multiple=False, only_dirs=False, confirm_overwrite=True, save_as=False, no_symlinks=False,
        file_types=(), default_ext=None, app_uid=None
):
    from calibre.gui2 import sanitize_env_vars
    secret = os.urandom(32).replace(b'\0', b' ')
    pipename = '\\\\.\\pipe\\%s' % uuid4()
    data = [serialize_string('PIPENAME', pipename), serialize_secret(secret)]
    parent = parent or None
    if parent is not None:
        data.append(serialize_hwnd(get_hwnd(parent)))
    if title:
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
            filename = os.fsdecode(filename)
        data.append(serialize_string('FILENAME', filename))
    if only_dirs:
        file_types = ()  # file types not allowed for dir only dialogs
    elif not file_types:
        file_types = [(_('All files'), ('*',))]
    if file_types:
        data.append(serialize_file_types(file_types))
    if default_ext:
        data.append(serialize_string('DEFAULT_EXTENSION', default_ext))
    app_uid = app_uid or current_app_uid
    if app_uid:
        data.append(serialize_string('APP_UID', app_uid))

    from qt.core import QEventLoop, Qt, pyqtSignal

    class Loop(QEventLoop):

        dialog_closed = pyqtSignal()

        def __init__(self):
            QEventLoop.__init__(self)
            self.dialog_closed.connect(self.exit, type=Qt.ConnectionType.QueuedConnection)

    loop = Loop()
    server = PipeServer(pipename)
    server.start()
    with sanitize_env_vars():
        h = Helper(subprocess.Popen(
            [HELPER], stdout=subprocess.PIPE, stdin=subprocess.PIPE, stderr=subprocess.PIPE),
               data, loop.dialog_closed.emit)
    h.start()
    loop.exec(QEventLoop.ProcessEventsFlag.ExcludeUserInputEvents)

    def decode(x):
        x = x or b''
        try:
            x = x.decode('utf-8')
        except Exception:
            x = repr(x)
        return x

    def get_errors():
        return decode(h.stdoutdata) + ' ' + decode(h.stderrdata)
    from calibre import prints
    from calibre.constants import DEBUG
    if DEBUG:
        prints('stdout+stderr from file dialog helper:', str([h.stdoutdata, h.stderrdata]))

    if h.rc != 0:
        raise Exception(f'File dialog failed (return code {h.rc}): {get_errors()}')
    server.join(2)
    if server.is_alive():
        raise Exception('Timed out waiting for read from pipe to complete')
    if server.err_msg:
        raise Exception(server.err_msg)
    if not server.data:
        return ()
    parts = list(filter(None, server.data.split(b'\0')))
    if DEBUG:
        prints('piped data from file dialog helper:', str(parts))
    if len(parts) < 2:
        return ()
    if parts[0] != secret:
        raise Exception('File dialog failed, incorrect secret received: ' + get_errors())

    from calibre_extensions.winutil import get_long_path_name

    def fix_path(x):
        u = os.path.abspath(x.decode('utf-8'))
        with suppress(Exception):
            try:
                return get_long_path_name(u)
            except FileNotFoundError:
                base, fn = os.path.split(u)
                return os.path.join(get_long_path_name(base), fn)
        return u

    ans = tuple(map(fix_path, parts[1:]))
    return ans


def get_initial_folder(name, title, default_dir='~', no_save_dir=False):
    name = name or 'dialog_' + title
    if no_save_dir:
        initial_folder = os.path.expanduser(default_dir)
    else:
        initial_folder = dynamic.get(name, os.path.expanduser(default_dir))
    if not initial_folder or not os.path.isdir(initial_folder):
        initial_folder = select_initial_dir(initial_folder)
    return name, initial_folder


def choose_dir(window, name, title, default_dir='~', no_save_dir=False):
    name, initial_folder = get_initial_folder(name, title, default_dir, no_save_dir)
    ans = run_file_dialog(window, title, only_dirs=True, initial_folder=initial_folder)
    if ans:
        ans = ans[0]
        if not no_save_dir:
            dynamic.set(name, ans)
        return ans


def choose_files(window, name, title,
                 filters=(), all_files=True, select_only_single_file=False, default_dir='~'):
    name, initial_folder = get_initial_folder(name, title, default_dir)
    file_types = list(filters)
    if all_files:
        file_types.append((_('All files'), ['*']))
    ans = run_file_dialog(window, title, allow_multiple=not select_only_single_file, initial_folder=initial_folder, file_types=file_types)
    if ans:
        dynamic.set(name, os.path.dirname(ans[0]))
        return ans
    return None


def choose_images(window, name, title, select_only_single_file=True, formats=None):
    if formats is None:
        from calibre.gui2.dnd import image_extensions
        formats = image_extensions()
    file_types = [(_('Images'), list(formats))]
    return choose_files(window, name, title, select_only_single_file=select_only_single_file, filters=file_types)


def choose_save_file(window, name, title, filters=[], all_files=True, initial_path=None, initial_filename=None):
    no_save_dir = False
    default_dir = '~'
    filename = initial_filename
    if initial_path is not None:
        no_save_dir = True
        default_dir = select_initial_dir(initial_path)
        filename = os.path.basename(initial_path)
    file_types = list(filters)
    if all_files:
        file_types.append((_('All files'), ['*']))
    all_exts = []
    for ftext, exts in file_types:
        for ext in exts:
            if '*' not in ext:
                all_exts.append(ext.lower())
    default_ext = all_exts[0] if all_exts else None
    name, initial_folder = get_initial_folder(name, title, default_dir, no_save_dir)
    ans = run_file_dialog(window, title, save_as=True, initial_folder=initial_folder, filename=filename, file_types=file_types, default_ext=default_ext)
    if ans:
        ans = ans[0]
        if not no_save_dir:
            dynamic.set(name, ans)
        return ans


class PipeServer(Thread):

    def __init__(self, pipename):
        Thread.__init__(self, name='PipeServer', daemon=True)
        from calibre_extensions import winutil
        self.client_connected = False
        self.pipe_handle = winutil.create_named_pipe(
            pipename, winutil.PIPE_ACCESS_INBOUND | winutil.FILE_FLAG_FIRST_PIPE_INSTANCE,
            winutil.PIPE_TYPE_BYTE | winutil.PIPE_READMODE_BYTE | winutil.PIPE_WAIT | winutil.PIPE_REJECT_REMOTE_CLIENTS,
            1, 8192, 8192, 0)
        winutil.set_handle_information(self.pipe_handle, winutil.HANDLE_FLAG_INHERIT, 0)
        self.err_msg = None
        self.data = b''

    def run(self):
        from calibre_extensions import winutil
        try:
            try:
                winutil.connect_named_pipe(self.pipe_handle)
            except Exception as err:
                self.err_msg = f'ConnectNamedPipe failed: {err}'
                return

            self.client_connected = True
            while True:
                try:
                    data = winutil.read_file(self.pipe_handle, 64 * 1024)
                except OSError as err:
                    if err.winerror == winutil.ERROR_BROKEN_PIPE:
                        break  # pipe was closed at the other end
                    self.err_msg = f'ReadFile on pipe failed: {err}'
                if not data:
                    break
                self.data += data
        finally:
            self.pipe_handle = None


def test(helper=HELPER):
    pipename = '\\\\.\\pipe\\%s' % uuid4()
    echo = '\U0001f431 Hello world!'
    secret = os.urandom(32).replace(b'\0', b' ')
    data = serialize_string('PIPENAME', pipename) +  serialize_string('ECHO', echo) + serialize_secret(secret)
    server = PipeServer(pipename)
    server.start()
    p = subprocess.Popen([helper], stdout=subprocess.PIPE, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = p.communicate(data)
    if p.wait() != 0:
        raise Exception('File dialog failed: ' + stdout.decode('utf-8') + ' ' + stderr.decode('utf-8'))
    if server.err_msg is not None:
        raise RuntimeError(server.err_msg)
    server.join(2)
    parts = list(filter(None, server.data.split(b'\0')))
    if parts[0] != secret:
        raise RuntimeError(f'Did not get back secret: {secret!r} != {parts[0]!r}')
    q = parts[1].decode('utf-8')
    if q != echo:
        raise RuntimeError('Unexpected response: %r' % server.data)


if __name__ == '__main__':
    from calibre.gui2 import Application
    app = Application([])
    print(choose_save_file(None, 'xxx', 'yyy'))
    del app
