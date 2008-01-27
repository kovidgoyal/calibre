##    Copyright (C) 2008 Kovid Goyal kovid@kovidgoyal.net
##    This program is free software; you can redistribute it and/or modify
##    it under the terms of the GNU General Public License as published by
##    the Free Software Foundation; either version 2 of the License, or
##    (at your option) any later version.
##
##    This program is distributed in the hope that it will be useful,
##    but WITHOUT ANY WARRANTY; without even the implied warranty of
##    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
##    GNU General Public License for more details.
##
##    You should have received a copy of the GNU General Public License along
##    with this program; if not, write to the Free Software Foundation, Inc.,
##    51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
'''
Used to run jobs in parallel in separate processes.
'''
import re, sys, tempfile, os, subprocess, cPickle, cStringIO, traceback, atexit, time, binascii
from functools import partial
from libprs500.ebooks.lrf.any.convert_from import main as any2lrf
from libprs500.ebooks.lrf.web.convert_from import main as web2lrf
from libprs500 import iswindows

PARALLEL_FUNCS = {
                  'any2lrf' : partial(any2lrf, gui_mode=True),
                  'web2lrf' : web2lrf,
                  }
Popen = subprocess.Popen

python = sys.executable
if iswindows:
    import win32con
    Popen = partial(Popen, creationflags=win32con.CREATE_NO_WINDOW)
    if hasattr(sys, 'frozen'):
        python = os.path.join(os.path.dirname(python), 'parallel.exe')
    else:
        python = os.path.join(os.path.dirname(python), 'Scripts\\parallel.exe')

def cleanup(tdir):
    try:
        import shutil
        shutil.rmtree(tdir, True)
    except:
        pass

class Server(object):
    
    def __init__(self):
        self.tdir = tempfile.mkdtemp('', 'libprs500_IPC_')
        atexit.register(cleanup, self.tdir)
        self.stdout = {}
        
    def run(self, job_id, func, args=(), kwdargs={}):
        job_id = str(job_id)
        job_dir = os.path.join(self.tdir, job_id)
        if os.path.exists(job_dir):
            raise ValueError('Cannot run job. The job_id %s has already been used.')
        os.mkdir(job_dir)
        self.stdout[job_id] = cStringIO.StringIO()
        
        job_data = os.path.join(job_dir, 'job_data.pickle')
        cPickle.dump((func, args, kwdargs), open(job_data, 'wb'), -1)
        prefix = ''
        if hasattr(sys, 'frameworks_dir'):
            fd = getattr(sys, 'frameworks_dir')
            prefix = 'import sys; sys.frameworks_dir = "%s"; sys.frozen = "macosx_app"; '%fd
            if fd not in os.environ['PATH']:
                os.environ['PATH'] += ':'+fd
        cmd = prefix + 'from libprs500.parallel import run_job; run_job(\'%s\')'%binascii.hexlify(job_data)
        
        p = Popen((python, '-c', cmd), stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        while p.returncode is None:
            self.stdout[job_id].write(p.stdout.readline())
            p.poll()
            time.sleep(0.5) # Wait for half a second
        self.stdout[job_id].write(p.stdout.read())
        
        job_result = os.path.join(job_dir, 'job_result.pickle')
        if not os.path.exists(job_result):
            result, exception, traceback = None, ('ParallelRuntimeError', 'The worker process died unexpectedly.'), ''
        else:              
            result, exception, traceback = cPickle.load(open(job_result, 'rb'))
        log = self.stdout[job_id].getvalue()
        self.stdout.pop(job_id)
        return result, exception, traceback, log
            
    
def run_job(job_data):
    job_data = binascii.unhexlify(job_data)
    job_result = os.path.join(os.path.dirname(job_data), 'job_result.pickle')
    func, args, kwdargs = cPickle.load(open(job_data, 'rb'))
    func = PARALLEL_FUNCS[func]
    exception, tb = None, None
    try:
        result = func(*args, **kwdargs)
    except (Exception, SystemExit), err:
        result = None
        exception = (err.__class__.__name__, unicode(str(err), 'utf-8', 'replace'))
        tb = traceback.format_exc()
    
    cPickle.dump((result, exception, tb), open(job_result, 'wb'))
    
def main():
    src = sys.argv[2]
    job_data = re.search(r'run_job\(\'([a-f0-9A-F]+)\'\)', src).group(1)
    run_job(job_data)
    
    return 0
    
if __name__ == '__main__':
    sys.exit(main())