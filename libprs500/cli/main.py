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
Provides a command-line and optional graphical interface to the SONY Reader PRS-500.

For usage information run the script. 
"""

import StringIO, sys, time, os
from optparse import OptionParser

from libprs500 import __version__ as VERSION
from libprs500.communicate import PRS500Device
from terminfo import TerminalController
from libprs500.errors import ArgumentError, DeviceError


MINIMUM_COL_WIDTH = 12 #: Minimum width of columns in ls output

def human_readable(size):
  """ Convert a size in bytes into a human readle form """
  if size < 1024: divisor, suffix = 1, ""
  elif size < 1024*1024: divisor, suffix = 1024., "K"
  elif size < 1024*1024*1024: divisor, suffix = 1024*1024, "M"
  elif size < 1024*1024*1024*1024: divisor, suffix = 1024*1024, "G"
  size = str(size/divisor)
  if size.find(".") > -1: size = size[:size.find(".")+2]
  return size + suffix

class FileFormatter(object):
  def __init__(self, file, term):    
    self.term = term
    self.is_dir      = file.is_dir
    self.is_readonly = file.is_readonly
    self.size        = file.size
    self.ctime       = file.ctime
    self.wtime       = file.wtime
    self.name        = file.name
    self.path        = file.path
    
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
      if self.term: blue, green, normal = self.term.BLUE, self.term.GREEN, self.term.NORMAL
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
      human_readable(self.size)
    return property(**locals())
    
  @apply
  def modification_time():
    doc=""" Last modified time in the Linux ls -l format """
    def fget(self):
      return time.strftime("%Y-%m-%d %H:%M", time.localtime(self.wtime))
    return property(**locals())
    
  @apply
  def creation_time():
    doc=""" Last modified time in the Linux ls -l format """
    def fget(self):
      return time.strftime("%Y-%m-%d %H:%M", time.localtime(self.ctime))
    return property(**locals())

def info(dev):
  info = dev.get_device_information()
  print "Device name:     ", info[0]
  print "Device version:  ", info[1]
  print "Software version:", info[2]
  print "Mime type:       ", info[3]

def ls(dev, path, term, recurse=False, color=False, human_readable_size=False, ll=False, cols=0):
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
  dirs = dev.list(path, recurse)
  for dir in dirs:
    if recurse: print >>output, dir[0] + ":" 
    lsoutput, lscoloutput = [], []
    files = dir[1]
    maxlen = 0
    if ll: # Calculate column width for size column
      for file in files:
        size = len(str(file.size))
        if human_readable_size: 
          file = FileFormatter(file, term)
          size = len(file.human_readable_size)
        if size > maxlen: maxlen = size
    for file in files:
      file = FileFormatter(file, term)
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

def main():
  term = TerminalController()
  cols = term.COLS
  
  parser = OptionParser(usage="usage: %prog [options] command args\n\ncommand is one of: info, books, df, ls, cp, mkdir, touch, cat, rm\n\n"+
                              "For help on a particular command: %prog command", version="libprs500 version: " + VERSION)
  parser.add_option("--log-packets", help="print out packet stream to stdout. "+\
                    "The numbers in the left column are byte offsets that allow the packet size to be read off easily.", 
                    dest="log_packets", action="store_true", default=False)
  parser.remove_option("-h")
  parser.disable_interspersed_args() # Allow unrecognized options
  options, args = parser.parse_args()

  if len(args) < 1:
    parser.print_help()
    return 1
  
  command = args[0]
  args = args[1:]
  dev = PRS500Device(log_packets=options.log_packets)
  try:
    if command == "df":
      data = dev.available_space()
      print "Filesystem\tSize \tUsed \tAvail \tUse%"
      for datum in data:
        total, free, used, percent = human_readable(datum[2]), human_readable(datum[1]), human_readable(datum[2]-datum[1]), \
                                     str(0 if datum[2]==0 else int(100*(datum[2]-datum[1])/(datum[2]*1.)))+"%"
        print "%-10s\t%s\t%s\t%s\t%s"%(datum[0], total, used, free, percent)
    elif command == "books":
      print "Books in main memory:"
      for book in dev.books(): print book
      print "\nBooks on storage card:"
      for book in dev.books(oncard=True): print book      
    elif command == "mkdir":
      parser = OptionParser(usage="usage: %prog mkdir [options] path\nCreate a directory on the device\n\npath must begin with /,a:/ or b:/")
      if len(args) != 1:
        parser.print_help()
        sys.exit(1)
      dev.mkdir(args[0])
    elif command == "ls":
      parser = OptionParser(usage="usage: %prog ls [options] path\nList files on the device\n\npath must begin with /,a:/ or b:/")
      parser.add_option("--color", help="show ls output in color", dest="color", action="store_true", default=False)
      parser.add_option("-l", help="In addition to the name of each file, print the file type, permissions, and  timestamp  (the  modification time unless other times are selected). Times are local.", dest="ll", action="store_true", default=False)
      parser.add_option("-R", help="Recursively list subdirectories encountered. /dev and /proc are omitted", dest="recurse", action="store_true", default=False)
      parser.remove_option("-h")
      parser.add_option("-h", "--human-readable", help="show sizes in human readable format", dest="hrs", action="store_true", default=False)
      options, args = parser.parse_args(args)
      if len(args) != 1:
        parser.print_help()
        return 1
      print ls(dev, args[0], term, color=options.color, recurse=options.recurse, ll=options.ll, human_readable_size=options.hrs, cols=cols),      
    elif command == "info":
      info(dev)
    elif command == "cp":
      usage="usage: %prog cp [options] source destination\nCopy files to/from the device\n\n"+\
            "One of source or destination must be a path on the device. \n\nDevice paths have the form\n"+\
            "prs500:mountpoint/my/path\n"+\
            "where mountpoint is one of /, a: or b:\n\n"+\
            "source must point to a file for which you have read permissions\n"+\
            "destination must point to a file or directory for which you have write permissions"
      parser = OptionParser(usage=usage)
      options, args = parser.parse_args(args)
      if len(args) != 2: 
        parser.print_help()
        return 1
      if args[0].startswith("prs500:"):
        outfile = args[1]
        path = args[0][7:]
        if path.endswith("/"): path = path[:-1]      
        if os.path.isdir(outfile):
          outfile = os.path.join(outfile, path[path.rfind("/")+1:]) 
        try:
          outfile = open(outfile, "w")
        except IOError, e:
          print >> sys.stderr, e
          parser.print_help()
          return 1
        dev.get_file(path, outfile)        
        outfile.close()
      elif args[1].startswith("prs500:"):
        try:
          infile = open(args[0], "r")
        except IOError, e:
          print >> sys.stderr, e
          parser.print_help()
          return 1
        dev.put_file(infile, args[1][7:])
        infile.close()
      else:
        parser.print_help()
        return 1
    elif command == "cat":
      outfile = sys.stdout
      parser = OptionParser(usage="usage: %prog cat path\nShow file on the device\n\npath should point to a file on the device and must begin with /,a:/ or b:/")
      options, args = parser.parse_args(args)
      if len(args) != 1: 
        parser.print_help()
        return 1
      if args[0].endswith("/"): path = args[0][:-1]
      else: path = args[0]
      outfile = sys.stdout
      dev.get_file(path, outfile)
    elif command == "rm":
      parser = OptionParser(usage="usage: %prog rm path\nDelete files from the device\n\npath should point to a file or empty directory on the device "+\
                                  "and must begin with /,a:/ or b:/\n\n"+\
                                  "rm will DELETE the file. Be very CAREFUL")
      options, args = parser.parse_args(args)
      if len(args) != 1: 
        parser.print_help()
        return 1
      dev.rm(args[0])      
    elif command == "touch":
      parser = OptionParser(usage="usage: %prog touch path\nCreate an empty file on the device\n\npath should point to a file on the device and must begin with /,a:/ or b:/\n\n"+
      "Unfortunately, I cant figure out how to update file times on the device, so if path already exists, touch does nothing" )
      options, args = parser.parse_args(args)
      if len(args) != 1: 
        parser.print_help()
        return 1
      dev.touch(args[0])
    else:
      parser.print_help()
      if dev.handle: dev.close()
      return 1
  except (ArgumentError, DeviceError), e:
     print >>sys.stderr, e
     return 1
  return 0
