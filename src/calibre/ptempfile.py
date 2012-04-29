from __future__ import with_statement
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
"""
Provides platform independent temporary files that persist even after
being closed.
"""
import tempfile, os, atexit
from future_builtins import map

from calibre.constants import (__version__, __appname__, filesystem_encoding,
        get_unicode_windows_env_var, iswindows, get_windows_temp_path)

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

def app_prefix(prefix):
    return '%s_%s_%s'%(__appname__, __version__, prefix)

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
            if base is None and iswindows:
                # On windows, if the TMP env var points to a path that
                # cannot be encoded using the mbcs encoding, then the
                # python 2 tempfile algorithm for getting the temporary
                # directory breaks. So we use the win32 api to get a
                # unicode temp path instead. See
                # https://bugs.launchpad.net/bugs/937389
                base = get_windows_temp_path()

            _base_dir = tempfile.mkdtemp(prefix=prefix, dir=base)
            atexit.register(remove_dir, _base_dir)

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
        if prefix == None:
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
        self.tdir = _make_dir(self.suffix, self.prefix, self.dir)
        return self.tdir

    def __exit__(self, *args):
        if not self.keep and os.path.exists(self.tdir):
            remove_dir(self.tdir)

class TemporaryFile(object):

    def __init__(self, suffix="", prefix="", dir=None, mode='w+b'):
        if prefix == None:
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
        if prefix == None:
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

