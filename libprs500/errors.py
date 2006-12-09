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
Defines the errors that libprs500 generates.

G{classtree ProtocolError}
"""
from exceptions import Exception

class ProtocolError(Exception):
  """ The base class for all exceptions in this package """
  def __init__(self, msg):
    Exception.__init__(self, msg)
    
class TimeoutError(ProtocolError):
  """ There was a timeout during communication """
  def __init__(self, func_name):
    ProtocolError.__init__(self, "There was a timeout while communicating with the device in function: "+func_name)

class DeviceError(ProtocolError):
  """ Raised when device is not found """
  def __init__(self):
    ProtocolError.__init__(self, "Unable to find SONY Reader. Is it connected?")
    
class DeviceBusy(ProtocolError):
  """ Raised when device is busy """
  def __init__(self):
    ProtocolError.__init__(self, "Device is in use by another application")
    
class PacketError(ProtocolError):
  """ Errors with creating/interpreting packets """
  
class FreeSpaceError(ProtocolError):
  """ Errors caused when trying to put files onto an overcrowded device """
    
class ArgumentError(ProtocolError):
  """ Errors caused by invalid arguments to a public interface function """
  
class PathError(ArgumentError):
  """ When a user supplies an incorrect/invalid path """

class ControlError(ProtocolError):
  """ Errors in Command/Response pairs while communicating with the device """
  def __init__(self, query=None, response=None, desc=None):
    self.query = query
    self.response = response
    Exception.__init__(self, desc)
    
  def __str__(self):    
    if self.query and self.response:
      return "Got unexpected response:\n" + \
           "query:\n"+str(self.query.query)+"\n"+\
           "expected:\n"+str(self.query.response)+"\n" +\
           "actual:\n"+str(self.response)
    if self.desc:
      return self.desc
    return "Unknown control error occurred"
