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
Define the minimum interface that a device backend must satisfy to be used in
the GUI. A device backend must subclass the L{Device} class. See prs500.py for
a backend that implement the Device interface for the SONY PRS500 Reader.
"""


class Device(object):
    """ 
    Defines the interface that should be implemented by backends that 
    communicate with an ebook reader. 
    
    The C{end_session} variables are used for USB session management. Sometimes
    the front-end needs to call several methods one after another, in which case 
    the USB session should not be closed after each method call.
    """
    # Ordered list of supported formats
    FORMATS     = ["lrf", "rtf", "pdf", "txt"]
    VENDOR_ID   = 0x0000
    PRODUCT_ID  = 0x0000 
    
    def __init__(self, key='-1', log_packets=False, report_progress=None) :
        """ 
        @param key: The key to unlock the device
        @param log_packets: If true the packet stream to/from the device is logged 
        @param report_progress: Function that is called with a % progress 
                                (number between 0 and 100) for various tasks
                                If it is called with -1 that means that the 
                                task does not have any progress information
        """
        raise NotImplementedError()
    
    @classmethod
    def is_connected(cls):
        '''Return True iff the device is physically connected to the computer'''
        raise NotImplementedError()
    
    def set_progress_reporter(self, report_progress):
        '''
        @param report_progress: Function that is called with a % progress 
                                (number between 0 and 100) for various tasks
                                If it is called with -1 that means that the 
                                task does not have any progress information
        '''
        raise NotImplementedError()
    
    def get_device_information(self, end_session=True):
        """ 
        Ask device for device information. See L{DeviceInfoQuery}. 
        @return: (device name, device version, software version on device, mime type)
        """
        raise NotImplementedError()
    
    def card_prefix(self, end_session=True):
        '''
        Return prefix to paths on the card or None if no cards present.
        '''
        raise NotImplementedError()
    
    def total_space(self, end_session=True):
        """ 
        Get total space available on the mountpoints:
          1. Main memory
          2. Memory Stick
          3. SD Card

        @return: A 3 element list with total space in bytes of (1, 2, 3). If a
        particular device doesn't have any of these locations it should return 0.
        """
        raise NotImplementedError()
    
    def free_space(self, end_session=True):
        """ 
        Get free space available on the mountpoints:
          1. Main memory
          2. Card A
          3. Card B

        @return: A 3 element list with free space in bytes of (1, 2, 3). If a
        particular device doesn't have any of these locations it should return -1.
        """    
        raise NotImplementedError()
    
    def books(self, oncard=False, end_session=True):
        """ 
        Return a list of ebooks on the device.
        @param oncard: If True return a list of ebooks on the storage card, 
                       otherwise return list of ebooks in main memory of device.
                       If True and no books on card return empty list. 
        @return: A list of Books. Each Book object must have the fields:
        title, authors, size, datetime (a UTC time tuple), path, thumbnail (can be None).
        """    
        raise NotImplementedError()
    
    def add_book(self, infile, name, info, booklists, oncard=False, \
                            sync_booklists=False, end_session=True):
        """
        Add a book to the device. If oncard is True then the book is copied 
        to the card rather than main memory. 

        @param infile: The source file, should be opened in "rb" mode
        @param name: The name of the book file when uploaded to the 
                                device. The extension of name must be one of 
                                the supported formats for this device.
        @param info: A dictionary that must have the keys "title", "authors", "cover". 
                     C{info["cover"]} should be a three element tuple (width, height, data)
                     where data is the image data in JPEG format as a string
        @param booklists: A tuple containing the result of calls to 
                                (L{books}(oncard=False), L{books}(oncard=True)).    
        """
        raise NotImplementedError()
    
    def remove_book(self, paths, booklists, end_session=True):
        """
        Remove the books specified by C{paths} from the device. The metadata
        cache on the device must also be updated.
        @param booklists: A tuple containing the result of calls to 
                                (L{books}(oncard=False), L{books}(oncard=True)).    
        """
        raise NotImplementedError()
    
    def sync_booklists(self, booklists, end_session=True):
        '''
        Update metadata on device.
        @param booklists: A tuple containing the result of calls to 
                                (L{books}(oncard=False), L{books}(oncard=True)).
        '''
        raise NotImplementedError()

