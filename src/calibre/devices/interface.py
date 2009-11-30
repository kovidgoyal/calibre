__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
"""
Define the minimum interface that a device backend must satisfy to be used in
the GUI. A device backend must subclass the L{Device} class. See prs500.py for
a backend that implement the Device interface for the SONY PRS500 Reader.
"""
import os

from calibre.customize import Plugin

class DevicePlugin(Plugin):
    """
    Defines the interface that should be implemented by backends that
    communicate with an ebook reader.

    The C{end_session} variables are used for USB session management. Sometimes
    the front-end needs to call several methods one after another, in which case
    the USB session should not be closed after each method call.
    """
    type = _('Device Interface')

    # Ordered list of supported formats
    FORMATS     = ["lrf", "rtf", "pdf", "txt"]
    VENDOR_ID   = 0x0000
    PRODUCT_ID  = 0x0000
    # BCD can be either None to not distinguish between devices based on BCD, or
    # it can be a list of the BCD numbers of all devices supported by this driver.
    BCD         = None
    THUMBNAIL_HEIGHT = 68 # Height for thumbnails on device
    # Whether the metadata on books can be set via the GUI.
    CAN_SET_METADATA = True
    #: Path separator for paths to books on device
    path_sep = os.sep


    def reset(self, key='-1', log_packets=False, report_progress=None) :
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
    def get_fdi(cls):
        '''Return the FDI description of this device for HAL on linux.'''
        return ''

    @classmethod
    def can_handle(cls, device_info):
        '''
        Optional method to perform further checks on a device to see if this driver
        is capable of handling it. If it is not it should return False. This method
        is only called after the vendor, product ids and the bcd have matched, so
        it can do some relatively time intensive checks. The default implementation
        returns True.

        :param device_info: On windows a device ID string. On Unix a tuple of
        ``(vendor_id, product_id, bcd)``.
        '''
        return True

    def open(self):
        '''
        Perform any device specific initialization. Called after the device is
        detected but before any other functions that communicate with the device.
        For example: For devices that present themselves as USB Mass storage
        devices, this method would be responsible for mounting the device or
        if the device has been automounted, for finding out where it has been
        mounted. The base class within USBMS device.py has a implementation of
        this function that should serve as a good example for USB Mass storage
        devices.
        '''
        raise NotImplementedError()

    def eject(self):
        '''
        Un-mount / eject the device from the OS. This does not check if there
        are pending GUI jobs that need to communicate with the device.
        '''
        raise NotImplementedError()

    def post_yank_cleanup(self):
        '''
        Called if the user yanks the device without ejecting it first.
        '''
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
        Return a 2 element list of the prefix to paths on the cards.
        If no card is present None is set for the card's prefix.
        E.G.
        ('/place', '/place2')
        (None, 'place2')
        ('place', None)
        (None, None)
        '''
        raise NotImplementedError()

    def total_space(self, end_session=True):
        """
        Get total space available on the mountpoints:
            1. Main memory
            2. Memory Card A
            3. Memory Card B

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

    def books(self, oncard=None, end_session=True):
        """
        Return a list of ebooks on the device.
        @param oncard:  If 'carda' or 'cardb' return a list of ebooks on the
                        specific storage card, otherwise return list of ebooks
                        in main memory of device. If a card is specified and no
                        books are on the card return empty list.
        @return: A BookList.
        """
        raise NotImplementedError()

    def upload_books(self, files, names, on_card=None, end_session=True,
                     metadata=None):
        '''
        Upload a list of books to the device. If a file already
        exists on the device, it should be replaced.
        This method should raise a L{FreeSpaceError} if there is not enough
        free space on the device. The text of the FreeSpaceError must contain the
        word "card" if C{on_card} is not None otherwise it must contain the word "memory".
        @param files: A list of paths and/or file-like objects.
        @param names: A list of file names that the books should have
        once uploaded to the device. len(names) == len(files)
        @return: A list of 3-element tuples. The list is meant to be passed
        to L{add_books_to_metadata}.
        @param metadata: If not None, it is a list of dictionaries. Each dictionary
        will have at least the key tags to allow the driver to choose book location
        based on tags. len(metadata) == len(files). If your device does not support
        hierarchical ebook folders, you can safely ignore this parameter.
        '''
        raise NotImplementedError()

    @classmethod
    def add_books_to_metadata(cls, locations, metadata, booklists):
        '''
        Add locations to the booklists. This function must not communicate with
        the device.
        @param locations: Result of a call to L{upload_books}
        @param metadata: List of dictionaries. Each dictionary must have the
        keys C{title}, C{authors}, C{author_sort}, C{cover}, C{tags}.
        The value of the C{cover}
        element can be None or a three element tuple (width, height, data)
        where data is the image data in JPEG format as a string. C{tags} must be
        a possibly empty list of strings. C{authors} must be a string.
        C{author_sort} may be None. It is upto the driver to decide whether to
        use C{author_sort} or not.
        The dictionary can also have an optional key "tag order" which should be
        another dictionary that maps tag names to lists of book ids. The ids are
        ids from the book database.
        @param booklists: A tuple containing the result of calls to
                                (L{books}(oncard=None), L{books}(oncard='carda'),
                                L{books}(oncard='cardb')).
        '''
        raise NotImplementedError

    def delete_books(self, paths, end_session=True):
        '''
        Delete books at paths on device.
        '''
        raise NotImplementedError()

    @classmethod
    def remove_books_from_metadata(cls, paths, booklists):
        '''
        Remove books from the metadata list. This function must not communicate
        with the device.
        @param paths: paths to books on the device.
        @param booklists:  A tuple containing the result of calls to
                                (L{books}(oncard=None), L{books}(oncard='carda'),
                                L{books}(oncard='cardb')).
        '''
        raise NotImplementedError()

    def sync_booklists(self, booklists, end_session=True):
        '''
        Update metadata on device.
        @param booklists: A tuple containing the result of calls to
                                (L{books}(oncard=None), L{books}(oncard='carda'),
                                L{books}(oncard='cardb')).
        '''
        raise NotImplementedError()

    def get_file(self, path, outfile, end_session=True):
        '''
        Read the file at C{path} on the device and write it to outfile.
        @param outfile: file object like C{sys.stdout} or the result of an C{open} call
        '''
        raise NotImplementedError()

    @classmethod
    def config_widget(cls):
        '''
        Should return a QWidget. The QWidget contains the settings for the device interface
        '''
        raise NotImplementedError()

    @classmethod
    def save_settings(cls, settings_widget):
        '''
        Should save settings to disk. Takes the widget created in config_widget
        and saves all settings to disk.
        '''
        raise NotImplementedError()

    @classmethod
    def settings(cls):
        '''
        Should return an opts object. The opts object should have one attribute
        `format_map` which is an ordered list of formats for the device.
        '''
        raise NotImplementedError()




class BookList(list):
    '''
    A list of books. Each Book object must have the fields:
      1. title
      2. authors
      3. size (file size of the book)
      4. datetime (a UTC time tuple)
      5. path (path on the device to the book)
      6. thumbnail (can be None)
      7. tags (a list of strings, can be empty).
    '''

    __getslice__ = None
    __setslice__ = None

    def supports_tags(self):
        ''' Return True if the the device supports tags (collections) for this book list. '''
        raise NotImplementedError()

    def set_tags(self, book, tags):
        '''
        Set the tags for C{book} to C{tags}.
        @param tags: A list of strings. Can be empty.
        @param book: A book object that is in this BookList.
        '''
        raise NotImplementedError()

