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
"""
Contains the logic for communication with the device (a SONY PRS-500).

The public interface of class L{PRS500Device} defines the methods for performing various tasks. 
"""
import usb, sys
from array import array

from prstypes import AcknowledgeBulkRead, Answer, Command, DeviceInfo, DirOpen, DirRead, DirClose, \
                     FileOpen, FileClose, FileRead, IdAnswer, ListAnswer, \
                     ListResponse, LongCommand, FileProperties, PathQuery, Response, \
                     ShortCommand, DeviceInfoQuery
from errors import *

MINIMUM_COL_WIDTH = 12 #: Minimum width of columns in ls output

class File(object):
  """ Wrapper that allows easy access to all information about files/directories """
  def __init__(self, file):
    self.is_dir      = file[1].is_dir      #: True if self is a directory
    self.is_readonly = file[1].is_readonly #: True if self is readonly
    self.size        = file[1].file_size   #: Size in bytes of self
    self.ctime       = file[1].ctime       #: Creation time of self as a epoch
    self.wtime       = file[1].wtime       #: Creation time of self as an epoch
    path = file[0]
    if path.endswith("/"): path = path[:-1]
    self.path = path                       #: Path to self  
    self.name = path[path.rfind("/")+1:].rstrip() #: Name of self
    
  def __repr__(self):
    """ Return path to self """
    return self.path


class DeviceDescriptor:
  """ 
  Describes a USB device.
  
  A description is composed of the Vendor Id, Product Id and Interface Id. 
  See the U{USB spec<http://www.usb.org/developers/docs/usb_20_05122006.zip>}
  """
  
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


class PRS500Device(object):
  
  """
  Contains the logic for performing various tasks on the reader. 
  
  The implemented tasks are:
    0. Getting information about the device
    1. Getting a file from the device
    2. Listing of directories. See the C{list} method. 
  """
  
  SONY_VENDOR_ID      = 0x054c #: SONY Vendor Id
  PRS500_PRODUCT_ID   = 0x029b #: Product Id for the PRS-500
  PRS500_INTERFACE_ID = 0      #: The interface we use to talk to the device
  PRS500_BULK_IN_EP   = 0x81   #: Endpoint for Bulk reads
  PRS500_BULK_OUT_EP  = 0x02   #: Endpoint for Bulk writes

  def __init__(self, log_packets=False) :
    """ @param log_packets: If true the packet stream to/from the device is logged """
    self.device_descriptor = DeviceDescriptor(PRS500Device.SONY_VENDOR_ID,
                                              PRS500Device.PRS500_PRODUCT_ID,
                                              PRS500Device.PRS500_INTERFACE_ID)
    self.device = self.device_descriptor.getDevice()
    self.handle = None
    self._log_packets = log_packets
    
  @classmethod
  def _validate_response(cls, res, type=0x00, number=0x00):
    """ Raise a ProtocolError if the type and number of C{res} is not the same as C{type} and C{number}. """
    if type != res.type or number != res.rnumber:
      raise ProtocolError("Inavlid response.\ntype: expected="+hex(type)+" actual="+hex(res.type)+
                          "\nrnumber: expected="+hex(number)+" actual="+hex(res.rnumber))

  def open(self) :
    """
    Claim an interface on the device for communication. Requires write privileges to the device file.
    
    @todo: Check this on Mac OSX
    """
    self.device = self.device_descriptor.getDevice()
    if not self.device:
      print >> sys.stderr, "Unable to find Sony Reader. Is it connected?"
      sys.exit(1)
    self.handle = self.device.open()
    if sys.platform == 'darwin' :
      # XXX : For some reason, Mac OS X doesn't set the
      # configuration automatically like Linux does.
      self.handle.setConfiguration(1) # TODO: Check on Mac OSX
    self.handle.claimInterface(self.device_descriptor.interface_id)
    self.handle.reset()
    
  def close(self):    
    """ Release device interface """
    self.handle.releaseInterface()
    self.handle, self.device = None, None

  def _send_command(self, command, response_type=Response, timeout=100):
    """ 
    Send L{command<Command>} to device and return its L{response<Response>}. 
    
    @param command:       an object of type Command or one of its derived classes
    @param response_type: an object of type 'type'. The return packet from the device is returned as an object of type response_type. 
    @param timeout:       the time to wait for a response from the device, in milliseconds. If there is no response, a L{usb.USBError} is raised.
    """
    if self._log_packets: print "Command\n%s\n--\n"%command
    bytes_sent = self.handle.controlMsg(0x40, 0x80, command)
    if bytes_sent != len(command):
      raise ControlError(desc="Could not send control request to device\n" + str(query.query))
    response = response_type(self.handle.controlMsg(0xc0, 0x81, Response.SIZE, timeout=timeout))
    if self._log_packets: print "Response\n%s\n--\n"%response
    return response
    
  def _send_validated_command(self, command, cnumber=None, response_type=Response, timeout=100):
    """ 
    Wrapper around L{_send_command} that checks if the C{Response.rnumber == cnumber or command.number if cnumber==None}. Also check that
    C{Response.type == Command.type}.
    """
    if cnumber == None: cnumber = command.number
    res = self._send_command(command, response_type=response_type, timeout=timeout)
    PRS500Device._validate_response(res, type=command.type, number=cnumber)
    return res
    
  def _bulk_read_packet(self, data_type=Answer, size=4096):
    """
    Read in a data packet via a Bulk Read.
    
    @param data_type: an object of type type. The data packet is returned as an object of type C{data_type}.
    @param size: the expected size of the data packet. 
    """
    data = data_type(self.handle.bulkRead(PRS500Device.PRS500_BULK_IN_EP, size))
    if self._log_packets: print "Answer\n%s\n--\n"%data
    return data
  
  def _bulk_read(self, bytes, command_number=0x00, packet_size=4096, data_type=Answer):
    """ Read in C{bytes} bytes via a bulk transfer in packets of size S{<=} C{packet_size} """
    bytes_left = bytes
    packets = []
    while bytes_left > 0:
      if packet_size > bytes_left: packet_size = bytes_left
      packet = self._bulk_read_packet(data_type=data_type, size=packet_size)
      bytes_left -= len(packet)
      packets.append(packet)
    self._send_validated_command(AcknowledgeBulkRead(packets[0].id), cnumber=command_number)
    return packets
    
  def _test_bulk_reads(self):
    """ Carries out a test of bulk reading as part of session initialization. """
    self._send_validated_command( ShortCommand(number=0x00, type=0x01, command=0x00) )    
    self._bulk_read(24, command_number=0x00)
      
  def _start_session(self):
    """ 
    Send the initialization sequence to the device. See the code for details. 
    This method should be called before any real work is done. Though most things seem to work without it.
    """    
    self.handle.reset()
    self._test_bulk_reads()
    self._send_validated_command( ShortCommand(number=0x0107, command=0x028000, type=0x01) ) # TODO: Figure out the meaning of this command
    self._test_bulk_reads()
    self._send_validated_command( ShortCommand(number=0x0106, type=0x01, command=0x312d) )   # TODO: Figure out the meaning of this command
    self._send_validated_command( ShortCommand(number=0x01, type=0x01, command=0x01) )
    
  def _end_session(self):
    """ Send the end session command to the device. Causes the device to change status from "Do not disconnect" to "USB Connected" """
    self._send_validated_command( ShortCommand(number=0x01, type=0x01, command=0x00) )
  
  def _run_session(self, *args):
    """
    Wrapper that automatically calls L{_start_session} and L{_end_session}.
    
    @param args: An array whose first element is the method to call and whose remaining arguments are passed to that mathos as an array.
    """
    self._start_session()
    res = None
    try:
      res = args[0](args[1:])
    except ArgumentError, e:
      self._end_session()
      raise e
    self._end_session()
    return res
  
  def _get_device_information(self, args):
    """ Ask device for device information. See L{DeviceInfoQuery}. """
    size = self._send_validated_command(DeviceInfoQuery()).data[2] + 16
    data = self._bulk_read(size, command_number=DeviceInfoQuery.NUMBER, data_type=DeviceInfo)[0]
    return (data.device_name, data.device_version, data.software_version, data.mime_type)
    
  def get_device_information(self):
    """ Return (device name, device version, software version on device, mime type). See L{_get_device_information} """
    return self._run_session(self._get_device_information)
  
  def _get_path_properties(self, path):
    """ Send command asking device for properties of C{path}. Return (L{Response}, L{Answer}). """
    res = self._send_validated_command(PathQuery(path), response_type=ListResponse)
    data = self._bulk_read(0x28, data_type=FileProperties, command_number=PathQuery.NUMBER)[0]
    if path.endswith("/"): path = path[:-1]
    if res.path_not_found : raise PathError(path + " does not exist on device")
    if res.is_invalid     : raise PathError(path + " is not a valid path")
    if res.is_unmounted   : raise PathError(path + " is not mounted")
    return (res, data)
     
  def get_file(self, path, outfile):
    """
    Read the file at path on the device and write it to outfile. For the logic see L{_get_file}.
    
    @param outfile: file object like C{sys.stdout} or the result of an C{open} call
    """
    self._run_session(self._get_file, path, outfile)
  
  def _get_file(self, args):
    """
    Fetch a file from the device and write it to an output stream. 
    
    The data is fetched in chunks of size S{<=} 32K. Each chunk is make of packets of size S{<=} 4K. See L{FileOpen},
    L{FileRead} and L{FileClose} for details on the command packets used. 
    
    @param args: C{path, outfile = arg[0], arg[1]}
    """
    path, outfile = args[0], args[1]
    if path.endswith("/"): path = path[:-1] # We only copy files
    res, data = self._get_path_properties(path)
    if data.is_dir: raise PathError("Cannot read as " + path + " is a directory")
    bytes = data.file_size
    self._send_validated_command(FileOpen(path))
    id = self._bulk_read(20, data_type=IdAnswer, command_number=FileOpen.NUMBER)[0].id    
    bytes_left, chunk_size, pos = bytes, 0x8000, 0    
    while bytes_left > 0:
      if chunk_size > bytes_left: chunk_size = bytes_left
      res = self._send_validated_command(FileRead(id, pos, chunk_size))
      packets = self._bulk_read(chunk_size+16, command_number=FileRead.NUMBER, packet_size=4096)
      try:
        array('B', packets[0][16:]).tofile(outfile) # The first 16 bytes are meta information on the packet stream
        for i in range(1, len(packets)): 
          array('B', packets[i]).tofile(outfile)
      except IOError, e:
        self._send_validated_command(FileClose(id))
        raise ArgumentError("File get operation failed. Could not write to local location: " + str(e))          
      bytes_left -= chunk_size
      pos += chunk_size
    self._send_validated_command(FileClose(id))
          
  
  def _list(self, args):
    """ 
    Ask the device to list a path. See the code for details. See L{DirOpen},
    L{DirRead} and L{DirClose} for details on the command packets used.
    
    @param args:  C{path=args[0]}
    @return: A list of tuples. The first element of each tuple is a string, the path. The second is a L{FileProperties}.
             If the path points to a file, the list will have length 1.
    """
    path = args[0]
    if not path.endswith("/"): path += "/" # Initially assume path is a directory
    files = []
    res, data = self._get_path_properties(path)
    if res.is_file: 
      path = path[:-1]
      res, data = self._get_path_properties(path)      
      files = [ (path, data) ]
    else:
      # Get query ID used to ask for next element in list
      self._send_validated_command(DirOpen(path), response_type=ListResponse)
      id = self._bulk_read(0x14, data_type=IdAnswer, command_number=DirOpen.NUMBER)[0].id
      # Create command asking for next element in list
      next = DirRead(id)
      items = []
      while True:
        res = self._send_validated_command(next, response_type=ListResponse)        
        size = res.data[2] + 16
        data = self._bulk_read(size, data_type=ListAnswer, command_number=DirRead.NUMBER)[0]
        # path_not_found seems to happen if the usb server doesn't have the permissions to access the directory
        if res.is_eol or res.path_not_found: break 
        items.append(data.name)
      self._send_validated_command(DirClose(id))
      for item in items:
        ipath = path + item
        res, data = self._get_path_properties(ipath)
        files.append( (ipath, data) )
    files.sort()
    return files
  
  def list(self, path, recurse=False):
    """
    Return a listing of path.
    
    See L{_list} for the communication logic.
    
    @type path: string
    @param path: The path to list
    @type recurse: boolean
    @param recurse: If true do a recursive listing    
    @return: A list of tuples. The first element of each tuple is a path.  The second element is a list of L{Files<File>}. 
             The path is the path we are listing, the C{Files} are the files/directories in that path. If it is a recursive
             list, then the first element will be (C{path}, children), the next will be (child, its children) and so on.
    """
    files = self._run_session(self._list, path)    
    files = [ File(file) for file in files ]
    dirs = [(path, files)]
    for file in files:
      if recurse and file.is_dir and not file.path.startswith(("/dev","/proc")):
        dirs[len(dirs):] = self.list(file.path, recurse=True)
    return dirs
