__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

'''
Secure access to locked files from multiple processes.
'''

from calibre.constants import iswindows, __appname__, \
                              win32api, win32event, winerror, fcntl
import time, atexit, os

class LockError(Exception):
    pass

class WindowsExclFile(object):

    def __init__(self, path, timeout=20):
        self.name = path
        import win32file as w
        import pywintypes

        while timeout > 0:
            timeout -= 1
            try:
                self._handle = w.CreateFile(path,
                    w.GENERIC_READ|w.GENERIC_WRITE, # Open for reading and writing
                    0, # Open exclusive
                    None, # No security attributes
                    w.OPEN_ALWAYS, # If file does not exist, create it
                    w.FILE_ATTRIBUTE_NORMAL, #Normal attributes
                    None, #No template file
                )
                break
            except pywintypes.error as err:
                if getattr(err, 'args', [-1])[0] in (0x20, 0x21):
                    time.sleep(1)
                    continue
                else:
                    raise

    def seek(self, amt, frm=0):
        import win32file as w
        if frm not in (0, 1, 2):
            raise ValueError('Invalid from for seek: %s'%frm)
        frm = {0:w.FILE_BEGIN, 1: w.FILE_CURRENT, 2:w.FILE_END}[frm]
        if frm is w.FILE_END:
            amt = 0 - amt
        w.SetFilePointer(self._handle, amt, frm)

    def tell(self):
        import win32file as w
        return w.SetFilePointer(self._handle, 0, w.FILE_CURRENT)

    def flush(self):
        import win32file as w
        w.FlushFileBuffers(self._handle)

    def close(self):
        if self._handle is not None:
            import win32file as w
            self.flush()
            w.CloseHandle(self._handle)
            self._handle = None

    def read(self, bytes=-1):
        import win32file as w
        sz = w.GetFileSize(self._handle)
        max = sz - self.tell()
        if bytes < 0: bytes = max
        bytes = min(max, bytes)
        if bytes < 1:
            return ''
        hr, ans = w.ReadFile(self._handle, bytes, None)
        if hr != 0:
            raise IOError('Error reading file: %s'%hr)
        return ans

    def readlines(self, sizehint=-1):
        return self.read().splitlines()

    def write(self, bytes):
        if isinstance(bytes, unicode):
            bytes = bytes.encode('utf-8')
        import win32file as w
        w.WriteFile(self._handle, bytes, None)

    def truncate(self, size=None):
        import win32file as w
        pos = self.tell()
        if size is None:
            size = pos
        t = min(size, pos)
        self.seek(t)
        w.SetEndOfFile(self._handle)
        self.seek(pos)

    def isatty(self):
        return False

    @property
    def closed(self):
        return self._handle is None


class ExclusiveFile(object):

    def __init__(self, path, timeout=15):
        self.path = path
        self.timeout = timeout

    def __enter__(self):
        self.file  =  WindowsExclFile(self.path, self.timeout) if iswindows else open(self.path, 'a+b')
        self.file.seek(0)
        timeout = self.timeout
        if not iswindows:
            while self.timeout < 0 or timeout >= 0:
                try:
                    fcntl.lockf(self.file.fileno(), fcntl.LOCK_EX|fcntl.LOCK_NB)
                    break
                except IOError:
                    time.sleep(1)
                    timeout -= 1
            if timeout < 0 and self.timeout >= 0:
                self.file.close()
                raise LockError('Failed to lock')
        return self.file

    def __exit__(self, type, value, traceback):
        self.file.close()

def _clean_lock_file(file):
    try:
        file.close()
    except:
        pass
    try:
        os.remove(file.name)
    except:
        pass


def singleinstance(name):
    '''
    Return True if no other instance of the application identified by name is running,
    False otherwise.
    @param name: The name to lock.
    @type name: string
    '''
    if iswindows:
        mutexname = 'mutexforsingleinstanceof'+__appname__+name
        mutex =  win32event.CreateMutex(None, False, mutexname)
        err = win32api.GetLastError()
        if err == winerror.ERROR_ALREADY_EXISTS:
            # Close this handle other wise this handle will prevent the mutex
            # from being deleted when the process that created it exits.
            win32api.CloseHandle(mutex)
        elif mutex and err != winerror.ERROR_INVALID_HANDLE:
            atexit.register(win32api.CloseHandle, mutex)
        return not err == winerror.ERROR_ALREADY_EXISTS
    else:
        path = os.path.expanduser('~/.'+__appname__+'_'+name+'.lock')
        try:
            f = open(path, 'w')
            fcntl.lockf(f.fileno(), fcntl.LOCK_EX|fcntl.LOCK_NB)
            atexit.register(_clean_lock_file, f)
            return True
        except IOError:
            return False

    return False
