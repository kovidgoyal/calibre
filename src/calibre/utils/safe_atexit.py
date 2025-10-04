#!/usr/bin/env python
# License: GPLv3 Copyright: 2025, Kovid Goyal <kovid at kovidgoyal.net>

# Atexit that works even if the process crashes

import atexit
import json
import os
import subprocess
import sys
import time
from contextlib import suppress
from functools import wraps
from threading import RLock, Thread

_plat = sys.platform.lower()
iswindows = 'win32' in _plat or 'win64' in _plat

lock = RLock()
worker = None
RMTREE_ACTION = 'rmtree'
UNLINK_ACTION = 'unlink'
RUN_PROGRAM_ACTION = 'run_program'


def thread_safe(f):

    @wraps(f)
    def wrapper(*a, **kw):
        with lock:
            return f(*a, **kw)
    return wrapper


@thread_safe
def remove_folder_atexit(path: str) -> None:
    _send_command(RMTREE_ACTION, os.path.abspath(path))


@thread_safe
def remove_file_atexit(path: str) -> None:
    _send_command(UNLINK_ACTION, os.path.abspath(path))


@thread_safe
def run_program_now(cmdline: list[str]) -> None:
    _send_command(RUN_PROGRAM_ACTION, cmdline)


def unlink(path):
    with suppress(Exception):
        import os as oss
        if oss.path.exists(path):
            oss.remove(path)


def run_program(cmdline: list[str]) -> None:
    process = subprocess.Popen(cmdline)
    Thread(name='WaitProgram', target=process.wait, daemon=True).start()


def close_worker(worker):
    import subprocess
    worker.stdin.close()
    try:
        worker.wait(10)
    except subprocess.TimeoutExpired:
        worker.kill()
    worker.wait()


def ensure_worker():
    global worker
    if worker is None:
        from calibre.utils.ipc.simple_worker import start_pipe_worker
        worker = start_pipe_worker('from calibre.utils.safe_atexit import main; main()', stdout=None)
        atexit.register(close_worker, worker)
    return worker


def reset_after_fork():
    global worker
    atexit.unregister(close_worker)
    worker = None


def _send_command(action: str, payload: str | list[str]) -> None:
    worker = ensure_worker()
    worker.stdin.write(json.dumps({'action': action, 'payload': payload}).encode('utf-8'))
    worker.stdin.write(os.linesep.encode())
    worker.stdin.flush()


if iswindows:
    def remove_dir(x):
        from calibre.utils.filenames import make_long_path_useable
        x = make_long_path_useable(x)
        import shutil
        import time
        for i in range(10):
            try:
                shutil.rmtree(x)
                return
            except Exception:
                import os  # noqa
                if os.path.exists(x):
                    # In case some other program has one of the files open.
                    time.sleep(0.1)
                else:
                    return
        with suppress(Exception):
            shutil.rmtree(x, ignore_errors=True)
else:
    def remove_dir(x):
        import shutil
        with suppress(Exception):
            shutil.rmtree(x, ignore_errors=True)


def reset_dll_dir():
    import ctypes
    from ctypes import wintypes
    _set_dll_directory_w = ctypes.WinDLL('kernel32', use_last_error=True).SetDllDirectoryW
    _set_dll_directory_w.argtypes = [wintypes.LPCWSTR]
    _set_dll_directory_w.restype = wintypes.BOOL
    if not _set_dll_directory_w(None):
        error_code = ctypes.get_last_error()
        raise ctypes.WinError(error_code)


def main():
    if iswindows:
        reset_dll_dir()
    else:
        import signal
        signal.signal(signal.SIGINT, signal.SIG_IGN)
    from calibre.constants import sanitize_env_vars
    with sanitize_env_vars():
        ac_map = {RMTREE_ACTION: remove_dir, UNLINK_ACTION: unlink}
        for line in sys.stdin.buffer:
            if line:
                try:
                    cmd = json.loads(line)
                    if cmd['action'] == RUN_PROGRAM_ACTION:
                        run_program(cmd['payload'])
                    else:
                        atexit.register(ac_map[cmd['action']], cmd['payload'])
                except Exception:
                    import traceback
                    traceback.print_exc()


def main_for_test(do_forced_exit=False, check_tdir=False):
    if check_tdir:
        import tempfile

        from calibre.ptempfile import base_dir
        print(tempfile.gettempdir())
        print(base_dir())
        return
    tf = 'test-folder'
    os.mkdir(tf)
    open(os.path.join(tf, 'test-file'), 'w').close()
    remove_folder_atexit(tf)
    if do_forced_exit:
        os._exit(os.EX_OK)
    else:
        sys.stdin.read()


def find_tests():
    import tempfile
    import unittest

    from calibre.utils.ipc.simple_worker import start_pipe_worker

    class TestSafeAtexit(unittest.TestCase):

        def wait_for_empty(self, tdir, timeout=10):
            st = time.monotonic()
            while time.monotonic() - st < timeout:
                q = os.listdir(tdir)
                if not q:
                    break
                time.sleep(0.01)
            self.assertFalse(q)

        def test_safe_atexit(self):
            with tempfile.TemporaryDirectory() as tdir:
                self.assertFalse(os.listdir(tdir))
                p = start_pipe_worker('from calibre.utils.safe_atexit import main_for_test; main_for_test()', cwd=tdir)
                p.stdin.close()
                p.wait(10)
                self.wait_for_empty(tdir)
                p = start_pipe_worker('from calibre.utils.safe_atexit import main_for_test; main_for_test()', cwd=tdir)
                p.kill()
                p.wait(10)
                self.wait_for_empty(tdir)
                p = start_pipe_worker('from calibre.utils.safe_atexit import main_for_test; main_for_test(True)', cwd=tdir)
                p.wait(10)
                self.wait_for_empty(tdir)
                p = start_pipe_worker('from calibre.utils.safe_atexit import main_for_test; main_for_test(check_tdir=True)')
                tempfiledir, bdir = p.stdout.read().decode().splitlines()[:2]
                p.wait(10)
                self.assertEqual(bdir, tempfiledir)

    return unittest.defaultTestLoader.loadTestsFromTestCase(TestSafeAtexit)
