from __future__ import with_statement
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
"""
Provides platform independent temporary files that persist even after
being closed.
"""
import tempfile, os, atexit, errno
from future_builtins import map

from calibre.constants import (__version__, __appname__, filesystem_encoding,
        get_unicode_windows_env_var, iswindows, get_windows_temp_path, isosx, cache_dir)


def cleanup(path):
    try:
        import os as oss
        if oss.path.exists(path):
            oss.remove(path)
    except:
        pass


_base_dir = None


def remove_dir(x):
    try:
        import shutil
        shutil.rmtree(x, ignore_errors=True)
    except:
        pass


def determined_remove_dir(x):
    for i in range(10):
        try:
            import shutil
            shutil.rmtree(x)
            return
        except:
            import os  # noqa
            if os.path.exists(x):
                # In case some other program has one of the temp files open.
                import time
                time.sleep(0.1)
            else:
                return
    try:
        import shutil
        shutil.rmtree(x, ignore_errors=True)
    except:
        pass


def app_prefix(prefix):
    if iswindows:
        return '%s_'%__appname__
    return '%s_%s_%s'%(__appname__, __version__, prefix)


def reset_temp_folder_permissions():
    # There are some broken windows installs where the permissions for the temp
    # folder are set to not be executable, which means chdir() into temp
    # folders fails. Try to fix that by resetting the permissions on the temp
    # folder.
    global _base_dir
    if iswindows and _base_dir:
        import subprocess
        from calibre import prints
        parent = os.path.dirname(_base_dir)
        retcode = subprocess.Popen(['icacls.exe', parent, '/reset', '/Q', '/T']).wait()
        prints('Trying to reset permissions of temp folder', parent, 'return code:', retcode)


_osx_cache_dir = None


def osx_cache_dir():
    global _osx_cache_dir
    if _osx_cache_dir:
        return _osx_cache_dir
    if _osx_cache_dir is None:
        _osx_cache_dir = False
        import ctypes
        libc = ctypes.CDLL(None)
        buf = ctypes.create_string_buffer(512)
        l = libc.confstr(65538, ctypes.byref(buf), len(buf))  # _CS_DARWIN_USER_CACHE_DIR = 65538
        if 0 < l < len(buf):
            try:
                q = buf.value.decode('utf-8').rstrip(u'\0')
            except ValueError:
                pass
            if q and os.path.isdir(q) and os.access(q, os.R_OK | os.W_OK | os.X_OK):
                _osx_cache_dir = q
                return q


def base_dir():
    global _base_dir
    if _base_dir is not None and not os.path.exists(_base_dir):
        # Some people seem to think that running temp file cleaners that
        # delete the temp dirs of running programs is a good idea!
        _base_dir = None
    if _base_dir is None:
        td = os.environ.get('CALIBRE_WORKER_TEMP_DIR', None)
        if td is not None:
            import cPickle, binascii
            try:
                td = cPickle.loads(binascii.unhexlify(td))
            except:
                td = None
        if td and os.path.exists(td):
            _base_dir = td
        else:
            base = os.environ.get('CALIBRE_TEMP_DIR', None)
            if base is not None and iswindows:
                base = get_unicode_windows_env_var('CALIBRE_TEMP_DIR')
            prefix = app_prefix(u'tmp_')
            if base is None:
                if iswindows:
                    # On windows, if the TMP env var points to a path that
                    # cannot be encoded using the mbcs encoding, then the
                    # python 2 tempfile algorithm for getting the temporary
                    # directory breaks. So we use the win32 api to get a
                    # unicode temp path instead. See
                    # https://bugs.launchpad.net/bugs/937389
                    base = get_windows_temp_path()
                elif isosx:
                    # Use the cache dir rather than the temp dir for temp files as Apple
                    # thinks deleting unused temp files is a good idea. See note under
                    # _CS_DARWIN_USER_TEMP_DIR here
                    # https://developer.apple.com/library/mac/documentation/Darwin/Reference/ManPages/man3/confstr.3.html
                    base = osx_cache_dir()

            _base_dir = tempfile.mkdtemp(prefix=prefix, dir=base)
            atexit.register(determined_remove_dir if iswindows else remove_dir, _base_dir)

        try:
            tempfile.gettempdir()
        except:
            # Widows temp vars set to a path not encodable in mbcs
            # Use our temp dir
            tempfile.tempdir = _base_dir

    return _base_dir


def reset_base_dir():
    global _base_dir
    _base_dir = None
    base_dir()


def force_unicode(x):
    # Cannot use the implementation in calibre.__init__ as it causes a circular
    # dependency
    if isinstance(x, bytes):
        x = x.decode(filesystem_encoding)
    return x


def _make_file(suffix, prefix, base):
    suffix, prefix = map(force_unicode, (suffix, prefix))
    return tempfile.mkstemp(suffix, prefix, dir=base)


def _make_dir(suffix, prefix, base):
    suffix, prefix = map(force_unicode, (suffix, prefix))
    return tempfile.mkdtemp(suffix, prefix, base)


class PersistentTemporaryFile(object):

    """
    A file-like object that is a temporary file that is available even after being closed on
    all platforms. It is automatically deleted on normal program termination.
    """
    _file = None

    def __init__(self, suffix="", prefix="", dir=None, mode='w+b'):
        if prefix is None:
            prefix = ""
        if dir is None:
            dir = base_dir()
        fd, name = _make_file(suffix, prefix, dir)

        self._file = os.fdopen(fd, mode)
        self._name = name
        self._fd = fd
        atexit.register(cleanup, name)

    def __getattr__(self, name):
        if name == 'name':
            return self.__dict__['_name']
        return getattr(self.__dict__['_file'], name)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def __del__(self):
        try:
            self.close()
        except:
            pass


def PersistentTemporaryDirectory(suffix='', prefix='', dir=None):
    '''
    Return the path to a newly created temporary directory that will
    be automatically deleted on application exit.
    '''
    if dir is None:
        dir = base_dir()
    tdir = _make_dir(suffix, prefix, dir)

    atexit.register(remove_dir, tdir)
    return tdir


class TemporaryDirectory(object):

    '''
    A temporary directory to be used in a with statement.
    '''

    def __init__(self, suffix='', prefix='', dir=None, keep=False):
        self.suffix = suffix
        self.prefix = prefix
        if dir is None:
            dir = base_dir()
        self.dir = dir
        self.keep = keep

    def __enter__(self):
        if not hasattr(self, 'tdir'):
            self.tdir = _make_dir(self.suffix, self.prefix, self.dir)
        return self.tdir

    def __exit__(self, *args):
        if not self.keep and os.path.exists(self.tdir):
            remove_dir(self.tdir)


class TemporaryFile(object):

    def __init__(self, suffix="", prefix="", dir=None, mode='w+b'):
        if prefix is None:
            prefix = ''
        if suffix is None:
            suffix = ''
        if dir is None:
            dir = base_dir()
        self.prefix, self.suffix, self.dir, self.mode = prefix, suffix, dir, mode
        self._file = None

    def __enter__(self):
        fd, name = _make_file(self.suffix, self.prefix, self.dir)
        self._file = os.fdopen(fd, self.mode)
        self._name = name
        self._file.close()
        return name

    def __exit__(self, *args):
        cleanup(self._name)


class SpooledTemporaryFile(tempfile.SpooledTemporaryFile):

    def __init__(self, max_size=0, suffix="", prefix="", dir=None, mode='w+b',
            bufsize=-1):
        if prefix is None:
            prefix = ''
        if suffix is None:
            suffix = ''
        if dir is None:
            dir = base_dir()
        tempfile.SpooledTemporaryFile.__init__(self, max_size=max_size,
                suffix=suffix, prefix=prefix, dir=dir, mode=mode,
                bufsize=bufsize)

    def truncate(self, *args):
        # The stdlib SpooledTemporaryFile implementation of truncate() doesn't
        # allow specifying a size.
        self._file.truncate(*args)


def better_mktemp(*args, **kwargs):
    fd, path = tempfile.mkstemp(*args, **kwargs)
    os.close(fd)
    return path


TDIR_LOCK = 'tdir-lock'

if iswindows:
    def lock_tdir(path):
        return lopen(os.path.join(path, TDIR_LOCK), 'wb')

    def remove_tdir(path, lock_file):
        lock_file.close()
        remove_dir(path)

    def is_tdir_locked(path):
        try:
            with lopen(os.path.join(path, TDIR_LOCK), 'wb'):
                pass
        except EnvironmentError:
            return True
        return False
else:
    import fcntl

    def lock_tdir(path):
        from calibre.utils.ipc import eintr_retry_call
        lf = os.path.join(path, TDIR_LOCK)
        f = lopen(lf, 'w')
        eintr_retry_call(fcntl.lockf, f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        return f

    def remove_tdir(path, lock_file):
        lock_file.close()
        remove_dir(path)

    def is_tdir_locked(path):
        from calibre.utils.ipc import eintr_retry_call
        lf = os.path.join(path, TDIR_LOCK)
        f = lopen(lf, 'w')
        try:
            eintr_retry_call(fcntl.lockf, f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            eintr_retry_call(fcntl.lockf, f.fileno(), fcntl.LOCK_UN)
            return False
        except EnvironmentError:
            return True
        finally:
            f.close()


def tdirs_in(b):
    try:
        tdirs = os.listdir(b)
    except EnvironmentError as e:
        if e.errno != errno.ENOENT:
            raise
        tdirs = ()
    for x in tdirs:
        x = os.path.join(b, x)
        if os.path.isdir(x):
            yield x


def clean_tdirs_in(b):
    # Remove any stale tdirs left by previous program crashes
    for q in tdirs_in(b):
        if not is_tdir_locked(q):
            remove_dir(q)


def tdir_in_cache(base):
    ''' Create a temp dir inside cache_dir/base. The created dir is robust
    against application crashes. i.e. it will be cleaned up the next time the
    application starts, even if it was left behind by a previous crash. '''
    b = os.path.join(cache_dir(), base)
    try:
        os.makedirs(b)
    except EnvironmentError as e:
        if e.errno != errno.EEXIST:
            raise
    if b not in tdir_in_cache.scanned:
        tdir_in_cache.scanned.add(b)
        try:
            clean_tdirs_in(b)
        except Exception:
            import traceback
            traceback.print_exc()
    tdir = _make_dir('', '', b)
    lock_data = lock_tdir(tdir)
    atexit.register(remove_tdir, tdir, lock_data)
    return tdir


tdir_in_cache.scanned = set()
