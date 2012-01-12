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
        self.org_tb = orig_tb

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

def communicate(ans, worker, listener, args, timeout=300):
    cw = ConnectedWorker(listener, args)
    cw.start()
    st = time.time()
    while worker.is_alive and cw.is_alive():
        cw.join(0.01)
        delta = time.time() - st
        if not cw.accepted and delta > min(10, timeout):
            break
        if delta > timeout:
            raise WorkerError('Worker appears to have hung')
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
        cwd=None, priority='normal', env={}, no_output=False):

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
        communicate(ans, w, listener, (mod_name, func_name, args, kwargs),
                timeout=timeout)
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
            mod, func, args, kwargs = args
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



