from __future__ import with_statement
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

'''
Wrapper for multi-threaded access to a single sqlite database connection. Serializes
all calls.
'''
import sqlite3 as sqlite, traceback, time, uuid, sys, os
import repr as reprlib
from sqlite3 import IntegrityError, OperationalError
from threading import Thread
from Queue import Queue
from threading import RLock
from datetime import datetime
from functools import partial

from calibre.ebooks.metadata import title_sort, author_to_author_sort
from calibre.utils.date import parse_date, isoformat, local_tz, UNDEFINED_DATE
from calibre import isbytestring, force_unicode
from calibre.constants import iswindows, DEBUG, plugins
from calibre.utils.icu import sort_key
from calibre import prints

from dateutil.tz import tzoffset

global_lock = RLock()

_c_speedup = plugins['speedup'][0]

def _c_convert_timestamp(val):
    if not val:
        return None
    try:
        ret = _c_speedup.parse_date(val.strip())
    except:
        ret = None
    if ret is None:
        return parse_date(val, as_utc=False)
    year, month, day, hour, minutes, seconds, tzsecs = ret
    try:
        return datetime(year, month, day, hour, minutes, seconds,
                tzinfo=tzoffset(None, tzsecs)).astimezone(local_tz)
    except OverflowError:
        return UNDEFINED_DATE.astimezone(local_tz)

def _py_convert_timestamp(val):
    if val:
        tzsecs = 0
        try:
            sign = {'+':1, '-':-1}.get(val[-6], None)
            if sign is not None:
                tzsecs = 60*((int(val[-5:-3])*60 + int(val[-2:])) * sign)
            year = int(val[0:4])
            month = int(val[5:7])
            day = int(val[8:10])
            hour = int(val[11:13])
            min = int(val[14:16])
            sec = int(val[17:19])
            return datetime(year, month, day, hour, min, sec,
                    tzinfo=tzoffset(None, tzsecs))
        except:
            pass
        return parse_date(val, as_utc=False)
    return None

convert_timestamp = _py_convert_timestamp if _c_speedup is None else \
                    _c_convert_timestamp

def adapt_datetime(dt):
    return isoformat(dt, sep=' ')

sqlite.register_adapter(datetime, adapt_datetime)
sqlite.register_converter('timestamp', convert_timestamp)

def convert_bool(val):
    return val != '0'

sqlite.register_adapter(bool, lambda x : 1 if x else 0)
sqlite.register_converter('bool', convert_bool)
sqlite.register_converter('BOOL', convert_bool)

class DynamicFilter(object):

    def __init__(self, name):
        self.name = name
        self.ids = frozenset([])

    def __call__(self, id_):
        return int(id_ in self.ids)

    def change(self, ids):
        self.ids = frozenset(ids)


class Concatenate(object):
    '''String concatenation aggregator for sqlite'''
    def __init__(self, sep=','):
        self.sep = sep
        self.ans = []

    def step(self, value):
        if value is not None:
            self.ans.append(value)

    def finalize(self):
        if not self.ans:
            return None
        return self.sep.join(self.ans)

class SortedConcatenate(object):
    '''String concatenation aggregator for sqlite, sorted by supplied index'''
    sep = ','
    def __init__(self):
        self.ans = {}

    def step(self, ndx, value):
        if value is not None:
            self.ans[ndx] = value

    def finalize(self):
        if len(self.ans) == 0:
            return None
        return self.sep.join(map(self.ans.get, sorted(self.ans.keys())))

class SortedConcatenateBar(SortedConcatenate):
    sep = '|'

class SortedConcatenateAmper(SortedConcatenate):
    sep = '&'

class IdentifiersConcat(object):
    '''String concatenation aggregator for the identifiers map'''
    def __init__(self):
        self.ans = []

    def step(self, key, val):
        self.ans.append(u'%s:%s'%(key, val))

    def finalize(self):
        return ','.join(self.ans)


class AumSortedConcatenate(object):
    '''String concatenation aggregator for the author sort map'''
    def __init__(self):
        self.ans = {}

    def step(self, ndx, author, sort, link):
        if author is not None:
            self.ans[ndx] = ':::'.join((author, sort, link))

    def finalize(self):
        keys = self.ans.keys()
        l = len(keys)
        if l == 0:
            return None
        if l == 1:
            return self.ans[keys[0]]
        return ':#:'.join([self.ans[v] for v in sorted(keys)])

class Connection(sqlite.Connection):

    def get(self, *args, **kw):
        ans = self.execute(*args)
        if not kw.get('all', True):
            ans = ans.fetchone()
            if not ans:
                ans = [None]
            return ans[0]
        return ans.fetchall()

def _author_to_author_sort(x):
    if not x: return ''
    return author_to_author_sort(x.replace('|', ','))

def pynocase(one, two, encoding='utf-8'):
    if isbytestring(one):
        try:
            one = one.decode(encoding, 'replace')
        except:
            pass
    if isbytestring(two):
        try:
            two = two.decode(encoding, 'replace')
        except:
            pass
    return cmp(one.lower(), two.lower())

def icu_collator(s1, s2):
    return cmp(sort_key(force_unicode(s1, 'utf-8')),
               sort_key(force_unicode(s2, 'utf-8')))

def load_c_extensions(conn, debug=DEBUG):
    try:
        conn.enable_load_extension(True)
        ext_path = os.path.join(sys.extensions_location, 'sqlite_custom.'+
                ('pyd' if iswindows else 'so'))
        conn.load_extension(ext_path)
        conn.enable_load_extension(False)
        return True
    except Exception as e:
        if debug:
            print 'Failed to load high performance sqlite C extension'
            print e
    return False


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
        self.conn.execute('pragma cache_size=5000')
        encoding = self.conn.execute('pragma encoding').fetchone()[0]
        self.conn.create_aggregate('sortconcat', 2, SortedConcatenate)
        self.conn.create_aggregate('sortconcat_bar', 2, SortedConcatenateBar)
        self.conn.create_aggregate('sortconcat_amper', 2, SortedConcatenateAmper)
        self.conn.create_aggregate('identifiers_concat', 2, IdentifiersConcat)
        load_c_extensions(self.conn)
        self.conn.row_factory = sqlite.Row if self.row_factory else  lambda cursor, row : list(row)
        self.conn.create_aggregate('concat', 1, Concatenate)
        self.conn.create_aggregate('aum_sortconcat', 4, AumSortedConcatenate)
        self.conn.create_collation('PYNOCASE', partial(pynocase,
            encoding=encoding))
        self.conn.create_function('title_sort', 1, title_sort)
        self.conn.create_function('author_to_author_sort', 1,
                _author_to_author_sort)
        self.conn.create_function('uuid4', 0, lambda : str(uuid.uuid4()))
        # Dummy functions for dynamically created filters
        self.conn.create_function('books_list_filter', 1, lambda x: 1)
        self.conn.create_collation('icucollate', icu_collator)

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
                        ok, res = True, tuple(self.conn.iterdump())
                    except Exception as err:
                        ok, res = False, (err, traceback.format_exc())
                elif func == 'create_dynamic_filter':
                    try:
                        f = DynamicFilter(args[0])
                        self.conn.create_function(args[0], 1, f)
                        ok, res = True, f
                    except Exception as err:
                        ok, res = False, (err, traceback.format_exc())
                else:
                    bfunc = getattr(self.conn, func)
                    try:
                        for i in range(3):
                            try:
                                ok, res = True, bfunc(*args, **kwargs)
                                break
                            except OperationalError as err:
                                # Retry if unable to open db file
                                e = str(err)
                                if 'unable to open' not in e or i == 2:
                                    if 'unable to open' in e:
                                        prints('Unable to open database for func',
                                            func, reprlib.repr(args),
                                            reprlib.repr(kwargs))
                                    raise
                            time.sleep(0.5)
                    except Exception as err:
                        ok, res = False, (err, traceback.format_exc())
                self.results.put((ok, res))
        except Exception as err:
            self.unhandled_error = (err, traceback.format_exc())

class DatabaseException(Exception):

    def __init__(self, err, tb):
        tb = '\n\t'.join(('\tRemote'+tb).splitlines())
        try:
            msg = unicode(err) +'\n' + tb
        except:
            msg = repr(err) + '\n' + tb
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

    @proxy
    def create_dynamic_filter(self): pass

def connect(dbpath, row_factory=None):
    conn = ConnectionProxy(DBThread(dbpath, row_factory))
    conn.proxy.start()
    while conn.proxy.unhandled_error[0] is None and conn.proxy.conn is None:
        time.sleep(0.01)
    if conn.proxy.unhandled_error[0] is not None:
        raise DatabaseException(*conn.proxy.unhandled_error)
    return conn

def test():
    c = sqlite.connect(':memory:')
    if load_c_extensions(c, True):
        print 'Loaded C extension successfully'

