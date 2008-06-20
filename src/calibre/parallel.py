from __future__ import with_statement
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
'''
Used to run jobs in parallel in separate processes.
'''
import sys, os, gc, cPickle, traceback, atexit, cStringIO, time, subprocess, socket, collections
from select import select
from functools import partial
from threading import RLock, Thread, Event

from calibre.ebooks.lrf.any.convert_from import main as any2lrf
from calibre.ebooks.lrf.web.convert_from import main as web2lrf
from calibre.ebooks.lrf.feeds.convert_from import main as feeds2lrf
from calibre.gui2.lrf_renderer.main import main as lrfviewer
from calibre.ptempfile import PersistentTemporaryFile

try:
    from calibre.ebooks.lrf.html.table_as_image import do_render as render_table
except: # Dont fail is PyQt4.4 not present
    render_table = None
from calibre import iswindows, islinux, detect_ncpus

sa = None
job_id = None

def report_progress(percent, msg=''):
    if sa is not None and job_id is not None:
        msg = 'progress:%s:%f:%s'%(job_id, percent, msg)
        sa.send_message(msg)

_notify = 'fskjhwseiuyweoiu987435935-0342'

PARALLEL_FUNCS = {
                  'any2lrf'   : partial(any2lrf, gui_mode=True),
                  'web2lrf'   : web2lrf,
                  'lrfviewer' : lrfviewer,
                  'feeds2lrf' : partial(feeds2lrf, notification=_notify),
                  'render_table': render_table,
                  }

python = sys.executable
popen = subprocess.Popen

if iswindows:
    if hasattr(sys, 'frozen'):
        python = os.path.join(os.path.dirname(python), 'parallel.exe')
    else:
        python = os.path.join(os.path.dirname(python), 'Scripts\\parallel.exe')
    popen = partial(subprocess.Popen, creationflags=0x08) # CREATE_NO_WINDOW=0x08 so that no ugly console is popped up

if islinux and hasattr(sys, 'frozen_path'):
    python = os.path.join(getattr(sys, 'frozen_path'), 'parallel')
    popen = partial(subprocess.Popen, cwd=getattr(sys, 'frozen_path')) 

prefix = 'import sys; sys.in_worker = True; '
if hasattr(sys, 'frameworks_dir'):
    fd = getattr(sys, 'frameworks_dir')
    prefix += 'sys.frameworks_dir = "%s"; sys.frozen = "macosx_app"; '%fd
    if fd not in os.environ['PATH']:
        os.environ['PATH'] += ':'+fd


def write(socket, msg, timeout=5):
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
    
    def repeat(self):
        while True:
            self.event.wait(self.interval)
            if self.event.isSet():
                break
            self.action()
    
    def __init__(self, interval, func):
        self.event    = Event()
        self.interval = interval
        self.action = func  
        Thread.__init__(self, target=self.repeat)
        self.setDaemon(True)
    
class ControlError(Exception):
    pass

class Overseer(object):
    
    KILL_RESULT = 'Server: job killed by user|||#@#$%&*)*(*$#$%#$@&'
    INTERVAL    = 0.1
    
    def __init__(self, server, port, timeout=5):
        self.cmd = prefix + 'from calibre.parallel import worker; worker(%s, %s)'%(repr('localhost'), repr(port))
        self.process = popen([python, '-c', self.cmd])
        self.socket = server.accept()[0]
        
        self.working = False
        self.timeout = timeout
        self.last_job_time = time.time()
        self.job_id = None
        self._stop = False
        if not select([self.socket], [], [], 120)[0]:
            raise RuntimeError(_('Could not launch worker process.'))
        if int(self.read()) != self.process.pid:
            raise RuntimeError('PID mismatch')
        self.write('OK')
        if self.read() != 'WAITING':
            raise RuntimeError('Worker sulking')
        
    def terminate(self):
        '''
        Kill process.
        '''
        try:
            if self.socket:
                self.socket.close()
        except:
            pass
        if iswindows:
            win32api = __import__('win32api')
            try:
                win32api.TerminateProcess(int(self.process.pid), -1)
            except:
                pass
        else:
            import signal
            try:
                os.kill(self.process.pid, signal.SIGKILL)
                time.sleep(0.05)
            except:
                pass
    
        
    def write(self, msg, timeout=None):
        write(self.socket, msg, timeout=self.timeout if timeout is None else timeout)
        
    def read(self, timeout=None):
        return read(self.socket, timeout=self.timeout if timeout is None else timeout)
        
    def __eq__(self, other):
        return hasattr(other, 'process') and hasattr(other.process, 'pid') and self.process.pid == other.process.pid
    
    def __bool__(self):
        self.process.poll()
        return self.process.returncode is None
    
    def pid(self):
        return self.process.pid
    
    def select(self, timeout=0):
        return select([self.socket], [self.socket], [self.socket], timeout)
    
    def initialize_job(self, job):
        self.job_id = job.job_id
        self.working = True
        self.write('JOB:'+cPickle.dumps((job.func, job.args, job.kwdargs), -1))
        msg = self.read()
        if msg != 'OK':
            raise ControlError('Failed to initialize job on worker %d:%s'%(self.process.pid, msg))
        self.output = job.output if callable(job.output) else sys.stdout.write
        self.progress = job.progress if callable(job.progress) else None
        self.job =  job
    
    def control(self):
        try:
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
            self.process.poll()
            if self.process.returncode is not None:
                return Result(None, ControlError('Worker process died unexpectedly with returncode: %d'%self.process.returncode), '')
        finally:
            self.working = False
            self.last_job_time = time.time()
                        
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
        self.job_lock = RLock()
        self.overseer_lock = RLock()
        self.working_lock = RLock()
        self.result_lock = RLock()
        self.pool_lock = RLock()
        self.start()
        
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
                        o = self.pool.pop() if self.pool else Overseer(self.server_socket, self.port)
                    try:
                        o.initialize_job(job)
                    except Exception, err:
                        res = Result(None, unicode(err), traceback.format_exc())
                        job.done(res)
                        o.terminate()
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
                            
            time.sleep(1)            
                
    
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
        cmd = prefix + 'from calibre.parallel import free_spirit; free_spirit(%s)'%repr(pt.name)
        popen([python, '-c', cmd])

##########################################################################################
##################################### CLIENT CODE #####################################
##########################################################################################

class BufferedSender(object):
    
    def __init__(self, socket):
        self.socket = socket
        self.wbuf, self.pbuf    = [], []
        self.wlock, self.plock   = RLock(), RLock()
        self.timer  = RepeatingTimer(0.5, self.send)
        self.prefix = prefix
        self.timer.start()
        
    def write(self, msg):
        if not isinstance(msg, basestring):
            msg = unicode(msg)
        with self.wlock:
            self.wbuf.append(msg)
    
    def send(self):
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

def work(client_socket, func, args, kwdargs):
    func = PARALLEL_FUNCS[func]
    if hasattr(func, 'keywords'):
        for key, val in func.keywords.items():
            if val == _notify:
                func.keywords[key] = sys.stdout.notify
    res = func(*args, **kwdargs)
    sys.stdout.send()
    return res
    
    
    

def worker(host, port):
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client_socket.connect((host, port))
    write(client_socket, str(os.getpid()))
    msg = read(client_socket, timeout=10)
    if msg != 'OK':
        return 1
    write(client_socket, 'WAITING')
    sys.stdout = BufferedSender(client_socket)
    sys.stderr = sys.stdout
        
    while True:
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
        elif msg == 'STOP:':
            return 0
    
def free_spirit(path):
    func, args, kwdargs = cPickle.load(open(path, 'rb'))
    try:
        os.unlink(path)
    except:
        pass
    PARALLEL_FUNCS[func](*args, **kwdargs)
    