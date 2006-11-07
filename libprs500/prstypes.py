##    Copyright (C) 2006 Kovid Goyal kovid@kovidgoyal.net
##    This program is free software; you can redistribute it and/or modify
##    it under the terms of the GNU General Public License as published by
##    the Free Software Foundation; either version 2 of the License, or
##    (at your option) any later version.
##
##    This program is distributed in the hope that it will be useful,
##    but WITHOUT ANY WARRANTY; without even the implied warranty of
##    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
##    GNU General Public License for more details.
##
##    You should have received a copy of the GNU General Public License along
##    with this program; if not, write to the Free Software Foundation, Inc.,
##    51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

"""
Defines the structure of packets that are sent to/received from the device. 

Packet structure is defined using classes and inheritance. Each class is a view that imposes
structure on the underlying data buffer. The data buffer is encoded in little-endian format, but you don't
have to worry about that if you are using the classes. The classes have instance variables with getter/setter functions defined
to take care of the encoding/decoding. The classes are intended to mimic C structs. 

There are three kinds of packets. L{Commands<Command>}, L{Responses<Response>}, and L{Answers<Answer>}. 
C{Commands} are sent to the device on the control bus, C{Responses} are received from the device, 
also on the control bus. C{Answers} and their sub-classes represent data packets sent to/received from
the device via bulk transfers. 

Commands are organized as follows: G{classtree Command}

You will typically only use sub-classes of Command. 

Responses are organized as follows: G{classtree Response}

Responses inherit Command as they share header structure.

Answers are organized as follows: G{classtree Answer}
"""

import struct
from errors import PacketError

BYTE      = "<B"    #: Unsigned char little endian encoded in 1 byte
WORD      = "<H"    #: Unsigned short little endian encoded in 2 bytes
DWORD     = "<I"    #: Unsigned integer little endian encoded in 4 bytes
DDWORD    = "<Q"    #: Unsigned long long little endian encoded in 8 bytes


class TransferBuffer(list):
  
  """
  Represents raw (unstructured) data packets sent over the usb bus.
  
  C{TransferBuffer} is a wrapper around the tuples used by L{PyUSB<usb>} for communication. 
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
    
    Packets are represented as hex strings, in 2-byte pairs, S{<=} 16 bytes to a line. An ASCII representation is included. For example::
        0700 0100 0000 0000 0000 0000 0c00 0000         ................
        0200 0000 0400 0000 4461 7461                   ........Data
    """
    ans, ascii = "", ""
    for i in range(0, len(self), 2):
      for b in range(2):
        try: 
          ans   += TransferBuffer.phex(self[i+b])
          ascii += chr(self[i+b]) if self[i+b] > 31 and self[i+b] < 127 else "."
        except IndexError: break      
      ans = ans + " "
      if (i+2)%16 == 0:
        if i+2 < len(self):
          ans += "   " + ascii + "\n"
          ascii = ""
    last_line = ans[ans.rfind("\n")+1:]
    padding = 40 - len(last_line)
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
    Encode C{val} and write it to buffer.
    
    @param fmt: See U{struct<http://docs.python.org/lib/module-struct.html>}
    @param start: Position in buffer at which to write encoded data
    """
    self[start:start+struct.calcsize(fmt)] = [ ord(i) for i in struct.pack(fmt, val) ]
      
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
    h=hex(num)[index:]
    if len(h) < 2: 
      h = "0"+h
    return sign + h

      

class Command(TransferBuffer):
  
  """ Defines the structure of command packets sent to the device. """
  
  def __init__(self, packet):
    """
    @param packet: len(packet) > 15 or packet > 15
    """
    if ("__len__" in dir(packet) and len(packet) < 16) or ("__len__" not in dir(packet) and packet < 16): 
      raise PacketError(str(self.__class__)[7:-2] + " packets must have length atleast 16")    
    TransferBuffer.__init__(self, packet)
    
  @apply
  def number():
    doc =\
    """
    Command number. C{unsigned int} stored in 4 bytes at byte 0.
    
    Observed command numbers are:
      1.  0x00
          Test bulk read
      2.  0x01
          End session
      3.  0x0101
          Ask for device information
      4.  0x1000
          Acknowledge
      5.  0x107
          Purpose unknown, occurs in the beginning of sessions duing command testing. Best guess is some sort of OK packet 
      6.  0x106
          Purpose unknown, occurs in the beginning of sessions duing command testing. Best guess is some sort of OK packet
      7.  0x18
          Ask for information about a file
      8.  0x33
          Open directory for reading
      9.  0x34
          Close directory
      10. 0x35
          Ask for next item in the directory
      11. 0x10
          File open command
      12. 0x11
          File close command
      13. 0x16
          File read command
    """
    def fget(self):
      return self.unpack(start=0, fmt=DWORD)[0]
      
    def fset(self, val):
      self.pack(val, start=0, fmt=DWORD)
      
    return property(**locals())
    
  @apply 
  def type():
    doc =\
    """ Command type. C{unsigned long long} stored in 8 bytes at byte 4. Known types 0x00, 0x01. Not sure what the type means. """
    def fget(self):
      return self.unpack(start=4, fmt=DDWORD)[0]
      
    def fset(self, val):
      self.pack(val, start=4, fmt=DDWORD)
      
    return property(**locals())
    
  @apply
  def length():
    doc =\
    """ Length in bytes of the data part of the query. C{unsigned int} stored in 4 bytes at byte 12. """
    def fget(self):
      return self.unpack(start=12, fmt=DWORD)[0]
      
    def fset(self, val):
      self.pack(val, start=12, fmt=DWORD)
      
    return property(**locals())
    
  @apply
  def data():
    doc =\
    """ 
    The data part of this command. Returned/set as/by a TransferBuffer. Stored at byte 16.
    
    Setting it by default changes self.length to the length of the new buffer. You may have to reset it to
    the significant part of the buffer. You would normally use the C{command} property of L{ShortCommand} or L{LongCommand} instead.
    """
    def fget(self):
      return self[16:]
      
    def fset(self, buffer):
      self[16:] = buffer
      self.length = len(buffer)
      
    return property(**locals())
    
  
class ShortCommand(Command):
  
  """ A L{Command} whoose data section is 4 bytes long """
  
  SIZE = 20 #: Packet size in bytes
  
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
    
  @apply
  def command():
    doc =\
    """ The command. Not sure why this is needed in addition to Command.number. C{unsigned int} 4 bytes long at byte 16. """
    def fget(self):
      return self.unpack(start=16, fmt=DWORD)[0]
      
    def fset(self, val):
      self.pack(val, start=16, fmt=DWORD)
      
    return property(**locals())

class DirOpen(Command):
  
  """ Open a directory for reading its contents  """  
  NUMBER     = 0x33 #: Command number
  
  def __init__(self, path):    
    Command.__init__(self, 20 + len(path))
    self.number=DirOpen.NUMBER
    self.type = 0x01
    self.length = 4 + len(path)
    self.path_length = len(path)
    self.path = path
    
  @apply
  def path_length():
    doc =\
    """ The length in bytes of the path to follow. C{unsigned int} stored at byte 16.  """
    def fget(self):
      return self.unpack(start=16, fmt=DWORD)[0]
      
    def fset(self, val):
      self.pack(val, start=16, fmt=DWORD)
      
    return property(**locals())
    
  @apply
  def path():
    doc =\
    """ The path. Stored as a string at byte 20. """
    
    def fget(self):
      return self.unpack(start=20, fmt="<"+str(self.path_length)+"s")[0]
      
    def fset(self, val):
      self.pack(val, start=20, fmt="<"+str(self.path_length)+"s")
      
    return property(**locals())

class DirRead(ShortCommand):
  """ The command that asks the device to send the next item in the list """
  NUMBER = 0x35 #: Command number
  def __init__(self, id):
    """ @param id: The identifier returned as a result of a L{DirOpen} command """
    ShortCommand.__init__(self, number=DirRead.NUMBER, type=0x01, command=id)
    
class DirClose(ShortCommand):
  """ Close a previously opened directory """
  NUMBER = 0x34 #: Command number
  def __init__(self, id):
    """ @param id: The identifier returned as a result of a L{DirOpen} command """
    ShortCommand.__init__(self, number=DirClose.NUMBER, type=0x01, command=id)


class LongCommand(Command):
  
  """ A L{Command} whoose data section is 16 bytes long """
  
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
  
  @apply
  def command():
    doc =\
    """ 
    The command. Not sure why it is needed in addition to L{Command.number}.  
    It is a list of C{unsigned integers} of length between 1 and 4. 4 C{unsigned int} stored in 16 bytes at byte 16.
    """
    def fget(self):
      return self.unpack(start=16, fmt="<"+str(self.length/4)+"I")
      
    def fset(self, val):
      if "__len__" not in dir(val): val = (val,)
      start = 16
      for command in val:
        self.pack(command, start=start, fmt=DWORD)
        start += struct.calcsize(DWORD)
      
    return property(**locals())


class AcknowledgeBulkRead(LongCommand):
  
  """ Must be sent to device after a bulk read """
  
  def __init__(self, bulk_read_id):
    """ bulk_read_id is an integer, the id of the bulk read we are acknowledging. See L{Answer.id} """
    LongCommand.__init__(self, number=0x1000, type=0x00, command=bulk_read_id)    

class DeviceInfoQuery(Command):
  """ The command used to ask for device information """
  NUMBER=0x0101 #: Command number
  def __init__(self):
    Command.__init__(self, 16)
    self.number=DeviceInfoQuery.NUMBER
    self.type=0x01

class FileClose(ShortCommand):
  """ File close command """
  NUMBER = 0x11 #: Command number
  def __init__(self, id):
    ShortCommand.__init__(self, number=FileClose.NUMBER, type=0x01, command=id)

class FileOpen(Command):
  """ File open command """
  NUMBER = 0x10
  READ   = 0x00
  WRITE  = 0x01
  def __init__(self, path, mode=0x00):
    Command.__init__(self, 24 + len(path))
    self.number=FileOpen.NUMBER
    self.type = 0x01
    self.length = 8 + len(path)
    self.mode = mode
    self.path_length = len(path)
    self.path = path
    
  @apply
  def mode():
    doc =\
    """ The file open mode. Is either L{FileOpen.READ} or L{FileOpen.WRITE}. C{unsigned int} stored at byte 16.  """
    def fget(self):
      return self.unpack(start=16, fmt=DWORD)[0]
      
    def fset(self, val):
      self.pack(val, start=16, fmt=DWORD)
      
    return property(**locals())
  
  @apply
  def path_length():
    doc =\
    """ The length in bytes of the path to follow. C{unsigned int} stored at byte 20.  """
    def fget(self):
      return self.unpack(start=20, fmt=DWORD)[0]
      
    def fset(self, val):
      self.pack(val, start=20, fmt=DWORD)
      
    return property(**locals())
    
  @apply
  def path():
    doc =\
    """ The path. Stored as a string at byte 24. """
    
    def fget(self):
      return self.unpack(start=24, fmt="<"+str(self.path_length)+"s")[0]
      
    def fset(self, val):
      self.pack(val, start=24, fmt="<"+str(self.path_length)+"s")
      
    return property(**locals())
  
class FileRead(Command):
  """ Command to read from an open file """
  NUMBER = 0x16 #: Command number to read from a file
  def __init__(self, id, offset, size):
    """
    @param id:     File identifier returned by a L{FileOpen} command
    @type id: C{unsigned int}
    @param offset: Position in file at which to read
    @type offset: C{unsigned long long}
    @param size: number of bytes to read
    @type size: C{unsigned int}
  """  
    Command.__init__(self, 32)
    self.number=FileRead.NUMBER
    self.type = 0x01
    self.length = 32
    self.id = id
    self.offset = offset
    self.size = size
    
  @apply
  def id():
    doc =\
    """ The file ID returned by a FileOpen command. C{unsigned int} stored in 4 bytes at byte 16. """
    def fget(self):
      return self.unpack(start=16, fmt=DWORD)[0]
      
    def fset(self, val):
      self.pack(val, start=16, fmt=DWORD)
      
    return property(**locals())
    
  @apply
  def offset():
    doc =\
    """ offset in the file at which to read. C{unsigned long long} stored in 8 bytes at byte 20. """
    def fget(self):
      return self.unpack(start=20, fmt=DDWORD)[0]
      
    def fset(self, val):
      self.pack(val, start=20, fmt=DDWORD)
      
    return property(**locals())
    
  @apply
  def size():
    doc =\
    """ The number of bytes to read. C{unsigned int} stored in 4 bytes at byte 28. """
    def fget(self):
      return self.unpack(start=28, fmt=DWORD)[0]
      
    def fset(self, val):
      self.pack(val, start=28, fmt=DWORD)
      
    return property(**locals())
  
  
  

class PathQuery(Command):
  
  """ 
  Defines structure of command that requests information about a path 
  
  >>> print prstypes.PathQuery("/test/path/", number=prstypes.PathQuery.PROPERTIES)
  1800 0000 0100 0000 0000 0000 0f00 0000    ................
  0b00 0000 2f74 6573 742f 7061 7468 2f      ..../test/path/
  """  
  NUMBER     = 0x18 #: Command number
  
  def __init__(self, path):    
    Command.__init__(self, 20 + len(path))
    self.number=PathQuery.NUMBER
    self.type = 0x01
    self.length = 4 + len(path)
    self.path_length = len(path)
    self.path = path
    
  @apply
  def path_length():
    doc =\
    """ The length in bytes of the path to follow. C{unsigned int} stored at byte 16.  """
    def fget(self):
      return self.unpack(start=16, fmt=DWORD)[0]
      
    def fset(self, val):
      self.pack(val, start=16, fmt=DWORD)
      
    return property(**locals())
    
  @apply
  def path():
    doc =\
    """ The path. Stored as a string at byte 20. """
    
    def fget(self):
      return self.unpack(start=20, fmt="<"+str(self.path_length)+"s")[0]
      
    def fset(self, val):
      self.pack(val, start=20, fmt="<"+str(self.path_length)+"s")
      
    return property(**locals())
    
    
class Response(Command):
  """ 
  Defines the structure of response packets received from the device. 
  
  C{Response} inherits from C{Command} as the first 16 bytes have the same structure.
  """
  
  SIZE = 32   #: Size of response packets in the SONY protocol 
  
  def __init__(self, packet):
    """ C{len(packet) == Response.SIZE} """
    if len(packet) != Response.SIZE:
        raise PacketError(str(self.__class__)[7:-2] + " packets must have exactly " + str(Response.SIZE) + " bytes not " + str(len(packet)))
    Command.__init__(self, packet)
    if self.number != 0x00001000:
      raise PacketError("Response packets must have their number set to " + hex(0x00001000))
  
  @apply
  def rnumber():
    doc =\
    """ 
    The response number. C{unsigned int} stored in 4 bytes at byte 16.
    
    It will be the command number from a command that was sent to the device sometime before this response.
    """
    def fget(self):
      return self.unpack(start=16, fmt=DWORD)[0]
      
    def fset(self, val):
      self.pack(val, start=16, fmt=DWORD)
      
    return property(**locals())
    
  @apply
  def data():
    doc =\
    """ The last 3 DWORDs (12 bytes) of data in this response packet. Returned as a list of unsigned integers. """
    def fget(self):
      return self.unpack(start=20, fmt="<III")
      
    def fset(self, val):
      self.pack(val, start=20, fmt="<III")
      
    return property(**locals())
    
class ListResponse(Response):
  
  """ Defines the structure of response packets received during list (ll) queries. See L{PathQuery}. """
  
  IS_FILE        = 0xffffffd2 #: Queried path is a file 
  IS_INVALID     = 0xfffffff9 #: Queried path is malformed/invalid
  IS_UNMOUNTED   = 0xffffffc8 #: Queried path is not mounted (i.e. a removed storage card/stick)
  IS_EOL         = 0xfffffffa #: There are no more entries in the list
  PATH_NOT_FOUND = 0xffffffd7 #: Queried path is not found 
  
  @apply
  def code():
    doc =\
    """ The response code. Used to indicate conditions like EOL/Error/IsFile etc. C{unsigned int} stored in 4 bytes at byte 20. """
    def fget(self):
      return self.unpack(start=20, fmt=DDWORD)[0]
      
    def fset(self, val):      
      self.pack(val, start=20, fmt=DDWORD)
      
    return property(**locals())
    
  @apply
  def is_file():
    """ True iff queried path is a file """
    def fget(self):      
      return self.code == ListResponse.IS_FILE
    return property(**locals())
    
  @apply
  def is_invalid():
    """ True iff queried path is invalid """
    def fget(self):    
      return self.code == ListResponse.IS_INVALID
    return property(**locals())
    
  @apply
  def path_not_found():
    """ True iff queried path is not found """
    def fget(self):    
      return self.code == ListResponse.PATH_NOT_FOUND
    return property(**locals())
    
  @apply
  def is_unmounted():
    """ True iff queried path is unmounted (i.e. removed storage card) """
    def fget(self):
      return self.code == ListResponse.IS_UNMOUNTED
    return property(**locals())
    
  @apply
  def is_eol():
    """ True iff there are no more items in the list """
    def fget(self):
      return self.code == ListResponse.IS_EOL
    return property(**locals())
    
class Answer(TransferBuffer):
  """ Defines the structure of packets sent to host via a bulk transfer (i.e., bulk reads) """
  
  def __init__(self, packet):
    """ @param packet: C{len(packet)} S{>=} C{16} """
    if len(packet) < 16 : raise PacketError(str(self.__class__)[7:-2] + " packets must have a length of atleast 16 bytes")
    TransferBuffer.__init__(self, packet)
    
  @apply
  def id():
    doc =\
    """ The id of this bulk transfer packet. C{unsigned int} stored in 4 bytes at byte 0. """
    
    def fget(self):
      return self.unpack(start=0, fmt=DWORD)[0]
      
    def fset(self, val):      
      self.pack(val, start=0, fmt=DWORD)
      
    return property(**locals())

class FileProperties(Answer):
  
  """ Defines the structure of packets that contain size, date and permissions information about files/directories. """
  
  @apply
  def file_size():
    doc =\
    """ The file size. C{unsigned long long} stored in 8 bytes at byte 16. """
    
    def fget(self):
      return self.unpack(start=16, fmt=DDWORD)[0]
      
    def fset(self, val):      
      self.pack(val, start=16, fmt=DDWORD)
      
    return property(**locals())
  
  @apply
  def is_dir():
    doc =\
    """ 
    True if path points to a directory, False if it points to a file. C{unsigned int} stored in 4 bytes at byte 24.
    
    Value of 1 == file and 2 == dir
    """
    
    def fget(self):
      return (self.unpack(start=24, fmt=DWORD)[0] == 2)
      
    def fset(self, val):
      if val: val = 2
      else: val = 1
      self.pack(val, start=24, fmt=DWORD)
      
    return property(**locals())
    
  @apply
  def ctime():
    doc =\
    """ The creation time of this file/dir as an epoch (seconds since Jan 1970). C{unsigned int} stored in 4 bytes at byte 28. """
    
    def fget(self):
      return self.unpack(start=28, fmt=DWORD)[0]
      
    def fset(self, val):      
      self.pack(val, start=28, fmt=DWORD)
      
    return property(**locals())
    
  @apply
  def wtime():
    doc =\
    """ The modification time of this file/dir as an epoch (seconds since Jan 1970). C{unsigned int} stored in 4 bytes at byte 32"""
    
    def fget(self):
      return self.unpack(start=32, fmt=DWORD)[0]
      
    def fset(self, val):      
      self.pack(val, start=32, fmt=DWORD)
      
    return property(**locals())
    
  @apply
  def is_readonly():
    doc =\
    """ 
    Whether this file is readonly. C{unsigned int} stored in 4 bytes at byte 36.
    
    A value of 0 corresponds to read/write and 4 corresponds to read-only. The device doesn't send full permissions information.
    """
    
    def fget(self):
      return self.unpack(start=36, fmt=DWORD)[0] != 0
      
    def fset(self, val):
      if val: val = 4
      else: val = 0
      self.pack(val, start=36, fmt=DWORD)
      
    return property(**locals())
    
class IdAnswer(Answer):
  
  """ Defines the structure of packets that contain identifiers for queries. """
  
  @apply
  def id():
    doc =\
    """ The identifier. C{unsigned int} stored in 4 bytes at byte 16. Should be sent in commands asking for the next item in the list. """
    
    def fget(self):
      return self.unpack(start=16, fmt=DWORD)[0]
      
    def fset(self, val):      
      self.pack(val, start=16, fmt=DWORD)
      
    return property(**locals())
    
class DeviceInfo(Answer):
  """ Defines the structure of the packet containing information about the device """
  
  @apply
  def device_name():
    """ The name of the device. Stored as a string in 32 bytes starting at byte 16. """
    def fget(self):
      src = self.unpack(start=16, fmt="<32s")[0]
      return src[0:src.find('\x00')]
    return property(**locals())
  
  @apply
  def device_version():
    """ The device version. Stored as a string in 32 bytes starting at byte 48. """
    def fget(self):
      src = self.unpack(start=48, fmt="<32s")[0]
      return src[0:src.find('\x00')]
    return property(**locals())
    
  @apply
  def software_version():
    """ Version of the software on the device. Stored as a string in 26 bytes starting at byte 80. """
    def fget(self):
      src = self.unpack(start=80, fmt="<26s")[0]
      return src[0:src.find('\x00')]
    return property(**locals()) 
    
  @apply
  def mime_type():
    """ Mime type served by tinyhttp?. Stored as a string in 32 bytes starting at byte 104. """
    def fget(self):
      src = self.unpack(start=104, fmt="<32s")[0]
      return src[0:src.find('\x00')]
    return property(**locals()) 

class ListAnswer(Answer):
  
  """ Defines the structure of packets that contain items in a list. """
  
  @apply
  def is_dir():
    doc =\
    """ True if list item points to a directory, False if it points to a file. C{unsigned int} stored in 4 bytes at byte 16. """
    
    def fget(self):
      return (self.unpack(start=16, fmt=DWORD)[0] == 2)
      
    def fset(self, val):
      if val: val = 2
      else: val = 1
      self.pack(val, start=16, fmt=DWORD)
      
    return property(**locals())
    
  @apply
  def name_length():
    doc =\
    """ The length in bytes of the list item to follow. C{unsigned int} stored in 4 bytes at byte 20 """
    def fget(self):
      return self.unpack(start=20, fmt=DWORD)[0]
      
    def fset(self, val):
      self.pack(val, start=20, fmt=DWORD)
      
    return property(**locals())
  
  @apply
  def name():
    doc =\
    """ The name of the list item. Stored as an (ascii?) string at byte 24. """
    
    def fget(self):
      return self.unpack(start=24, fmt="<"+str(self.name_length)+"s")[0]
      
    def fset(self, val):      
      self.pack(val, start=24, fmt="<"+str(self.name_length)+"s")
      
    return property(**locals())
