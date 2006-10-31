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

import sys, re
from prstypes import *

# The sequence of control commands to send the device before attempting any operations. Should be preceeded by a reset?
initialization = []
initialization.append(\
ControlQuery(TransferBuffer((0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 4, 0, 0, 0, 0, 0, 0, 0)),\
             TransferBuffer((0, 16, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 12, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)), bulkTransfer=24))
initialization.append(\
ControlQuery(TransferBuffer((0, 16, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 16, 0, 0, 0, 5, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)), \
             TransferBuffer((0, 16, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 12, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0))))
initialization.append(\
ControlQuery(TransferBuffer((7, 1, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 4, 0, 0, 0, 0, 128, 2, 0)), \
             TransferBuffer((0, 16, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 12, 0, 0, 0, 7, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0))))
initialization.append(\
ControlQuery(TransferBuffer((0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 4, 0, 0, 0, 1, 0, 0, 0)), \
             TransferBuffer((0, 16, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 12, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)), bulkTransfer=24))
initialization.append(\
ControlQuery(TransferBuffer((0, 16, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 16, 0, 0, 0, 5, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)), \
             TransferBuffer((0, 16, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 12, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0))))
initialization.append(\
ControlQuery(TransferBuffer((6, 1, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 8, 0, 0, 0, 45, 49, 0, 0, 0, 0, 0, 0)), \
             TransferBuffer((0, 16, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 12, 0, 0, 0, 6, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0))))
initialization.append(\
ControlQuery(TransferBuffer((1, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 4, 0, 0, 0, 1, 0, 0, 0)), \
             TransferBuffer((0, 16, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 12, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0))))

end_transaction = \
ControlQuery(TransferBuffer((1, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 4, 0, 0, 0, 0, 0, 0, 0)),\
             TransferBuffer((0, 16, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 12, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)))

def string_to_buffer(string):
  """ Convert a string to a TransferBuffer """
  return TransferBuffer([ ord(ch) for ch in string ])
  
class LSQuery(ControlQuery):
  """
  Contains all the device specific data (packet formats) needed to implement a simple ls command. 
  See PRS500Device.ls() to understand how it is used.
  """
  PATH_NOT_FOUND_RESPONSE = (0, 16, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 12, 0, 0, 0, 24, 0, 0, 0, 215, 255, 255, 255, 0, 0, 0, 0, 0, 0, 0, 0)
  IS_FILE_RESPONSE        = (0, 16, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 12, 0, 0, 0, 24, 0, 0, 0, 210, 255, 255, 255, 0, 0, 0, 0, 0, 0, 0, 0)
  NOT_MOUNTED_RESPONSE    = (0, 16, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 12, 0, 0, 0, 24, 0, 0, 0, 200, 255, 255, 255, 0, 0, 0, 0, 0, 0, 0, 0)
  INVALID_PATH_RESPONSE   = (0, 16, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 12, 0, 0, 0, 24, 0, 0, 0, 249, 255, 255, 255, 0, 0, 0, 0, 0, 0, 0, 0)
  ACKNOWLEDGE_RESPONSE    = (0, 16, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 12, 0, 0, 0, 0x35, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
  ACKNOWLEDGE_COMMAND     = (0, 16, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 16, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)  
  SEND_NAME_COMMAND       = (53, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 4 , 0, 0, 0, 0, 0, 0, 0)
  EOL_RESPONSE            = (0, 16, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 16, 0, 0, 0, 53, 0, 0, 0, 250, 255, 255, 255, 0, 0, 0, 0, 0, 0, 0, 0)
  
  
  def __init__(self, path, type=1):
    self.path = path
    if len(self.path) >= 8:
      self.path_fragment = self.path[8:]
      for i in range(4 - len(self.path_fragment)): 
        self.path_fragment += '\x00'
      self.path_fragment = [ ord(self.path_fragment[i]) for i in range(4) ]
    else: 
      self.path_fragment = [ 0x00 for i in range(4) ]
    src = [ 0x00 for i in range(20) ]
    if type == 1:
      src[0] = 0x18
    elif type == 2:
      src[0] = 0x33
    src[4], src[12], src[16] = 0x01, len(path)+4, len(path)
    query = TransferBuffer(src) + string_to_buffer(path)
    src = [ 0x00 for i in range(32) ]
    src[1], src[4], src[12], src[16] = 0x10, 0x01, 0x0c, 0x18
    if type == 2: src[16] = 0x33
    ControlQuery.__init__(self, query, TransferBuffer(src), bulkTransfer = 0x28)
    
  def acknowledge_query(self, type, error_type=0):
    """
    Return the acknowledge query used after receiving data as part of an ls query
    
    type       - should only take values 0,1,2,3 corresponding to the 4 different types of acknowledge queries.
                 If it takes any other value it is assumed to be zero.
           
    error_type - 0 = no error, 1 = path not found, 2 = is file, 3 = not mounted, 4 = invalid path
    """
    if error_type == 1:
      response = list(LSQuery.PATH_NOT_FOUND_RESPONSE)
      response[4] = 0x00
    elif error_type == 2: 
      response = list(LSQuery.IS_FILE_RESPONSE)
      response[4] = 0x00
    elif error_type == 3:
      response = list(LSQuery.NOT_MOUNTED_RESPONSE)
      response[4] = 0x00
    elif error_type == 4:
      response = list(LSQuery.INVALID_PATH_RESPONSE)
      response[4] = 0x00
    else: response = list(LSQuery.ACKNOWLEDGE_RESPONSE)    
    query = list(LSQuery.ACKNOWLEDGE_COMMAND)
    response[-4:] = self.path_fragment
    if type == 1:
      query[16] = 0x03
      response[16] = 0x18      
    elif type == 2:
      query[16] = 0x06
      response[16] = 0x33
    elif type == 3:
      query[16] = 0x07
      response[16] = 0x35
    else: # All other type values are mapped to 0, which is an EOL condition
      response[20], response[21], response[22], response[23] = 0xfa, 0xff, 0xff, 0xff
      
    return ControlQuery(TransferBuffer(query), TransferBuffer(response))
  
  def send_name_query(self, buffer):
    """
    Return a ControlQuery that will cause the device to send the next name in the list
    
    buffer - TransferBuffer that contains 4 bytes of information that identify the directory we are listing.
    
    Note that the response to this command contains information (the size of the receive buffer for the next bulk read) thus
    the expected response is set to null.
    """
    query = list(LSQuery.SEND_NAME_COMMAND)
    query[-4:] = list(buffer)[-4:]
    response = [ 0x00 for i in range(32) ]
    return ControlQuery(TransferBuffer(query), TransferBuffer(response))
    

def main(file):
  """ Convenience method for converting spike.pl output to python code. Used to read control packet data from USB logs """
  PSF = open(file, 'r')
  lines = PSF.readlines()
  
  packets = []
  temp = []
  for line in lines:
    if re.match("\s+$", line):
      temp = "".join(temp)
      packet = []
      for i in range(0, len(temp), 2):
        packet.append(int(temp[i]+temp[i+1], 16))
      temp = []
      packets.append(tuple(packet))
      continue
    temp = temp + line.split()
  print r"seq = []"
  for i in range(0, len(packets), 2):
    print "seq.append(ControlQuery(TransferBuffer(" + str(packets[i]) + "), TransferBuffer(" + str(packets[i+1]) + ")))"

if __name__ == "__main__":
  main(sys.argv[1])
