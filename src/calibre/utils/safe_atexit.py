#!/usr/bin/env python
# License: GPLv3 Copyright: 2025, Kovid Goyal <kovid at kovidgoyal.net>

# Atexit that works even if the process crashes

import atexit
import json
import os
import sys
import time
from contextlib import suppress
from functools import wraps
from threading import Lock

from calibre.constants import iswindows
from calibre.utils.filenames import make_long_path_useable
from calibre.utils.ipc.simple_worker import start_pipe_worker

lock = Lock()
worker = None
RMTREE_ACTION = 'rmtree'


def thread_safe(f):

    @wraps(f)
    def wrapper(*a, **kw):
        with lock:
            return f(*a, **kw)
    return wrapper


@thread_safe
def remove_folder(path: str) -> None:
    _send_command(RMTREE_ACTION, os.path.abspath(path))


def ensure_worker():
    global worker
    if worker is None:
        worker = start_pipe_worker('from calibre.utils.safe_atexit import main; main()', stdout=None)
        def close_worker():
            worker.stdin.close()
            worker.wait(10)
        atexit.register(close_worker)
    return worker


def _send_command(action: str, payload: str) -> None:
    worker = ensure_worker()
    worker.stdin.write(json.dumps({'action': action, 'payload': payload}).encode('utf-8'))
    worker.stdin.write(os.linesep.encode())
    worker.stdin.flush()


if iswindows:
    def remove_dir(x):
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


def main():
    for line in sys.stdin.buffer:
        if line:
            try:
                cmd = json.loads(line)
                if cmd['action'] == RMTREE_ACTION:
                    atexit.register(remove_dir, cmd['payload'])
            except Exception:
                import traceback
                traceback.print_exc()


def main_for_test(do_forced_exit=False):
    tf = 'test-folder'
    os.mkdir(tf)
    open(os.path.join(tf, 'test-file'), 'w').close()
    remove_folder(tf)
    if do_forced_exit:
        os._exit(os.EX_OK)
    else:
        sys.stdin.read()


def find_tests():
    import tempfile
    import unittest

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

    return unittest.defaultTestLoader.loadTestsFromTestCase(TestSafeAtexit)
