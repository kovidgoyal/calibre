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

"""
Contains convenience wrappers for packet data that allow output in the same format as the logs produced by spike.pl
"""


def normalize_buffer(tb):
  """ Replace negative bytes by 256 + byte """
  nb = list(tb)
  for i in range(len(nb)):
    if nb[i] < 0: 
      nb[i] = 256 + nb[i]
  return TransferBuffer(nb)

def phex(num):
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
  

class TransferBuffer(tuple):
  """
  Thin wrapper around tuple to present the string representation of a transfer buffer as in the output of spike.pl """
  def __init__(self, packet):
    tuple.__init__(packet)
    self.packet = packet
    
  def __add__(self, tb):
    return TransferBuffer(tuple.__add__(self, tb))
    
  def __str__(self):
    """
    Return a string representation of this packet in the same format as that produced by spike.pl
    """
    ans = ""
    for i in range(0, len(self), 2):
      for b in range(2):
        try:
          ans = ans + phex(self[i+b])
        except IndexError:
          break
      ans = ans + " "
      if (i+2)%16 == 0: 
        ans = ans + "\n"
    return ans.strip()
    
class ControlQuery:
  """
  Container for all the transfer buffers that make up a single query. 
  
  A query has a transmitted buffer, an expected response and an optional buffer that is either read
  from or written to via a bulk transfer.
  """
  
  def __init__(self, query, response, bulkTransfer=None):
    """
    Construct this query.
    
    query        - A TransferBuffer that should be sent to the device on the control pipe
    response     - A TransferBuffer that the device is expected to return. Used for error checking.
    bulkTransfer - If it is a number, it indicates that a buffer of size bulkTransfer should be read from the device via a
                   bulk read. If it is a TransferBuffer then it will be sent to the device via a bulk write.
    """
    self.query = query
    self.response = response
    self.bulkTransfer = bulkTransfer
    
  def __eq__(self, cq):
    """ Bulk transfers are not compared to decide equality. """
    return self.query == cq.query and self.response == cq.response
    

