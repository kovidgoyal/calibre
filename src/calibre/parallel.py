from __future__ import with_statement
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

'''
Used to run jobs in parallel in separate processes. Features output streaming,
support for progress notification as well as job killing. The worker processes
are controlled via a simple protocol run over TCP/IP sockets. The control happens 
mainly in two class, :class:`Server` and :class:`Overseer`. The worker is
encapsulated in the function :function:`worker`. Every worker process
has the environment variable :envvar:`CALIBRE_WORKER` defined.

The worker control protocol has two modes of operation. In the first mode, the
worker process listens for commands from the controller process. The controller
process can either hand off a job to the worker or tell the worker to die. 
Once a job is handed off to the worker, the protocol enters the second mode, where
the controller listens for messages from the worker. The worker can send progress updates
as well as console output (i.e. text that would normally have been written to stdout
or stderr by the job). Once the job completes (or raises an exception) the worker
returns the result (or exception) to the controller adnt he protocol reverts to the first mode.

In the second mode, the controller can also send the worker STOP messages, in which case
the worker interrupts the job and dies. The sending of progress and console output messages
is buffered and asynchronous to prevent the job from being IO bound.  
'''
import sys, os, gc, cPickle, traceback, atexit, cStringIO, time, signal, \
       subprocess, socket, collections, binascii, re, tempfile, thread
from select import select
from functools import partial
from threading import RLock, Thread, Event

from calibre.ptempfile import PersistentTemporaryFile
from calibre import iswindows, detect_ncpus, isosx


#: A mapping from job names to functions that perform the jobs
PARALLEL_FUNCS = {
                  'any2lrf'      : 
        ('calibre.ebooks.lrf.any.convert_from', 'main', dict(gui_mode=True), None),
                  
                  'lrfviewer'    : 
        ('calibre.gui2.lrf_renderer.main', 'main', {}, None),
        
                  'feeds2lrf'    : 
        ('calibre.ebooks.lrf.feeds.convert_from', 'main', {}, 'notification'),
        
                  'render_table' : 
        ('calibre.ebooks.lrf.html.table_as_image', 'do_render', {}, None),
}


isfrozen = hasattr(sys, 'frozen')

win32event   = __import__('win32event') if iswindows else None
win32process = __import__('win32process') if iswindows else None
msvcrt       = __import__('msvcrt') if iswindows else None

class WorkerStatus(object):
    '''
    A platform independent class to control child processes. Provides the
    methods:
    
    .. method:: WorkerStatus.is_alive()
    
        Return True is the child process is alive (i.e. it hasn't exited and returned a return code).
        
    .. method:: WorkerStatus.returncode()
    
        Wait for the child process to exit and return its return code (blocks until child returns).
        
    .. method:: WorkerStatus.kill()
    
        Forcibly terminates child process using operating system specific semantics. 
    '''
    
    def __init__(self, obj):
        '''
        `obj`: On windows a process handle, on unix a subprocess.Popen object.
        '''
        self.obj = obj
        self.win32process = win32process # Needed if kill is called during shutdown of interpreter
        self.os           = os
        self.signal       = signal
        ext = 'windows' if iswindows else 'unix'
        for func in ('is_alive', 'returncode', 'kill'):
            setattr(self, func, getattr(self, func+'_'+ext))
        
    def is_alive_unix(self):
        return self.obj.poll() == None
    
    def returncode_unix(self):
        return self.obj.wait()
    
    def kill_unix(self):
        os.kill(self.obj.pid, self.signal.SIGKILL)
    
    def is_alive_windows(self):
        return win32event.WaitForSingleObject(self.obj, 0) != win32event.WAIT_OBJECT_0
    
    def returncode_windows(self):
        return win32process.GetExitCodeProcess(self.obj)
    
    def kill_windows(self, returncode=-1):
        self.win32process.TerminateProcess(self.obj, returncode)

class WorkerMother(object):
    '''
    Platform independent object for launching child processes. All processes
    have the environment variable :envvar:`CALIBRE_WORKER` set.
    
    ..method:: WorkerMother.spawn_free_spirit(arg)
    
        Launch a non monitored process with argument `arg`.
        
    ..method:: WorkerMother.spawn_worker(arg)
         
        Launch a monitored and controllable process with argument `arg`. 
    '''
    
    def __init__(self):
        ext = 'windows' if iswindows else 'osx' if isosx else 'linux'
        self.os = os # Needed incase cleanup called when interpreter is shutting down
        self.env = {}
        if iswindows:
            self.executable = os.path.join(os.path.dirname(sys.executable),
                   'calibre-parallel.exe' if isfrozen else 'Scripts\\calibre-parallel.exe')
        elif isosx:
            self.executable = sys.executable
            self.prefix = ''
            if isfrozen:
                fd = getattr(sys, 'frameworks_dir')
                contents = os.path.dirname(fd)
                resources = os.path.join(contents, 'Resources')
                sp = os.path.join(resources, 'lib', 'python'+sys.version[:3], 'site-packages.zip')
                
                self.prefix += 'import sys; sys.frameworks_dir = "%s"; sys.frozen = "macosx_app"; '%fd
                self.prefix += 'sys.path.insert(0, %s); '%repr(sp)
                if fd not in os.environ['PATH']:
                    self.env['PATH'] = os.environ['PATH']+':'+fd
                self.env['PYTHONHOME'] = resources
        else:
            self.executable = os.path.join(getattr(sys, 'frozen_path'), 'calibre-parallel') \
                                if isfrozen else 'calibre-parallel'
            if isfrozen:
                self.env['LD_LIBRARY_PATH'] = getattr(sys, 'frozen_path') + ':' + os.environ.get('LD_LIBRARY_PATH', '')
    
        self.spawn_worker_windows = lambda arg : self.spawn_free_spirit_windows(arg, type='worker')
        self.spawn_worker_linux   = lambda arg : self.spawn_free_spirit_linux(arg, type='worker')
        self.spawn_worker_osx     = lambda arg : self.spawn_free_spirit_osx(arg, type='worker')
        
        for func in ('spawn_free_spirit', 'spawn_worker'):
            setattr(self, func, getattr(self, func+'_'+ext))
        
        
    def cleanup_child_windows(self, child, name=None, fd=None):
        try:
            child.kill()
        except:
            pass
        try:
            if fd is not None:
                self.os.close(fd)
        except:
            pass
        try:
            if name is not None and os.path.exists(name):
                self.os.unlink(name)
        except:
            pass
    
    def cleanup_child_linux(self, child):
        try:
            child.kill()
        except:
            pass            
    
    def get_env(self):
        env = dict(os.environ)
        env['CALIBRE_WORKER'] = '1'
        env['ORIGWD'] = os.path.abspath(os.getcwd())
        if hasattr(self, 'env'):
            env.update(self.env)
        return env
    
    def spawn_free_spirit_osx(self, arg, type='free_spirit'):
        script = 'from calibre.parallel import main; main(args=["calibre-parallel", %s]);'%repr(arg)
        cmdline = [self.executable, '-c', self.prefix+script]
        child = WorkerStatus(subprocess.Popen(cmdline, env=self.get_env()))
        atexit.register(self.cleanup_child_linux, child)
        return child
    
    def spawn_free_spirit_linux(self, arg, type='free_spirit'):
        cmdline = [self.executable, arg]
        child = WorkerStatus(subprocess.Popen(cmdline, 
                        env=self.get_env(), cwd=getattr(sys, 'frozen_path', None)))
        atexit.register(self.cleanup_child_linux, child)
        return child 
    
    def spawn_free_spirit_windows(self, arg, type='free_spirit'):
        fd, name = tempfile.mkstemp('.log', 'calibre_'+type+'_')
        handle = msvcrt.get_osfhandle(fd)
        si = win32process.STARTUPINFO()
        si.hStdOutput = handle
        si.hStdError  =  handle
        cmdline = self.executable + ' ' + str(arg)
        hProcess = \
        win32process.CreateProcess(
            None,    # Application Name
            cmdline, # Command line
            None,    # processAttributes
            None,    # threadAttributes
            1,       # bInheritHandles
            win32process.CREATE_NO_WINDOW, # Dont want ugly console popping up
            self.get_env(), # New environment
            None,    # Current directory
            si
        )[0]
        child = WorkerStatus(hProcess)
        atexit.register(self.cleanup_child_windows, child, name, fd)
        return child
        
    
mother = WorkerMother()        

def write(socket, msg, timeout=5):
    '''
    Write a message on socket. If `msg` is unicode, it is encoded in utf-8.
    Raises a `RuntimeError` if the socket is not ready for writing or the writing fails.
    `msg` is broken into chunks of size 4096 and sent. The :function:`read` function
    automatically re-assembles the chunks into whole message. 
    '''
    if isinstance(msg, unicode):
        msg = msg.encode('utf-8')
    length = None
    while len(msg) > 0:
        if length is None:
            length = len(msg)
            chunk = ('%-12d'%length) + msg[:4096-12]
            msg = msg[4096-12:]
        else:
            chunk, msg = msg[:4096], msg[4096:]
        w = select([], [socket], [], timeout)[1]
        if not w:
            raise RuntimeError('Write to socket timed out')
        if socket.sendall(chunk) is not None:
            raise RuntimeError('Failed to write chunk to socket')
        
    
def read(socket, timeout=5):
    '''
    Read a message from `socket`. The message must have been sent with the :function:`write`
    function. Raises a `RuntimeError` if the message is corrpted. Can return an 
    empty string.
    '''
    buf = cStringIO.StringIO()
    length = None
    while select([socket],[],[],timeout)[0]:
        msg = socket.recv(4096)
        if not msg:
            break
        if length is None:
            length, msg = int(msg[:12]), msg[12:]
        buf.write(msg)
        if buf.tell() >= length:
            break
    if not length:
        return ''
    msg = buf.getvalue()[:length]
    if len(msg) < length:
        raise RuntimeError('Corrupted packet received')
    
    return msg    

class RepeatingTimer(Thread):
    '''
    Calls a specified function repeatedly at a specified interval. Runs in a 
    daemon thread (i.e. the interpreter can exit while it is still running).
    Call :meth:`start()` to start it. 
    '''
    
    def repeat(self):
        while True:
            self.event.wait(self.interval)
            if self.event.isSet():
                break
            self.action()
    
    def __init__(self, interval, func, name):
        self.event    = Event()
        self.interval = interval
        self.action = func  
        Thread.__init__(self, target=self.repeat, name=name)
        self.setDaemon(True)
    
class ControlError(Exception):
    pass

class Overseer(object):
    '''
    Responsible for controlling worker processes. The main interface is the
    methods, :meth:`initialize_job`, :meth:`control`.
    '''
    
    KILL_RESULT = 'Server: job killed by user|||#@#$%&*)*(*$#$%#$@&'
    INTERVAL    = 0.1
    
    def __init__(self, server, port, timeout=5):
        self.worker_status = mother.spawn_worker('127.0.0.1:%d'%port)
        self.socket = server.accept()[0]
        # Needed if terminate called hwen interpreter is shutting down
        self.os = os
        self.signal = signal
        
        self.working = False
        self.timeout = timeout
        self.last_job_time = time.time()
        self.job_id = None
        self._stop = False
        if not select([self.socket], [], [], 120)[0]:
            raise RuntimeError(_('Could not launch worker process.'))
        ID = self.read().split(':') 
        if ID[0] != 'CALIBRE_WORKER':
            raise RuntimeError('Impostor')
        self.worker_pid = int(ID[1])
        self.write('OK')
        if self.read() != 'WAITING':
            raise RuntimeError('Worker sulking')
        
    def terminate(self):
        'Kill worker process.'
        try:
            if self.socket:
                self.write('STOP:')
                time.sleep(1)
                self.socket.shutdown(socket.SHUT_RDWR)
        except:
            pass
        if iswindows:
            win32api = __import__('win32api')
            try:
                handle = win32api.OpenProcess(1, False, self.worker_pid)
                win32api.TerminateProcess(handle, -1)
            except:
                pass
        else:
            try:
                try:
                    self.os.kill(self.worker_pid, self.signal.SIGKILL)
                    time.sleep(0.5)
                finally:
                    self.worker_status.kill()
            except:
                pass
    
        
    def write(self, msg, timeout=None):
        write(self.socket, msg, timeout=self.timeout if timeout is None else timeout)
        
    def read(self, timeout=None):
        return read(self.socket, timeout=self.timeout if timeout is None else timeout)
        
    def __eq__(self, other):
        return hasattr(other, 'process') and hasattr(other, 'worker_pid') and self.worker_pid == other.worker_pid
    
    def __bool__(self):
        return self.worker_status.is_alive()
    
    def select(self, timeout=0):
        return select([self.socket], [self.socket], [self.socket], timeout)
    
    def initialize_job(self, job):
        '''
        Sends `job` to worker process. Can raise `ControlError` if worker process
        does not respond appropriately. In this case, this Overseer is useless
        and should be discarded.
        
        `job`: An instance of :class:`Job`.
        '''
        self.job_id = job.job_id
        self.working = True
        self.write('JOB:'+cPickle.dumps((job.func, job.args, job.kwdargs), -1))
        msg = self.read()
        if msg != 'OK':
            raise ControlError('Failed to initialize job on worker %d:%s'%(self.worker_pid, msg))
        self.output = job.output if callable(job.output) else sys.stdout.write
        self.progress = job.progress if callable(job.progress) else None
        self.job =  job
    
    def control(self):
        '''
        Listens for messages from the worker process and dispatches them
        appropriately. If the worker process dies unexpectedly, returns a result
        of None with a ControlError indicating the worker died.
        
        Returns a :class:`Result` instance or None, if the worker is still working.
        '''
        if select([self.socket],[],[],0)[0]:
            msg = self.read()
            word, msg = msg.partition(':')[0], msg.partition(':')[-1]
            if word == 'RESULT':
                self.write('OK')
                return Result(cPickle.loads(msg), None, None)
            elif word == 'OUTPUT':
                self.write('OK')
                try:
                    self.output(''.join(cPickle.loads(msg)))
                except:
                    self.output('Bad output message: '+ repr(msg))
            elif word == 'PROGRESS':
                self.write('OK')
                percent = None
                try:
                    percent, msg = cPickle.loads(msg)[-1]
                except:
                    print 'Bad progress update:', repr(msg)
                if self.progress and percent is not None:
                    self.progress(percent, msg)
            elif word == 'ERROR':
                self.write('OK')
                return Result(None, *cPickle.loads(msg))
            else:
                self.terminate()
                return Result(None, ControlError('Worker sent invalid msg: %s', repr(msg)), '')
        if not self.worker_status.is_alive():
            return Result(None, ControlError('Worker process died unexpectedly with returncode: %d'%self.process.returncode), '')
    
            
                        
class Job(object):
    
    def __init__(self, job_id, func, args, kwdargs, output, progress, done):
        self.job_id = job_id
        self.func = func
        self.args = args
        self.kwdargs = kwdargs
        self.output = output
        self.progress = progress
        self.done = done
        
class Result(object):
    
    def __init__(self, result, exception, traceback):
        self.result = result
        self.exception = exception
        self.traceback = traceback
        
    def __len__(self):
        return 3
    
    def __item__(self, i):
        return (self.result, self.exception, self.traceback)[i]
    
    def __iter__(self):
        return iter((self.result, self.exception, self.traceback))

class Server(Thread):
    
    KILL_RESULT = Overseer.KILL_RESULT
    START_PORT = 10013
    
    def __init__(self, number_of_workers=detect_ncpus()):
        Thread.__init__(self)
        self.setDaemon(True)
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.port = self.START_PORT
        while True:
            try:
                self.server_socket.bind(('localhost', self.port))
                break
            except:
                self.port += 1
        self.server_socket.listen(5)
        self.number_of_workers = number_of_workers 
        self.pool, self.jobs, self.working, self.results = [], collections.deque(), [], {}
        atexit.register(self.killall)
        atexit.register(self.close)
        self.job_lock = RLock()
        self.overseer_lock = RLock()
        self.working_lock = RLock()
        self.result_lock = RLock()
        self.pool_lock = RLock()
        self.start()
        
    def close(self):
        try:
            self.server_socket.shutdown(socket.SHUT_RDWR)
        except:
            pass
    
    def add_job(self, job):
        with self.job_lock:
            self.jobs.append(job)
            
    def store_result(self, result, id=None):
        if id:
            with self.job_lock:
                self.results[id] = result
                
    def result(self, id):
        with self.result_lock:
            return self.results.pop(id, None)
    
    def run(self):
        while True:
            job = None
            with self.job_lock:
                if len(self.jobs) > 0 and len(self.working) < self.number_of_workers:
                    job = self.jobs.popleft()
                    with self.pool_lock:
                        o = None
                        while self.pool:
                            o = self.pool.pop()
                            try:
                                o.initialize_job(job)
                                break
                            except:
                                o.terminate()
                        if o is None:
                            o = Overseer(self.server_socket, self.port)
                            try:
                                o.initialize_job(job)
                            except Exception, err:
                                o.terminate()
                                res = Result(None, unicode(err), traceback.format_exc())
                                job.done(res)
                                o = None
                    if o:
                        with self.working_lock:
                            self.working.append(o)
                    
            with self.working_lock:
                done = []
                for o in self.working:
                    try:
                        res = o.control()
                    except Exception, err:
                        res = Result(None, unicode(err), traceback.format_exc())
                        o.terminate()
                    if isinstance(res, Result):
                        o.job.done(res)
                        done.append(o)
                for o in done:
                    self.working.remove(o)
                    if o:
                        with self.pool_lock:
                            self.pool.append(o)
                            
            try:
                time.sleep(1)
            except:
                return            
                
    
    def killall(self):
        with self.pool_lock:
            map(lambda x: x.terminate(), self.pool)
            self.pool = []
        
        
    def kill(self, job_id):
        with self.working_lock:
            pop = None
            for o in self.working:
                if o.job_id == job_id:
                    o.terminate()
                    o.job.done(Result(self.KILL_RESULT, None, ''))
                    pop = o
                    break
            if pop is not None:
                self.working.remove(pop)
                
                
        
    def run_job(self, job_id, func, args=[], kwdargs={}, 
                output=None, progress=None, done=None):
        '''
        Run a job in a separate process. Supports job control, output redirection 
        and progress reporting.
        '''
        if done is None:
            done = partial(self.store_result, id=job_id)
        job = Job(job_id, func, args, kwdargs, output, progress, done)
        with self.job_lock:
            self.jobs.append(job)
            
    def run_free_job(self, func, args=[], kwdargs={}):
        pt = PersistentTemporaryFile('.pickle', '_IPC_')
        pt.write(cPickle.dumps((func, args, kwdargs)))
        pt.close()
        mother.spawn_free_spirit(binascii.hexlify(pt.name))
        

##########################################################################################
##################################### CLIENT CODE #####################################
##########################################################################################

class BufferedSender(object):
    
    def __init__(self, socket):
        self.socket = socket
        self.wbuf, self.pbuf    = [], []
        self.wlock, self.plock   = RLock(), RLock()
        self.timer  = RepeatingTimer(0.5, self.send, 'BufferedSender')
        self.timer.start()
        
    def write(self, msg):
        if not isinstance(msg, basestring):
            msg = unicode(msg)
        with self.wlock:
            self.wbuf.append(msg)
    
    def send(self):
        if callable(select) and select([self.socket], [], [], 0)[0]:
            msg = read(self.socket)
            if msg == 'PING:':
                write(self.socket, 'OK')
            elif msg:
                self.socket.shutdown(socket.SHUT_RDWR)
                thread.interrupt_main()
                time.sleep(1)
                raise SystemExit
        if not select([], [self.socket], [], 30)[1]:
            print >>sys.__stderr__, 'Cannot pipe to overseer'
            return
        
        with self.wlock:
            if self.wbuf:
                msg = cPickle.dumps(self.wbuf, -1)
                self.wbuf = []
                write(self.socket, 'OUTPUT:'+msg)
                read(self.socket, 10)
                
        with self.plock:
            if self.pbuf:
                msg = cPickle.dumps(self.pbuf, -1)
                self.pbuf = []
                write(self.socket, 'PROGRESS:'+msg)
                read(self.socket, 10)        
                
    def notify(self, percent, msg=''):
        with self.plock:
            self.pbuf.append((percent, msg))
        
    def flush(self):
        pass

def get_func(name):
    module, func, kwdargs, notification = PARALLEL_FUNCS[name]
    module = __import__(module, fromlist=[1])
    func = getattr(module, func)
    return func, kwdargs, notification

def work(client_socket, func, args, kwdargs):
    func, kargs, notification = get_func(func)
    if notification is not None and hasattr(sys.stdout, 'notify'):
        kargs[notification] = sys.stdout.notify
    kargs.update(kwdargs)
    res = func(*args, **kargs)
    if hasattr(sys.stdout, 'send'): 
        sys.stdout.send()
    return res
    

def worker(host, port):
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client_socket.connect((host, port))
    write(client_socket, 'CALIBRE_WORKER:%d'%os.getpid())
    msg = read(client_socket, timeout=10)
    if msg != 'OK':
        return 1
    write(client_socket, 'WAITING')
    
    sys.stdout = BufferedSender(client_socket)
    sys.stderr = sys.stdout
    
    while True:
        if not select([client_socket], [], [], 60)[0]:
            time.sleep(1)
            continue
        msg = read(client_socket, timeout=60)
        if msg.startswith('JOB:'):
            func, args, kwdargs = cPickle.loads(msg[4:])
            write(client_socket, 'OK')
            try:
                result = work(client_socket, func, args, kwdargs)
                write(client_socket, 'RESULT:'+ cPickle.dumps(result))
            except (Exception, SystemExit), err:
                exception = (err.__class__.__name__, unicode(str(err), 'utf-8', 'replace'))
                tb = traceback.format_exc()
                write(client_socket, 'ERROR:'+cPickle.dumps((exception, tb),-1))
            if read(client_socket, 10) != 'OK':
                break
            gc.collect()
        elif msg == 'PING:':
            write(client_socket, 'OK')    
        elif msg == 'STOP:':
            client_socket.shutdown(socket.SHUT_RDWR)
            return 0
        elif not msg:
            time.sleep(1)
        else:
            print >>sys.__stderr__, 'Invalid protocols message', msg
            return 1
    
def free_spirit(path):
    func, args, kwdargs = cPickle.load(open(path, 'rb'))
    try:
        os.unlink(path)
    except:
        pass
    func, kargs = get_func(func)[:2]
    kargs.update(kwdargs)
    func(*args, **kargs)
    
def main(args=sys.argv):
    args = args[1].split(':')
    if len(args) == 1:
        free_spirit(binascii.unhexlify(re.sub(r'[^a-f0-9A-F]', '', args[0])))
    else:
        worker(args[0].replace("'", ''), int(args[1])) 
    return 0

if __name__ == '__main__':
    sys.exit(main())
    
