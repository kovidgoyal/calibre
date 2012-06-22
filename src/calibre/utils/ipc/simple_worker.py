#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os, cPickle, traceback, time, importlib
from binascii import hexlify, unhexlify
from multiprocessing.connection import Listener, arbitrary_address, Client
from threading import Thread
from contextlib import closing

from calibre.constants import iswindows
from calibre.utils.ipc.launch import Worker

class WorkerError(Exception):
    def __init__(self, msg, orig_tb=''):
        Exception.__init__(self, msg)
        self.orig_tb = orig_tb

class ConnectedWorker(Thread):

    def __init__(self, listener, args):
        Thread.__init__(self)
        self.daemon = True

        self.listener = listener
        self.args = args
        self.accepted = False
        self.tb = None
        self.res = None

    def run(self):
        conn = tb = None
        for i in range(2):
            # On OS X an EINTR can interrupt the accept() call
            try:
                conn = self.listener.accept()
                break
            except:
                tb = traceback.format_exc()
                pass
        if conn is None:
            self.tb = tb
            return
        self.accepted = True
        with closing(conn):
            try:
                try:
                    conn.send(self.args)
                except:
                    # Maybe an EINTR
                    conn.send(self.args)
                try:
                    self.res = conn.recv()
                except:
                    # Maybe an EINTR
                    self.res = conn.recv()
            except:
                self.tb = traceback.format_exc()

def communicate(ans, worker, listener, args, timeout=300, heartbeat=None,
        abort=None):
    cw = ConnectedWorker(listener, args)
    cw.start()
    st = time.time()
    check_heartbeat = callable(heartbeat)

    while worker.is_alive and cw.is_alive():
        cw.join(0.01)
        delta = time.time() - st
        if not cw.accepted and delta > min(10, timeout):
            break
        hung = not heartbeat() if check_heartbeat else delta > timeout
        if hung:
            raise WorkerError('Worker appears to have hung')
        if abort is not None and abort.is_set():
            # The worker process will be killed by fork_job, after we return
            return

    if not cw.accepted:
        if not cw.tb:
            raise WorkerError('Failed to connect to worker process')
        raise WorkerError('Failed to connect to worker process', cw.tb)

    if cw.tb:
        raise WorkerError('Failed to communicate with worker process')
    if cw.res.get('tb', None):
        raise WorkerError('Worker failed', cw.res['tb'])
    ans['result'] = cw.res['result']

def fork_job(mod_name, func_name, args=(), kwargs={}, timeout=300, # seconds
        cwd=None, priority='normal', env={}, no_output=False, heartbeat=None,
        abort=None, module_is_source_code=False):
    '''
    Run a job in a worker process. A job is simply a function that will be
    called with the supplied arguments, in the worker process.
    The result of the function will be returned.
    If an error occurs a WorkerError is raised.

    :param mod_name: Module to import in the worker process

    :param func_name: Function to call in the worker process from the imported
    module

    :param args: Positional arguments to pass to the function

    :param kwargs: Keyword arguments to pass to the function

    :param timeout: The time in seconds to wait for the worker process to
    complete. If it takes longer a WorkerError is raised and the process is
    killed.

    :param cwd: The working directory for the worker process. I recommend
    against using this, unless you are sure the path is pure ASCII.

    :param priority: The process priority for the worker process

    :param env: Extra environment variables to set for the worker process

    :param no_output: If True, the stdout and stderr of the worker process are
    discarded

    :param heartbeat: If not None, it is used to check if the worker has hung,
    instead of a simple timeout. It must be a callable that takes no
    arguments and returns True or False. The worker will be assumed to have
    hung if this function returns False. At that point, the process will be
    killed and a WorkerError will be raised.

    :param abort: If not None, it must be an Event. As soon as abort.is_set()
    returns True, the worker process is killed. No error is raised.

    :param module_is_source_code: If True, the ``mod`` is treated as python
    source rather than a module name to import. The source is executed as a
    module. Useful if you want to use fork_job from within a script to run some
    dynamically generated python.

    :return: A dictionary with the keys result and stdout_stderr. result is the
    return value of the function (it must be picklable). stdout_stderr is the
    path to a file that contains the stdout and stderr of the worker process.
    If you set no_output=True, then this will not be present.
    '''

    ans = {'result':None, 'stdout_stderr':None}

    address = arbitrary_address('AF_PIPE' if iswindows else 'AF_UNIX')
    if iswindows and address[1] == ':':
        address = address[2:]
    auth_key = os.urandom(32)
    listener = Listener(address=address, authkey=auth_key)

    env = dict(env)
    env.update({
                'CALIBRE_WORKER_ADDRESS' :
                    hexlify(cPickle.dumps(listener.address, -1)),
                'CALIBRE_WORKER_KEY' : hexlify(auth_key),
                'CALIBRE_SIMPLE_WORKER':
                            'calibre.utils.ipc.simple_worker:main',
            })

    w = Worker(env)
    w(cwd=cwd, priority=priority)
    try:
        communicate(ans, w, listener, (mod_name, func_name, args, kwargs,
            module_is_source_code), timeout=timeout, heartbeat=heartbeat,
            abort=abort)
    finally:
        t = Thread(target=w.kill)
        t.daemon=True
        t.start()
        if no_output:
            try:
                os.remove(w.log_path)
            except:
                pass
    if not no_output:
        ans['stdout_stderr'] = w.log_path
    return ans

def compile_code(src):
    import re, io
    if not isinstance(src, unicode):
        match = re.search(r'coding[:=]\s*([-\w.]+)', src[:200])
        enc = match.group(1) if match else 'utf-8'
        src = src.decode(enc)
    # Python complains if there is a coding declaration in a unicode string
    src = re.sub(r'^#.*coding\s*[:=]\s*([-\w.]+)', '#', src, flags=re.MULTILINE)
    # Translate newlines to \n
    src = io.StringIO(src, newline=None).getvalue()

    namespace = {
            'time':time, 're':re, 'os':os, 'io':io,
    }
    exec src in namespace
    return namespace

def main():
    # The entry point for the simple worker process
    address = cPickle.loads(unhexlify(os.environ['CALIBRE_WORKER_ADDRESS']))
    key     = unhexlify(os.environ['CALIBRE_WORKER_KEY'])
    with closing(Client(address, authkey=key)) as conn:
        try:
            args = conn.recv()
        except:
            # Maybe EINTR
            args = conn.recv()
        try:
            mod, func, args, kwargs, module_is_source_code = args
            if module_is_source_code:
                importlib.import_module('calibre.customize.ui') # Load plugins
                mod = compile_code(mod)
                func = mod[func]
            else:
                try:
                    mod = importlib.import_module(mod)
                except ImportError:
                    importlib.import_module('calibre.customize.ui') # Load plugins
                    mod = importlib.import_module(mod)
                func = getattr(mod, func)
            res = {'result':func(*args, **kwargs)}
        except:
            res = {'tb': traceback.format_exc()}

        try:
            conn.send(res)
        except:
            # Maybe EINTR
            conn.send(res)



