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
from PyQt4.QtCore import QThread, SIGNAL, QObject

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
            
        
        
class DeviceManager(QObject):
    def __init__(self, device_class):
        QObject.__init__(self)
        self.device_class = device_class
        self.device = device_class()
        
    def device_removed(self):
        self.device = None
        
    def info_func(self):
        ''' Return callable that returns device information and free space on device'''
        def get_device_information(updater):
            '''Get device information'''
            self.device.set_progress_reporter(updater)
            info = self.device.get_device_information(end_session=False)
            info = [i.replace('\x00', '').replace('\x01', '') for i in info]
            cp = self.device.card_prefix(end_session=False)
            fs = self.device.free_space()
            return info, cp, fs
        return get_device_information
    
    def books_func(self):
        '''Return callable that returns the list of books on device as two booklists'''
        def books(updater):
            '''Get metadata from device'''
            self.device.set_progress_reporter(updater)
            mainlist = self.device.books(oncard=False, end_session=False)
            cardlist = self.device.books(oncard=True)
            return (mainlist, cardlist)
        return books
    
    def sync_booklists_func(self):
        '''Upload booklists to device'''
        def sync_booklists(updater, booklists):
            '''Sync metadata to device'''
            self.device.set_progress_reporter(updater)
            self.device.sync_booklists(booklists, end_session=False)
            return self.device.card_prefix(end_session=False), self.device.free_space()
        return sync_booklists
    
    def upload_books_func(self):
        '''Upload books to device'''
        def upload_books(updater, files, names, on_card=False):
            '''Upload books to device: '''
            return self.device.upload_books(files, names, on_card, end_session=False)
        return upload_books
    
    def add_books_to_metadata(self, locations, metadata, booklists):
        self.device_class.add_books_to_metadata(locations, metadata, booklists)
    
    def delete_books_func(self):
        '''Remove books from device'''
        def delete_books(updater, paths):
            '''Delete books from device'''
            self.device.delete_books(paths, end_session=True)
        return delete_books
    
    def remove_books_from_metadata(self, paths, booklists):
        self.device_class.remove_books_from_metadata(paths, booklists)