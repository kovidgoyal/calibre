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
import usb, sys, os, time
from array import array
from xml.sax.handler import ContentHandler
from xml.sax import make_parser
from xml.sax.handler import feature_namespaces
from base64 import b64decode as decode
from tempfile import TemporaryFile

from prstypes import *
from errors import *

MINIMUM_COL_WIDTH = 12 #: Minimum width of columns in ls output
_packet_number = 0     #: Keep track of the packet number of packet tracing
KNOWN_USB_PROTOCOL_VERSIONS = [0x3030303030303130L] #: Protocol versions libprs500 has been tested with

def _log_packet(packet, header, stream=sys.stderr):
  """ Log C{packet} to stream C{stream}. Header should be a small word describing the type of packet. """
  global _packet_number
  _packet_number += 1
  print >>stream, str(_packet_number), header, "Type:", packet.__class__.__name__
  print >>stream, packet
  print >>stream, "--"

class FindBooks(ContentHandler):
  """ Used to parse the cache.xml/media.xml files on the PRS 500 """
  class Book(dict):
    def __init__(self, src):
      dict.__init__(self, src)
      if not self.has_key("author") or len(self["author"].rstrip()) == 0:
        self["author"] = "Unknown"
      self["title"] = self["title"].strip()
        
    def __repr__(self):      
      return self["title"] + " by " + self["author"] + " at " + self["path"]
      
    def __str__(self):
      return self.__repr__()
      
  def __init__(self, type="media", root="/Data/media/"):
    ContentHandler.__init__(self)
    self.books = []
    self.root  = root
    self.thumbnail = ""
    self.in_book = False
    self.in_thumbnail = False
    self.book_name = "text"
    self.thumbnail_name = "thumbnail"
    if type == "media":
      self.book_name = "xs1:" + self.book_name
      self.thumbnail_name = "xs1:" + self.thumbnail_name

  def startElement(self, name, attrs):
    if name == self.book_name:
      data = FindBooks.Book(attrs)
      data["path"] = self.root + data["path"]      
      self.books.append(data)
      self.in_book = True
    elif self.in_book and name == self.thumbnail_name:
      self.in_thumbnail = True

  def characters(self, ch):
    if self.in_thumbnail:
      self.thumbnail += ch
      
  def endElement(self, name):
    if self.in_book and name == self.thumbnail_name:
      if len(self.books) > 0: self.books[len(self.books)-1]["thumbnail"] = decode(self.thumbnail)
      self.thumbnail, self.in_thumbnail = "", False
    elif name == self.book_name: self.in_book = False


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
    return "File:"+self.path
    
  def __str__(self):
    return self.name


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

  def safe(func):
    """ 
    Decorator that wraps a call to C{func} to ensure that exceptions are handled correctly. 
    It also calls L{open} to claim the interface and initialize the Reader if needed.
    
    As a convenience, C{safe} automatically sends the a L{USBConnect} after calling func, unless func has
    a keyword argument named C{end_session} set to C{False}.
    
    An L{ArgumentError} will cause the L{USBConnect} command to be sent to the device, unless end_session is set to C{False}.
    An L{usb.USBError} will cause the library to release control of the USB interface via a call to L{close}.
    """
    def run_session(*args, **kwargs):
      dev = args[0]      
      res = None
      try:
        if not dev.handle: dev.open()
        res = func(*args, **kwargs)
      except ArgumentError, e:
        if not kwargs.has_key("end_session") or kwargs["end_session"]:
          dev._send_validated_command(USBConnect())        
        raise e
      except usb.USBError, e:
        if "No such device" in str(e):
          raise DeviceError()
        elif "Connection timed out" in str(e):
          raise TimeoutError(func.__name__)
        dev.close()
        raise e
      if not kwargs.has_key("end_session") or kwargs["end_session"]:
        dev._send_validated_command(USBConnect())
      return res
      
    return run_session

  def __init__(self, log_packets=False) :
    """ @param log_packets: If true the packet stream to/from the device is logged """
    self.device_descriptor = DeviceDescriptor(PRS500Device.SONY_VENDOR_ID,
                                              PRS500Device.PRS500_PRODUCT_ID,
                                              PRS500Device.PRS500_INTERFACE_ID)
    self.device = self.device_descriptor.getDevice() #: The actual device (PyUSB object)
    self.handle = None                               #: Handle that is used to communicate with device. Setup in L{open}
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
    Also initialize the device. See the source code for the sequenceof initialization commands.
    
    @todo: Implement unlocking of the device
    @todo: Check this on Mac OSX
    """
    self.device = self.device_descriptor.getDevice()
    if not self.device:
      raise DeviceError()
    self.handle = self.device.open()
    self.handle.claimInterface(self.device_descriptor.interface_id)
    self.handle.reset()
    res = self._send_validated_command(GetUSBProtocolVersion())
    if res.code != 0: raise ProtocolError("Unable to get USB Protocol version.")
    version = self._bulk_read(24, data_type=USBProtocolVersion)[0].version
    if version not in KNOWN_USB_PROTOCOL_VERSIONS:
      print >>sys.stderr, "WARNING: Usb protocol version " + hex(version) + " is unknown"
    res = self._send_validated_command(SetBulkSize(size=0x028000))
    if res.code != 0: raise ProtocolError("Unable to set bulk size.")
    self._send_validated_command(UnlockDevice(key=0x312d))
    if res.code != 0: 
      raise ProtocolError("Unlocking of device not implemented. Remove locking and retry.")
    
    
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
    if self._log_packets: _log_packet(command, "Command")
    bytes_sent = self.handle.controlMsg(0x40, 0x80, command)
    if bytes_sent != len(command):
      raise ControlError(desc="Could not send control request to device\n" + str(query.query))
    response = response_type(self.handle.controlMsg(0xc0, 0x81, Response.SIZE, timeout=timeout))
    if self._log_packets: _log_packet(response, "Response")
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
    
  def _bulk_write(self, data, packet_size=0x1000):
    """ 
    Send data to device via a bulk transfer.
    @type data: Any listable type supporting __getslice__
    @param packet_size: Size of packets to be sent to device. C{data} is broken up into packets to be sent to device.
    """
    def bulk_write_packet(packet):
      self.handle.bulkWrite(PRS500Device.PRS500_BULK_OUT_EP, packet)
      if self._log_packets: _log_packet(Answer(packet), "Answer h->d")
        
    bytes_left = len(data)        
    if bytes_left + 16 <= packet_size:
      packet_size = bytes_left +16
      first_packet = Answer(bytes_left+16)
      first_packet[16:] = data
      first_packet.length = len(data)
    else:
      first_packet = Answer(packet_size)
      first_packet[16:] = data[0:packet_size-16]
      first_packet.length = packet_size-16
    first_packet.number = 0x10005
    bulk_write_packet(first_packet)
    pos = first_packet.length
    bytes_left -= first_packet.length
    while bytes_left > 0:
      endpos = pos + packet_size if pos + packet_size <= len(data) else len(data)
      bulk_write_packet(data[pos:endpos])
      bytes_left -= endpos - pos
      pos = endpos
    res = Response(self.handle.controlMsg(0xc0, 0x81, Response.SIZE, timeout=5000))
    if self._log_packets: _log_packet(res, "Response")
    if res.rnumber != 0x10005 or res.code != 0:
      raise ProtocolError("Sending via Bulk Transfer failed with response:\n"+str(res))  
    if res.data_size != len(data):
      raise ProtocolError("Unable to transfer all data to device. Response packet:\n"+str(res))
    
  
  def _bulk_read(self, bytes, command_number=0x00, packet_size=4096, data_type=Answer):
    """ 
    Read in C{bytes} bytes via a bulk transfer in packets of size S{<=} C{packet_size} 
    @param data_type: an object of type type. The data packet is returned as an object of type C{data_type}.    
    @return: A list of packets read from the device. Each packet is of type data_type
    @todo: Figure out how to make bulk reads work in OSX
    """
    def bulk_read_packet(data_type=Answer, size=0x1000):
      data = data_type(self.handle.bulkRead(PRS500Device.PRS500_BULK_IN_EP, size))
      if self._log_packets: _log_packet(data, "Answer d->h")
      return data
      
    bytes_left = bytes
    packets = []
    while bytes_left > 0:
      if packet_size > bytes_left: packet_size = bytes_left
      packet = bulk_read_packet(data_type=data_type, size=packet_size)
      bytes_left -= len(packet)
      packets.append(packet)
    self._send_validated_command(AcknowledgeBulkRead(packets[0].number), cnumber=command_number)
    return packets
    
  @safe
  def get_device_information(self, end_session=True):
    """ 
    Ask device for device information. See L{DeviceInfoQuery}. 
    @return: (device name, device version, software version on device, mime type)
    """
    size = self._send_validated_command(DeviceInfoQuery()).data[2] + 16
    data = self._bulk_read(size, command_number=DeviceInfoQuery.NUMBER, data_type=DeviceInfo)[0]
    return (data.device_name, data.device_version, data.software_version, data.mime_type)
    
  @safe
  def path_properties(self, path, end_session=True):
    """ Send command asking device for properties of C{path}. Return L{FileProperties}. """
    res  = self._send_validated_command(PathQuery(path), response_type=ListResponse)
    data = self._bulk_read(0x28, data_type=FileProperties, command_number=PathQuery.NUMBER)[0]
    if path.endswith("/"): path = path[:-1]
    if res.path_not_found : raise PathError(path + " does not exist on device")
    if res.is_invalid     : raise PathError(path + " is not a valid path")
    if res.is_unmounted   : raise PathError(path + " is not mounted")
    if res.code not in (0, PathResponseCodes.IS_FILE):
      raise PathError(path + " has an unknown error. Code: " + hex(res.code))
    return data
     
  @safe
  def get_file(self, path, outfile, end_session=True):
    """
    Read the file at path on the device and write it to outfile. For the logic see L{_get_file}.
    
    The data is fetched in chunks of size S{<=} 32K. Each chunk is make of packets of size S{<=} 4K. See L{FileOpen},
    L{FileRead} and L{FileClose} for details on the command packets used. 
        
    @param outfile: file object like C{sys.stdout} or the result of an C{open} call
    """
    if path.endswith("/"): path = path[:-1] # We only copy files
    file = self.path_properties(path, end_session=False)
    if file.is_dir: raise PathError("Cannot read as " + path + " is a directory")
    bytes = file.file_size
    res = self._send_validated_command(FileOpen(path))
    if res.code != 0:
      raise PathError("Unable to open " + path + " for reading. Response code: " + hex(res.code))
    id = self._bulk_read(20, data_type=IdAnswer, command_number=FileOpen.NUMBER)[0].id    
    bytes_left, chunk_size, pos = bytes, 0x8000, 0    
    while bytes_left > 0:
      if chunk_size > bytes_left: chunk_size = bytes_left
      res = self._send_validated_command(FileIO(id, pos, chunk_size))
      if res.code != 0:
        self._send_validated_command(FileClose(id))
        raise ProtocolError("Error while reading from " + path + ". Response code: " + hex(res.code))
      packets = self._bulk_read(chunk_size+16, command_number=FileIO.RNUMBER, packet_size=4096)
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
    # Not going to check response code to see if close was successful as there's not much we can do if it wasnt
          
  
  
  @safe
  def list(self, path, recurse=False, end_session=True):
    """
    Return a listing of path. See the code for details. See L{DirOpen},
    L{DirRead} and L{DirClose} for details on the command packets used.
    
    @type path: string
    @param path: The path to list
    @type recurse: boolean
    @param recurse: If true do a recursive listing    
    @return: A list of tuples. The first element of each tuple is a path.  The second element is a list of L{Files<File>}. 
             The path is the path we are listing, the C{Files} are the files/directories in that path. If it is a recursive
             list, then the first element will be (C{path}, children), the next will be (child, its children) and so on. If it
             is not recursive the length of the outermost list will be 1.
    """
    def _list(path): # Do a non recursive listsing of path
      if not path.endswith("/"): path += "/" # Initially assume path is a directory
      files = []
      candidate = self.path_properties(path, end_session=False)
      if not candidate.is_dir: 
        path = path[:-1]
        data = self.path_properties(path, end_session=False)      
        files = [ File((path, data)) ]
      else:
        # Get query ID used to ask for next element in list
        res = self._send_validated_command(DirOpen(path))
        if res.code != 0:
          raise PathError("Unable to open directory " + path + " for reading. Response code: " + hex(res.code))
        id = self._bulk_read(0x14, data_type=IdAnswer, command_number=DirOpen.NUMBER)[0].id
        # Create command asking for next element in list
        next = DirRead(id)
        items = []
        while True:
          res = self._send_validated_command(next, response_type=ListResponse)        
          size = res.data_size + 16
          data = self._bulk_read(size, data_type=ListAnswer, command_number=DirRead.NUMBER)[0]
          # path_not_found seems to happen if the usb server doesn't have the permissions to access the directory
          if res.is_eol or res.path_not_found: break 
          elif res.code != 0:
            raise ProtocolError("Unknown error occured while reading contents of directory " + path + ". Response code: " + haex(res.code))
          items.append(data.name)
        self._send_validated_command(DirClose(id)) # Ignore res.code as we cant do anything if close fails
        for item in items:
          ipath = path + item
          data = self.path_properties(ipath, end_session=False)
          files.append( File( (ipath, data) ) )
      files.sort()
      return files
      
    files = _list(path)
    dirs = [(path, files)]
      
    for file in files:
      if recurse and file.is_dir and not file.path.startswith(("/dev","/proc")):
        dirs[len(dirs):] = self.list(file.path, recurse=True, end_session=False)
    return dirs
    
  @safe
  def available_space(self, end_session=True):
    """ 
    Get free space available on the mountpoints:
      1. /Data/ Device memory
      2. a:/    Memory Stick
      3. b:/    SD Card
      
    @return: A list of tuples. Each tuple has form ("location", free space, total space)
    """    
    data = []
    for path in ("/Data/", "a:/", "b:/"):
      res = self._send_validated_command(FreeSpaceQuery(path),timeout=5000) # Timeout needs to be increased as it takes time to read card
      buffer_size = 16 + res.data[2]
      pkt = self._bulk_read(buffer_size, data_type=FreeSpaceAnswer, command_number=FreeSpaceQuery.NUMBER)[0]
      data.append( (path, pkt.free_space, pkt.total) )
    return data
    
  def _exists(self, path):
    """ Return (True, FileProperties) if path exists or (False, None) otherwise """
    dest = None
    try:
      dest = self.path_properties(path, end_session=False)
    except PathError, e:
      if "does not exist" in str(e): return (False, None)
      else: raise e
    return (True, dest)
  
  @safe
  def touch(self, path, end_session=True):
    """ Create a file at path """
    if path.endswith("/") and len(path) > 1: path = path[:-1]
    exists, file = self._exists(path)
    if exists and file.is_dir:
      raise PathError("Cannot touch directories")
    if not exists:
      res = self._send_validated_command(FileCreate(path))
      if res.code != 0:
        raise PathError("Could not create file " + path + ". Response code: " + str(hex(res.code)))
    
  
  @safe
  def put_file(self, infile, path, end_session=True):
    exists, dest = self._exists(path)        
    if exists:
      if not dest.is_dir: raise PathError("Cannot write to " + path + " as it already exists")
      if not path.endswith("/"): path += "/"
      path += os.path.basename(infile.name)
      exists, dest = self._exists(path)
      if exists: raise PathError("Cannot write to " + path + " as it already exists")
    res = self._send_validated_command(FileCreate(path))
    if res.code != 0:
      raise ProtocolError("There was an error creating device:"+path+". Response code: "+hex(res.code))
    chunk_size = 0x8000
    data_left = True
    res = self._send_validated_command(FileOpen(path, mode=FileOpen.WRITE))
    if res.code != 0:
      raise ProtocolError("Unable to open " + path + " for writing. Response code: " + hex(res.code))
    id = self._bulk_read(20, data_type=IdAnswer, command_number=FileOpen.NUMBER)[0].id    
    pos = 0
    while data_left:
      data = array('B')
      try:
        data.fromfile(infile, chunk_size)
      except EOFError: 
        data_left = False
      res = self._send_validated_command(FileIO(id, pos, len(data), mode=FileIO.WNUMBER))      
      if res.code != 0:
        raise ProtocolError("Unable to write to " + path + ". Response code: " + hex(res.code))
      self._bulk_write(data)
      pos += len(data)
    self._send_validated_command(FileClose(id)) # Ignore res.code as cant do anything if close fails
    file = self.path_properties(path, end_session=False)
    if file.file_size != pos:
      raise ProtocolError("Copying to device failed. The file was truncated by " + str(data.file_size - pos) + " bytes")
    
  @safe
  def del_file(self, path, end_session=True):
    data = self.path_properties(path, end_session=False)
    if data.is_dir: raise PathError("Cannot delete directories")
    res = self._send_validated_command(FileDelete(path), response_type=ListResponse)
    if res.code != 0:
      raise ProtocolError("Unable to delete " + path + " with response:\n" + str(res))
      
  @safe
  def mkdir(self, path, end_session=True):
    if not path.endswith("/"): path += "/"
    error_prefix = "Cannot create directory " + path
    res = self._send_validated_command(DirCreate(path)).data[0]
    if res == 0xffffffcc:
      raise PathError(error_prefix + " as it already exists")
    elif res == PathResponseCodes.NOT_FOUND:
      raise PathError(error_prefix + " as " + path[0:path[:-1].rfind("/")] + " does not exist ")
    elif res == PathResponseCodes.INVALID:
      raise PathError(error_prefix + " as " + path + " is invalid")
    elif res != 0:
      raise PathError(error_prefix + ". Response code: " + hex(res))
  
  @safe
  def rm(self, path, end_session=True):
    """ Delete path from device if it is a file or an empty directory """
    dir = self.path_properties(path, end_session=False)
    if not dir.is_dir:
      self.del_file(path, end_session=False)
    else:
      if not path.endswith("/"):  path += "/"        
      res = self._send_validated_command(DirDelete(path))
      if res.code == PathResponseCodes.HAS_CHILDREN:
        raise PathError("Cannot delete directory " + path + " as it is not empty")
      if res.code != 0:
        raise ProtocolError("Failed to delete directory " + path + ". Response code: " + hex(res.code))
        
  @safe
  def books(self):
    """ 
    Return a list of all ebooks on the device 
    
    @return: A four element tuple. The first element is the books in the main memory and the second is the books on the storage card.
             The first two elements are each a list of dictionaries. If there is no card the second list is empty. 
             Important fields in each dictionary are "title", "author", "path" and "thumbnail". 
             The third and fourth elements are the temporary files that hold main.xml and cache.xml
    """
    main_xml = TemporaryFile()
    media = self.get_file("/Data/database/cache/media.xml", main_xml, end_session=False)
    parser = make_parser()
    parser.setFeature(feature_namespaces, 0)
    finder = FindBooks()
    parser.setContentHandler(finder)
    main_xml.seek(0)
    parser.parse(main_xml)
    books = finder.books
    root = "a:/"
    cache_xml = TemporaryFile()
    cbooks = []
    try:
      self.get_file("a:/Sony Reader/database/cache.xml", cache_xml, end_session=False)
    except PathError:
      try:
        self.get_file("b:/Sony Reader/database/cache.xml", cache_xml, end_session=False)
        root = "b:/"
      except PathError: 
        pass
    if cache_xml.tell() > 0:
      finder = FindBooks(type="cache", root=root)
      cache_xml.seek(0)
      parser.setContentHandler(finder)
      parser.parse(cache_xml)
      cbooks = finder.books
    return books, cbooks, main_xml, cache_xml
    


##dev = PRS500Device(log_packets=False)
##dev.open()
##print dev.books()
##dev.close()

