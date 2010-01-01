__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
"""
Define the minimum interface that a device backend must satisfy to be used in
the GUI. A device backend must subclass the L{Device} class. See prs500.py for
a backend that implement the Device interface for the SONY PRS500 Reader.
"""
import os

from calibre.customize import Plugin
from calibre.constants import iswindows

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
    #: VENDOR_ID can be either an integer, a list of integers or a dictionary
    #: If it is a dictionary, it must be a dictionary of dictionaries, of the form
    #: {
    #:  integer_vendor_id : { product_id : [list of BCDs], ... },
    #:  ...
    #: }
    VENDOR_ID   = 0x0000
    #: An integer or a list of integers
    PRODUCT_ID  = 0x0000
    # BCD can be either None to not distinguish between devices based on BCD, or
    # it can be a list of the BCD numbers of all devices supported by this driver.
    BCD         = None
    THUMBNAIL_HEIGHT = 68 # Height for thumbnails on device
    # Whether the metadata on books can be set via the GUI.
    CAN_SET_METADATA = True
    #: Path separator for paths to books on device
    path_sep = os.sep
    #: Icon for this device
    icon = I('reader.svg')

    @classmethod
    def test_bcd_windows(cls, device_id, bcd):
        if bcd is None or len(bcd) == 0:
            return True
        for c in bcd:
            # Bug in winutil.get_usb_devices converts a to :
            rev = ('rev_%4.4x'%c).replace('a', ':')
            if rev in device_id:
                return True
        return False

    @classmethod
    def print_usb_device_info(cls, info):
        try:
            print '\t', repr(info)
        except:
            import traceback
            traceback.print_exc()

    @classmethod
    def is_usb_connected_windows(cls, devices_on_system, debug=False):

        def id_iterator():
            if hasattr(cls.VENDOR_ID, 'keys'):
                for vid in cls.VENDOR_ID:
                    vend = cls.VENDOR_ID[vid]
                    for pid in vend:
                        bcd = vend[pid]
                        yield vid, pid, bcd
            else:
                vendors = cls.VENDOR_ID if hasattr(cls.VENDOR_ID, '__len__') else [cls.VENDOR_ID]
                products = cls.PRODUCT_ID if hasattr(cls.PRODUCT_ID, '__len__') else [cls.PRODUCT_ID]
                for vid in vendors:
                    for pid in products:
                        yield vid, pid, cls.BCD

        for vendor_id, product_id, bcd in id_iterator():
            vid, pid = 'vid_%4.4x'%vendor_id, 'pid_%4.4x'%product_id
            vidd, pidd = 'vid_%i'%vendor_id, 'pid_%i'%product_id
            for device_id in devices_on_system:
                if (vid in device_id or vidd in device_id) and \
                   (pid in device_id or pidd in device_id) and \
                   cls.test_bcd_windows(device_id, bcd):
                       if debug:
                           cls.print_usb_device_info(device_id)
                       if cls.can_handle(device_id):
                           return True
        return False

    @classmethod
    def test_bcd(cls, bcdDevice, bcd):
        if bcd is None or len(bcd) == 0:
            return True
        for c in bcd:
            if c == bcdDevice:
                return True
        return False

    @classmethod
    def is_usb_connected(cls, devices_on_system, debug=False):
        '''
        Return True, device_info if a device handled by this plugin is currently connected.

        :param devices_on_system: List of devices currently connected
        '''
        if iswindows:
            return cls.is_usb_connected_windows(devices_on_system, debug=debug), None

        vendors_on_system = set([x[0] for x in devices_on_system])
        vendors = cls.VENDOR_ID if hasattr(cls.VENDOR_ID, '__len__') else [cls.VENDOR_ID]
        if hasattr(cls.VENDOR_ID, 'keys'):
            products = []
            for ven in cls.VENDOR_ID:
                products.extend(cls.VENDOR_ID[ven].keys())
        else:
            products = cls.PRODUCT_ID if hasattr(cls.PRODUCT_ID, '__len__') else [cls.PRODUCT_ID]

        for vid in vendors:
            if vid in vendors_on_system:
                for dev in devices_on_system:
                    cvid, pid, bcd = dev[:3]
                    if cvid == vid:
                        if pid in products:
                            if hasattr(cls.VENDOR_ID, 'keys'):
                                cbcd = cls.VENDOR_ID[vid][pid]
                            else:
                                cbcd = cls.BCD
                            if cls.test_bcd(bcd, cbcd):
                                if debug:
                                    cls.print_usb_device_info(dev)
                                if cls.can_handle(dev, debug=debug):
                                    return True, dev
        return False, None


    def reset(self, key='-1', log_packets=False, report_progress=None,
            detected_device=None) :
        """
        :key: The key to unlock the device
        :log_packets: If true the packet stream to/from the device is logged
        :report_progress: Function that is called with a % progress
                                (number between 0 and 100) for various tasks
                                If it is called with -1 that means that the
                                task does not have any progress information
        :detected_device: Device information from the device scanner
        """
        raise NotImplementedError()

    @classmethod
    def get_fdi(cls):
        '''Return the FDI description of this device for HAL on linux.'''
        return ''

    @classmethod
    def can_handle(cls, device_info, debug=False):
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
        :files: A list of paths and/or file-like objects.
        :names: A list of file names that the books should have
        once uploaded to the device. len(names) == len(files)
        :return: A list of 3-element tuples. The list is meant to be passed
        to L{add_books_to_metadata}.
        :metadata: If not None, it is a list of :class:`MetaInformation` objects.
        The idea is to use the metadata to determine where on the device to
        put the book. len(metadata) == len(files). Apart from the regular
        cover_data, there may also be a thumbnail attribute, which should
        be used in preference. The thumbnail attribute is of the form
        (width, height, cover_data as jpeg). In addition the MetaInformation
        objects can have a tag_order attribute.
        '''
        raise NotImplementedError()

    @classmethod
    def add_books_to_metadata(cls, locations, metadata, booklists):
        '''
        Add locations to the booklists. This function must not communicate with
        the device.
        @param locations: Result of a call to L{upload_books}
        @param metadata: List of MetaInformation objects, same as for
        :method:`upload_books`.
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

