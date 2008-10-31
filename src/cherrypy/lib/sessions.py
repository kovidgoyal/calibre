"""Session implementation for CherryPy.

We use cherrypy.request to store some convenient variables as
well as data about the session for the current request. Instead of
polluting cherrypy.request we use a Session object bound to
cherrypy.session to store these variables.
"""

import datetime
import os
try:
    import cPickle as pickle
except ImportError:
    import pickle
import random
import sha
import time
import threading
import types
from warnings import warn

import cherrypy
from cherrypy.lib import http


missing = object()

class Session(object):
    """A CherryPy dict-like Session object (one per request)."""
    
    __metaclass__ = cherrypy._AttributeDocstrings
    
    _id = None
    id_observers = None
    id_observers__doc = "A list of callbacks to which to pass new id's."
    
    id__doc = "The current session ID."
    def _get_id(self):
        return self._id
    def _set_id(self, value):
        self._id = value
        for o in self.id_observers:
            o(value)
    id = property(_get_id, _set_id, doc=id__doc)
    
    timeout = 60
    timeout__doc = "Number of minutes after which to delete session data."
    
    locked = False
    locked__doc = """
    If True, this session instance has exclusive read/write access
    to session data."""
    
    loaded = False
    loaded__doc = """
    If True, data has been retrieved from storage. This should happen
    automatically on the first attempt to access session data."""
    
    clean_thread = None
    clean_thread__doc = "Class-level Monitor which calls self.clean_up."
    
    clean_freq = 5
    clean_freq__doc = "The poll rate for expired session cleanup in minutes."
    
    def __init__(self, id=None, **kwargs):
        self.id_observers = []
        self._data = {}
        
        for k, v in kwargs.iteritems():
            setattr(self, k, v)
        
        if id is None:
            self.regenerate()
        else:
            self.id = id
            if not self._exists():
                # Expired or malicious session. Make a new one.
                # See http://www.cherrypy.org/ticket/709.
                self.id = None
                self.regenerate()
    
    def regenerate(self):
        """Replace the current session (with a new id)."""
        if self.id is not None:
            self.delete()
        
        old_session_was_locked = self.locked
        if old_session_was_locked:
            self.release_lock()
        
        self.id = None
        while self.id is None:
            self.id = self.generate_id()
            # Assert that the generated id is not already stored.
            if self._exists():
                self.id = None
        
        if old_session_was_locked:
            self.acquire_lock()
    
    def clean_up(self):
        """Clean up expired sessions."""
        pass
    
    try:
        os.urandom(20)
    except (AttributeError, NotImplementedError):
        # os.urandom not available until Python 2.4. Fall back to random.random.
        def generate_id(self):
            """Return a new session id."""
            return sha.new('%s' % random.random()).hexdigest()
    else:
        def generate_id(self):
            """Return a new session id."""
            return os.urandom(20).encode('hex')
    
    def save(self):
        """Save session data."""
        try:
            # If session data has never been loaded then it's never been
            #   accessed: no need to delete it
            if self.loaded:
                t = datetime.timedelta(seconds = self.timeout * 60)
                expiration_time = datetime.datetime.now() + t
                self._save(expiration_time)
            
        finally:
            if self.locked:
                # Always release the lock if the user didn't release it
                self.release_lock()
    
    def load(self):
        """Copy stored session data into this session instance."""
        data = self._load()
        # data is either None or a tuple (session_data, expiration_time)
        if data is None or data[1] < datetime.datetime.now():
            # Expired session: flush session data
            self._data = {}
        else:
            self._data = data[0]
        self.loaded = True
        
        # Stick the clean_thread in the class, not the instance.
        # The instances are created and destroyed per-request.
        cls = self.__class__
        if not cls.clean_thread:
            # clean_up is in instancemethod and not a classmethod,
            # so that tool config can be accessed inside the method.
            t = cherrypy.process.plugins.Monitor(
                cherrypy.engine, self.clean_up, self.clean_freq * 60)
            t.subscribe()
            cls.clean_thread = t
            t.start()
    
    def delete(self):
        """Delete stored session data."""
        self._delete()
    
    def __getitem__(self, key):
        if not self.loaded: self.load()
        return self._data[key]
    
    def __setitem__(self, key, value):
        if not self.loaded: self.load()
        self._data[key] = value
    
    def __delitem__(self, key):
        if not self.loaded: self.load()
        del self._data[key]
    
    def pop(self, key, default=missing):
        """Remove the specified key and return the corresponding value.
        If key is not found, default is returned if given,
        otherwise KeyError is raised.
        """
        if not self.loaded: self.load()
        if default is missing:
            return self._data.pop(key)
        else:
            return self._data.pop(key, default)
    
    def __contains__(self, key):
        if not self.loaded: self.load()
        return key in self._data
    
    def has_key(self, key):
        """D.has_key(k) -> True if D has a key k, else False."""
        if not self.loaded: self.load()
        return self._data.has_key(key)
    
    def get(self, key, default=None):
        """D.get(k[,d]) -> D[k] if k in D, else d.  d defaults to None."""
        if not self.loaded: self.load()
        return self._data.get(key, default)
    
    def update(self, d):
        """D.update(E) -> None.  Update D from E: for k in E: D[k] = E[k]."""
        if not self.loaded: self.load()
        self._data.update(d)
    
    def setdefault(self, key, default=None):
        """D.setdefault(k[,d]) -> D.get(k,d), also set D[k]=d if k not in D."""
        if not self.loaded: self.load()
        return self._data.setdefault(key, default)
    
    def clear(self):
        """D.clear() -> None.  Remove all items from D."""
        if not self.loaded: self.load()
        self._data.clear()
    
    def keys(self):
        """D.keys() -> list of D's keys."""
        if not self.loaded: self.load()
        return self._data.keys()
    
    def items(self):
        """D.items() -> list of D's (key, value) pairs, as 2-tuples."""
        if not self.loaded: self.load()
        return self._data.items()
    
    def values(self):
        """D.values() -> list of D's values."""
        if not self.loaded: self.load()
        return self._data.values()


class RamSession(Session):
    
    # Class-level objects. Don't rebind these!
    cache = {}
    locks = {}
    
    def clean_up(self):
        """Clean up expired sessions."""
        now = datetime.datetime.now()
        for id, (data, expiration_time) in self.cache.items():
            if expiration_time < now:
                try:
                    del self.cache[id]
                except KeyError:
                    pass
                try:
                    del self.locks[id]
                except KeyError:
                    pass
    
    def _exists(self):
        return self.id in self.cache
    
    def _load(self):
        return self.cache.get(self.id)
    
    def _save(self, expiration_time):
        self.cache[self.id] = (self._data, expiration_time)
    
    def _delete(self):
        del self.cache[self.id]
    
    def acquire_lock(self):
        """Acquire an exclusive lock on the currently-loaded session data."""
        self.locked = True
        self.locks.setdefault(self.id, threading.RLock()).acquire()
    
    def release_lock(self):
        """Release the lock on the currently-loaded session data."""
        self.locks[self.id].release()
        self.locked = False
    
    def __len__(self):
        """Return the number of active sessions."""
        return len(self.cache)


class FileSession(Session):
    """Implementation of the File backend for sessions
    
    storage_path: the folder where session data will be saved. Each session
        will be saved as pickle.dump(data, expiration_time) in its own file;
        the filename will be self.SESSION_PREFIX + self.id.
    """
    
    SESSION_PREFIX = 'session-'
    LOCK_SUFFIX = '.lock'
    
    def setup(cls, **kwargs):
        """Set up the storage system for file-based sessions.
        
        This should only be called once per process; this will be done
        automatically when using sessions.init (as the built-in Tool does).
        """
        if 'storage_path' in kwargs:
            kwargs['storage_path'] = os.path.abspath(kwargs['storage_path'])
        
        for k, v in kwargs.iteritems():
            setattr(cls, k, v)
        
        # Warn if any lock files exist at startup.
        lockfiles = [fname for fname in os.listdir(cls.storage_path)
                     if (fname.startswith(cls.SESSION_PREFIX)
                         and fname.endswith(cls.LOCK_SUFFIX))]
        if lockfiles:
            plural = ('', 's')[len(lockfiles) > 1]
            warn("%s session lockfile%s found at startup. If you are "
                 "only running one process, then you may need to "
                 "manually delete the lockfiles found at %r."
                 % (len(lockfiles), plural, cls.storage_path))
    setup = classmethod(setup)
    
    def _get_file_path(self):
        f = os.path.join(self.storage_path, self.SESSION_PREFIX + self.id)
        if not os.path.abspath(f).startswith(self.storage_path):
            raise cherrypy.HTTPError(400, "Invalid session id in cookie.")
        return f
    
    def _exists(self):
        path = self._get_file_path()
        return os.path.exists(path)
    
    def _load(self, path=None):
        if path is None:
            path = self._get_file_path()
        try:
            f = open(path, "rb")
            try:
                return pickle.load(f)
            finally:
                f.close()
        except (IOError, EOFError):
            return None
    
    def _save(self, expiration_time):
        f = open(self._get_file_path(), "wb")
        try:
            pickle.dump((self._data, expiration_time), f)
        finally:
            f.close()
    
    def _delete(self):
        try:
            os.unlink(self._get_file_path())
        except OSError:
            pass
    
    def acquire_lock(self, path=None):
        """Acquire an exclusive lock on the currently-loaded session data."""
        if path is None:
            path = self._get_file_path()
        path += self.LOCK_SUFFIX
        while True:
            try:
                lockfd = os.open(path, os.O_CREAT|os.O_WRONLY|os.O_EXCL)
            except OSError:
                time.sleep(0.1)
            else:
                os.close(lockfd) 
                break
        self.locked = True
    
    def release_lock(self, path=None):
        """Release the lock on the currently-loaded session data."""
        if path is None:
            path = self._get_file_path()
        os.unlink(path + self.LOCK_SUFFIX)
        self.locked = False
    
    def clean_up(self):
        """Clean up expired sessions."""
        now = datetime.datetime.now()
        # Iterate over all session files in self.storage_path
        for fname in os.listdir(self.storage_path):
            if (fname.startswith(self.SESSION_PREFIX)
                and not fname.endswith(self.LOCK_SUFFIX)):
                # We have a session file: lock and load it and check
                #   if it's expired. If it fails, nevermind.
                path = os.path.join(self.storage_path, fname)
                self.acquire_lock(path)
                try:
                    contents = self._load(path)
                    # _load returns None on IOError
                    if contents is not None:
                        data, expiration_time = contents
                        if expiration_time < now:
                            # Session expired: deleting it
                            os.unlink(path)
                finally:
                    self.release_lock(path)
    
    def __len__(self):
        """Return the number of active sessions."""
        return len([fname for fname in os.listdir(self.storage_path)
                    if (fname.startswith(self.SESSION_PREFIX)
                        and not fname.endswith(self.LOCK_SUFFIX))])


class PostgresqlSession(Session):
    """ Implementation of the PostgreSQL backend for sessions. It assumes
        a table like this:

            create table session (
                id varchar(40),
                data text,
                expiration_time timestamp
            )
    
    You must provide your own get_db function.
    """
    
    def __init__(self, id=None, **kwargs):
        Session.__init__(self, id, **kwargs)
        self.cursor = self.db.cursor()
    
    def setup(cls, **kwargs):
        """Set up the storage system for Postgres-based sessions.
        
        This should only be called once per process; this will be done
        automatically when using sessions.init (as the built-in Tool does).
        """
        for k, v in kwargs.iteritems():
            setattr(cls, k, v)
        
        self.db = self.get_db()
    setup = classmethod(setup)
    
    def __del__(self):
        if self.cursor:
            self.cursor.close()
        self.db.commit()
    
    def _exists(self):
        # Select session data from table
        self.cursor.execute('select data, expiration_time from session '
                            'where id=%s', (self.id,))
        rows = self.cursor.fetchall()
        return bool(rows)
    
    def _load(self):
        # Select session data from table
        self.cursor.execute('select data, expiration_time from session '
                            'where id=%s', (self.id,))
        rows = self.cursor.fetchall()
        if not rows:
            return None
        
        pickled_data, expiration_time = rows[0]
        data = pickle.loads(pickled_data)
        return data, expiration_time
    
    def _save(self, expiration_time):
        pickled_data = pickle.dumps(self._data)
        self.cursor.execute('update session set data = %s, '
                            'expiration_time = %s where id = %s',
                            (pickled_data, expiration_time, self.id))
    
    def _delete(self):
        self.cursor.execute('delete from session where id=%s', (self.id,))
   
    def acquire_lock(self):
        """Acquire an exclusive lock on the currently-loaded session data."""
        # We use the "for update" clause to lock the row
        self.locked = True
        self.cursor.execute('select id from session where id=%s for update',
                            (self.id,))
    
    def release_lock(self):
        """Release the lock on the currently-loaded session data."""
        # We just close the cursor and that will remove the lock
        #   introduced by the "for update" clause
        self.cursor.close()
        self.locked = False
    
    def clean_up(self):
        """Clean up expired sessions."""
        self.cursor.execute('delete from session where expiration_time < %s',
                            (datetime.datetime.now(),))


class MemcachedSession(Session):
    
    # The most popular memcached client for Python isn't thread-safe.
    # Wrap all .get and .set operations in a single lock.
    mc_lock = threading.RLock()
    
    # This is a seperate set of locks per session id.
    locks = {}
    
    servers = ['127.0.0.1:11211']
    
    def setup(cls, **kwargs):
        """Set up the storage system for memcached-based sessions.
        
        This should only be called once per process; this will be done
        automatically when using sessions.init (as the built-in Tool does).
        """
        for k, v in kwargs.iteritems():
            setattr(cls, k, v)
        
        import memcache
        cls.cache = memcache.Client(cls.servers)
    setup = classmethod(setup)
    
    def _exists(self):
        self.mc_lock.acquire()
        try:
            return bool(self.cache.get(self.id))
        finally:
            self.mc_lock.release()
    
    def _load(self):
        self.mc_lock.acquire()
        try:
            return self.cache.get(self.id)
        finally:
            self.mc_lock.release()
    
    def _save(self, expiration_time):
        # Send the expiration time as "Unix time" (seconds since 1/1/1970)
        td = int(time.mktime(expiration_time.timetuple()))
        self.mc_lock.acquire()
        try:
            if not self.cache.set(self.id, (self._data, expiration_time), td):
                raise AssertionError("Session data for id %r not set." % self.id)
        finally:
            self.mc_lock.release()
    
    def _delete(self):
        self.cache.delete(self.id)
    
    def acquire_lock(self):
        """Acquire an exclusive lock on the currently-loaded session data."""
        self.locked = True
        self.locks.setdefault(self.id, threading.RLock()).acquire()
    
    def release_lock(self):
        """Release the lock on the currently-loaded session data."""
        self.locks[self.id].release()
        self.locked = False
    
    def __len__(self):
        """Return the number of active sessions."""
        raise NotImplementedError


# Hook functions (for CherryPy tools)

def save():
    """Save any changed session data."""
    
    if not hasattr(cherrypy.serving, "session"):
        return
    
    # Guard against running twice
    if hasattr(cherrypy.request, "_sessionsaved"):
        return
    cherrypy.request._sessionsaved = True
    
    if cherrypy.response.stream:
        # If the body is being streamed, we have to save the data
        #   *after* the response has been written out
        cherrypy.request.hooks.attach('on_end_request', cherrypy.session.save)
    else:
        # If the body is not being streamed, we save the data now
        # (so we can release the lock).
        if isinstance(cherrypy.response.body, types.GeneratorType):
            cherrypy.response.collapse_body()
        cherrypy.session.save()
save.failsafe = True

def close():
    """Close the session object for this request."""
    sess = getattr(cherrypy.serving, "session", None)
    if getattr(sess, "locked", False):
        # If the session is still locked we release the lock
        sess.release_lock()
close.failsafe = True
close.priority = 90


def init(storage_type='ram', path=None, path_header=None, name='session_id',
         timeout=60, domain=None, secure=False, clean_freq=5, **kwargs):
    """Initialize session object (using cookies).
    
    storage_type: one of 'ram', 'file', 'postgresql'. This will be used
        to look up the corresponding class in cherrypy.lib.sessions
        globals. For example, 'file' will use the FileSession class.
    path: the 'path' value to stick in the response cookie metadata.
    path_header: if 'path' is None (the default), then the response
        cookie 'path' will be pulled from request.headers[path_header].
    name: the name of the cookie.
    timeout: the expiration timeout (in minutes) for both the cookie and
        stored session data.
    domain: the cookie domain.
    secure: if False (the default) the cookie 'secure' value will not
        be set. If True, the cookie 'secure' value will be set (to 1).
    clean_freq (minutes): the poll rate for expired session cleanup.
    
    Any additional kwargs will be bound to the new Session instance,
    and may be specific to the storage type. See the subclass of Session
    you're using for more information.
    """
    
    request = cherrypy.request
    
    # Guard against running twice
    if hasattr(request, "_session_init_flag"):
        return
    request._session_init_flag = True
    
    # Check if request came with a session ID
    id = None
    if name in request.cookie:
        id = request.cookie[name].value
    
    # Find the storage class and call setup (first time only).
    storage_class = storage_type.title() + 'Session'
    storage_class = globals()[storage_class]
    if not hasattr(cherrypy, "session"):
        if hasattr(storage_class, "setup"):
            storage_class.setup(**kwargs)
    
    # Create and attach a new Session instance to cherrypy.serving.
    # It will possess a reference to (and lock, and lazily load)
    # the requested session data.
    kwargs['timeout'] = timeout
    kwargs['clean_freq'] = clean_freq
    cherrypy.serving.session = sess = storage_class(id, **kwargs)
    def update_cookie(id):
        """Update the cookie every time the session id changes."""
        cherrypy.response.cookie[name] = id
    sess.id_observers.append(update_cookie)
    
    # Create cherrypy.session which will proxy to cherrypy.serving.session
    if not hasattr(cherrypy, "session"):
        cherrypy.session = cherrypy._ThreadLocalProxy('session')
    
    set_response_cookie(path=path, path_header=path_header, name=name,
                        timeout=timeout, domain=domain, secure=secure)


def set_response_cookie(path=None, path_header=None, name='session_id',
                        timeout=60, domain=None, secure=False):
    """Set a response cookie for the client.
    
    path: the 'path' value to stick in the response cookie metadata.
    path_header: if 'path' is None (the default), then the response
        cookie 'path' will be pulled from request.headers[path_header].
    name: the name of the cookie.
    timeout: the expiration timeout for the cookie.
    domain: the cookie domain.
    secure: if False (the default) the cookie 'secure' value will not
        be set. If True, the cookie 'secure' value will be set (to 1).
    """
    # Set response cookie
    cookie = cherrypy.response.cookie
    cookie[name] = cherrypy.serving.session.id
    cookie[name]['path'] = (path or cherrypy.request.headers.get(path_header)
                            or '/')
    
    # We'd like to use the "max-age" param as indicated in
    # http://www.faqs.org/rfcs/rfc2109.html but IE doesn't
    # save it to disk and the session is lost if people close
    # the browser. So we have to use the old "expires" ... sigh ...
##    cookie[name]['max-age'] = timeout * 60
    if timeout:
        cookie[name]['expires'] = http.HTTPDate(time.time() + (timeout * 60))
    if domain is not None:
        cookie[name]['domain'] = domain
    if secure:
        cookie[name]['secure'] = 1


def expire():
    """Expire the current session cookie."""
    name = cherrypy.request.config.get('tools.sessions.name', 'session_id')
    one_year = 60 * 60 * 24 * 365
    exp = time.gmtime(time.time() - one_year)
    t = time.strftime("%a, %d-%b-%Y %H:%M:%S GMT", exp)
    cherrypy.response.cookie[name]['expires'] = t


