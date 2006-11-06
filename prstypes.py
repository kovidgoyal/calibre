#!/usr/bin/env python
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

import struct
from errors import PacketError

BYTE      = "<B"    # Unsigned char little endian encoded in 1 byte
WORD      = "<H"    # Unsigned short little endian encoded in 2 bytes
DWORD     = "<I"    # Unsigned integer little endian encoded in 4 bytes
DDWORD    = "<Q"    # Unsigned long long little endian encoded in 8 bytes


class TransferBuffer(list):  
  def __init__(self, packet):
    """ 
    packet should be any listable object, or an integer. If it is an integer, a zero buffer of that length is created. 
    packet is normalized (see TransferBuffer.normalize)
    """    
    if "__len__" in dir(packet): 
      list.__init__(self, list(packet))
      self.normalize()
    else: list.__init__(self, [0 for i in range(packet)])
    
  def __add__(self, tb):
    """ Return a TransferBuffer rather thana  list as the sum """
    return TransferBuffer(list.__add__(self, tb))
    
  def __getslice__(self, start, end):
    """ Return a TransferBuffer rather than a list as the slice """
    return TransferBuffer(list.__getslice__(self, start, end))
    
  def __str__(self):
    """
    Return a string representation of this buffer in the same format as that produced by spike.pl
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
        ans += "\t" + ascii + "\n"
        ascii = ""
    if len(ascii) > 0:
      last_line = ans[ans.rfind("\n")+1:]
      padding = 32 - len(last_line)
      ans += "".ljust(padding) + "\t\t" + ascii
    return ans.strip()
    
  def unpack(self, fmt=DWORD, start=0):
    """ Return decoded data from buffer. See pydoc struct for fmt. start is position in buffer from which to decode. """
    end = start + struct.calcsize(fmt)    
    return struct.unpack(fmt, "".join([ chr(i) for i in list.__getslice__(self, start, end) ]))
    
  def pack(self, val, fmt=DWORD, start=0):
    """ Encode data and write it to buffer. See pydoc struct fmt. start is position in buffer at which to write encoded data. """
    self[start:start+struct.calcsize(fmt)] = [ ord(i) for i in struct.pack(fmt, val) ]
      
  def normalize(self):
    """ Replace negative bytes by 256 + byte """
    for i in range(len(self)):
      if self[i] < 0:         
        self[i] = 256 + self[i]    
        
  @classmethod
  def phex(cls, num):
    """ 
    Return the hex representation of num without the 0x prefix. 
  
    If the hex representation is only 1 digit it is padded to the left with a zero.
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
    if ("__len__" in dir(packet) and len(packet) < 16) or ("__len__" not in dir(packet) and packet < 16): 
      raise PacketError(str(self.__class__)[7:-2] + " packets must have length atleast 16")    
    TransferBuffer.__init__(self, packet)
    
  @apply
  def number():
    doc =\
    """
    Command number
    
    Observed command numbers are:
    0x00001000 -- Acknowledge
    0x00000107 -- Purpose unknown, occurs in start_session 
    0x00000106 -- Purpose unknown, occurs in start_session
    """
    def fget(self):
      return self.unpack(start=0, fmt=DWORD)[0]
      
    def fset(self, val):
      self.pack(val, start=0, fmt=DWORD)
      
    return property(**locals())
    
  @apply 
  def type():
    doc =\
    """
    Command type. Known types 0x00, 0x01. Not sure what the type means.
    """
    def fget(self):
      return self.unpack(start=4, fmt=DDWORD)[0]
      
    def fset(self, val):
      self.pack(val, start=4, fmt=DDWORD)
      
    return property(**locals())
    
  @apply
  def length():
    doc =\
    """ Length in bytes of the data part of the query """
    def fget(self):
      return self.unpack(start=12, fmt=DWORD)[0]
      
    def fset(self, val):
      self.pack(val, start=12, fmt=DWORD)
      
    return property(**locals())
    
  @apply
  def data():
    doc =\
    """ 
    The data part of this command. Returned/set as/by a TransferBuffer. 
    
    Setting it by default changes self.length to the length of the new buffer. You may have to reset it to
    the significant part of the buffer.
    """
    def fget(self):
      return self[16:]
      
    def fset(self, buffer):
      self[16:] = buffer
      self.length = len(buffer)
      
    return property(**locals())
    
  
class ShortCommand(Command):
  
  SIZE = 20 #Packet size in bytes
  
  def __init__(self, number=0x00, type=0x00, command=0x00):
    """ command must be an integer """
    Command.__init__(self, ShortCommand.SIZE)
    self.number  = number
    self.type    = type
    self.length  = 4
    self.command = command
    
  @classmethod
  def list_command(cls, id):
    """ Return the command packet used to ask for the next item in the list """
    return ShortCommand(number=0x35, type=0x01, command=id)
  
  @apply
  def command():
    doc =\
    """ 
    The command. Not sure why this is needed in addition to Command.number
    """
    def fget(self):
      return self.unpack(start=16, fmt=DWORD)[0]
      
    def fset(self, val):
      self.pack(val, start=16, fmt=DWORD)
      
    return property(**locals())

class LongCommand(Command):
  
  SIZE = 32 # Size in bytes of long command packets
  
  def __init__(self, number=0x00, type=0x00, command=0x00):
    """ command must be either an integer or a list of not more than 4 integers """    
    Command.__init__(self, LongCommand.SIZE)
    self.number  = number
    self.type    = type 
    self.length  = 16
    self.command = command
    
  @apply
  def command():
    doc =\
    """ 
    The command.
    
    It should be set to a x-integer list, where 0<x<5.    
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
    """ bulk_read_id is an integer, the id of the bulk read we are acknowledging """
    LongCommand.__init__(self, number=0x1000, type=0x00, command=bulk_read_id)    

class PathQuery(Command):
  
  """ Defines structure of commands that request information about a path """
  
  # Command.number values used in path queries
  PROPERTIES = 0x18 # Ask for file properties
  ID         = 0x33 # Ask for query id for a directory listing
  
  def __init__(self, path, number=0x18):
    Command.__init__(self, 20 + len(path))
    self.number=number
    self.type = 0x01
    self.length = 4 + len(path)
    self.path_length = len(path)
    self.path = path
    
  @apply
  def path_length():
    doc =\
    """ The length in bytes of the path to follow  """
    def fget(self):
      return self.unpack(start=16, fmt=DWORD)[0]
      
    def fset(self, val):
      self.pack(val, start=16, fmt=DWORD)
      
    return property(**locals())
    
  @apply
  def path():
    doc =\
    """ The path """
    
    def fget(self):
      return self.unpack(start=20, fmt="<"+str(self.path_length)+"s")[0]
      
    def fset(self, val):
      self.pack(val, start=20, fmt="<"+str(self.path_length)+"s")
      
    return property(**locals())
    
    
class Response(Command):
  """ Defines the structure of response packets received from the device. """
  
  SIZE = 32   # Size of response packets in the SONY protocol 
  
  def __init__(self, packet):
    """ len(packet) == Response.SIZE """
    if len(packet) != Response.SIZE:
        raise PacketError(str(self.__class__)[7:-2] + " packets must have exactly " + str(Response.SIZE) + " bytes not " + str(len(packet)))
    Command.__init__(self, packet)
    if self.number != 0x00001000:
      raise PacketError("Response packets must have their number set to " + hex(0x00001000))
  
  @apply
  def rnumber():
    doc =\
    """ 
    The response number.
    
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
    """ The last 3 DWORDs of data in this response packet. Returned as a list. """
    def fget(self):
      return self.unpack(start=20, fmt="<III")
      
    def fset(self, val):
      self.pack(val, start=20, fmt="<III")
      
    return property(**locals())
    
class ListResponse(Response):
  
  """ Defines the structure of response packets received during list (ll) queries """
  
  IS_FILE        = 0xffffffd2
  IS_INVALID     = 0xfffffff9
  IS_UNMOUNTED   = 0xffffffc8
  IS_EOL         = 0xfffffffa
  PATH_NOT_FOUND = 0xffffffd7    
  
  @apply
  def code():
    doc =\
    """ 
    The response code. Used to indicate conditions like EOL/Error/IsFile
    
    fmt=DWORD
    """
    def fget(self):
      return self.unpack(start=20, fmt=DDWORD)[0]
      
    def fset(self, val):      
      self.pack(val, start=20, fmt=DDWORD)
      
    return property(**locals())
    
  @apply
  def is_file():
    def fget(self):      
      return self.code == ListResponse.IS_FILE
    return property(**locals())
    
  @apply
  def is_invalid():
    def fget(self):    
      return self.code == ListResponse.IS_INVALID
    return property(**locals())
    
  @apply
  def path_not_found():
    def fget(self):    
      return self.code == ListResponse.PATH_NOT_FOUND
    return property(**locals())
    
  @apply
  def is_unmounted():
    def fget(self):
      return self.code == ListResponse.IS_UNMOUNTED
    return property(**locals())
    
  @apply
  def is_eol():
    def fget(self):
      return self.code == ListResponse.IS_EOL
    return property(**locals())
    
class Answer(TransferBuffer):
  """ Defines the structure of packets sent to host via a bulk transfer (i.e., bulk reads) """
  
  def __init__(self, packet):
    """ packet must be a listable object of length >= 16 """
    if len(packet) < 16 : raise PacketError(str(self.__class__)[7:-2] + " packets must have a length of atleast 16 bytes")
    TransferBuffer.__init__(self, packet)
    
  @apply
  def id():
    doc =\
    """ The id of this bulk transfer packet """
    
    def fget(self):
      return self.unpack(start=0, fmt=DWORD)[0]
      
    def fset(self, val):      
      self.pack(val, start=0, fmt=DWORD)
      
    return property(**locals())

class PathAnswer(Answer):
  
  """ Defines the structure of packets that contain size, date and permissions information about files/directories. """
  
  @apply
  def file_size():
    doc =\
    """ The file size """
    
    def fget(self):
      return self.unpack(start=16, fmt=DDWORD)[0]
      
    def fset(self, val):      
      self.pack(val, start=16, fmt=DDWORD)
      
    return property(**locals())
  
  @apply
  def is_dir():
    doc =\
    """ True if path points to a directory, False if it points to a file """
    
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
    """ The creation time of this file/dir as an epoch """
    
    def fget(self):
      return self.unpack(start=28, fmt=DWORD)[0]
      
    def fset(self, val):      
      self.pack(val, start=28, fmt=DWORD)
      
    return property(**locals())
    
  @apply
  def wtime():
    doc =\
    """ The modification time of this file/dir as an epoch """
    
    def fget(self):
      return self.unpack(start=32, fmt=DWORD)[0]
      
    def fset(self, val):      
      self.pack(val, start=32, fmt=DWORD)
      
    return property(**locals())
    
  @apply
  def is_readonly():
    doc =\
    """ Whether this file is readonly """
    
    def fget(self):
      return self.unpack(start=36, fmt=DWORD)[0] != 0
      
    def fset(self, val):
      if val: val = 4
      else: val = 0
      self.pack(val, start=36, fmt=DWORD)
      
    return property(**locals())
    
class IdAnswer(Answer):
  
  """ Defines the structure of packets that contain identifiers for directories. """
  
  @apply
  def id():
    doc =\
    """ The identifier """
    
    def fget(self):
      return self.unpack(start=16, fmt=DWORD)[0]
      
    def fset(self, val):      
      self.pack(val, start=16, fmt=DWORD)
      
    return property(**locals())
    
class ListAnswer(Answer):
  
  """ Defines the structure of packets that contain items in a list. """
  
  @apply
  def is_dir():
    doc =\
    """ True if list item points to a directory, False if it points to a file """
    
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
    """ The length in bytes of the list item to follow  """
    def fget(self):
      return self.unpack(start=20, fmt=DWORD)[0]
      
    def fset(self, val):
      self.pack(val, start=20, fmt=DWORD)
      
    return property(**locals())
  
  @apply
  def name():
    doc =\
    """ The name of the list item """
    
    def fget(self):
      return self.unpack(start=24, fmt="<"+str(self.name_length)+"s")[0]
      
    def fset(self, val):      
      self.pack(val, start=24, fmt="<"+str(self.name_length)+"s")
      
    return property(**locals())
