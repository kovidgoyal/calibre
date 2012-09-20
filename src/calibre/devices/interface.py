__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
import os
from collections import namedtuple

from calibre.customize import Plugin
from calibre.constants import iswindows

class DevicePlugin(Plugin):
    """
    Defines the interface that should be implemented by backends that
    communicate with an ebook reader.
    """
    type = _('Device Interface')

    #: Ordered list of supported formats
    FORMATS     = ["lrf", "rtf", "pdf", "txt"]
    # If True, the config dialog will not show the formats box
    HIDE_FORMATS_CONFIG_BOX = False

    #: VENDOR_ID can be either an integer, a list of integers or a dictionary
    #: If it is a dictionary, it must be a dictionary of dictionaries,
    #: of the form::
    #:
    #:   {
    #:    integer_vendor_id : { product_id : [list of BCDs], ... },
    #:    ...
    #:   }
    #:
    VENDOR_ID   = 0x0000

    #: An integer or a list of integers
    PRODUCT_ID  = 0x0000
    #: BCD can be either None to not distinguish between devices based on BCD, or
    #: it can be a list of the BCD numbers of all devices supported by this driver.
    BCD         = None

    #: Height for thumbnails on the device
    THUMBNAIL_HEIGHT = 68
    #: Width for thumbnails on the device. Setting this will force thumbnails
    #: to this size, not preserving aspect ratio. If it is not set, then
    #: the aspect ratio will be preserved and the thumbnail will be no higher
    #: than THUMBNAIL_HEIGHT
    # THUMBNAIL_WIDTH = 68

    #: Set this to True if the device supports updating cover thumbnails during
    #: sync_booklists. Setting it to true will ask device.py to refresh the
    #: cover thumbnails during book matching
    WANTS_UPDATED_THUMBNAILS = False

    #: Whether the metadata on books can be set via the GUI.
    CAN_SET_METADATA = ['title', 'authors', 'collections']

    #: Whether the device can handle device_db metadata plugboards
    CAN_DO_DEVICE_DB_PLUGBOARD = False

    # Set this to None if the books on the device are files that the GUI can
    # access in order to add the books from the device to the library
    BACKLOADING_ERROR_MESSAGE = _('Cannot get files from this device')

    #: Path separator for paths to books on device
    path_sep = os.sep

    #: Icon for this device
    icon = I('reader.png')

    # Encapsulates an annotation fetched from the device
    UserAnnotation = namedtuple('Annotation','type, value')

    #: GUI displays this as a message if not None. Useful if opening can take a
    #: long time
    OPEN_FEEDBACK_MESSAGE = None

    #: Set of extensions that are "virtual books" on the device
    #: and therefore cannot be viewed/saved/added to library
    #: For example: ``frozenset(['kobo'])``
    VIRTUAL_BOOK_EXTENSIONS = frozenset([])

    #: Whether to nuke comments in the copy of the book sent to the device. If
    #: not None this should be short string that the comments will be replaced
    #: by.
    NUKE_COMMENTS = None

    #: If True indicates that  this driver completely manages device detection,
    #: ejecting and so forth. If you set this to True, you *must* implement the
    #: detect_managed_devices and debug_managed_device_detection methods.
    #: A driver with this set to true is responsible for detection of devices,
    #: managing a blacklist of devices, a list of ejected devices and so forth.
    #: calibre will periodically call the detect_managed_devices() method and
    #: is it returns a detected device, calibre will call open(). open() will
    #: be called every time a device is returned even is previous calls to open()
    #: failed, therefore the driver must maintain its own blacklist of failed
    #: devices. Similarly, when ejecting, calibre will call eject() and then
    #: assuming the next call to detect_managed_devices() returns None, it will
    #: call post_yank_cleanup().
    MANAGES_DEVICE_PRESENCE = False

    #: If set the True, calibre will call the :meth:`get_driveinfo()` method
    #: after the books lists have been loaded to get the driveinfo.
    SLOW_DRIVEINFO = False

    #: If set to True, calibre will ask the user if they want to manage the
    #: device with calibre, the first time it is detected. If you set this to
    #: True you must implement :meth:`get_device_uid()` and
    #: :meth:`ignore_connected_device()`.
    ASK_TO_ALLOW_CONNECT = False

    @classmethod
    def get_gui_name(cls):
        if hasattr(cls, 'gui_name'):
            return cls.gui_name
        if hasattr(cls, '__name__'):
            return cls.__name__
        return cls.name

    # Device detection {{{
    def test_bcd_windows(self, device_id, bcd):
        if bcd is None or len(bcd) == 0:
            return True
        for c in bcd:
            rev = 'rev_%4.4x'%c
            # Bug in winutil.get_usb_devices sometimes converts a to :
            if rev in device_id or rev.replace('a', ':') in device_id:
                return True
        return False

    def print_usb_device_info(self, info):
        try:
            print '\t', repr(info)
        except:
            import traceback
            traceback.print_exc()

    def is_usb_connected_windows(self, devices_on_system, debug=False,
            only_presence=False):

        def id_iterator():
            if hasattr(self.VENDOR_ID, 'keys'):
                for vid in self.VENDOR_ID:
                    vend = self.VENDOR_ID[vid]
                    for pid in vend:
                        bcd = vend[pid]
                        yield vid, pid, bcd
            else:
                vendors = self.VENDOR_ID if hasattr(self.VENDOR_ID, '__len__') else [self.VENDOR_ID]
                products = self.PRODUCT_ID if hasattr(self.PRODUCT_ID, '__len__') else [self.PRODUCT_ID]
                for vid in vendors:
                    for pid in products:
                        yield vid, pid, self.BCD

        for vendor_id, product_id, bcd in id_iterator():
            vid, pid = 'vid_%4.4x'%vendor_id, 'pid_%4.4x'%product_id
            vidd, pidd = 'vid_%i'%vendor_id, 'pid_%i'%product_id
            for device_id in devices_on_system:
                if (vid in device_id or vidd in device_id) and \
                   (pid in device_id or pidd in device_id) and \
                   self.test_bcd_windows(device_id, bcd):
                       if debug:
                           self.print_usb_device_info(device_id)
                       if only_presence or self.can_handle_windows(device_id, debug=debug):
                           try:
                               bcd = int(device_id.rpartition(
                                   'rev_')[-1].replace(':', 'a'), 16)
                           except:
                               bcd = None
                           return True, (vendor_id, product_id, bcd, None,
                                   None, None)
        return False, None

    def test_bcd(self, bcdDevice, bcd):
        if bcd is None or len(bcd) == 0:
            return True
        for c in bcd:
            if c == bcdDevice:
                return True
        return False

    def is_usb_connected(self, devices_on_system, debug=False,
            only_presence=False):
        '''
        Return True, device_info if a device handled by this plugin is currently connected.

        :param devices_on_system: List of devices currently connected

        '''
        if iswindows:
            return self.is_usb_connected_windows(devices_on_system,
                    debug=debug, only_presence=only_presence)

        vendors_on_system = set([x[0] for x in devices_on_system])
        vendors = self.VENDOR_ID if hasattr(self.VENDOR_ID, '__len__') else [self.VENDOR_ID]
        if hasattr(self.VENDOR_ID, 'keys'):
            products = []
            for ven in self.VENDOR_ID:
                products.extend(self.VENDOR_ID[ven].keys())
        else:
            products = self.PRODUCT_ID if hasattr(self.PRODUCT_ID, '__len__') else [self.PRODUCT_ID]

        for vid in vendors:
            if vid in vendors_on_system:
                for dev in devices_on_system:
                    cvid, pid, bcd = dev[:3]
                    if cvid == vid:
                        if pid in products:
                            if hasattr(self.VENDOR_ID, 'keys'):
                                try:
                                    cbcd = self.VENDOR_ID[vid][pid]
                                except KeyError:
                                    # Vendor vid does not have product pid, pid
                                    # exists for some other vendor in this
                                    # device
                                    continue
                            else:
                                cbcd = self.BCD
                            if self.test_bcd(bcd, cbcd):
                                if debug:
                                    self.print_usb_device_info(dev)
                                if self.can_handle(dev, debug=debug):
                                    return True, dev
        return False, None

    def detect_managed_devices(self, devices_on_system, force_refresh=False):
        '''
        Called only if MANAGES_DEVICE_PRESENCE is True.

        Scan for devices that this driver can handle. Should return a device
        object if a device is found. This object will be passed to the open()
        method as the connected_device. If no device is found, return None. The
        returned object can be anything, calibre does not use it, it is only
        passed to open().

        This method is called periodically by the GUI, so make sure it is not
        too resource intensive. Use a cache to avoid repeatedly scanning the
        system.

        :param devices_on_system: Set of USB devices found on the system.

        :param force_refresh: If True and the driver uses a cache to prevent
                              repeated scanning, the cache must be flushed.

        '''
        raise NotImplementedError()

    def debug_managed_device_detection(self, devices_on_system, output):
        '''
        Called only if MANAGES_DEVICE_PRESENCE is True.

        Should write information about the devices detected on the system to
        output, which is a file like object.

        Should return True if a device was detected and successfully opened,
        otherwise False.
        '''
        raise NotImplementedError()

    # }}}

    def reset(self, key='-1', log_packets=False, report_progress=None,
            detected_device=None):
        """
        :param key: The key to unlock the device
        :param log_packets: If true the packet stream to/from the device is logged
        :param report_progress: Function that is called with a % progress
                                (number between 0 and 100) for various tasks
                                If it is called with -1 that means that the
                                task does not have any progress information
        :param detected_device: Device information from the device scanner

        """
        raise NotImplementedError()

    def can_handle_windows(self, device_id, debug=False):
        '''
        Optional method to perform further checks on a device to see if this driver
        is capable of handling it. If it is not it should return False. This method
        is only called after the vendor, product ids and the bcd have matched, so
        it can do some relatively time intensive checks. The default implementation
        returns True. This method is called only on windows. See also
        :meth:`can_handle`.

        :param device_info: On windows a device ID string. On Unix a tuple of
                            ``(vendor_id, product_id, bcd)``.

        '''
        return True

    def can_handle(self, device_info, debug=False):
        '''
        Unix version of :meth:`can_handle_windows`

        :param device_info: Is a tuple of (vid, pid, bcd, manufacturer, product,
                            serial number)

        '''

        return True

    def open(self, connected_device, library_uuid):
        '''
        Perform any device specific initialization. Called after the device is
        detected but before any other functions that communicate with the device.
        For example: For devices that present themselves as USB Mass storage
        devices, this method would be responsible for mounting the device or
        if the device has been automounted, for finding out where it has been
        mounted. The method :meth:`calibre.devices.usbms.device.Device.open` has
        an implementation of
        this function that should serve as a good example for USB Mass storage
        devices.

        This method can raise an OpenFeedback exception to display a message to
        the user.

        :param connected_device: The device that we are trying to open. It is
            a tuple of (vendor id, product id, bcd, manufacturer name, product
            name, device serial number). However, some devices have no serial
            number and on windows only the first three fields are present, the
            rest are None.

        :param library_uuid: The UUID of the current calibre library. Can be
            None if there is no library (for example when used from the command
            line).

        '''
        raise NotImplementedError()

    def eject(self):
        '''
        Un-mount / eject the device from the OS. This does not check if there
        are pending GUI jobs that need to communicate with the device.

        NOTE: That this method may not be called on the same thread as the rest
        of the device methods.
        '''
        raise NotImplementedError()

    def post_yank_cleanup(self):
        '''
        Called if the user yanks the device without ejecting it first.
        '''
        raise NotImplementedError()

    def set_progress_reporter(self, report_progress):
        '''
        Set a function to report progress information.

        :param report_progress: Function that is called with a % progress
                                (number between 0 and 100) for various tasks
                                If it is called with -1 that means that the
                                task does not have any progress information

        '''
        raise NotImplementedError()

    def get_device_information(self, end_session=True):
        """
        Ask device for device information. See L{DeviceInfoQuery}.

        :return: (device name, device version, software version on device, mime type)
                 The tuple can optionally have a fifth element, which is a
                 drive information dictionary. See usbms.driver for an example.

        """
        raise NotImplementedError()

    def get_driveinfo(self):
        '''
        Return the driveinfo dictionary. Usually called from
        get_device_information(), but if loading the driveinfo is slow for this
        driver, then it should set SLOW_DRIVEINFO. In this case, this method
        will be called by calibre after the book lists have been loaded. Note
        that it is not called on the device thread, so the driver should cache
        the drive info in the books() method and this function should return
        the cached data.
        '''
        return {}

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

        :return: A 3 element list with total space in bytes of (1, 2, 3). If a
                 particular device doesn't have any of these locations it should return 0.

        """
        raise NotImplementedError()

    def free_space(self, end_session=True):
        """
        Get free space available on the mountpoints:
          1. Main memory
          2. Card A
          3. Card B

        :return: A 3 element list with free space in bytes of (1, 2, 3). If a
                 particular device doesn't have any of these locations it should return -1.

        """
        raise NotImplementedError()

    def books(self, oncard=None, end_session=True):
        """
        Return a list of ebooks on the device.

        :param oncard:  If 'carda' or 'cardb' return a list of ebooks on the
                        specific storage card, otherwise return list of ebooks
                        in main memory of device. If a card is specified and no
                        books are on the card return empty list.

        :return: A BookList.

        """
        raise NotImplementedError()

    def upload_books(self, files, names, on_card=None, end_session=True,
                     metadata=None):
        '''
        Upload a list of books to the device. If a file already
        exists on the device, it should be replaced.
        This method should raise a :class:`FreeSpaceError` if there is not enough
        free space on the device. The text of the FreeSpaceError must contain the
        word "card" if ``on_card`` is not None otherwise it must contain the word "memory".

        :param files: A list of paths
        :param names: A list of file names that the books should have
                      once uploaded to the device. len(names) == len(files)
        :param metadata: If not None, it is a list of :class:`Metadata` objects.
                         The idea is to use the metadata to determine where on the device to
                         put the book. len(metadata) == len(files). Apart from the regular
                         cover (path to cover), there may also be a thumbnail attribute, which should
                         be used in preference. The thumbnail attribute is of the form
                         (width, height, cover_data as jpeg).

        :return: A list of 3-element tuples. The list is meant to be passed
                 to :meth:`add_books_to_metadata`.
        '''
        raise NotImplementedError()

    @classmethod
    def add_books_to_metadata(cls, locations, metadata, booklists):
        '''
        Add locations to the booklists. This function must not communicate with
        the device.

        :param locations: Result of a call to L{upload_books}
        :param metadata: List of :class:`Metadata` objects, same as for
                         :meth:`upload_books`.
        :param booklists: A tuple containing the result of calls to
                          (:meth:`books(oncard=None)`,
                          :meth:`books(oncard='carda')`,
                          :meth`books(oncard='cardb')`).

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

        :param paths: paths to books on the device.
        :param booklists: A tuple containing the result of calls to
                          (:meth:`books(oncard=None)`,
                          :meth:`books(oncard='carda')`,
                          :meth`books(oncard='cardb')`).

        '''
        raise NotImplementedError()

    def sync_booklists(self, booklists, end_session=True):
        '''
        Update metadata on device.

        :param booklists: A tuple containing the result of calls to
                          (:meth:`books(oncard=None)`,
                          :meth:`books(oncard='carda')`,
                          :meth`books(oncard='cardb')`).

        '''
        raise NotImplementedError()

    def get_file(self, path, outfile, end_session=True):
        '''
        Read the file at ``path`` on the device and write it to outfile.

        :param outfile: file object like ``sys.stdout`` or the result of an
                       :func:`open` call.

        '''
        raise NotImplementedError()

    @classmethod
    def config_widget(cls):
        '''
        Should return a QWidget. The QWidget contains the settings for the
        device interface
        '''
        raise NotImplementedError()

    @classmethod
    def save_settings(cls, settings_widget):
        '''
        Should save settings to disk. Takes the widget created in
        :meth:`config_widget` and saves all settings to disk.
        '''
        raise NotImplementedError()

    @classmethod
    def settings(cls):
        '''
        Should return an opts object. The opts object should have at least one
        attribute `format_map` which is an ordered list of formats for the
        device.
        '''
        raise NotImplementedError()

    def set_plugboards(self, plugboards, pb_func):
        '''
        provide the driver the current set of plugboards and a function to
        select a specific plugboard. This method is called immediately before
        add_books and sync_booklists.

        pb_func is a callable with the following signature::
            def pb_func(device_name, format, plugboards)

        You give it the current device name (either the class name or
        DEVICE_PLUGBOARD_NAME), the format you are interested in (a 'real'
        format or 'device_db'), and the plugboards (you were given those by
        set_plugboards, the same place you got this method).

        :return: None or a single plugboard instance.

        '''
        pass

    def set_driveinfo_name(self, location_code, name):
        '''
        Set the device name in the driveinfo file to 'name'. This setting will
        persist until the file is re-created or the name is changed again.

        Non-disk devices should implement this method based on the location
        codes returned by the get_device_information() method.
        '''
        pass

    def prepare_addable_books(self, paths):
        '''
        Given a list of paths, returns another list of paths. These paths
        point to addable versions of the books.

        If there is an error preparing a book, then instead of a path, the
        position in the returned list for that book should be a three tuple:
        (original_path, the exception instance, traceback)
        '''
        return paths

    def startup(self):
        '''
        Called when calibre is is starting the device. Do any initialization
        required. Note that multiple instances of the class can be instantiated,
        and thus __init__ can be called multiple times, but only one instance
        will have this method called. This method is called on the device
        thread, not the GUI thread.
        '''
        pass

    def shutdown(self):
        '''
        Called when calibre is shutting down, either for good or in preparation
        to restart. Do any cleanup required. This method is called on the
        device thread, not the GUI thread.
        '''
        pass

    def get_device_uid(self):
        '''
        Must return a unique id for the currently connected device (this is
        called immediately after a successful call to open()). You must
        implement this method if you set ASK_TO_ALLOW_CONNECT = True
        '''
        raise NotImplementedError()

    def ignore_connected_device(self, uid):
        '''
        Should ignore the device identified by uid (the result of a call to
        get_device_uid()) in the future. You must implement this method if you
        set ASK_TO_ALLOW_CONNECT = True. Note that this function is called
        immediately after open(), so if open() caches some state, the driver
        should reset that state.
        '''
        raise NotImplementedError()

    # Dynamic control interface.
    # The following methods are probably called on the GUI thread. Any driver
    # that implements these methods must take pains to be thread safe, because
    # the device_manager might be using the driver at the same time that one of
    # these methods is called.

    def is_dynamically_controllable(self):
        '''
        Called by the device manager when starting plugins. If this method returns
        a string, then a) it supports the device manager's dynamic control
        interface, and b) that name is to be used when talking to the plugin.

        This method can be called on the GUI thread. A driver that implements
        this method must be thread safe.
        '''
        return None

    def start_plugin(self):
        '''
        This method is called to start the plugin. The plugin should begin
        to accept device connections however it does that. If the plugin is
        already accepting connections, then do nothing.

        This method can be called on the GUI thread. A driver that implements
        this method must be thread safe.
        '''
        pass

    def stop_plugin(self):
        '''
        This method is called to stop the plugin. The plugin should no longer
        accept connections, and should cleanup behind itself. It is likely that
        this method should call shutdown. If the plugin is already not accepting
        connections, then do nothing.

        This method can be called on the GUI thread. A driver that implements
        this method must be thread safe.
        '''
        pass

    def get_option(self, opt_string, default=None):
        '''
        Return the value of the option indicated by opt_string. This method can
        be called when the plugin is not started. Return None if the option does
        not exist.

        This method can be called on the GUI thread. A driver that implements
        this method must be thread safe.
        '''
        return default

    def set_option(self, opt_string, opt_value):
        '''
        Set the value of the option indicated by opt_string. This method can
        be called when the plugin is not started.

        This method can be called on the GUI thread. A driver that implements
        this method must be thread safe.
        '''
        pass

    def is_running(self):
        '''
        Return True if the plugin is started, otherwise false

        This method can be called on the GUI thread. A driver that implements
        this method must be thread safe.
        '''
        return False

class BookList(list):
    '''
    A list of books. Each Book object must have the fields

      #. title
      #. authors
      #. size (file size of the book)
      #. datetime (a UTC time tuple)
      #. path (path on the device to the book)
      #. thumbnail (can be None) thumbnail is either a str/bytes object with the
         image data or it should have an attribute image_path that stores an
         absolute (platform native) path to the image
      #. tags (a list of strings, can be empty).

    '''

    __getslice__ = None
    __setslice__ = None

    def __init__(self, oncard, prefix, settings):
        pass

    def supports_collections(self):
        ''' Return True if the device supports collections for this book list. '''
        raise NotImplementedError()

    def add_book(self, book, replace_metadata):
        '''
        Add the book to the booklist. Intent is to maintain any device-internal
        metadata. Return True if booklists must be sync'ed
        '''
        raise NotImplementedError()

    def remove_book(self, book):
        '''
        Remove a book from the booklist. Correct any device metadata at the
        same time
        '''
        raise NotImplementedError()

    def get_collections(self, collection_attributes):
        '''
        Return a dictionary of collections created from collection_attributes.
        Each entry in the dictionary is of the form collection name:[list of
        books]

        The list of books is sorted by book title, except for collections
        created from series, in which case series_index is used.

        :param collection_attributes: A list of attributes of the Book object

        '''
        raise NotImplementedError()

