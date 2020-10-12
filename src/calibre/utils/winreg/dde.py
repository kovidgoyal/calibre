#!/usr/bin/env python
# vim:fileencoding=utf-8


__license__ = 'GPL v3'
__copyright__ = '2015, Kovid Goyal <kovid at kovidgoyal.net>'

import numbers
from ctypes import POINTER, WINFUNCTYPE, c_void_p, c_ulong, c_char_p, windll, byref
from ctypes.wintypes import BOOL, DWORD, LPCWSTR, UINT

from polyglot.builtins import itervalues

HCONV     = c_void_p  # = DECLARE_HANDLE(HCONV)
HDDEDATA  = c_void_p  # = DECLARE_HANDLE(HDDEDATA)
HSZ       = c_void_p  # = DECLARE_HANDLE(HSZ)
LPBYTE    = c_char_p  # POINTER(BYTE)
LPDWORD   = POINTER(DWORD)
LPSTR    = c_char_p
ULONG_PTR = c_ulong

DML_ERRORS = {
    'ADVACKTIMEOUT': (0x4000, 'A request for a synchronous advise transaction has timed out.'),

    'BUSY': (0x4001, 'The response to the transaction caused the DDE_FBUSY flag to be set.'),

    'DATAACKTIMEOUT': (0x4002, 'A request for a synchronous data transaction has timed out.'),

    'DLL_NOT_INITIALIZED': (0x4003, 'A DDEML function was called without first calling the DdeInitialize function, or an invalid instance identifier was passed to a DDEML function.'),  # noqa

    'DLL_USAGE': (0x4004, 'An application initialized as APPCLASS_MONITOR has attempted to perform a DDE transaction, or an application initialized as APPCMD_CLIENTONLY has attempted to perform server transactions.'),  # noqa

    'EXECACKTIMEOUT': (0x4005, 'A request for a synchronous execute transaction has timed out.'),

    'INVALIDPARAMETER': (0x4006, 'An invalid transaction identifier was passed to a DDEML function. Once the application has returned from an XTYP_XACT_COMPLETE callback, the transaction identifier for that callback function is no longer valid.  A parameter failed to be validated by the DDEML. Some of the possible causes follow: The application used a data handle initialized with a different item name handle than was required by the transaction.  The application used a data handle that was initialized with a different clipboard data format than was required by the transaction.  The application used a client-side conversation handle with a server-side function or vice versa.  The application used a freed data handle or string handle.  More than one instance of the application used the same object.'),  # noqa

    'LOW_MEMORY': (0x4007, 'A DDEML application has created a prolonged race condition (in which the server application outruns the client), causing large amounts of memory to be consumed.'),  # noqa

    'MEMORY_ERROR': (0x4008, 'A memory allocation has failed.'),

    'NO_CONV_ESTABLISHED': (0x400a, 'A client\'s attempt to establish a conversation has failed.'),

    'NOTPROCESSED': (0x4009, 'A transaction has failed.'),

    'POKEACKTIMEOUT': (0x400b, 'A request for a synchronous poke transaction has timed out.'),

    'POSTMSG_FAILED': (0x400c, 'An internal call to the PostMessage function has failed.'),

    'REENTRANCY': (0x400d, 'An application instance with a synchronous transaction already in progress attempted to initiate another synchronous transaction, or the DdeEnableCallback function was called from within a DDEML callback function.'),  # noqa

    'SERVER_DIED': (0x400e, 'A server-side transaction was attempted on a conversation terminated by the client, or the server terminated before completing a transaction.'),  # noqa

    'SYS_ERROR': (0x400f, 'An internal error has occurred in the DDEML.'),

    'UNADVACKTIMEOUT': (0x4010, 'A request to end an advise transaction has timed out.'),

    'UNFOUND_QUEUE_ID': (0x4011, 'An invalid transaction identifier was passed to a DDEML function. Once the application has returned from an XTYP_XACT_COMPLETE callback, the transaction identifier for that callback function is no longer valid.'),  # noqa
}
DML_ERROR_TEXT = {code:text for (code, text) in itervalues(DML_ERRORS)}

user32 = windll.user32

DDECALLBACK = WINFUNCTYPE(HDDEDATA, UINT, UINT, HCONV, HSZ, HSZ, HDDEDATA, ULONG_PTR, ULONG_PTR)
APPCMD_CLIENTONLY = 0x10
CP_WINUNICODE = 1200
# See windows/ddeml.h for declaration of struct CONVCONTEXT
PCONVCONTEXT = c_void_p
XCLASS_FLAGS         = 0x4000
XTYP_EXECUTE         = (0x0050 | XCLASS_FLAGS)


class DDEError(ValueError):
    pass


def init_errcheck(result, func, args):
    if result != 0:
        raise DDEError('Failed to initialize DDE client with return code: %x' % result)
    return args


def no_errcheck(result, func, args):
    return args


def dde_error(instance):
    errcode = GetLastError(instance)
    raise DDEError(DML_ERRORS.get(errcode, 'Unknown DDE error code: %x' % errcode))


def default_errcheck(result, func, args):
    if (isinstance(result, numbers.Integral) and result == 0) or (getattr(result, 'value', False) is None):
        dde_error(args[0])
    return args


null = object()


class a(object):

    def __init__(self, name, typ, default=null, in_arg=True):
        self.typ=typ
        if default is null:
            self.spec=((1 if in_arg else 2), name)
        else:
            self.spec=((1 if in_arg else 2), name, default)


def cwrap(name, restype, *args, **kw):
    params=(restype,) + tuple(x.typ for x in args)
    paramflags=tuple(x.spec for x in args)
    func=WINFUNCTYPE(*params)((name, kw.get('lib', user32)), paramflags)
    func.errcheck=kw.get('errcheck', default_errcheck)
    return func


GetLastError = cwrap('DdeGetLastError', UINT, a('instance', DWORD), errcheck=no_errcheck)

Initialize = cwrap('DdeInitializeW', UINT, a('instance_p', LPDWORD), a('callback', DDECALLBACK), a('command', DWORD),
                   a('reserved', DWORD, 0), errcheck=init_errcheck)
CreateStringHandle = cwrap('DdeCreateStringHandleW', HSZ, a('instance', DWORD), a('string', LPCWSTR), a('codepage', UINT, CP_WINUNICODE))
Connect = cwrap('DdeConnect', HCONV, a('instance', DWORD), a('service', HSZ), a('topic', HSZ), a('context', PCONVCONTEXT))
FreeStringHandle = cwrap('DdeFreeStringHandle', BOOL, a('instance', DWORD), a('handle', HSZ), errcheck=no_errcheck)
ClientTransaction = cwrap('DdeClientTransaction', HDDEDATA, a('data', LPBYTE), a('size', DWORD), a('conversation', HCONV), a('item', HSZ),
                          a('fmt', UINT, 0), a('type', UINT, XTYP_EXECUTE), a('timeout', DWORD, 5000), a('result', LPDWORD, LPDWORD()), errcheck=no_errcheck)
FreeDataHandle = cwrap('DdeFreeDataHandle', BOOL, a('data', HDDEDATA), errcheck=no_errcheck)
Disconnect = cwrap('DdeDisconnect', BOOL, a('conversation', HCONV), errcheck=no_errcheck)
Uninitialize = cwrap('DdeUninitialize', BOOL, a('instance', DWORD), errcheck=no_errcheck)


def send_dde_command(service, topic, command):
    instance = DWORD(0)

    def cb(*args):
        pass  # ignore callbacks
    callback = DDECALLBACK(cb)

    Initialize(byref(instance), callback, APPCMD_CLIENTONLY, 0)
    hservice = CreateStringHandle(instance, service)
    htopic = CreateStringHandle(instance, topic)
    conversation = Connect(instance, hservice, htopic, PCONVCONTEXT())
    FreeStringHandle(instance, hservice)
    FreeStringHandle(instance, htopic)
    data = c_char_p(command)
    sz = DWORD(len(command) + 1)
    res = ClientTransaction(data, sz, conversation, HSZ())
    if res == 0:
        dde_error(instance)
    FreeDataHandle(res)
    Disconnect(conversation)
    Uninitialize(instance)


if __name__ == '__main__':
    send_dde_command('WinWord', 'System', '[REM_DDE_Direct][FileOpen("C:/cygwin64/home/kovid/demo.docx")]')
