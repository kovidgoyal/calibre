__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
'''
Used to run jobs in parallel in separate processes.
'''
import re, sys, tempfile, os, cPickle, traceback, atexit, binascii, time, subprocess
from functools import partial


from calibre.ebooks.lrf.any.convert_from import main as any2lrf
from calibre.ebooks.lrf.web.convert_from import main as web2lrf
from calibre.ebooks.lrf.feeds.convert_from import main as feeds2lrf
from calibre.gui2.lrf_renderer.main import main as lrfviewer
from calibre import iswindows, __appname__
try:
    from calibre.utils.single_qt_application import SingleApplication
except:
    SingleApplication = None

sa = None
job_id = None

def report_progress(percent, msg=''):
    if sa is not None and job_id is not None:
        msg = 'progress:%s:%f:%s'%(job_id, percent, msg)
        sa.send_message(msg)


PARALLEL_FUNCS = {
                  'any2lrf'   : partial(any2lrf, gui_mode=True),
                  'web2lrf'   : web2lrf,
                  'lrfviewer' : lrfviewer,
                  'feeds2lrf' : partial(feeds2lrf, notification=report_progress),
                  }

python = sys.executable
popen = subprocess.Popen

if iswindows:
    if hasattr(sys, 'frozen'):
        python = os.path.join(os.path.dirname(python), 'parallel.exe')
    else:
        python = os.path.join(os.path.dirname(python), 'Scripts\\parallel.exe')
    popen = partial(subprocess.Popen, creationflags=0x08) # CREATE_NO_WINDOW=0x08 so that no ugly console is popped up 

def cleanup(tdir):
    try:
        import shutil
        shutil.rmtree(tdir, True)
    except:
        pass

class Server(object):
    
    #: Interval in seconds at which child processes are polled for status information
    INTERVAL = 0.1
    KILL_RESULT = 'Server: job killed by user|||#@#$%&*)*(*$#$%#$@&'
    
    def __init__(self):
        self.tdir = tempfile.mkdtemp('', '%s_IPC_'%__appname__)
        atexit.register(cleanup, self.tdir)
        self.kill_jobs = []
        
    def kill(self, job_id):
        '''
        Kill the job identified by job_id.
        '''
        self.kill_jobs.append(str(job_id))
        
    def _terminate(self, process):
        '''
        Kill process.
        '''
        if iswindows:
            win32api = __import__('win32api')
            try:
                win32api.TerminateProcess(int(process.pid), -1)
            except:
                pass
        else:
            import signal
            os.kill(process.pid, signal.SIGKILL)
            time.sleep(0.05)
        
        
    
    def run(self, job_id, func, args=[], kwdargs={}, monitor=True):
        '''
        Run a job in a separate process.
        @param job_id: A unique (per server) identifier
        @param func: One of C{PARALLEL_FUNCS.keys()}
        @param args: A list of arguments to pass of C{func}
        @param kwdargs: A dictionary of keyword arguments to pass to C{func}
        @param monitor: If False launch the child process and return. Do not monitor/communicate with it.
        @return: (result, exception, formatted_traceback, log) where log is the combined
        stdout + stderr of the child process; or None if monitor is True. If a job is killed
        by a call to L{kill()} then result will be L{KILL_RESULT}
        '''
        job_id = str(job_id)
        job_dir = os.path.join(self.tdir, job_id)
        if os.path.exists(job_dir):
            raise ValueError('Cannot run job. The job_id %s has already been used.'%job_id)
        os.mkdir(job_dir)
        
        job_data = os.path.join(job_dir, 'job_data.pickle')
        cPickle.dump((job_id, func, args, kwdargs), open(job_data, 'wb'), -1)
        prefix = ''
        if hasattr(sys, 'frameworks_dir'):
            fd = getattr(sys, 'frameworks_dir')
            prefix = 'import sys; sys.frameworks_dir = "%s"; sys.frozen = "macosx_app"; '%fd
            if fd not in os.environ['PATH']:
                os.environ['PATH'] += ':'+fd
        cmd = prefix + 'from calibre.parallel import run_job; run_job(\'%s\')'%binascii.hexlify(job_data)
        
        if not monitor:
            popen([python, '-c', cmd], stdout=subprocess.PIPE, stdin=subprocess.PIPE,
                  stderr=subprocess.PIPE)
            return
        
        output = open(os.path.join(job_dir, 'output.txt'), 'wb')
        p = popen([python, '-c', cmd], stdout=output, stderr=output,
                             stdin=subprocess.PIPE)
        p.stdin.close()
        while p.returncode is None:
            if job_id in self.kill_jobs:
                self._terminate(p)
                return self.KILL_RESULT, None, None, _('Job killed by user')
            time.sleep(0.1)
            p.poll()
        
             
        output.close()
        job_result = os.path.join(job_dir, 'job_result.pickle')
        if not os.path.exists(job_result):
            result, exception, traceback = None, ('ParallelRuntimeError',
                                                  'The worker process died unexpectedly.'), ''
        else:
            result, exception, traceback = cPickle.load(open(job_result, 'rb'))
        log = open(output.name, 'rb').read()
        
        return result, exception, traceback, log
            

def run_job(job_data):
    global sa, job_id
    if SingleApplication is not None:
        sa = SingleApplication('calibre GUI')
    job_data = binascii.unhexlify(job_data)
    base = os.path.dirname(job_data)
    job_result = os.path.join(base, 'job_result.pickle')
    job_id, func, args, kwdargs = cPickle.load(open(job_data, 'rb'))
    func = PARALLEL_FUNCS[func]
    exception, tb = None, None
    try:
        result = func(*args, **kwdargs)
    except (Exception, SystemExit), err:
        result = None
        exception = (err.__class__.__name__, unicode(str(err), 'utf-8', 'replace'))
        tb = traceback.format_exc()
    
    if os.path.exists(os.path.dirname(job_result)):
        cPickle.dump((result, exception, tb), open(job_result, 'wb'))
    
def main():
    src = sys.argv[2]
    job_data = re.search(r'run_job\(\'([a-f0-9A-F]+)\'\)', src).group(1)
    run_job(job_data)
    
    return 0
    
if __name__ == '__main__':
    sys.exit(main())


