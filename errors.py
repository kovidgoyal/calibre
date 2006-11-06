#!/usr/bin/env python
from exceptions import Exception

class ProtocolError(Exception):
  """ The base class for all exceptions in this package """
  def __init__(self, msg):
    Exception.__init__(self, msg)
    
class PacketError(ProtocolError):
  """ Errors with creating/interpreting packets """
  def __init__(self, msg):
    ProtocolError.__init__(self, msg)
    
class PathError(ProtocolError):
  def __init__(self, msg):
    Exception.__init__(self, msg)

class ControlError(ProtocolError):
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
