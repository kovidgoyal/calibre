"""
Copyright (c) 2007 Ian Cook and John Popplewell

Permission is hereby granted, free of charge, to any person obtaining
a copy of this software and associated documentation files (the
"Software"), to deal in the Software without restriction, including
without limitation the rights to use, copy, modify, merge, publish,
distribute, sublicense, and/or sell copies of the Software, and to
permit persons to whom the Software is furnished to do so, subject to
the following conditions:

The above copyright notice and this permission notice shall be included
in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY
CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

Date    : 13 August 2007
Version : 1.0.2
Contact : John Popplewell
Email   : john@johnnypops.demon.co.uk
Web     : http://www.johnnypops.demon.co.uk/python/
Origin  : Based on the original script by Ian Cook
          http://www.kirbyfooty.com/simplemapi.py
Comments: Works (and tested) with:
          Outlook Express, Outlook 97 and 2000, 
          Eudora, Incredimail and Mozilla Thunderbird (1.5.0.2)
Thanks  : Werner F. Bruhin and Michele Petrazzo on the ctypes list.
          Lukas Lalinsky for patches and encouragement.

If you have any bug-fixes, enhancements or suggestions regarding this 
software, please contact me at the above email address.
"""

import os
from ctypes import *

FLAGS = c_ulong
LHANDLE = c_ulong
LPLHANDLE = POINTER(LHANDLE)

# Return codes
SUCCESS_SUCCESS                 = 0
MAPI_USER_ABORT                 = 1
MAPI_E_USER_ABORT               = MAPI_USER_ABORT
MAPI_E_FAILURE                  = 2
MAPI_E_LOGON_FAILURE            = 3
MAPI_E_LOGIN_FAILURE            = MAPI_E_LOGON_FAILURE
MAPI_E_DISK_FULL                = 4
MAPI_E_INSUFFICIENT_MEMORY      = 5
MAPI_E_ACCESS_DENIED            = 6
MAPI_E_TOO_MANY_SESSIONS        = 8
MAPI_E_TOO_MANY_FILES           = 9
MAPI_E_TOO_MANY_RECIPIENTS      = 10
MAPI_E_ATTACHMENT_NOT_FOUND     = 11
MAPI_E_ATTACHMENT_OPEN_FAILURE  = 12
MAPI_E_ATTACHMENT_WRITE_FAILURE = 13
MAPI_E_UNKNOWN_RECIPIENT        = 14
MAPI_E_BAD_RECIPTYPE            = 15
MAPI_E_NO_MESSAGES              = 16
MAPI_E_INVALID_MESSAGE          = 17
MAPI_E_TEXT_TOO_LARGE           = 18
MAPI_E_INVALID_SESSION          = 19
MAPI_E_TYPE_NOT_SUPPORTED       = 20
MAPI_E_AMBIGUOUS_RECIPIENT      = 21
MAPI_E_AMBIG_RECIP              = MAPI_E_AMBIGUOUS_RECIPIENT
MAPI_E_MESSAGE_IN_USE           = 22
MAPI_E_NETWORK_FAILURE          = 23
MAPI_E_INVALID_EDITFIELDS       = 24
MAPI_E_INVALID_RECIPS           = 25
MAPI_E_NOT_SUPPORTED            = 26
# Recipient class
MAPI_ORIG       = 0
MAPI_TO         = 1
# Send flags
MAPI_LOGON_UI   = 1
MAPI_DIALOG     = 8

class MapiRecipDesc(Structure):
    _fields_ = [
        ('ulReserved',      c_ulong),
        ('ulRecipClass',    c_ulong),
        ('lpszName',        c_char_p),
        ('lpszAddress',     c_char_p),
        ('ulEIDSize',       c_ulong),
        ('lpEntryID',       c_void_p),
    ]
lpMapiRecipDesc  = POINTER(MapiRecipDesc)
lppMapiRecipDesc = POINTER(lpMapiRecipDesc)

class MapiFileDesc(Structure):
    _fields_ = [
        ('ulReserved',      c_ulong),
        ('flFlags',         c_ulong),
        ('nPosition',       c_ulong),
        ('lpszPathName',    c_char_p),
        ('lpszFileName',    c_char_p),
        ('lpFileType',      c_void_p),
    ]
lpMapiFileDesc = POINTER(MapiFileDesc)

class MapiMessage(Structure):
    _fields_ = [
        ('ulReserved',          c_ulong),
        ('lpszSubject',         c_char_p),
        ('lpszNoteText',        c_char_p),
        ('lpszMessageType',     c_char_p),
        ('lpszDateReceived',    c_char_p),
        ('lpszConversationID',  c_char_p),
        ('flFlags',             FLAGS),
        ('lpOriginator',        lpMapiRecipDesc),
        ('nRecipCount',         c_ulong),
        ('lpRecips',            lpMapiRecipDesc),
        ('nFileCount',          c_ulong),
        ('lpFiles',             lpMapiFileDesc),
    ]
lpMapiMessage = POINTER(MapiMessage)

MAPI                    = windll.mapi32
MAPISendMail            = MAPI.MAPISendMail
MAPISendMail.restype    = c_ulong
MAPISendMail.argtypes   = (LHANDLE, c_ulong, lpMapiMessage, FLAGS, c_ulong)

MAPIResolveName         = MAPI.MAPIResolveName
MAPIResolveName.restype = c_ulong
MAPIResolveName.argtypes= (LHANDLE, c_ulong, c_char_p, FLAGS, c_ulong, lppMapiRecipDesc)

MAPIFreeBuffer          = MAPI.MAPIFreeBuffer
MAPIFreeBuffer.restype  = c_ulong
MAPIFreeBuffer.argtypes = (c_void_p, )

MAPILogon               = MAPI.MAPILogon
MAPILogon.restype       = c_ulong
MAPILogon.argtypes      = (LHANDLE, c_char_p, c_char_p, FLAGS, c_ulong, LPLHANDLE)

MAPILogoff              = MAPI.MAPILogoff
MAPILogoff.restype      = c_ulong
MAPILogoff.argtypes     = (LHANDLE, c_ulong, FLAGS, c_ulong)


class MAPIError(WindowsError):

    def __init__(self, code):
        WindowsError.__init__(self)
        self.code = code

    def __str__(self):
        return 'MAPI error %d' % (self.code,)


def _logon(profileName=None, password=None):
    pSession = LHANDLE()
    rc = MAPILogon(0, profileName, password, MAPI_LOGON_UI, 0, byref(pSession))
    if rc != SUCCESS_SUCCESS:
        raise MAPIError, rc
    return pSession


def _logoff(session):
    rc = MAPILogoff(session, 0, 0, 0)
    if rc != SUCCESS_SUCCESS:
        raise MAPIError, rc


def _resolveName(session, name):
    pRecipDesc = lpMapiRecipDesc()
    rc = MAPIResolveName(session, 0, name, 0, 0, byref(pRecipDesc))
    if rc != SUCCESS_SUCCESS:
        raise MAPIError, rc
    rd = pRecipDesc.contents
    name, address = rd.lpszName, rd.lpszAddress
    rc = MAPIFreeBuffer(pRecipDesc)
    if rc != SUCCESS_SUCCESS:
        raise MAPIError, rc
    return name, address


def _sendMail(session, recipient, subject, body, attach, preview):
    nFileCount = len(attach)
    if attach: 
        MapiFileDesc_A = MapiFileDesc * len(attach) 
        fda = MapiFileDesc_A() 
        for fd, fa in zip(fda, attach): 
            fd.ulReserved = 0 
            fd.flFlags = 0 
            fd.nPosition = -1 
            fd.lpszPathName = fa 
            fd.lpszFileName = None 
            fd.lpFileType = None 
        lpFiles = fda
    else:
        lpFiles = lpMapiFileDesc()

    RecipWork = recipient.split(';')
    RecipCnt = len(RecipWork)
    MapiRecipDesc_A = MapiRecipDesc * len(RecipWork) 
    rda = MapiRecipDesc_A() 
    for rd, ra in zip(rda, RecipWork):
        rd.ulReserved = 0 
        rd.ulRecipClass = MAPI_TO
        try:
            rd.lpszName, rd.lpszAddress = _resolveName(session, ra)
        except WindowsError:
            # work-round for Mozilla Thunderbird
            rd.lpszName, rd.lpszAddress = None, ra
        rd.ulEIDSize = 0
        rd.lpEntryID = None
    recip = rda

    msg = MapiMessage(0, subject, body, None, None, None, 0, lpMapiRecipDesc(),
                      RecipCnt, recip,
                      nFileCount, lpFiles)
    flags = 0
    if preview:
        flags = MAPI_DIALOG
    rc = MAPISendMail(session, 0, byref(msg), flags, 0)
    if rc != SUCCESS_SUCCESS:
        raise MAPIError, rc


def SendMail(recipient, subject="", body="", attachfiles="", preview=1):
    """Post an e-mail message using Simple MAPI
    
    recipient - string: address to send to (multiple addresses separated with a semicolon)
    subject   - string: subject header
    body      - string: message text
    attach    - string: files to attach (multiple attachments separated with a semicolon)
    preview   - bool  : if false, minimise user interaction. Default:true
    """

    attach = []
    AttachWork = attachfiles.split(';')
    for filename in AttachWork:
        if os.path.exists(filename):
            attach.append(filename)
    attach = map(os.path.abspath, attach)

    restore = os.getcwd()
    try:
        session = _logon()
        try:
            _sendMail(session, recipient, subject, body, attach, preview)
        finally:
            _logoff(session)
    finally:
        os.chdir(restore)


if __name__ == '__main__':
    import sys
    recipient = "test@johnnypops.demon.co.uk"
    subject = "Test Message Subject"
    body = "Hi,\r\n\r\nthis is a quick test message,\r\n\r\ncheers,\r\nJohn."
    attachment = sys.argv[0]
    SendMail(recipient, subject, body, attachment)


