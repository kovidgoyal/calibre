from __future__ import with_statement
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

'''
Used to run jobs in parallel in separate processes. Features output streaming,
support for progress notification as well as job killing. The worker processes
are controlled via a simple protocol run over sockets. The control happens
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
returns the result (or exception) to the controller and the protocol reverts to the first mode.

In the second mode, the controller can also send the worker STOP messages, in which case
the worker interrupts the job and dies. The sending of progress and console output messages
is buffered and asynchronous to prevent the job from being IO bound.
'''
import sys, os, gc, cPickle, traceback, cStringIO, time, signal, \
       subprocess, socket, collections, binascii, re, thread, tempfile, atexit
from select import select
from threading import RLock, Thread, Event
from math import ceil

from calibre.ptempfile import PersistentTemporaryFile
from calibre import iswindows, detect_ncpus, isosx, preferred_encoding
from calibre.utils.config import prefs

DEBUG = False

#: A mapping from job names to functions that perform the jobs
PARALLEL_FUNCS = {
      'any2lrf'      :
        ('calibre.ebooks.lrf.any.convert_from', 'main', dict(gui_mode=True), None),

      'lrfviewer'    :
        ('calibre.gui2.lrf_renderer.main', 'main', {}, None),
        
      'ebook-viewer'    :
        ('calibre.gui2.viewer.main', 'main', {}, None),  

      'feeds2lrf'    :
        ('calibre.ebooks.lrf.feeds.convert_from', 'main', {}, 'notification'),

      'render_table' :
        ('calibre.ebooks.lrf.html.table_as_image', 'do_render', {}, None),
        
      'render_pages' :
        ('calibre.ebooks.lrf.comic.convert_from', 'render_pages', {}, 'notification'),

      'comic2lrf'    :
        ('calibre.ebooks.lrf.comic.convert_from', 'do_convert', {}, 'notification'),
        
      'any2epub'     :
        ('calibre.ebooks.epub.from_any', 'any2epub', {}, None),
        
      'feeds2epub'   :
        ('calibre.ebooks.epub.from_feeds', 'main', {}, 'notification'),
        
      'comic2epub'    :
        ('calibre.ebooks.epub.from_comic', 'convert', {}, 'notification'),
        
      'any2mobi'     :
        ('calibre.ebooks.mobi.from_any', 'any2mobi', {}, None),
        
      'feeds2mobi'   :
        ('calibre.ebooks.mobi.from_feeds', 'main', {}, 'notification'),
        
      'comic2mobi'    :
        ('calibre.ebooks.mobi.from_comic', 'convert', {}, 'notification'),
}


isfrozen = hasattr(sys, 'frozen')
isworker = False

win32event   = __import__('win32event') if iswindows else None
win32process = __import__('win32process') if iswindows else None
msvcrt       = __import__('msvcrt') if iswindows else None

SOCKET_TYPE = socket.AF_UNIX if not iswindows else socket.AF_INET

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
            self.executable = self.gui_executable = sys.executable
            self.prefix = ''
            if isfrozen:
                fd = os.path.realpath(getattr(sys, 'frameworks_dir'))
                contents = os.path.dirname(fd)
                self.gui_executable = os.path.join(contents, 'MacOS',
                                               os.path.basename(sys.executable))
                contents = os.path.join(contents, 'console.app', 'Contents')
                self.executable = os.path.join(contents, 'MacOS',
                                               os.path.basename(sys.executable))
                
                resources = os.path.join(contents, 'Resources')
                fd = os.path.join(contents, 'Frameworks')
                sp = os.path.join(resources, 'lib', 'python'+sys.version[:3], 'site-packages.zip')
                self.prefix += 'import sys; sys.frameworks_dir = "%s"; sys.frozen = "macosx_app"; '%fd
                self.prefix += 'sys.path.insert(0, %s); '%repr(sp)
                if fd not in os.environ['PATH']:
                    self.env['PATH']    = os.environ['PATH']+':'+fd
                self.env['PYTHONHOME']  = resources
                self.env['MAGICK_HOME'] = os.path.join(fd, 'ImageMagick')
                self.env['DYLD_LIBRARY_PATH'] = os.path.join(fd, 'ImageMagick', 'lib')
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
        exe = self.gui_executable if type == 'free_spirit' else self.executable
        cmdline = [exe, '-c', self.prefix+script]
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
        priority = {'high':win32process.HIGH_PRIORITY_CLASS, 'normal':win32process.NORMAL_PRIORITY_CLASS,
                    'low':win32process.IDLE_PRIORITY_CLASS}[prefs['worker_process_priority']]
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
            win32process.CREATE_NO_WINDOW|priority, # Dont want ugly console popping up
            self.get_env(), # New environment
            None,    # Current directory
            si
        )[0]
        child = WorkerStatus(hProcess)
        atexit.register(self.cleanup_child_windows, child, name, fd)
        return child


mother = WorkerMother()

_comm_lock = RLock()
def write(socket, msg, timeout=5):
    '''
    Write a message on socket. If `msg` is unicode, it is encoded in utf-8.
    Raises a `RuntimeError` if the socket is not ready for writing or the writing fails.
    `msg` is broken into chunks of size 4096 and sent. The :function:`read` function
    automatically re-assembles the chunks into whole message.
    '''
    if isworker:
        _comm_lock.acquire()
    try:
        if isinstance(msg, unicode):
            msg = msg.encode('utf-8')
        if DEBUG:
            print >>sys.__stdout__, 'write(%s):'%('worker' if isworker else 'overseer'), repr(msg)
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
    finally:
        if isworker:
            _comm_lock.release()

def read(socket, timeout=5):
    '''
    Read a message from `socket`. The message must have been sent with the :function:`write`
    function. Raises a `RuntimeError` if the message is corrupted. Can return an
    empty string.
    '''
    if isworker:
        _comm_lock.acquire()
    try:
        buf = cStringIO.StringIO()
        length = None
        while select([socket],[],[],timeout)[0]:
            msg = socket.recv(4096)
            if not msg:
                break
            if length is None:
                try:
                    length, msg = int(msg[:12]), msg[12:]
                except ValueError:
                    if DEBUG:
                        print >>sys.__stdout__, 'read(%s):'%('worker' if isworker else 'overseer'), 'no length in', msg
                    return ''
            buf.write(msg)
            if buf.tell() >= length:
                break
        if not length:
            if DEBUG:
                print >>sys.__stdout__, 'read(%s):'%('worker' if isworker else 'overseer'), 'nothing'
            return ''
        msg = buf.getvalue()[:length]
        if len(msg) < length:
            raise RuntimeError('Corrupted packet received')
        if DEBUG:
            print >>sys.__stdout__, 'read(%s):'%('worker' if isworker else 'overseer'), repr(msg)
        return msg
    finally:
        if isworker:
            _comm_lock.release()

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
        self.worker_status = mother.spawn_worker('127.0.0.1:'+str(port))
        self.socket = server.accept()[0]
        # Needed if terminate called when interpreter is shutting down
        self.os = os
        self.signal = signal
        self.on_probation = False
        self.terminated = False

        self.working = False
        self.timeout = timeout
        self.last_job_time = time.time()
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
        self.terminated = True
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

    def is_viable(self):
        if self.terminated:
            return False
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
        self.working = True
        self.write('JOB:'+cPickle.dumps((job.func, job.args, job.kwargs), -1))
        msg = self.read()
        if msg != 'OK':
            raise ControlError('Failed to initialize job on worker %d:%s'%(self.worker_pid, msg))
        self.job =  job
        self.last_report = time.time()
        job.start_work()

    def control(self):
        '''
        Listens for messages from the worker process and dispatches them
        appropriately. If the worker process dies unexpectedly, returns a result
        of None with a ControlError indicating the worker died.

        Returns a :class:`Result` instance or None, if the worker is still working.
        '''
        if select([self.socket],[],[],0)[0]:
            msg = self.read()
            if msg:
                self.on_probation = False
                self.last_report = time.time()
            else:
                if self.on_probation:
                    self.terminate()
                    self.job.result = None
                    self.job.exception = ControlError('Worker process died unexpectedly')
                    return
                else:
                    self.on_probation = True
                    return
            word, msg = msg.partition(':')[0], msg.partition(':')[-1]
            if word == 'PING':
                self.write('OK')
                return
            elif word == 'RESULT':
                self.write('OK')
                self.job.result = cPickle.loads(msg)
                return True
            elif word == 'OUTPUT':
                self.write('OK')
                try:
                    self.job.output(''.join(cPickle.loads(msg)))
                except:
                    self.job.output('Bad output message: '+ repr(msg))
            elif word == 'PROGRESS':
                self.write('OK')
                percent = None
                try:
                    percent, msg = cPickle.loads(msg)[-1]
                except:
                    print 'Bad progress update:', repr(msg)
                if percent is not None:
                    self.job.update_status(percent, msg)
            elif word == 'ERROR':
                self.write('OK')
                exception, traceback = cPickle.loads(msg)
                self.job.output(u'%s\n%s'%(exception, traceback))
                self.job.exception, self.job.traceback = exception, traceback
                return True
            else:
                self.terminate()
                self.job.exception = ControlError('Worker sent invalid msg: %s'%repr(msg))
                return
        if not self.worker_status.is_alive() or time.time() - self.last_report > 380:
            self.terminate()
            self.job.exception = ControlError('Worker process died unexpectedly')
            return

class JobKilled(Exception):
    pass

class Job(object):
    
    def __init__(self, job_done, job_manager=None, 
                 args=[], kwargs={}, description=None):
        self.args            = args
        self.kwargs          = kwargs
        self._job_done       = job_done
        self.job_manager     = job_manager
        self.is_running      = False
        self.has_run         = False
        self.percent         = -1
        self.msg             = None
        self.description     = description
        self.start_time      = None
        self.running_time    = None
        
        self.result = self.exception = self.traceback = self.log = None
    
    def __cmp__(self, other):
        sstatus, ostatus = self.status(), other.status()
        if sstatus == ostatus or (self.has_run and other.has_run):
            if self.start_time == other.start_time:
                return cmp(id(self), id(other))
            return cmp(self.start_time, other.start_time)
        if sstatus == 'WORKING':
            return -1
        if ostatus == 'WORKING':
            return 1
        if sstatus == 'WAITING':
            return -1
        if ostatus == 'WAITING':
            return 1
        
    
    def job_done(self):
        self.is_running, self.has_run = False, True
        self.running_time = (time.time() - self.start_time) if \
                                    self.start_time is not None else 0
        if self.job_manager is not None:
            self.job_manager.job_done(self)
        self._job_done(self)
        
    def start_work(self):
        self.is_running = True
        self.has_run    = False
        self.start_time = time.time()
        if self.job_manager is not None:
            self.job_manager.start_work(self)
    
    def update_status(self, percent, msg=None):
        self.percent = percent
        self.msg     = msg
        if self.job_manager is not None:
            try:
                self.job_manager.status_update(self)
            except:
                traceback.print_exc()
        
    def status(self):
        if self.is_running:
            return 'WORKING'
        if not self.has_run:
            return 'WAITING'
        if self.has_run:
            if self.exception is None:
                return 'DONE'
            return 'ERROR'
            
    def console_text(self):
        ans = [u'Job: ']
        if self.description:
            ans[0] += self.description
        if self.exception is not None:
            header = unicode(self.exception.__class__.__name__) if \
                    hasattr(self.exception, '__class__') else u'Error'
            header = u'**%s**'%header
            header += u': '
            try:
                header += unicode(self.exception)
            except:
                header += unicode(repr(self.exception))
            ans.append(header)
            if self.traceback:
                ans.append(u'**Traceback**:')
                ans.extend(self.traceback.split('\n'))
        
        if self.log:
            if isinstance(self.log, str):
                self.log = unicode(self.log, 'utf-8', 'replace')
            ans.append(self.log)
        return (u'\n'.join(ans)).encode('utf-8')
    
    def gui_text(self):
        ans = [u'Job: ']
        if self.description:
            if not isinstance(self.description, unicode):
                self.description = self.description.decode('utf-8', 'replace')
            ans[0] += u'**%s**'%self.description
        if self.exception is not None:
            header = unicode(self.exception.__class__.__name__) if \
                    hasattr(self.exception, '__class__') else u'Error'
            header = u'**%s**'%header
            header += u': '
            try:
                header += unicode(self.exception)
            except:
                header += unicode(repr(self.exception))
            ans.append(header)
            if self.traceback:
                ans.append(u'**Traceback**:')
                ans.extend(self.traceback.split('\n'))
        if self.log:
            ans.append(u'**Log**:')
            if isinstance(self.log, str):
                self.log = unicode(self.log, 'utf-8', 'replace')
            ans.extend(self.log.split('\n'))
        
        ans = [x.decode(preferred_encoding, 'replace') if isinstance(x, str) else x for x in ans]
        
        return u'<br>'.join(ans)


class ParallelJob(Job):
    
    def __init__(self, func, *args, **kwargs):
        Job.__init__(self, *args, **kwargs)
        self.func = func
        self.done = self.job_done
        
    def output(self, msg):
        if not self.log:
            self.log = u''
        if not isinstance(msg, unicode):
            msg = msg.decode('utf-8', 'replace')
        if msg:
            self.log += msg
        if self.job_manager is not None:
            self.job_manager.output(self)
    

def remove_ipc_socket(path):
    os = __import__('os')
    if os.path.exists(path):
        os.unlink(path)

class Server(Thread):

    KILL_RESULT = Overseer.KILL_RESULT
    START_PORT = 10013
    PID = os.getpid()


    def __init__(self, number_of_workers=detect_ncpus()):
        Thread.__init__(self)
        self.setDaemon(True)
        self.server_socket = socket.socket(SOCKET_TYPE, socket.SOCK_STREAM)
        self.port = tempfile.mktemp(prefix='calibre_server')+'_%d_'%self.PID if not iswindows else self.START_PORT
        while True:
            try:
                address = ('localhost', self.port) if iswindows else self.port
                self.server_socket.bind(address)
                break
            except socket.error:
                self.port += (1 if iswindows else '1')
        if not iswindows:
            atexit.register(remove_ipc_socket, self.port)
        self.server_socket.listen(5)
        self.number_of_workers = number_of_workers
        self.pool, self.jobs, self.working = [], collections.deque(), []
        atexit.register(self.killall)
        atexit.register(self.close)
        self.job_lock = RLock()
        self.overseer_lock = RLock()
        self.working_lock = RLock()
        self.result_lock = RLock()
        self.pool_lock = RLock()
        self.start()
        
    def split(self, tasks):
        '''
        Split a list into a list of sub lists, with the number of sub lists being
        no more than the number of workers this server supports. Each sublist contains
        two tuples of the form (i, x) where x is an element fro the original list
        and i is the index of the element x in the original list.
        '''
        ans, count, pos = [], 0, 0
        delta = int(ceil(len(tasks)/float(self.number_of_workers)))
        while count < len(tasks):
            section = []
            for t in tasks[pos:pos+delta]:
                section.append((count, t))
                count += 1
            ans.append(section)
            pos += delta
        return ans
        

    def close(self):
        try:
            self.server_socket.shutdown(socket.SHUT_RDWR)
        except:
            pass

    def add_job(self, job):
        with self.job_lock:
            self.jobs.append(job)
        if job.job_manager is not None:
            job.job_manager.add_job(job)
            
    def poll(self):
        '''
        Return True if the server has either working or queued jobs
        '''
        with self.job_lock:
            with self.working_lock:
                return len(self.jobs) + len(self.working) > 0
            
    def wait(self, sleep=1):
        '''
        Wait until job queue is empty
        '''
        while self.poll():
            time.sleep(sleep)
    
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
                                job.exception = err
                                job.traceback = traceback.format_exc()
                                job.done()
                                o = None
                    if o and o.is_viable():
                        with self.working_lock:
                            self.working.append(o)

            with self.working_lock:
                done = []
                for o in self.working:
                    try:
                        if o.control() is not None or o.job.exception is not None:
                            o.job.done()
                            done.append(o)
                    except Exception, err:
                        o.job.exception = err
                        o.job.traceback = traceback.format_exc()
                        o.terminate()
                        o.job.done()
                        done.append(o)
                for o in done:
                    self.working.remove(o)
                    if o and o.is_viable():
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


    def kill(self, job):
        with self.working_lock:
            pop = None
            for o in self.working:
                if o.job == job or o == job:
                    try:
                        o.terminate()
                    except: pass
                    o.job.exception = JobKilled(_('Job stopped by user'))
                    try:
                        o.job.done()
                    except: pass
                    pop = o
                    break
            if pop is not None:
                self.working.remove(pop)

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
        self.last_report = None
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

        reported = False
        with self.wlock:
            if self.wbuf:
                msg = cPickle.dumps(self.wbuf, -1)
                self.wbuf = []
                write(self.socket, 'OUTPUT:'+msg)
                read(self.socket, 10)
                reported = True

        with self.plock:
            if self.pbuf:
                msg = cPickle.dumps(self.pbuf, -1)
                self.pbuf = []
                write(self.socket, 'PROGRESS:'+msg)
                read(self.socket, 10)
                reported = True

        if self.last_report is not None:
            if reported:
                self.last_report = time.time()
            elif time.time() - self.last_report > 60:
                write(self.socket, 'PING:')
                read(self.socket, 10)
                self.last_report = time.time()

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

_atexit = collections.deque()
def myatexit(func, *args, **kwargs):
    _atexit.append((func, args, kwargs))

def work(client_socket, func, args, kwdargs):
    sys.stdout.last_report = time.time()
    orig = atexit.register
    atexit.register = myatexit
    try:
        func, kargs, notification = get_func(func)
        if notification is not None and hasattr(sys.stdout, 'notify'):
            kargs[notification] = sys.stdout.notify
        kargs.update(kwdargs)
        res = func(*args, **kargs)
        if hasattr(sys.stdout, 'send'):
            sys.stdout.send()
        return res
    finally:
        atexit.register = orig
        sys.stdout.last_report = None
        while True:
            try:
                func, args, kwargs = _atexit.pop()
            except IndexError:
                break
            try:
                func(*args, **kwargs)
            except (Exception, SystemExit):
                continue
                
        time.sleep(5) # Give any in progress BufferedSend time to complete


def worker(host, port):
    client_socket = socket.socket(SOCKET_TYPE, socket.SOCK_STREAM)
    address = (host, port) if iswindows else port
    client_socket.connect(address)
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
            except BaseException, err:
                exception = (err.__class__.__name__, unicode(str(err), 'utf-8', 'replace'))
                tb = unicode(traceback.format_exc(), 'utf-8', 'replace')
                msg = 'ERROR:'+cPickle.dumps((exception, tb),-1)
                write(client_socket, msg)
            res = read(client_socket, 10)
            if res != 'OK':
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
    global isworker
    isworker = True
    args = args[1].split(':')
    if len(args) == 1:
        free_spirit(binascii.unhexlify(re.sub(r'[^a-f0-9A-F]', '', args[0])))
    else:
        worker(args[0].replace("'", ''), int(args[1]) if iswindows else args[1])
    return 0

if __name__ == '__main__':
    sys.exit(main())

