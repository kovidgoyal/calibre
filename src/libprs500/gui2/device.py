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
import traceback

from PyQt4.QtCore import QThread, SIGNAL, QObject, Qt

from libprs500.devices.prs500.driver import PRS500

class DeviceDetector(QThread):
    '''
    Worker thread that polls the USB ports for devices. Emits the
    signal connected(PyQt_PyObject, PyQt_PyObject) on connection and
    disconnection events.
    '''
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
            
class DeviceJob(QThread):
    '''
    Worker thread that communicates with device.
    '''
    def __init__(self, id, mutex, func, *args, **kwargs):
        QThread.__init__(self)
        self.id = id
        self.func = func
        self.args = args
        self.kwargs = kwargs
        self.mutex = mutex
        self.result = None
        
    def run(self):
        if self.mutex != None:
            self.mutex.lock()
        last_traceback, exception = None, None
        try:            
            try:
                self.result = self.func(self.progress_update, *self.args, **self.kwargs)
            except Exception, err:
                exception = err
                last_traceback = traceback.format_exc()            
        finally:
            if self.mutex != None:
                self.mutex.unlock()
            self.emit(SIGNAL('jobdone(PyQt_PyObject, PyQt_PyObject, PyQt_PyObject, PyQt_PyObject)'), 
                      self.id, self.result, exception, last_traceback)
            
    def progress_update(self, val):
        print val
        self.emit(SIGNAL('status_update(int)'), int(val), Qt.QueuedConnection)
        
        
class DeviceManager(QObject):
    def __init__(self, device_class):
        QObject.__init__(self)
        self.device_class = device_class
        self.device = device_class()
        
    def get_info_func(self):
        ''' Return callable that returns device information and free space on device'''
        def get_device_information(updater):
            self.device.set_updater(updater)
            info = self.device.get_device_information(end_session=False)
            info = {'name':info[0], 'version':info[1], 'swversion':[2], 'mimetype':info[3]}
            cp = self.device.card_prefix(end_session=False)
            fs = self.device.free_space()
            fs = {'main':fs[0], 'carda':fs[1], 'cardb':fs[2]}
            return info, cp, fs
        return get_device_information
    
    def books_func(self):
        '''Return callable that returns the list of books on device as two booklists'''
        def books(updater):
            self.device.set_updater(updater)
            mainlist = self.device.books(oncard=False, end_session=False)
            cardlist = self.device.books(oncard=True)
            return mainlist, cardlist
        return books