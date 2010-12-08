# -*- coding: utf-8 -*-

__license__   = 'GPL v3'
__copyright__ = '2010, Li Fanxi <lifanxi at freemindworld.com>'
__docformat__ = 'restructuredtext en'

'''
Sanda library wrapper 
'''

import ctypes, uuid, hashlib
from threading import Event, Lock
from calibre.constants import iswindows, islinux

try:
    if iswindows:
        text_encoding = 'mbcs'
        lib_handle = ctypes.cdll.BambookCore
    elif islinux:
        text_encoding = 'utf-8'
        lib_handle = ctypes.CDLL('libBambookCore.so')
except:
    lib_handle = None

# Constant
DEFAULT_BAMBOOK_IP = '192.168.250.2'
BAMBOOK_SDK_VERSION = 0x00090000
BR_SUCC             = 0     # 操作成功
BR_FAIL             = 1001  # 操作失败
BR_NOT_IMPL         = 1002  # 该功能还未实现
BR_DISCONNECTED     = 1003  # 与设备的连接已断开
BR_PARAM_ERROR      = 1004  # 调用函数传入的参数错误
BR_TIMEOUT          = 1005  # 操作或通讯超时
BR_INVALID_HANDLE   = 1006  # 传入的句柄无效
BR_INVALID_FILE     = 1007  # 传入的文件不存在或格式无效
BR_INVALID_DIR      = 1008  # 传入的目录不存在
BR_BUSY             = 1010  # 设备忙，另一个操作还未完成
BR_EOF              = 1011  # 文件或操作已结束
BR_IO_ERROR         = 1012  # 文件读写失败
BR_FILE_NOT_INSIDE  = 1013  # 指定的文件不在包里

# 当前连接状态
CONN_CONNECTED      = 0     # 已连接
CONN_DISCONNECTED   = 1     # 未连接或连接已断开
CONN_CONNECTING     = 2     # 正在连接
CONN_WAIT_FOR_AUTH  = 3     # 已连接，正在等待身份验证（暂未实现）

#传输状态
TRANS_STATUS_TRANS	= 0	#正在传输
TRANS_STATUS_DONE	= 1	#传输完成
TRANS_STATUS_ERR        = 2	#传输出错

# Key Enums
BBKeyNum0 = 0
BBKeyNum1 = 1
BBKeyNum2 = 2
BBKeyNum3 = 3 
BBKeyNum4 = 4
BBKeyNum5 = 5
BBKeyNum6 = 6
BBKeyNum7 = 7
BBKeyNum8 = 8
BBKeyNum9 = 9
BBKeyStar = 10
BBKeyCross = 11
BBKeyUp = 12
BBKeyDown = 13
BBKeyLeft = 14
BBKeyRight = 15
BBKeyPageUp = 16
BBKeyPageDown = 17 
BBKeyOK = 18
BBKeyESC = 19
BBKeyBookshelf = 20
BBKeyStore = 21
BBKeyTTS = 22
BBKeyMenu = 23
BBKeyInteract =24

class DeviceInfo(ctypes.Structure):
    _fields_ = [ ("cbSize", ctypes.c_int),
                 ("sn", ctypes.c_char * 20),
                 ("firmwareVersion", ctypes.c_char * 20),
                 ("deviceVolume", ctypes.c_int),
                 ("spareVolume", ctypes.c_int),
               ]
    def __init__(self):
        self.cbSize = ctypes.sizeof(self)

class PrivBookInfo(ctypes.Structure):
    _fields_ = [ ("cbSize", ctypes.c_int),
                 ("bookGuid", ctypes.c_char * 20),
                 ("bookName", ctypes.c_char * 80),
                 ("bookAuthor", ctypes.c_char * 40),
                 ("bookAbstract", ctypes.c_char * 256),
               ]
    def Clone(self):
        bookInfo = PrivBookInfo()
        bookInfo.cbSize = self.cbSize
        bookInfo.bookGuid = self.bookGuid
        bookInfo.bookName = self.bookName
        bookInfo.bookAuthor = self.bookAuthor
        bookInfo.bookAbstract = self.bookAbstract
        return bookInfo

    def __init__(self):
        self.cbSize = ctypes.sizeof(self)

# extern "C"_declspec(dllexport) BB_RESULT BambookConnect(const char* lpszIP, int timeOut, BB_HANDLE* hConn);
def BambookConnect(ip = DEFAULT_BAMBOOK_IP, timeout = 0):
    if isinstance(ip, unicode):
        ip = ip.encode('ascii')
    handle = ctypes.c_int(0)
    if lib_handle == None:
        raise Exception(_('Bambook SDK has not been installed.'))
    ret = lib_handle.BambookConnect(ip, timeout, ctypes.byref(handle))
    if ret == BR_SUCC:
        return handle
    else:
        return None

# extern "C" _declspec(dllexport) BB_RESULT BambookGetConnectStatus(BB_HANDLE hConn, int* status);
def BambookGetConnectStatus(handle):
    status = ctypes.c_int(0)
    ret = lib_handle.BambookGetConnectStatus(handle, ctypes.byref(status))
    if ret == BR_SUCC:
        return status.value
    else:
        return None

# extern "C" _declspec(dllexport) BB_RESULT BambookDisconnect(BB_HANDLE hConn);
def BambookDisconnect(handle):
    ret = lib_handle.BambookDisconnect(handle)
    if ret == BR_SUCC:
        return True
    else:
        return False

# extern "C" const char * BambookGetErrorString(BB_RESULT nCode)
def BambookGetErrorString(code):
    func = lib_handle.BambookGetErrorString
    func.restype = ctypes.c_char_p
    return func(code)
    

# extern "C" BB_RESULT BambookGetSDKVersion(uint32_t * version);
def BambookGetSDKVersion():
    version = ctypes.c_int(0)
    lib_handle.BambookGetSDKVersion(ctypes.byref(version))
    return version.value

# extern "C" BB_RESULT BambookGetDeviceInfo(BB_HANDLE hConn, DeviceInfo* pInfo);
def BambookGetDeviceInfo(handle):
    deviceInfo = DeviceInfo()
    ret = lib_handle.BambookGetDeviceInfo(handle, ctypes.byref(deviceInfo))
    if ret == BR_SUCC:
        return deviceInfo
    else:
        return None


# extern "C" BB_RESULT BambookKeyPress(BB_HANDLE hConn, BambookKey key);
def BambookKeyPress(handle, key):
    ret = lib_handle.BambookKeyPress(handle, key)
    if ret == BR_SUCC:
        return True
    else:
        return False

# extern "C" BB_RESULT BambookGetFirstPrivBookInfo(BB_HANDLE hConn, PrivBookInfo * pInfo);
def BambookGetFirstPrivBookInfo(handle, bookInfo):
    bookInfo.contents.cbSize = ctypes.sizeof(bookInfo.contents)
    ret = lib_handle.BambookGetFirstPrivBookInfo(handle, bookInfo)
    if ret == BR_SUCC:
        return True
    else:
        return False

# extern "C" BB_RESULT BambookGetNextPrivBookInfo(BB_HANDLE hConn, PrivBookInfo * pInfo);
def BambookGetNextPrivBookInfo(handle, bookInfo):
    bookInfo.contents.cbSize = ctypes.sizeof(bookInfo.contents)
    ret = lib_handle.BambookGetNextPrivBookInfo(handle, bookInfo)
    if ret == BR_SUCC:
        return True
    elif ret == BR_EOF:
        return False
    else:
        return False

# extern "C" BB_RESULT BambookDeletePrivBook(BB_HANDLE hConn, const char * lpszBookID);
def BambookDeletePrivBook(handle, guid):
    if isinstance(guid, unicode):
        guid = guid.encode('ascii')
    ret = lib_handle.BambookDeletePrivBook(handle, guid)
    if ret == BR_SUCC:
        return True
    else:
        return False

class JobQueue:
    jobs = {}
    maxID = 0
    lock = Lock()
    def __init__(self):
        self.maxID = 0

    def NewJob(self):
        self.lock.acquire()
        self.maxID = self.maxID + 1
        maxid = self.maxID
        self.lock.release()
        event = Event()
        self.jobs[maxid] = (event, TRANS_STATUS_TRANS)
        return maxid

    def FinishJob(self, jobID, status):
        self.jobs[jobID] = (self.jobs[jobID][0], status)
        self.jobs[jobID][0].set()

    def WaitJob(self, jobID):
        self.jobs[jobID][0].wait()
        return (self.jobs[jobID][1] == TRANS_STATUS_DONE)

    def DeleteJob(self, jobID):
        del self.jobs[jobID]

job = JobQueue()

def BambookTransferCallback(status, progress, userData):
    if status == TRANS_STATUS_DONE and progress == 100:
        job.FinishJob(userData, status)
    elif status == TRANS_STATUS_ERR:
        job.FinishJob(userData, status)

TransCallback = ctypes.CFUNCTYPE(None, ctypes.c_int, ctypes.c_int, ctypes.c_int)
bambookTransferCallback = TransCallback(BambookTransferCallback)

# extern "C" BB_RESULT BambookAddPrivBook(BB_HANDLE hConn, const char * pszSnbFile,
#                                         TransCallback pCallbackFunc, intptr_t userData);
def BambookAddPrivBook(handle, filename, callback, userData):
    if isinstance(filename, unicode):
        filename = filename.encode('ascii')
    ret = lib_handle.BambookAddPrivBook(handle, filename, callback, userData)
    if ret == BR_SUCC:
        return True
    else:
        return False

# extern "C" BB_RESULT BambookReplacePrivBook(BB_HANDLE hConn, const char *
#     pszSnbFile, const char * lpszBookID, TransCallback pCallbackFunc, intptr_t userData);
def BambookReplacePrivBook(handle, filename, bookID, callback, userData):
    if isinstance(filename, unicode):
        filename = filename.encode('ascii')
    if isinstance(bookID, unicode):
        bookID = bookID.encode('ascii')
    ret = lib_handle.BambookReplacePrivBook(handle, filename, bookID, callback, userData)
    if ret == BR_SUCC:
        return True
    else:
        return False
    
# extern "C" BB_RESULT BambookFetchPrivBook(BB_HANDLE hConn, const char *
#     lpszBookID, const char * lpszFilePath, TransCallback pCallbackFunc, intptr_t userData);
def BambookFetchPrivBook(handle, bookID, filename, callback, userData):
    if isinstance(filename, unicode):
        filename = filename.encode('ascii')
    if isinstance(bookID, unicode):
        bookID = bookID.encode('ascii')
    ret = lib_handle.BambookFetchPrivBook(handle, bookID, filename, bambookTransferCallback, userData)
    if ret == BR_SUCC:
        return True
    else:
        return False

# extern "C" BB_RESULT BambookVerifySnbFile(const char * snbName)
def BambookVerifySnbFile(filename):
    if isinstance(filename, unicode):
        filename = filename.encode('ascii')
    if lib_handle.BambookVerifySnbFile(filename) == BR_SUCC:
        return True
    else:
        return False

#  BB_RESULT BambookPackSnbFromDir ( const char * snbName,, const char * rootDir );
def BambookPackSnbFromDir(snbFileName, rootDir):
    if isinstance(snbFileName, unicode):
        snbFileName = snbFileName.encode('ascii')
    if isinstance(rootDir, unicode):
        rootDir = rootDir.encode('ascii')
    ret = lib_handle.BambookPackSnbFromDir(snbFileName, rootDir)
    if ret == BR_SUCC:
        return True
    else:
        return False

# BB_RESULT BambookUnpackFileFromSnb ( const char * snbName,, const char * relativePath, const char * outfname );
def BambookUnpackFileFromSnb(snbFileName, relPath, outFileName):
    if isinstance(snbFileName, unicode):
        snbFileName = snbFileName.encode('ascii')
    if isinstance(relPath, unicode):
        relPath = relPath.encode('ascii')
    if isinstance(outFileName, unicode):
        outFileName = outFileName.encode('ascii')
    ret = lib_handle.BambookUnpackFileFromSnb(snbFileName, relPath, outFileName)
    if ret == BR_SUCC:
        return True
    else:
        return False

class Bambook:
    def __init__(self):
        self.handle = None

    def Connect(self, ip = DEFAULT_BAMBOOK_IP, timeout = 10000):
        self.handle = BambookConnect(ip, timeout)
        if self.handle and self.handle != 0:
            return True
        else:
            return False

    def Disconnect(self):
        if self.handle:
            return BambookDisconnect(self.handle)
        return False
    
    def GetState(self):
        if self.handle:
            return BambookGetConnectStatus(self.handle)
        return CONN_DISCONNECTED

    def GetDeviceInfo(self):
        if self.handle:
            return BambookGetDeviceInfo(self.handle)
        return None

    def SendFile(self, fileName, guid = None):
        if self.handle:
            taskID = job.NewJob()
            if guid:
                if BambookReplacePrivBook(self.handle, fileName, guid, 
                                          bambookTransferCallback, taskID):
                    if(job.WaitJob(taskID)):
                        job.DeleteJob(taskID)
                        return guid
                    else:
                        job.DeleteJob(taskID)
                        return None
                else:
                    job.DeleteJob(taskID)
                    return None
            else:
                guid = hashlib.md5(str(uuid.uuid4())).hexdigest()[0:15] + ".snb"
                if BambookReplacePrivBook(self.handle, fileName, guid,
                                          bambookTransferCallback, taskID):
                    if job.WaitJob(taskID):
                        job.DeleteJob(taskID)
                        return guid
                    else:
                        job.DeleteJob(taskID)
                        return None
                else:
                    job.DeleteJob(taskID)
                    return None
        return False

    def GetFile(self, guid, fileName):
        if self.handle:
            taskID = job.NewJob()
            ret = BambookFetchPrivBook(self.handle, guid, fileName, bambookTransferCallback, taskID)
            if ret:
                ret = job.WaitJob(taskID)
                job.DeleteJob(taskID)
                return ret
            else:
                job.DeleteJob(taskID)
                return False
        return False    

    def DeleteFile(self, guid):
        if self.handle:
            ret = BambookDeletePrivBook(self.handle, guid)
            return ret
        return False

    def GetBookList(self):
        if self.handle:
            books = []
            bookInfo = PrivBookInfo()
            bi = ctypes.pointer(bookInfo)
            
            ret = BambookGetFirstPrivBookInfo(self.handle, bi)
            while ret:
                books.append(bi.contents.Clone())
                ret = BambookGetNextPrivBookInfo(self.handle, bi)
            return books
            
    @staticmethod
    def GetSDKVersion():
        return BambookGetSDKVersion()

    @staticmethod
    def VerifySNB(fileName):
        return BambookVerifySnbFile(fileName);

    @staticmethod
    def ExtractSNBContent(fileName, relPath, path):
        return BambookUnpackFileFromSnb(fileName, relPath, path)

    @staticmethod
    def ExtractSNB(fileName, path):
        ret = BambookUnpackFileFromSnb(fileName, 'snbf/book.snbf', path + '/snbf/book.snbf')
        if not ret:
            return False
        ret = BambookUnpackFileFromSnb(fileName, 'snbf/toc.snbf', path + '/snbf/toc.snbf')
        if not ret:
            return False
        
        return True

    @staticmethod
    def PackageSNB(fileName, path):
        return BambookPackSnbFromDir(fileName, path)
    
def passed():
    print "> Pass"

def failed():
    print "> Failed"

if __name__ == "__main__":

    print "Bambook SDK Unit Test"
    bb = Bambook()

    print "Disconnect State"
    if bb.GetState() == CONN_DISCONNECTED:
        passed()
    else:
        failed()

    print "Get SDK Version"
    if bb.GetSDKVersion() == BAMBOOK_SDK_VERSION:
        passed()
    else:
        failed()
        
    print "Verify good SNB File"
    if bb.VerifySNB(u'/tmp/f8268e6c1f4e78c.snb'):
        passed()
    else:
        failed()

    print "Verify bad SNB File"
    if not bb.VerifySNB('./libwrapper.py'):
        passed()
    else:
        failed()
        
    print "Extract SNB File"
    if bb.ExtractSNB('./test.snb', '/tmp/test'):
        passed()
    else:
        failed()
    
    print "Packet SNB File"
    if bb.PackageSNB('/tmp/tmp.snb', '/tmp/test') and bb.VerifySNB('/tmp/tmp.snb'):
        passed()
    else:
        failed()

    print "Connect to Bambook"
    if bb.Connect('192.168.250.2', 10000) and bb.GetState() == CONN_CONNECTED:
        passed()
    else:
        failed()

    print "Get Bambook Info"
    devInfo = bb.GetDeviceInfo()
    if devInfo:
#        print "Info Size: ", devInfo.cbSize
#        print "SN: ", devInfo.sn
#        print "Firmware: ", devInfo.firmwareVersion
#        print "Capacity: ", devInfo.deviceVolume
#        print "Free: ", devInfo.spareVolume
        if devInfo.cbSize == 52 and devInfo.deviceVolume == 1714232:
            passed()
    else:
        failed()

    print "Send file"
    if bb.SendFile('/tmp/tmp.snb'):
        passed()
    else:
        failed()
    
    print "Get book list"
    books = bb.GetBookList()
    if len(books) > 10:
        passed()
    else:
        failed()

    print "Get book"
    if bb.GetFile('f8268e6c1f4e78c.snb', '/tmp') and bb.VerifySNB('/tmp/f8268e6c1f4e78c.snb'):
        passed()
    else:
        failed()

    print "Disconnect"
    if bb.Disconnect():
        passed()
    else:
        failed()
