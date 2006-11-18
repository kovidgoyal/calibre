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
from main_gui import Ui_MainWindow
from libprs500.communicate import PRS500Device as device
from libprs500.errors import *
from PyQt4.Qt import QThread


class DeviceDetector(QThread):
  def __init__(self, detected_slot):
    QThread.__init__(self)
    self.dev = None
    self.detected_slot = detected_slot
    self.removed = False
    
  def run(self):
    wait = 1
    while None == self.msleep(wait):
      wait = 1000
      if self.removed or not self.dev:        
        self.dev = device()
        self.removed = False
        self.detected_slot()
      
    

class MainWindow(Ui_MainWindow):
  
  def safe(func):
    def call_func(*args, **kwargs):
      window = args[0]
      res = None
      try:
        res = func(*args, **kwargs)
      except DeviceError:
        window.device_removed()
      except TimeoutError, e:
        print e
        window.timeout_error()
      return res
    return call_func
  
  @apply
  def dev():
    def fget(self):
      return self.detector.dev
    return property(**locals())
  
  def __init__(self, window, log_packets):
    Ui_MainWindow.__init__(self)
    self.log_packets = log_packets
    self.detector = DeviceDetector(self.establish_connection)
    self.detector.start()
    self.setupUi(window)
    window.show()
    
  def device_removed(self, timeout=False):
    """ @todo: implement this """
    self.detector.removed = True
  
  def timeout_error(self):
    """ @todo: update status bar """
    self.detector.sleep(10)
    self.device_removed(timeout=True)
  
  @safe
  def establish_connection(self):
    mb, cb, mx, cx = self.dev.books()
    self.main_books = mb
    self.card_books = cb
    self.main_xml = mx
    self.cache_xml = cx
    print self.main_books + self.card_books
    
    
    
