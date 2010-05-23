'''
    Device driver for iTunes

    GRiker

    22 May 2010
'''
import datetime

from calibre.constants import isosx, iswindows
from calibre.devices.interface import DevicePlugin
#from calibre.ebooks.metadata import MetaInformation
from calibre.utils.config import Config

if isosx:
    print "running in OSX"
    import appscript

if iswindows:
    print "running in Windows"
    import win32com.client

class ITUNES(DevicePlugin):
    name = 'Apple device interface'
    gui_name = 'Apple device'
    icon = I('devices/iPad.png')
    description    = _('Communicate with iBooks through iTunes.')
    supported_platforms = ['windows','osx']
    author = 'GRiker'

    FORMATS = ['epub']

    VENDOR_ID = [0x05ac]
    # 0x129a:iPad  0x1292:iPhone 3G
    PRODUCT_ID = [0x129a,0x1292]
    BCD = [0x01]

    app = None
    is_connected = False


    # Public methods

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

    def books(self, oncard=None, end_session=True):
        """
        Return a list of ebooks on the device.
        @param oncard:  If 'carda' or 'cardb' return a list of ebooks on the
                        specific storage card, otherwise return list of ebooks
                        in main memory of device. If a card is specified and no
                        books are on the card return empty list.
        @return: A BookList.
        """
        print "ITUNES:books(oncard=%s)" % oncard
        if not oncard:
            myBooks = BookList()
            book = Book()

            myBooks.add_book(book, False)
            print "len(myBooks): %d" % len(myBooks)
            return myBooks
        else:
            return []

    def can_handle(self, device_info, debug=False):
        '''
        Unix version of :method:`can_handle_windows`

        :param device_info: Is a tupe of (vid, pid, bcd, manufacturer, product,
        serial number)
        '''
        print "ITUNES:can_handle()"
        return True

    def can_handle_windows(self, device_id, debug=False):
        '''
        Optional method to perform further checks on a device to see if this driver
        is capable of handling it. If it is not it should return False. This method
        is only called after the vendor, product ids and the bcd have matched, so
        it can do some relatively time intensive checks. The default implementation
        returns True. This method is called only on windows. See also
        :method:`can_handle`.

        :param device_info: On windows a device ID string. On Unix a tuple of
        ``(vendor_id, product_id, bcd)``.
        '''
        print "ITUNES:can_handle_windows()"
        return True

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
        print "ITUNES:card_prefix()"
        return (None,None)

    def config_widget(cls):
        '''
        Should return a QWidget. The QWidget contains the settings for the device interface
        '''
        raise NotImplementedError()

    def delete_books(self, paths, end_session=True):
        '''
        Delete books at paths on device.
        '''
        raise NotImplementedError()

    def eject(self):
        '''
        Un-mount / eject the device from the OS. This does not check if there
        are pending GUI jobs that need to communicate with the device.
        '''
        print "ITUNES:eject()"

    def free_space(self, end_session=True):
        """
        Get free space available on the mountpoints:
          1. Main memory
          2. Card A
          3. Card B

        @return: A 3 element list with free space in bytes of (1, 2, 3). If a
        particular device doesn't have any of these locations it should return -1.
        """
        print "ITUNES:free_space()"
        return (0,-1,-1)

    def get_device_information(self, end_session=True):
        """
        Ask device for device information. See L{DeviceInfoQuery}.
        @return: (device name, device version, software version on device, mime type)
        """
        print "ITUNES:get_device_information()"
        return ('iPad','hw v1.0','sw v1.0', 'mime type')

    def get_file(self, path, outfile, end_session=True):
        '''
        Read the file at C{path} on the device and write it to outfile.
        @param outfile: file object like C{sys.stdout} or the result of an C{open} call
        '''
        raise NotImplementedError()

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
        print "ITUNES.open()"
        if isosx:
            # Launch iTunes if not already running
            running_apps = appscript.app('System Events')
            if not 'iTunes' in running_apps.processes.name():
                print " launching iTunes"
                app = appscript.app('iTunes', hide=True)
                app.run()
                self.app = app
                # May need to set focus back to calibre here?

    def post_yank_cleanup(self):
        '''
        Called if the user yanks the device without ejecting it first.
        '''
        raise NotImplementedError()

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
        print "ITUNE.reset()"

    def save_settings(cls, settings_widget):
        '''
        Should save settings to disk. Takes the widget created in config_widget
        and saves all settings to disk.
        '''
        raise NotImplementedError()

    def set_progress_reporter(self, report_progress):
        '''
        @param report_progress: Function that is called with a % progress
                                (number between 0 and 100) for various tasks
                                If it is called with -1 that means that the
                                task does not have any progress information
        '''
        print "ITUNES:set_progress_reporter()"

    def settings(cls):
        '''
        Should return an opts object. The opts object should have one attribute
        `format_map` which is an ordered list of formats for the device.
        '''
        print "ITUNES.settings()"
        klass = cls if isinstance(cls, type) else cls.__class__
        c = Config('device_drivers_%s' % klass.__name__, _('settings for device drivers'))
        c.add_opt('format_map', default=cls.FORMATS,
            help=_('Ordered list of formats the device will accept'))
        return c.parse()

    def sync_booklists(self, booklists, end_session=True):
        '''
        Update metadata on device.
        @param booklists: A tuple containing the result of calls to
                                (L{books}(oncard=None), L{books}(oncard='carda'),
                                L{books}(oncard='cardb')).
        '''
        print "ITUNES:sync_booklists():"

    def total_space(self, end_session=True):
        """
        Get total space available on the mountpoints:
            1. Main memory
            2. Memory Card A
            3. Memory Card B

        @return: A 3 element list with total space in bytes of (1, 2, 3). If a
        particular device doesn't have any of these locations it should return 0.
        """
        print "ITUNES:total_space()"

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
        cover (path to cover), there may also be a thumbnail attribute, which should
        be used in preference. The thumbnail attribute is of the form
        (width, height, cover_data as jpeg).
        '''
        raise NotImplementedError()

    # Private methods

    def _get_source(self):
        '''
        Get iTunes sources (Library, iPod, Radio ...)
        '''
        sources = self._app.sources()
        names = [s.name() for s in sources]
        kinds = [s.kind() for s in sources]
        return dict(zip(kinds,names))

class BookList(list):
    '''
    A list of books. Each Book object must have the fields:
      1. title
      2. authors
      3. size (file size of the book)
      4. datetime (a UTC time tuple)
      5. path (path on the device to the book)
      6. thumbnail (can be None) thumbnail is either a str/bytes object with the
         image data or it should have an attribute image_path that stores an
         absolute (platform native) path to the image
      7. tags (a list of strings, can be empty).
    '''

    __getslice__ = None
    __setslice__ = None

    def __init__(self):
        pass

    def supports_collections(self):
        ''' Return True if the the device supports collections for this book list. '''
        return False

    def add_book(self, book, replace_metadata):
        '''
        Add the book to the booklist. Intent is to maintain any device-internal
        metadata. Return True if booklists must be sync'ed
        '''
        print "adding %s" % book
        self.append(book)

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
        return {}

class Book(object):
    '''
    A simple class describing a book in the iTunes Books Library.
    These seem to be the minimum Book attributes needed.
    '''
    def __init__(self):
        setattr(self,'title','A Book Title')
        setattr(self,'authors',['John Doe'])
        setattr(self,'path','some/path.epub')
        setattr(self,'size',1234567)
        setattr(self,'datetime',datetime.datetime.now().timetuple())
        setattr(self,'thumbnail',None)
        setattr(self,'db_id',0)
        setattr(self,'device_collections',[])
        setattr(self,'tags',['Genre'])


