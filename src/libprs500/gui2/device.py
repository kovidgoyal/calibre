##    Copyright (C) 2007 Kovid Goyal kovid@kovidgoyal.net
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
##    51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.Warning
from PyQt4.QtCore import QThread, SIGNAL

from libprs500.devices.prs500.driver import PRS500

class DeviceDetector(QThread):
    def __init__(self, sleep_time=2000):
        '''        
        @param sleep_time: Time to sleep between device probes in millisecs
        @type sleep_time: integer
        '''
        self.devices    = ([PRS500, False],)
        self.sleep_time = sleep_time
        QThread.__init__(self)
        
    def run(self):
        while True:
            for device in self.devices:
                connected = device[0].is_connected()
                if connected and not device[1]:
                    self.emit(SIGNAL('connected(PyQt_PyObject, PyQt_PyObject)'), device[0], True)
                    device[1] ^= True
                elif not connected and device[1]:
                    self.emit(SIGNAL('connected(PyQt_PyObject, PyQt_PyObject)'), device[0], False)
                    device[1] ^= True
            self.msleep(self.sleep_time)