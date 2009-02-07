__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
"""
Defines the structure of packets that are sent to/received from the device. 

Packet structure is defined using classes and inheritance. Each class is a 
view that imposes structure on the underlying data buffer. 
The data buffer is encoded in little-endian format, but you don't
have to worry about that if you are using the classes. 
The classes have instance variables with getter/setter functions defined
to take care of the encoding/decoding. 
The classes are intended to mimic C structs. 

There are three kinds of packets. L{Commands<Command>}, 
L{Responses<Response>}, and L{Answers<Answer>}. 
C{Commands} are sent to the device on the control bus, 
C{Responses} are received from the device, 
also on the control bus. C{Answers} and their sub-classes represent 
data packets sent to/received from the device via bulk transfers. 

Commands are organized as follows: G{classtree Command}

You will typically only use sub-classes of Command. 

Responses are organized as follows: G{classtree Response}

Responses inherit Command as they share header structure.

Answers are organized as follows: G{classtree Answer}
"""

import struct
import time
from datetime import datetime

from calibre.devices.errors import PacketError

WORD      = "<H"    #: Unsigned integer little endian encoded in 2 bytes
DWORD     = "<I"    #: Unsigned integer little endian encoded in 4 bytes
DDWORD    = "<Q"    #: Unsigned long long little endian encoded in 8 bytes


class PathResponseCodes(object):
    """ Known response commands to path related commands """
    NOT_FOUND    = 0xffffffd7
    INVALID      = 0xfffffff9
    IS_FILE      = 0xffffffd2
    HAS_CHILDREN = 0xffffffcc
    PERMISSION_DENIED = 0xffffffd6


class TransferBuffer(list):
    
    """
    Represents raw (unstructured) data packets sent over the usb bus.
    
    C{TransferBuffer} is a wrapper around the tuples used by libusb for communication. 
    It has convenience methods to read and write data from the underlying buffer. See 
    L{TransferBuffer.pack} and L{TransferBuffer.unpack}.
    """
    
    def __init__(self, packet):
        """ 
        Create a L{TransferBuffer} from C{packet} or an empty buffer.
        
        @type packet: integer or listable object
        @param packet: If packet is a list, it is copied into the C{TransferBuffer} and then normalized (see L{TransferBuffer._normalize}).
        If it is an integer, a zero buffer of that length is created.
        """    
        if "__len__" in dir(packet): 
            list.__init__(self, list(packet))
            self._normalize()
        else: list.__init__(self, [0 for i in range(packet)])
    
    def __add__(self, tb):
        """ Return a TransferBuffer rather than a list as the sum """
        return TransferBuffer(list.__add__(self, tb))
    
    def __getslice__(self, start, end):
        """ Return a TransferBuffer rather than a list as the slice """
        return TransferBuffer(list.__getslice__(self, start, end))
    
    def __str__(self):
        """
        Return a string representation of this buffer.
        
        Packets are represented as hex strings, in 2-byte pairs, S{<=} 16 bytes to a line. 
        An ASCII representation is included. For example::
        0700 0100 0000 0000 0000 0000 0c00 0000         ................
        0200 0000 0400 0000 4461 7461                   ........Data
        """
        ans, ascii = ": ".rjust(10,"0"), ""
        for i in range(0, len(self), 2):
            for b in range(2):
                try: 
                    ans   += TransferBuffer.phex(self[i+b])
                    ascii += chr(self[i+b]) if self[i+b] > 31 and self[i+b] < 127 else "."
                except IndexError: break      
            ans = ans + " "
            if (i+2)%16 == 0:
                if i+2 < len(self):
                    ans += "   " + ascii + "\n" + (TransferBuffer.phex(i+2)+": ").rjust(10, "0")
                    ascii = ""
        last_line = ans[ans.rfind("\n")+1:]
        padding = 50 - len(last_line)
        ans += "".ljust(padding) + "   " + ascii
        return ans.strip()
    
    def unpack(self, fmt=DWORD, start=0):
        """ 
        Return decoded data from buffer. 
        
        @param fmt: See U{struct<http://docs.python.org/lib/module-struct.html>}
        @param start: Position in buffer from which to decode
        """
        end = start + struct.calcsize(fmt)    
        return struct.unpack(fmt, "".join([ chr(i) for i in list.__getslice__(self, start, end) ]))
    
    def pack(self, val, fmt=DWORD, start=0):
        """ 
        Encode C{val} and write it to buffer. For fmt==WORD val is  
        adjusted to be in the range 0 <= val < 256**2.
        
        @param fmt: See U{struct<http://docs.python.org/lib/module-struct.html>}
        @param start: Position in buffer at which to write encoded data
        """
        # struct.py is fussy about packing values into a WORD. The value must be
        # between 0 and 65535 or a DeprecationWarning is raised. In the future 
        # this may become an error, so it's best to take care of wrapping here.
        if fmt == WORD:
            val = val % 256**2
        self[start:start+struct.calcsize(fmt)] = \
                                    [ ord(i) for i in struct.pack(fmt, val) ]
        
    def _normalize(self):
        """ Replace negative bytes in C{self} by 256 + byte """
        for i in range(len(self)):
            if self[i] < 0:         
                self[i] = 256 + self[i]    
    
    @classmethod
    def phex(cls, num):
        """ 
        Return the hex representation of num without the 0x prefix. 
        
        If the hex representation is only 1 digit it is padded to the left with a zero. Used in L{TransferBuffer.__str__}.
        """
        index, sign = 2, ""
        if num < 0: 
            index, sign  = 3, "-"
        h = hex(num)[index:]
        if len(h) < 2: 
            h = "0"+h
        return sign + h


class field(object):
    """ A U{Descriptor<http://www.cafepy.com/article/python_attributes_and_methods/python_attributes_and_methods.html>}, that implements access
    to protocol packets in a human readable way. 
    """
    def __init__(self, start=16, fmt=DWORD):
        """
        @param start: The byte at which this field is stored in the buffer
        @param fmt:   The packing format for this field. 
        See U{struct<http://docs.python.org/lib/module-struct.html>}.
        """
        self._fmt, self._start = fmt, start    
    
    def __get__(self, obj, typ=None):
        return obj.unpack(start=self._start, fmt=self._fmt)[0]
    
    def __set__(self, obj, val):
        obj.pack(val, start=self._start, fmt=self._fmt)
    
    def __repr__(self):
        typ = ""
        if self._fmt == DWORD: 
            typ  = "unsigned int"
        if self._fmt == DDWORD: 
            typ = "unsigned long long"
        return "An " + typ + " stored in " + \
        str(struct.calcsize(self._fmt)) + \
        " bytes starting at byte " + str(self._start)

class stringfield(object):
    """ A field storing a variable length string. """
    def __init__(self, length_field, start=16):
        """
        @param length_field: A U{Descriptor<http://www.cafepy.com/article/python_attributes_and_methods/python_attributes_and_methods.html>} 
        that returns the length of the string.
        @param start: The byte at which this field is stored in the buffer
        """
        self._length_field = length_field
        self._start = start
    
    def __get__(self, obj, typ=None):    
        length = str(self._length_field.__get__(obj))
        return obj.unpack(start=self._start, fmt="<"+length+"s")[0]
    
    def __set__(self, obj, val):
        if isinstance(val, unicode):
            val = val.encode('utf8')
        else:
            val = str(val)
        obj.pack(val, start=self._start, fmt="<"+str(len(val))+"s")
    
    def __repr__(self):
        return "A string starting at byte " + str(self._start)

class Command(TransferBuffer):
    
    """ Defines the structure of command packets sent to the device. """
    #    Command number. C{unsigned int} stored in 4 bytes at byte 0.
    #    
    #    Command numbers are:
    #    0 GetUsbProtocolVersion
    #    1 ReqEndSession      
    #    10 FskFileOpen
    #    11 FskFileClose
    #    12 FskGetSize
    #    13 FskSetSize
    #    14 FskFileSetPosition
    #    15 FskGetPosition
    #    16 FskFileRead
    #    17 FskFileWrite
    #    18 FskFileGetFileInfo
    #    19 FskFileSetFileInfo
    #    1A FskFileCreate
    #    1B FskFileDelete
    #    1C FskFileRename      
    #    30 FskFileCreateDirectory
    #    31 FskFileDeleteDirectory
    #    32 FskFileRenameDirectory
    #    33 FskDirectoryIteratorNew
    #    34 FskDirectoryIteratorDispose
    #    35 FskDirectoryIteratorGetNext      
    #    52 FskVolumeGetInfo
    #    53 FskVolumeGetInfoFromPath      
    #    80 FskFileTerminate     
    #    100 ConnectDevice
    #    101 GetProperty
    #    102 GetMediaInfo
    #    103 GetFreeSpace
    #    104 SetTime
    #    105 DeviceBeginEnd
    #    106 UnlockDevice
    #    107 SetBulkSize      
    #    110 GetHttpRequest
    #    111 SetHttpRespponse
    #    112 Needregistration
    #    114 GetMarlinState    
    #    200 ReqDiwStart
    #    201 SetDiwPersonalkey
    #    202 GetDiwPersonalkey
    #    203 SetDiwDhkey
    #    204 GetDiwDhkey
    #    205 SetDiwChallengeserver
    #    206 GetDiwChallengeserver
    #    207 GetDiwChallengeclient
    #    208 SetDiwChallengeclient
    #    209 GetDiwVersion
    #    20A SetDiwWriteid
    #    20B GetDiwWriteid
    #    20C SetDiwSerial
    #    20D GetDiwModel
    #    20C SetDiwSerial
    #    20E GetDiwDeviceid
    #    20F GetDiwSerial
    #    210 ReqDiwCheckservicedata
    #    211 ReqDiwCheckiddata
    #    212 ReqDiwCheckserialdata
    #    213 ReqDiwFactoryinitialize
    #    214 GetDiwMacaddress
    #    215 ReqDiwTest
    #    216 ReqDiwDeletekey    
    #    300 UpdateChangemode
    #    301 UpdateDeletePartition
    #    302 UpdateCreatePartition
    #    303 UpdateCreatePartitionWithImage
    #    304 UpdateGetPartitionSize    
    number = field(start=0, fmt=DWORD)
    # Known types are 0x00 and 0x01. Acknowledge commands are always type 0x00
    type   = field(start=4, fmt=DDWORD) 
    # Length of the data part of this packet
    length = field(start=12, fmt=DWORD) 
    
    @dynamic_property
    def data(self):
        doc = \
        """ 
        The data part of this command. Returned/set as/by a TransferBuffer. 
        Stored at byte 16.
        
        Setting it by default changes self.length to the length of the new 
        buffer. You may have to reset it to  the significant part of the buffer.
        You would normally use the C{command} property of 
        L{ShortCommand} or L{LongCommand} instead.
        """
        def fget(self):
            return self[16:]
        
        def fset(self, buff):
            self[16:] = buff
            self.length = len(buff)
        
        return property(doc=doc, fget=fget, fset=fset)
    
    def __init__(self, packet):
        """
        @param packet: len(packet) > 15 or packet > 15
        """
        if ("__len__" in dir(packet) and len(packet) < 16) or\
           ("__len__" not in dir(packet) and packet < 16): 
            raise PacketError(str(self.__class__)[7:-2] + \
                      " packets must have length atleast 16")    
        TransferBuffer.__init__(self, packet)


class SetTime(Command):
    """ 
    Set time on device. All fields refer to time in the GMT time zone.
    """
    NUMBER = 0x104
    # -time.timezone with negative numbers encoded 
    # as int(0xffffffff +1 -time.timezone/60.)
    timezone = field(start=0x10, fmt=DWORD) 
    year        = field(start=0x14, fmt=DWORD) #: year e.g. 2006
    month    = field(start=0x18, fmt=DWORD)  #: month 1-12
    day         = field(start=0x1c, fmt=DWORD) #: day 1-31
    hour       = field(start=0x20, fmt=DWORD) #: hour 0-23
    minute   = field(start=0x24, fmt=DWORD) #: minute 0-59
    second   = field(start=0x28, fmt=DWORD) #: second 0-59
    
    def __init__(self, t=None):
        """ @param t: time as an epoch """
        self.number = SetTime.NUMBER
        self.type = 0x01
        self.length = 0x1c
        td = datetime.now() - datetime.utcnow()
        tz = int((td.days*24*3600 + td.seconds)/60.)
        self.timezone = tz if tz > 0 else 0xffffffff +1 + tz
        if not t: t = time.time()
        t = time.gmtime(t)
        self.year = t[0]
        self.month = t[1]
        self.day = t[2]
        self.hour = t[3]
        self.minute = t[4]
        # Hack you should actually update the entire time tree if 
        # second is > 59
        self.second = t[5] if t[5] < 60 else 59 


class ShortCommand(Command):  
    
    """ A L{Command} whose data section is 4 bytes long """  
    
    SIZE = 20 #: Packet size in bytes
    # Usually carries additional information
    command = field(start=16, fmt=DWORD) 
    
    def __init__(self, number=0x00, type=0x00, command=0x00):
        """
        @param number: L{Command.number}
        @param type: L{Command.type}
        @param command: L{ShortCommand.command}
        """
        Command.__init__(self, ShortCommand.SIZE)
        self.number  = number
        self.type    = type
        self.length  = 4
        self.command = command

class DirRead(ShortCommand):
    """ The command that asks the device to send the next item in the list """
    NUMBER = 0x35 #: Command number
    def __init__(self, _id):
        """ @param id: The identifier returned as a result of a L{DirOpen} command """
        ShortCommand.__init__(self, number=DirRead.NUMBER, type=0x01, \
                                             command=_id)

class DirClose(ShortCommand):
    """ Close a previously opened directory """
    NUMBER = 0x34 #: Command number
    def __init__(self, _id):
        """ @param id: The identifier returned as a result of a L{DirOpen} command """
        ShortCommand.__init__(self, number=DirClose.NUMBER, type=0x01, 
                                            command=_id)

class BeginEndSession(ShortCommand):
    """ 
    Ask device to either start or end a session.
    """
    NUMBER = 0x01 #: Command number
    def __init__(self, end=True):
        command = 0x00 if end else 0x01
        ShortCommand.__init__(self, \
        number=BeginEndSession.NUMBER, type=0x01, command=command)

class GetUSBProtocolVersion(ShortCommand):
    """ Get USB Protocol version used by device """
    NUMBER = 0x0 #: Command number
    def __init__(self):
        ShortCommand.__init__(self, \
        number=GetUSBProtocolVersion.NUMBER, \
        type=0x01, command=0x00)

class SetBulkSize(Command):
    """ Set size for bulk transfers in this session """
    NUMBER = 0x107 #: Command number
    chunk_size = field(fmt=WORD, start=0x10)
    unknown = field(fmt=WORD, start=0x12)
    def __init__(self, chunk_size=0x8000, unknown=0x2):
        Command.__init__(self, [0 for i in range(24)])
        self.number = SetBulkSize.NUMBER
        self.type = 0x01
        self.chunk_size = chunk_size
        self.unknown = unknown

class UnlockDevice(Command):
    """ Unlock the device """
    NUMBER = 0x106 #: Command number  
    key = stringfield(8, start=16) #: The key defaults to -1
    
    def __init__(self, key='-1\0\0\0\0\0\0'):
        Command.__init__(self, 24)
        self.number = UnlockDevice.NUMBER
        self.type = 0x01
        self.length = 8
        self.key = key

class LongCommand(Command):
    
    """ A L{Command} whose data section is 16 bytes long """
    
    SIZE = 32 #: Size in bytes of C{LongCommand} packets
    
    def __init__(self, number=0x00, type=0x00, command=0x00):
        """ 
        @param number: L{Command.number}
        @param type: L{Command.type}
        @param command: L{LongCommand.command}
        """    
        Command.__init__(self, LongCommand.SIZE)
        self.number  = number
        self.type    = type 
        self.length  = 16
        self.command = command
    
    @dynamic_property
    def command(self):
        doc = \
        """ 
        Usually carries extra information needed for the command
        It is a list of C{unsigned integers} of length between 1 and 4. 4 
        C{unsigned int} stored in 16 bytes at byte 16.
        """
        def fget(self):
            return self.unpack(start=16, fmt="<"+str(self.length/4)+"I")
        
        def fset(self, val):
            if "__len__" not in dir(val): val = (val,)
            start = 16
            for command in val:
                self.pack(command, start=start, fmt=DWORD)
                start += struct.calcsize(DWORD)
        
        return property(doc=doc, fget=fget, fset=fset)

class PathCommand(Command):
    """ Abstract class that defines structure common to all path related commands. """
    
    path_length = field(start=16, fmt=DWORD)         #: Length of the path to follow
    path             = stringfield(path_length, start=20) #: The path this query is about
    def __init__(self, path, number, path_len_at_byte=16):    
        Command.__init__(self, path_len_at_byte+4+len(path))
        if isinstance(path, unicode):
            path = path.encode('utf8')
        self.path_length = len(path)
        self.path = path
        self.type = 0x01
        self.length = len(self) - 16
        self.number = number

class TotalSpaceQuery(PathCommand):
    """ Query the total space available on the volume represented by path """
    NUMBER = 0x53 #: Command number  
    def __init__(self, path):
        """ @param path: valid values are 'a:', 'b:', '/Data/' """ 
        PathCommand.__init__(self, path, TotalSpaceQuery.NUMBER)

class FreeSpaceQuery(ShortCommand):
    """ Query the free space available """
    NUMBER = 0x103 #: Command number
    def __init__(self, where):
        """ @param where: valid values are: 'a:', 'b:', '/' """
        c = 0
        if where.startswith('a:'): c = 1
        elif where.startswith('b:'): c = 2
        ShortCommand.__init__(self, \
        number=FreeSpaceQuery.NUMBER, type=0x01, command=c)

class DirCreate(PathCommand):
    """ Create a directory """
    NUMBER = 0x30
    def __init__(self, path):
        PathCommand.__init__(self, path, DirCreate.NUMBER)

class DirOpen(PathCommand):  
    """ Open a directory for reading its contents  """  
    NUMBER     = 0x33 #: Command number
    def __init__(self, path):    
        PathCommand.__init__(self, path, DirOpen.NUMBER)


class AcknowledgeBulkRead(LongCommand):
    """ Must be sent to device after a bulk read """
    def __init__(self, bulk_read_id):
        """ 
        bulk_read_id is an integer, the id of the bulk read 
        we are acknowledging. See L{Answer.id} 
        """
        LongCommand.__init__(self, number=0x1000, \
        type=0x00, command=bulk_read_id)    

class DeviceInfoQuery(Command):
    """ The command used to ask for device information """
    NUMBER = 0x101 #: Command number
    def __init__(self):
        Command.__init__(self, 16)
        self.number = DeviceInfoQuery.NUMBER
        self.type = 0x01

class FileClose(ShortCommand):
    """ File close command """
    NUMBER = 0x11 #: Command number
    def __init__(self, _id):
        ShortCommand.__init__(self, number=FileClose.NUMBER, \
                                            type=0x01, command=_id)

class FileCreate(PathCommand):
    """ Create a file """
    NUMBER = 0x1a #: Command number
    def __init__(self, path):
        PathCommand.__init__(self, path, FileCreate.NUMBER)

class FileDelete(PathCommand):
    """ Delete a file """
    NUMBER = 0x1B
    def __init__(self, path):
        PathCommand.__init__(self, path, FileDelete.NUMBER)

class DirDelete(PathCommand):
    """ Delete a directory """
    NUMBER = 0x31
    def __init__(self, path):
        PathCommand.__init__(self, path, DirDelete.NUMBER)

class FileOpen(PathCommand):
    """ File open command """
    NUMBER = 0x10 #: Command number
    READ   = 0x00 #: Open file in read mode
    WRITE  = 0x01 #: Open file in write mode
    path_length = field(start=20, fmt=DWORD)
    path        = stringfield(path_length, start=24)
    
    def __init__(self, path, mode=0x00):
        PathCommand.__init__(self, path, FileOpen.NUMBER, path_len_at_byte=20)
        self.mode = mode
    
    @dynamic_property
    def mode(self):
        doc = \
                    """ 
                    The file open mode. Is either L{FileOpen.READ} 
                    or L{FileOpen.WRITE}. C{unsigned int} stored at byte 16. 
                    """
        def fget(self):
            return self.unpack(start=16, fmt=DWORD)[0]
        
        def fset(self, val):
            self.pack(val, start=16, fmt=DWORD)
        
        return property(doc=doc, fget=fget, fset=fset)


class FileIO(Command):
    """ Command to read/write from an open file """
    RNUMBER = 0x16 #: Command number to read from a file
    WNUMBER = 0x17 #: Command number to write  to a file
    id = field(start=16, fmt=DWORD) #: The file ID returned by a FileOpen command
    offset = field(start=20, fmt=DDWORD) #: offset in the file at which to read
    size = field(start=28, fmt=DWORD)   #: The number of bytes to reead from file.
    def __init__(self, _id, offset, size, mode=0x16):
        """
        @param _id:     File identifier returned by a L{FileOpen} command
        @type id: C{unsigned int}
        @param offset: Position in file at which to read
        @type offset: C{unsigned long long}
        @param size: number of bytes to read
        @type size: C{unsigned int}
        @param mode: Either L{FileIO.RNUMBER} or L{File.WNUMBER}
        """  
        Command.__init__(self, 32)
        self.number = mode
        self.type = 0x01
        self.length = 16
        self.id = _id
        self.offset = offset
        self.size = size


class PathQuery(PathCommand):  
    """ Defines structure of command that requests information about a path """  
    NUMBER     = 0x18 #: Command number  
    def __init__(self, path):    
        PathCommand.__init__(self, path, PathQuery.NUMBER)

class SetFileInfo(PathCommand):
    """ Set File information """
    NUMBER = 0x19 #: Command number  
    def __init__(self, path):
        PathCommand.__init__(self, path, SetFileInfo.NUMBER)

class Response(Command):
    """ 
    Defines the structure of response packets received from the device. 
    
    C{Response} inherits from C{Command} as the 
    first 16 bytes have the same structure.
    """
    
    SIZE      = 32              #: Size of response packets in the SONY protocol 
    # Response number, the command number of a command 
    # packet sent sometime before this packet was received
    rnumber   = field(start=16, fmt=DWORD)
   # Used to indicate error conditions. A value of 0 means 
   # there was no error 
    code      = field(start=20, fmt=DWORD) 
    # Used to indicate the size of the next bulk read
    data_size = field(start=28, fmt=DWORD) 
    
    def __init__(self, packet):
        """ C{len(packet) == Response.SIZE} """
        if len(packet) != Response.SIZE:
            raise PacketError(str(self.__class__)[7:-2] + \
            " packets must have exactly " + \
            str(Response.SIZE) + " bytes not " + str(len(packet)))
        Command.__init__(self, packet)
        if self.number != 0x00001000:
            raise PacketError("Response packets must have their number set to " \
            + hex(0x00001000))
    
    @dynamic_property
    def data(self):
        doc = \
                  """ 
                  The last 3 DWORDs (12 bytes) of data in this 
                  response packet. Returned as a list of unsigned integers.
                  """
        def fget(self):
            return self.unpack(start=20, fmt="<III")
        
        def fset(self, val):
            self.pack(val, start=20, fmt="<III")
        
        return property(doc=doc, fget=fget, fset=fset)

class ListResponse(Response):
    
    """ 
    Defines the structure of response packets received 
    during list (ll) queries. See L{PathQuery}. 
    """
    
    IS_FILE        = 0xffffffd2 #: Queried path is a file 
    IS_INVALID     = 0xfffffff9 #: Queried path is malformed/invalid
    # Queried path is not mounted (i.e. a removed storage card/stick)
    IS_UNMOUNTED   = 0xffffffc8 
    IS_EOL         = 0xfffffffa #: There are no more entries in the list
    PATH_NOT_FOUND = 0xffffffd7 #: Queried path is not found 
    PERMISSION_DENIED = 0xffffffd6 #: Permission denied
    
    @dynamic_property
    def is_file(self):
        doc = """ True iff queried path is a file """
        def fget(self):      
            return self.code == ListResponse.IS_FILE
        return property(doc=doc, fget=fget)
    
    @dynamic_property
    def is_invalid(self):
        doc = """ True iff queried path is invalid """
        def fget(self):    
            return self.code == ListResponse.IS_INVALID
        return property(doc=doc, fget=fget)
    
    @dynamic_property
    def path_not_found(self):
        doc = """ True iff queried path is not found """
        def fget(self):    
            return self.code == ListResponse.PATH_NOT_FOUND
        return property(doc=doc, fget=fget)
    
    @dynamic_property
    def permission_denied(self):
        doc = """ True iff permission is denied for path operations """
        def fget(self):    
            return self.code == ListResponse.PERMISSION_DENIED
        return property(doc=doc, fget=fget)
    
    @dynamic_property
    def is_unmounted(self):
        doc = """ True iff queried path is unmounted (i.e. removed storage card) """
        def fget(self):
            return self.code == ListResponse.IS_UNMOUNTED
        return property(doc=doc, fget=fget)
    
    @dynamic_property
    def is_eol(self):
        doc = """ True iff there are no more items in the list """
        def fget(self):
            return self.code == ListResponse.IS_EOL
        return property(doc=doc, fget=fget)

class Answer(TransferBuffer):
    """ 
    Defines the structure of packets sent to host via a 
    bulk transfer (i.e., bulk reads) 
    """
    
    number = field(start=0, fmt=DWORD)  #: Answer identifier
    length = field(start=12, fmt=DWORD) #: Length of data to follow
    
    def __init__(self, packet):
        """ @param packet: C{len(packet)} S{>=} C{16} """
        if "__len__" in dir(packet):
            if len(packet) < 16 : 
                raise PacketError(str(self.__class__)[7:-2] + \
                " packets must have a length of atleast 16 bytes. "\
                "Got initializer of " + str(len(packet)) + " bytes.")
        elif packet < 16:
            raise PacketError(str(self.__class__)[7:-2] + \
            " packets must have a length of atleast 16 bytes")
        TransferBuffer.__init__(self, packet)


class FileProperties(Answer):
    
    """ 
    Defines the structure of packets that contain size, date and 
    permissions information about files/directories. 
    """
    
    file_size   = field(start=16, fmt=DDWORD) #: Size in bytes of the file
    file_type   = field(start=24, fmt=DWORD)  #: 1 == file, 2 == dir
    ctime       = field(start=28, fmt=DWORD)  #: Creation time as an epoch
    wtime       = field(start=32, fmt=DWORD)  #: Modification time as an epoch
    # 0 = default permissions, 4 = read only
    permissions = field(start=36, fmt=DWORD)  
    
    @dynamic_property
    def is_dir(self):
        doc = """True if path points to a directory, False if it points to a file."""    
        
        def fget(self):
            return (self.file_type == 2)
        
        def fset(self, val):
            if val: 
                val = 2
            else: 
                val = 1
            self.file_type = val
        
        return property(doc=doc, fget=fget, fset=fset)
    
    
    @dynamic_property
    def is_readonly(self):
        doc = """ Whether this file is readonly."""
        
        def fget(self):
            return self.unpack(start=36, fmt=DWORD)[0] != 0
        
        def fset(self, val):
            if val: 
                val = 4
            else: 
                val = 0
            self.pack(val, start=36, fmt=DWORD)
        
        return property(doc=doc, fget=fget, fset=fset)


class USBProtocolVersion(Answer):
    """ Get USB Protocol version """
    version = field(start=16, fmt=DDWORD)

class IdAnswer(Answer):
    
    """ Defines the structure of packets that contain identifiers for queries. """
    
    @dynamic_property
    def id(self):
        doc = \
        """ 
        The identifier. C{unsigned int} stored in 4 bytes 
        at byte 16. Should be sent in commands asking 
        for the next item in the list. 
        """
        
        def fget(self):
            return self.unpack(start=16, fmt=DWORD)[0]
        
        def fset(self, val):      
            self.pack(val, start=16, fmt=DWORD)
        
        return property(doc=doc, fget=fget, fset=fset)

class DeviceInfo(Answer):
    """ Defines the structure of the packet containing information about the device """
    device_name = field(start=16, fmt="<32s")
    device_version = field(start=48, fmt="<32s")
    software_version = field(start=80, fmt="<24s")
    mime_type = field(start=104, fmt="<32s")


class TotalSpaceAnswer(Answer):
    total = field(start=24, fmt=DDWORD) #: Total space available 
    # Supposedly free space available, but it does not work for main memory
    free_space = field(start=32, fmt=DDWORD) 

class FreeSpaceAnswer(Answer): 
    SIZE = 24
    free = field(start=16, fmt=DDWORD)


class ListAnswer(Answer):  
    """ Defines the structure of packets that contain items in a list. """
    name_length = field(start=20, fmt=DWORD)
    name        = stringfield(name_length, start=24)
    
    @dynamic_property
    def is_dir(self):
        doc = \
        """ 
        True if list item points to a directory, False if it points to a file.
        C{unsigned int} stored in 4 bytes at byte 16.
        """
        
        def fget(self):
            return (self.unpack(start=16, fmt=DWORD)[0] == 2)
        
        def fset(self, val):
            if val: val = 2
            else: val = 1
            self.pack(val, start=16, fmt=DWORD)
        
        return property(doc=doc, fget=fget, fset=fset)

