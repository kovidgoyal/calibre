#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai


__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os, time, traceback, importlib
from multiprocessing.connection import Client
from threading import Thread
from contextlib import closing

from calibre.constants import iswindows
from calibre.utils.ipc import eintr_retry_call
from calibre.utils.ipc.launch import Worker
from calibre.utils.serialize import msgpack_loads, msgpack_dumps
from calibre.utils.monotonic import monotonic
from polyglot.builtins import unicode_type, string_or_bytes, environ_item
from polyglot.binary import as_hex_unicode, from_hex_bytes


class WorkerError(Exception):

    def __init__(self, msg, orig_tb='', log_path=None):
        Exception.__init__(self, msg)
        self.orig_tb = orig_tb
        self.log_path = log_path


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
        conn = None
        try:
            conn = eintr_retry_call(self.listener.accept)
        except BaseException:
            self.tb = traceback.format_exc()
            return
        self.accepted = True
        with closing(conn):
            try:
                eintr_retry_call(conn.send, self.args)
                self.res = eintr_retry_call(conn.recv)
            except BaseException:
                self.tb = traceback.format_exc()


class OffloadWorker(object):

    def __init__(self, listener, worker):
        self.listener = listener
        self.worker = worker
        self.conn = None
        self.kill_thread = t = Thread(target=self.worker.kill)
        t.daemon = True

    def __call__(self, module, func, *args, **kwargs):
        if self.conn is None:
            self.conn = eintr_retry_call(self.listener.accept)
        eintr_retry_call(self.conn.send, (module, func, args, kwargs))
        return eintr_retry_call(self.conn.recv)

    def shutdown(self):
        try:
            eintr_retry_call(self.conn.send, None)
        except IOError:
            pass
        except:
            import traceback
            traceback.print_exc()
        finally:
            self.conn = None
            try:
                os.remove(self.worker.log_path)
            except:
                pass
            self.kill_thread.start()

    def is_alive(self):
        return self.worker.is_alive or self.kill_thread.is_alive()


def communicate(ans, worker, listener, args, timeout=300, heartbeat=None,
        abort=None):
    cw = ConnectedWorker(listener, args)
    cw.start()
    st = monotonic()
    check_heartbeat = callable(heartbeat)

    while worker.is_alive and cw.is_alive():
        cw.join(0.01)
        delta = monotonic() - st
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
        raise WorkerError('Failed to communicate with worker process', cw.tb)
    if cw.res is None:
        raise WorkerError('Something strange happened. The worker process was aborted without an exception.')
    if cw.res.get('tb', None):
        raise WorkerError('Worker failed', cw.res['tb'])
    ans['result'] = cw.res['result']


def create_worker(env, priority='normal', cwd=None, func='main'):
    from calibre.utils.ipc.server import create_listener
    auth_key = os.urandom(32)
    address, listener = create_listener(auth_key)

    env = dict(env)
    env.update({
        'CALIBRE_WORKER_ADDRESS': environ_item(as_hex_unicode(msgpack_dumps(address))),
        'CALIBRE_WORKER_KEY': environ_item(as_hex_unicode(auth_key)),
        'CALIBRE_SIMPLE_WORKER': environ_item('calibre.utils.ipc.simple_worker:%s' % func),
    })

    w = Worker(env)
    w(cwd=cwd, priority=priority)
    return listener, w


def start_pipe_worker(command, env=None, priority='normal', **process_args):
    import subprocess
    w = Worker(env or {})
    args = {'stdout':subprocess.PIPE, 'stdin':subprocess.PIPE, 'env':w.env}
    args.update(process_args)
    if iswindows:
        priority = {
                'high'   : subprocess.HIGH_PRIORITY_CLASS,
                'normal' : subprocess.NORMAL_PRIORITY_CLASS,
                'low'    : subprocess.IDLE_PRIORITY_CLASS}[priority]
        args['creationflags'] = subprocess.CREATE_NO_WINDOW|priority
    else:
        niceness = {'normal' : 0, 'low'    : 10, 'high'   : 20}[priority]
        args['env']['CALIBRE_WORKER_NICENESS'] = str(niceness)

    exe = w.executable
    cmd = [exe] if isinstance(exe, string_or_bytes) else exe
    p = subprocess.Popen(cmd + ['--pipe-worker', command], **args)
    return p


def two_part_fork_job(env=None, priority='normal', cwd=None):
    env = env or {}
    listener, w = create_worker(env, priority, cwd)

    def run_job(
        mod_name, func_name, args=(), kwargs=None, timeout=300,  # seconds
        no_output=False, heartbeat=None, abort=None, module_is_source_code=False
    ):
        ans = {'result':None, 'stdout_stderr':None}
        kwargs = kwargs or {}
        try:
            communicate(ans, w, listener, (mod_name, func_name, args, kwargs,
                module_is_source_code), timeout=timeout, heartbeat=heartbeat,
                abort=abort)
        except WorkerError as e:
            if not no_output:
                e.log_path = w.log_path
            raise
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
    run_job.worker = w

    return run_job


def fork_job(mod_name, func_name, args=(), kwargs=None, timeout=300,  # seconds
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
    return two_part_fork_job(env, priority, cwd)(
        mod_name, func_name, args=args, kwargs=kwargs, timeout=timeout,
        no_output=no_output, heartbeat=heartbeat, abort=abort,
        module_is_source_code=module_is_source_code
    )


def offload_worker(env={}, priority='normal', cwd=None):
    listener, w = create_worker(env=env, priority=priority, cwd=cwd, func='offload')
    return OffloadWorker(listener, w)


def compile_code(src):
    import re, io
    if not isinstance(src, unicode_type):
        match = re.search(br'coding[:=]\s*([-\w.]+)', src[:200])
        enc = match.group(1).decode('utf-8') if match else 'utf-8'
        src = src.decode(enc)
    # Python complains if there is a coding declaration in a unicode string
    src = re.sub(r'^#.*coding\s*[:=]\s*([-\w.]+)', '#', src, flags=re.MULTILINE)
    # Translate newlines to \n
    src = io.StringIO(src, newline=None).getvalue()

    namespace = {
            'time':time, 're':re, 'os':os, 'io':io,
    }
    exec(src, namespace)
    return namespace


def main():
    # The entry point for the simple worker process
    address = msgpack_loads(from_hex_bytes(os.environ['CALIBRE_WORKER_ADDRESS']))
    key     = from_hex_bytes(os.environ['CALIBRE_WORKER_KEY'])
    with closing(Client(address, authkey=key)) as conn:
        args = eintr_retry_call(conn.recv)
        try:
            mod, func, args, kwargs, module_is_source_code = args
            if module_is_source_code:
                importlib.import_module('calibre.customize.ui')  # Load plugins
                mod = compile_code(mod)
                func = mod[func]
            else:
                try:
                    mod = importlib.import_module(mod)
                except ImportError:
                    importlib.import_module('calibre.customize.ui')  # Load plugins
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


def offload():
    # The entry point for the offload worker process
    address = msgpack_loads(from_hex_bytes(os.environ['CALIBRE_WORKER_ADDRESS']))
    key     = from_hex_bytes(os.environ['CALIBRE_WORKER_KEY'])
    func_cache = {}
    with closing(Client(address, authkey=key)) as conn:
        while True:
            args = eintr_retry_call(conn.recv)
            if args is None:
                break
            res = {'result':None, 'tb':None}
            try:
                mod, func, args, kwargs = args
                if mod is None:
                    eintr_retry_call(conn.send, res)
                    continue
                f = func_cache.get((mod, func), None)
                if f is None:
                    try:
                        m = importlib.import_module(mod)
                    except ImportError:
                        importlib.import_module('calibre.customize.ui')  # Load plugins
                        m = importlib.import_module(mod)
                    func_cache[(mod, func)] = f = getattr(m, func)
                res['result'] = f(*args, **kwargs)
            except:
                import traceback
                res['tb'] = traceback.format_exc()

            eintr_retry_call(conn.send, res)
