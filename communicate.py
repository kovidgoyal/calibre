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

import sys, usb, logging, StringIO, time
from optparse import OptionParser

from prstypes import *
from errors import *
from terminfo import TerminalController

#try:
#        import psyco
#        psyco.full()
#except ImportError:
#        print 'Psyco not installed, the program will just run slower'
_term = None

LOG_PACKETS=False # If True all packets are looged to stdout
MINIMUM_COL_WIDTH = 12

class File(object):
  def __init__(self, file):
    self.is_dir      = file[1].is_dir
    self.is_readonly = file[1].is_readonly
    self.size        = file[1].file_size
    self.ctime       = file[1].ctime
    self.wtime       = file[1].wtime
    path = file[0]
    if path.endswith("/"): path = path[:-1]
    self.path = path
    self.name = path[path.rfind("/")+1:].rstrip()
    
  def __repr__(self):
    return self.path
    
  @apply
  def mode_string():
    doc=""" The mode string for this file. There are only two modes read-only and read-write """
    def fget(self):
      mode, x = "-", "-"      
      if self.is_dir: mode, x = "d", "x"
      if self.is_readonly: mode += "r-"+x+"r-"+x+"r-"+x
      else: mode += "rw"+x+"rw"+x+"rw"+x
      return mode
    return property(**locals())
    
  @apply
  def name_in_color():
    doc=""" The name in ANSI text. Directories are blue, ebooks are green """
    def fget(self):
      cname = self.name
      blue, green, normal = "", "", ""
      if _term: blue, green, normal = _term.BLUE, _term.GREEN, _term.NORMAL
      if self.is_dir: cname = blue + self.name + normal
      else:
        ext = self.name[self.name.rfind("."):]
        if ext in (".pdf", ".rtf", ".lrf", ".lrx", ".txt"): cname = green + self.name + normal        
      return cname
    return property(**locals())
    
  @apply
  def human_readable_size():
    doc=""" File size in human readable form """
    def fget(self):
      if self.size < 1024: divisor, suffix = 1, ""
      elif self.size < 1024*1024: divisor, suffix = 1024., "M"
      elif self.size < 1024*1024*1024: divisor, suffix = 1024*1024, "G"
      size = str(self.size/divisor)
      if size.find(".") > -1: size = size[:size.find(".")+2]
      return size + suffix
    return property(**locals())
    
  @apply
  def modification_time():
    doc=""" Last modified time in the Linux ls -l format """
    def fget(self):
      return time.strftime("%Y-%m-%d %H:%M", time.gmtime(self.wtime))
    return property(**locals())
    
  @apply
  def creation_time():
    doc=""" Last modified time in the Linux ls -l format """
    def fget(self):
      return time.strftime("%Y-%m-%d %H:%M", time.gmtime(self.ctime))
    return property(**locals())


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


    
  
class PRS500Device(object):
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
    
  @classmethod
  def _validate_response(cls, res, type=0x00, number=0x00):
    if type != res.type or number != res.rnumber:
      raise ProtocolError("Inavlid response.\ntype: expected="+hex(type)+" actual="+hex(res.type)+
                          "\nrnumber: expected="+hex(number)+" actual="+hex(res.rnumber))

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

  def _send_command(self, command, response_type=Response, timeout=100):
    """ 
    Send command to device and return its response. 
    
    command       -- an object of type Command or one of its derived classes
    response_type -- an object of type 'type'. The return packet from the device is returned as an object of type response_type. 
    timeout       -- the time to wait for a response from the device, in milliseconds
    """
    if LOG_PACKETS: print "Command\n%s\n--\n"%command
    bytes_sent = self.handle.controlMsg(0x40, 0x80, command)
    if bytes_sent != len(command):
      raise ControlError(desc="Could not send control request to device\n" + str(query.query))
    response = response_type(self.handle.controlMsg(0xc0, 0x81, Response.SIZE, timeout=timeout))
    if LOG_PACKETS: print "Response\n%s\n--\n"%response
    return response
    
  def _send_validated_command(self, command, cnumber=None, response_type=Response, timeout=100):
    """ Wrapper around _send_command that checks if the response's rnumber == cnumber or command.number if cnumber==None """
    if cnumber == None: cnumber = command.number
    res = self._send_command(command, response_type=response_type, timeout=timeout)
    PRS500Device._validate_response(res, type=command.type, number=cnumber)
    return res
    
  def _bulk_read(self, data_type=Answer, size=4096):
    data = data_type(self.handle.bulkRead(PRS500Device.PRS500_BULK_IN_EP, size))
    if LOG_PACKETS: print "Answer\n%s\n--\n"%data
    return data
    
  def _read_single_bulk_packet(self, command_number=0x00, data_type=Answer, size=4096):
    data = self._bulk_read(data_type=data_type, size=size)
    self._send_validated_command(AcknowledgeBulkRead(data.id), cnumber=command_number)
    return data    
    
  def _test_bulk_reads(self):
    self._send_validated_command( ShortCommand(number=0x00, type=0x01, command=0x00) )    
    self._read_single_bulk_packet(command_number=0x00, size=24)
      
  def _start_session(self):
    self.handle.reset()
    self._test_bulk_reads()
    self._send_validated_command( ShortCommand(number=0x0107, command=0x028000, type=0x01) ) # TODO: Figure out the meaning of this command
    self._test_bulk_reads()
    self._send_validated_command( ShortCommand(number=0x0106, type=0x01, command=0x312d) )   # TODO: Figure out the meaning of this command
    self._send_validated_command( ShortCommand(number=0x01, type=0x01, command=0x01) )
    
  def _end_session(self):
    self._send_validated_command( ShortCommand(number=0x01, type=0x01, command=0x00) )
  
  def _run_session(self, *args):
    self._start_session()
    res = None
    try:
      res = args[0](args[1:])
    finally:
      self._end_session()
      pass
    return res
    
  def _get_path_properties(self, path):
    res = self._send_validated_command(PathQuery(path), response_type=ListResponse)
    data = self._read_single_bulk_packet(size=0x28, data_type=PathAnswer, command_number=PathQuery.PROPERTIES)
    if res.path_not_found : raise PathError(path[:-1] + " does not exist on device")
    if res.is_invalid     : raise PathError(path[:-1] + " is not a valid path")
    if res.is_unmounted   : raise PathError(path[:-1] + " is not mounted")
    return (res, data)
     
  def _list(self, args):
    path = args[0]
    if not path.endswith("/"): path += "/" # Initially assume path is a directory
    files = []
    res, data = self._get_path_properties(path)
    if res.is_file: 
      path = path[:-1]
      res, data = self._get_path_properties(path)      
      files = [ (path, data) ]
    else:
      self._send_validated_command(PathQuery(path, number=PathQuery.ID), response_type=ListResponse)
      id = self._read_single_bulk_packet(size=0x14, data_type=IdAnswer, command_number=PathQuery.ID).id
      next = ShortCommand.list_command(id=id)
      cnumber = next.number
      items = []
      while True:
        res = self._send_validated_command(next, response_type=ListResponse)        
        size = res.data[2] + 16
        data = self._read_single_bulk_packet(size=size, data_type=ListAnswer, command_number=cnumber)
        # path_not_found seems to happen if the usb server doesn't have the permissions to access the directory
        if res.is_eol or res.path_not_found: break 
        items.append(data.name)      
      for item in items:
        ipath = path + item
        res, data = self._get_path_properties(ipath)
        files.append( (ipath, data) )
    files.sort()
    return files
  
  def list(self, path, recurse=False):
    files = self._run_session(self._list, path)    
    files = [ File(file) for file in files ]
    dirs = [(path, files)]
    for file in files:
      if recurse and file.is_dir and not file.path.startswith(("/dev","/proc")):
        dirs[len(dirs):] = self.list(file.path, recurse=True)
    return dirs
  
  def ls(self, path, recurse=False, color=False, human_readable_size=False, ll=False, cols=0):
    def col_split(l, cols): # split list l into columns 
      rows = len(l) / cols
      if len(l) % cols:
          rows += 1
      m = []
      for i in range(rows):
          m.append(l[i::rows])
      return m
    
    def row_widths(table): # Calculate widths for each column in the row-wise table      
      tcols = len(table[0])
      rowwidths = [ 0 for i in range(tcols) ]
      for row in table:
        c = 0
        for item in row:
          rowwidths[c] = len(item) if len(item) > rowwidths[c] else rowwidths[c]
          c += 1
      return rowwidths
    
    output = StringIO.StringIO()    
    if path.endswith("/"): path = path[:-1]
    dirs = self.list(path, recurse)
    for dir in dirs:
      if recurse: print >>output, dir[0] + ":" 
      lsoutput, lscoloutput = [], []
      files = dir[1]
      maxlen = 0
      if ll: # Calculate column width for size column
        for file in files:
          size = len(str(file.size))
          if human_readable_size: size = len(file.human_readable_size)
          if size > maxlen: maxlen = size
      for file in files:
        name = file.name
        lsoutput.append(name)
        if color: name = file.name_in_color
        lscoloutput.append(name)
        if ll:
          size = str(file.size)
          if human_readable_size: size = file.human_readable_size
          print >>output, file.mode_string, ("%"+str(maxlen)+"s")%size, file.modification_time, name
      if not ll and len(lsoutput) > 0:          
        trytable = []
        for colwidth in range(MINIMUM_COL_WIDTH, cols):
          trycols = int(cols/colwidth)
          trytable = col_split(lsoutput, trycols)    
          works = True
          for row in trytable:
            row_break = False
            for item in row:
              if len(item) > colwidth - 1: 
                works, row_break = False, True
                break
            if row_break: break
          if works: break
        rowwidths = row_widths(trytable)
        trytablecol = col_split(lscoloutput, len(trytable[0]))
        for r in range(len(trytable)):          
          for c in range(len(trytable[r])):
            padding = rowwidths[c] - len(trytable[r][c])
            print >>output, trytablecol[r][c], "".ljust(padding),
          print >>output    
      print >>output
    listing = output.getvalue().rstrip()+ "\n"    
    output.close()
    return listing



def main(argv):
  if _term : cols = _term.COLS
  else: cols = 70
  
  parser = OptionParser(usage="usage: %prog command [options] args\n\ncommand is one of: ls, get, put or rm\n\n"+
                              "For help on a particular command: %prog command")
  parser.add_option("--log-packets", help="print out packet stream to stdout", dest="log_packets", action="store_true", default=False)
  parser.remove_option("-h")
  parser.disable_interspersed_args() # Allow unrecognized options
  options, args = parser.parse_args()
  global LOG_PACKETS
  LOG_PACKETS = options.log_packets
  if len(args) < 1:
    parser.print_help()
    sys.exit(1)
  command = args[0]
  args = args[1:]
  dev = PRS500Device()
  if command == "ls":
    parser = OptionParser(usage="usage: %prog ls [options] path\n\npath must begin with /,a:/ or b:/")
    parser.add_option("--color", help="show ls output in color", dest="color", action="store_true", default=False)
    parser.add_option("-l", help="In addition to the name of each file, print the file type, permissions, and  timestamp  (the  modification time unless other times are selected)", dest="ll", action="store_true", default=False)
    parser.add_option("-R", help="Recursively list subdirectories encountered. /dev and /proc are omitted", dest="recurse", action="store_true", default=False)
    parser.remove_option("-h")
    parser.add_option("-h", "--human-readable", help="show sizes in human readable format", dest="hrs", action="store_true", default=False)
    options, args = parser.parse_args(args)
    if len(args) < 1:
      parser.print_help()
      sys.exit(1)
    dev.open()
    try: 
      print dev.ls(args[0], color=options.color, recurse=options.recurse, ll=options.ll, human_readable_size=options.hrs, cols=cols),
    except PathError, e: 
      print >> sys.stderr, e
      sys.exit(1)
    finally: 
      dev.close()
  else:
    parser.print_help()
    sys.exit(1)
  
if __name__ == "__main__":
  _term = TerminalController()
  main(sys.argv)
