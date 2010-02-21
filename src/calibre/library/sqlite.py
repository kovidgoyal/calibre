from __future__ import with_statement
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

'''
Wrapper for multi-threaded access to a single sqlite database connection. Serializes
all calls.
'''
import sqlite3 as sqlite, traceback, time, uuid
from sqlite3 import IntegrityError, OperationalError
from threading import Thread
from Queue import Queue
from threading import RLock
from datetime import datetime

from calibre.ebooks.metadata import title_sort
from calibre.utils.date import parse_date, isoformat

global_lock = RLock()

def convert_timestamp(val):
    return parse_date(val, as_utc=False)

def adapt_datetime(dt):
    return isoformat(dt)

sqlite.register_adapter(datetime, adapt_datetime)
sqlite.register_converter('timestamp', convert_timestamp)

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

class SortedConcatenate(object):
    '''String concatenation aggregator for sqlite, sorted by supplied index'''
    def __init__(self, sep=','):
        self.sep = sep
        self.ans = {}

    def step(self, ndx, value):
        if value is not None:
            self.ans[ndx] = value

    def finalize(self):
        if len(self.ans) == 0:
            return None
        return self.sep.join(map(self.ans.get, sorted(self.ans.keys())))

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
        self.conn.create_aggregate('sortconcat', 2, SortedConcatenate)
        self.conn.create_function('title_sort', 1, title_sort)
        self.conn.create_function('uuid4', 0, lambda : str(uuid.uuid4()))

    def run(self):
        try:
            self.connect()
            while True:
                func, args, kwargs = self.requests.get()
                if func == self.CLOSE:
                    self.conn.close()
                    break
                if func == 'dump':
                    try:
                        ok, res = True, '\n'.join(self.conn.iterdump())
                    except Exception, err:
                        ok, res = False, (err, traceback.format_exc())
                else:
                    func = getattr(self.conn, func)
                    try:
                        for i in range(3):
                            try:
                                ok, res = True, func(*args, **kwargs)
                                break
                            except OperationalError, err:
                                # Retry if unable to open db file
                                if 'unable to open' not in str(err) or i == 2:
                                    raise
                                traceback.print_exc()
                            time.sleep(0.5)
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
        if self.closed:
            raise DatabaseException('Connection closed', '')
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
        self.closed = False

    def close(self):
        if self.proxy.unhandled_error[0] is None:
            self.proxy.requests.put((self.proxy.CLOSE, [], {}))
            self.closed = True

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

    @proxy
    def dump(self): pass

def connect(dbpath, row_factory=None):
    conn = ConnectionProxy(DBThread(dbpath, row_factory))
    conn.proxy.start()
    while conn.proxy.unhandled_error[0] is None and conn.proxy.conn is None:
        time.sleep(0.01)
    if conn.proxy.unhandled_error[0] is not None:
        raise DatabaseException(*conn.proxy.unhandled_error)
    return conn
