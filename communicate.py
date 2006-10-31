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

import sys, usb
from data import *
from types import *
from exceptions import Exception

### End point description for PRS-500 procductId=667
### Endpoint Descriptor:
###        bLength                 7
###        bDescriptorType         5
###        bEndpointAddress     0x81  EP 1 IN
###        bmAttributes            2
###          Transfer Type            Bulk
###          Synch Type               None
###          Usage Type               Data
###        wMaxPacketSize     0x0040  1x 64 bytes
###        bInterval               0
###      Endpoint Descriptor:
###        bLength                 7
###        bDescriptorType         5
###        bEndpointAddress     0x02  EP 2 OUT
###        bmAttributes            2
###          Transfer Type            Bulk
###          Synch Type               None
###          Usage Type               Data
###        wMaxPacketSize     0x0040  1x 64 bytes
###        bInterval               0
### 
###
###  Endpoint 0x81 is device->host and endpoint 0x02 is host->device. You can establish Stream pipes to/from these endpoints for Bulk transfers.
###  Has two configurations 1 is the USB charging config 2 is the self-powered config. 
###  I think config management is automatic. Endpoints are the same

class PathError(Exception):
  def __init__(self, msg):
    Exception.__init__(self, msg)

class ControlError(Exception):
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

class DeviceDescriptor:
  def __init__(self, vendor_id, product_id, interface_id) :
    self.vendor_id = vendor_id
    self.product_id = product_id
    self.interface_id = interface_id

  def getDevice(self) :
    """
    Return the device corresponding to the device descriptor if it is
    available on a USB bus.  Otherwise, return None.  Note that the
    returned device has yet to be claimed or opened.
    """
    buses = usb.busses()
    for bus in buses :
      for device in bus.devices :
        if device.idVendor == self.vendor_id :
          if device.idProduct == self.product_id :
            return device
    return None


class PRS500Device:
  SONY_VENDOR_ID      = 0x054c
  PRS500_PRODUCT_ID   = 0x029b
  PRS500_INTERFACE_ID = 0
  PRS500_BULK_IN_EP   = 0x81
  PRS500_BULK_OUT_EP  = 0x02

  def __init__(self) :
    self.device_descriptor = DeviceDescriptor(PRS500Device.SONY_VENDOR_ID,
                                              PRS500Device.PRS500_PRODUCT_ID,
                                              PRS500Device.PRS500_INTERFACE_ID)
    self.device = self.device_descriptor.getDevice()
    self.handle = None

  def open(self) :
    self.device = self.device_descriptor.getDevice()
    if not self.device:
      print >> sys.stderr, "Unable to find Sony Reader. Is it connected?"
      sys.exit(1)
    self.handle = self.device.open()
    if sys.platform == 'darwin' :
      # XXX : For some reason, Mac OS X doesn't set the
      # configuration automatically like Linux does.
      self.handle.setConfiguration(1)
    self.handle.claimInterface(self.device_descriptor.interface_id)
    self.handle.reset()

  def close(self):    
    self.handle.releaseInterface()
    self.handle, self.device = None, None

  def send_sony_control_query(self, query, timeout=100):
    r = self.handle.controlMsg(0x40, 0x80, query.query)
    if r != len(query.query):
      raise ControlError(desc="Could not send control request to device\n" + str(query.query))
    res = normalize_buffer(self.handle.controlMsg(0xc0, 0x81, len(query.response), timeout=timeout))
    if res != query.response:
      raise ControlError(query=query, response=res)
    
  def bulkRead(self, size):
    return TransferBuffer(self.handle.bulkRead(PRS500Device.PRS500_BULK_IN_EP, size))
    
  def initialize(self):
    self.handle.reset()
    for query in initialization:
      self.send_sony_control_query(query)      
      if query.bulkTransfer and "__len__" not in dir(query.bulkTransfer):
        self.bulkRead(query.bulkTransfer)
    
  def ls(self, path):
    """
    ls path
    
    Packet scheme: query, bulk read, acknowledge; repeat
    Errors, EOF conditions are indicated in the reply to query. They also show up in the reply to acknowledge
    I haven't figured out what the first bulk read is for
    """
    if path[len(path)-1] != "/": path = path + "/"
    self.initialize()
    q1 = LSQuery(path, type=1)
    files, res1, res2, error_type = [], None, None, 0
    try:
      self.send_sony_control_query(q1)
    except ControlError, e:
      if e.response == LSQuery.PATH_NOT_FOUND_RESPONSE: 
        error_type = 1
        raise PathError(path[:-1] + " does not exist")        
      elif e.response == LSQuery.IS_FILE_RESPONSE: error_type = 2
      elif e.response == LSQuery.NOT_MOUNTED_RESPONSE: 
        error_type = 3
        raise PathError(path + " is not mounted")
      elif e.response == LSQuery.INVALID_PATH_RESPONSE: 
        error_type = 4
        raise PathError(path + " is an invalid path")      
      else: raise e
    finally:
      res1 = normalize_buffer(self.bulkRead(q1.bulkTransfer))
      self.send_sony_control_query(q1.acknowledge_query(1, error_type=error_type))
    
    if error_type == 2: # If path points to a file
      files.append(path[:-1])
    else:
      q2 = LSQuery(path, type=2)
      try:
        self.send_sony_control_query(q2)
      finally:
        res2 = normalize_buffer(self.bulkRead(q2.bulkTransfer))
        self.send_sony_control_query(q1.acknowledge_query(2))
        
      send_name = q2.send_name_query(res2)
      buffer_length = 0
      while True:
        try:
          self.send_sony_control_query(send_name)
        except ControlError, e:
          buffer_length = 16 + e.response[28] + e.response[29] + e.response[30] + e.response[31]
          res = self.bulkRead(buffer_length)
          if e.response == LSQuery.EOL_RESPONSE:
            self.send_sony_control_query(q2.acknowledge_query(0))
            break
          else: 
            self.send_sony_control_query(q2.acknowledge_query(3))
            files.append("".join([chr(i) for i in list(res)[23:]]))        
    return files
    

def main(path):
  dev = PRS500Device()
  dev.open()  
  try:
    print " ".join(dev.ls(path))
  except PathError, e:
    print >> sys.stderr, e
  finally:
    dev.close()

if __name__ == "__main__":
  main(sys.argv[1])
