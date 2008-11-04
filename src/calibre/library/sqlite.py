from __future__ import with_statement
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

'''
Wrapper for multi-threaded access to a single sqlite database connection. Serializes
all calls.
'''
import sqlite3 as sqlite, traceback, time
from sqlite3 import IntegrityError
from threading import Thread
from Queue import Queue
from threading import RLock

from calibre.library import title_sort

global_lock = RLock()

class Concatenate(object):
    '''String concatenation aggregator for sqlite'''
    def __init__(self, sep=','):
        self.sep = sep
        self.ans = ''
        
    def step(self, value):
        if value is not None:
            self.ans += value + self.sep
    
    def finalize(self):
        if not self.ans:
            return None
        if self.sep:
            return self.ans[:-len(self.sep)]
        return self.ans

class Connection(sqlite.Connection):
    
    def get(self, *args, **kw):
        ans = self.execute(*args)
        if not kw.get('all', True):
            ans = ans.fetchone()
            if not ans:
                ans = [None]
            return ans[0]
        return ans.fetchall()
 

class DBThread(Thread):
    
    CLOSE = '-------close---------'
    
    def __init__(self, path, row_factory):
        Thread.__init__(self)
        self.setDaemon(True)
        self.path = path
        self.unhandled_error = (None, '')
        self.row_factory = row_factory
        self.requests = Queue(1)
        self.results  = Queue(1)
        self.conn = None
        
    def connect(self):
        self.conn = sqlite.connect(self.path, factory=Connection, 
                                   detect_types=sqlite.PARSE_DECLTYPES|sqlite.PARSE_COLNAMES)
        self.conn.row_factory = sqlite.Row if self.row_factory else  lambda cursor, row : list(row)
        self.conn.create_aggregate('concat', 1, Concatenate)
        self.conn.create_function('title_sort', 1, title_sort)
    
    def run(self):
        try:
            self.connect()
            while True:
                func, args, kwargs = self.requests.get()
                if func == self.CLOSE:
                    self.conn.close()
                    break
                func = getattr(self.conn, func)
                try:
                    ok, res = True, func(*args, **kwargs)
                except Exception, err:
                    ok, res = False, (err, traceback.format_exc())
                self.results.put((ok, res))
        except Exception, err:
            self.unhandled_error = (err, traceback.format_exc())

class DatabaseException(Exception):
    
    def __init__(self, err, tb):
        tb = '\n\t'.join(('\tRemote'+tb).splitlines())
        msg = unicode(err) +'\n' + tb
        Exception.__init__(self, msg)
        self.orig_err = err
        self.orig_tb  = tb

def proxy(fn):
    ''' Decorator to call methods on the database connection in the proxy thread '''
    def run(self, *args, **kwargs):
        with global_lock:
            if self.proxy.unhandled_error[0] is not None:
                raise DatabaseException(*self.proxy.unhandled_error)
            self.proxy.requests.put((fn.__name__, args, kwargs))
            ok, res = self.proxy.results.get()
            if not ok:
                if isinstance(res[0], IntegrityError):
                    raise IntegrityError(unicode(res[0]))
                raise DatabaseException(*res)
            return res
    return run
            

class ConnectionProxy(object):
    
    def __init__(self, proxy):
        self.proxy = proxy
    
    def close(self):
        if self.proxy.unhandled_error is None:
            self.proxy.requests.put((self.proxy.CLOSE, [], {}))
    
    @proxy
    def get(self, query, all=True): pass
    
    @proxy        
    def commit(self): pass
    
    @proxy
    def execute(self): pass
    
    @proxy
    def executemany(self): pass
    
    @proxy
    def executescript(self): pass
    
    @proxy
    def create_aggregate(self): pass
    
    @proxy
    def create_function(self): pass
    
    @proxy
    def cursor(self): pass
    
def connect(dbpath, row_factory=None):
    conn = ConnectionProxy(DBThread(dbpath, row_factory))
    conn.proxy.start()
    while conn.proxy.unhandled_error[0] is None and conn.proxy.conn is None:
        time.sleep(0.01)
    if conn.proxy.unhandled_error[0] is not None:
        raise DatabaseException(*conn.proxy.unhandled_error)
    return conn