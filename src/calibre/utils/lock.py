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

class ExclusiveFile(object):

    def __init__(self, path, timeout=15):
        self.path = path
        self.timeout = timeout

    def __enter__(self):
        self.file  = open(self.path, 'a+b')
        self.file.seek(0)
        timeout = self.timeout
        if iswindows:
            name = ('Local\\'+(__appname__+self.file.name).replace('\\', '_'))[:201]
            while self.timeout < 0 or timeout >= 0:
                self.mutex = win32event.CreateMutex(None, False, name)
                if win32api.GetLastError() != winerror.ERROR_ALREADY_EXISTS: break
                time.sleep(1)
                timeout -= 1
        else:
            while self.timeout < 0 or timeout >= 0:
                try:
                    fcntl.lockf(self.file.fileno(), fcntl.LOCK_EX|fcntl.LOCK_NB)
                    break
                except IOError:
                    time.sleep(1)
                    timeout -= 1
        if timeout < 0 and self.timeout >= 0:
            self.file.close()
            raise LockError
        return self.file

    def __exit__(self, type, value, traceback):
        if iswindows:
            win32api.CloseHandle(self.mutex)
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
        if mutex:
            atexit.register(win32api.CloseHandle, mutex)
        return not win32api.GetLastError() == winerror.ERROR_ALREADY_EXISTS
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
