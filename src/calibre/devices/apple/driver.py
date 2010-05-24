'''
    Device driver for iTunes

    GRiker

    22 May 2010
'''
import datetime, re, sys

from calibre.constants import isosx, iswindows
from calibre.devices.interface import DevicePlugin
from calibre.ebooks.metadata import MetaInformation
from calibre.utils.config import Config
from calibre.utils.date import parse_date

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
    # Product IDs:
    #  0x129a:iPad
    #  0x1292:iPhone 3G
    PRODUCT_ID = [0x129a,0x1292]
    BCD = [0x01]

    # Properties
    cached_paths = {}
    iTunes= None
    sources = None
    verbose = True


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
            # Fetch a list of books from iPod device connected to iTunes
            if isosx:
                '''
                print "self.sources: %s" % self.sources
                print "self.sources['library']: %s" % self.sources['library']
                lib = self.iTunes.sources['library']

                if 'Books' in lib.playlists.name():
                    booklist = BookList()
                    it_books = lib.playlists['Books'].file_tracks()
                    for it_book in it_books:
                        this_book = Book(it_book.name(), it_book.artist())
                        this_book.datetime = parse_date(str(it_book.date_added())).timetuple()
                        this_book.db_id = None
                        this_book.device_collections = []
                        this_book.path = 'iTunes/Books/%s.epub' % it_book.name()
                        this_book.size = it_book.size()
                        this_book.thumbnail = None
                        booklist.add_book(this_book, False)
                    return booklist

                else:
                    return []
                '''
                if 'iPod' in self.sources:
                    device = self.sources['iPod']
                    if 'Books' in self.iTunes.sources[device].playlists.name():
                        booklist = BookList()
                        cached_paths = {}
                        books = self.iTunes.sources[device].playlists['Books'].file_tracks()
                        for book in books:
                            this_book = Book(book.name(), book.artist())
                            this_book.datetime = parse_date(str(book.date_added())).timetuple()
                            this_book.db_id = None
                            this_book.device_collections = []
                            this_book.path = 'iTunes/%s - %s.epub' % (book.name(), book.artist())
                            this_book.size = book.size()
                            this_book.thumbnail = None
                            booklist.add_book(this_book, False)
                            cached_paths[this_book.path] = { 'title':book.name(),
                                                            'author':book.artist(),
                                                              'book':book}
                        self.cached_paths = cached_paths
                        print self.cached_paths
                        return booklist
                    else:
                        # No books installed on this device
                        return []

        else:
            return []

    def can_handle(self, device_info, debug=False):
        '''
        Unix version of :method:`can_handle_windows`

        :param device_info: Is a tupe of (vid, pid, bcd, manufacturer, product,
        serial number)

        Confirm that:
            - iTunes is running
            - there is an iPod-type device connected
        This gets called first when the device fingerprint is read, so it needs to
        instantate iTunes if necessary
        This gets called ~1x/second while device fingerprint is sensed
        '''
        # print "ITUNES:can_handle()"
        if isosx:
            # Launch iTunes if not already running
            if not self.iTunes:
                if self.verbose:
                    print "ITUNES:can_handle(): Instantiating iTunes"
                running_apps = appscript.app('System Events')
                if not 'iTunes' in running_apps.processes.name():
                    if self.verbose:
                        print "ITUNES:can_handle(): Launching iTunes"
                    self.iTunes = iTunes= appscript.app('iTunes', hide=True)
                    iTunes.run()
                    if self.verbose:
                        print "%s - %s (launched)" % (self.iTunes.name(), self.iTunes.version())
                else:
                    self.iTunes = appscript.app('iTunes')
                    if self.verbose:
                        print " %s - %s (already running)" % (self.iTunes.name(), self.iTunes.version())

            # Check for connected book-capable device
            names = [s.name() for s in self.iTunes.sources()]
            kinds = [str(s.kind()).rpartition('.')[2] for s in self.iTunes.sources()]
            self.sources = sources = dict(zip(kinds,names))
            if 'iPod' in sources:
                if self.verbose:
                    sys.stdout.write('.')
                    sys.stdout.flush()
                return True
            else:
                if self.verbose:
                    print "ITUNES.can_handle(): device not connected"
                    self.iTunes = None
                    self.sources = None
                return False

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
        Since we're deleting through iTunes, we'll use the cached handle to the book
        '''
        for path in paths:
            title = self.cached_paths[path]['title']
            author = self.cached_paths[path]['author']
            book = self.cached_paths[path]['book']
            print "ITUNES.delete_books(): Searching for '%s - %s'" % (title,author)
            if True:
                results = self.iTunes.playlists['library'].file_tracks[
                    (appscript.its.name == title).AND
                    (appscript.its.artist == author).AND
                    (appscript.its.kind == 'Book')].get()
                if len(results) == 1:
                    book_to_delete = results[0]
                    print "book_to_delete: %s" % book_to_delete
                    if self.verbose:
                        print "ITUNES:delete_books(): Deleting '%s - %s'" % (title, author)
                    self.iTunes.delete(results[0])
                elif len(results) > 1:
                    print "ITUNES.delete_books(): More than one book matches '%s - %s'" % (title, author)
                else:
                    print "ITUNES.delete_books(): No book '%s - %s' found in iTunes" % (title, author)
            else:
                if self.verbose:
                    print "ITUNES:delete_books(): Deleting '%s - %s'" % (title, author)
                self.iTunes.delete(book)


    def eject(self):
        '''
        Un-mount / eject the device from the OS. This does not check if there
        are pending GUI jobs that need to communicate with the device.
        '''
        if self.verbose:
            print "ITUNES:eject(): ejecting '%s'" % self.sources['iPod']
        self.iTunes.eject(self.sources['iPod'])
        self.iTunes = None
        self.sources = None

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

        free_space = 0
        if isosx:
            if 'iPod' in self.sources:
                connected_device = self.sources['iPod']
                free_space = self.iTunes.sources[connected_device].free_space()

        return (free_space,-1,-1)

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
        print "ITUNES.remove_books_from_metadata(): need to implement"

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

class Book(MetaInformation):
    '''
    A simple class describing a book in the iTunes Books Library.
    Q's:
    - Should thumbnail come from calibre if available?
    - See ebooks.metadata.__init__ for all fields
    '''
    def __init__(self,title,author):

        MetaInformation.__init__(self, title, authors=[author])

    @dynamic_property
    def title_sorter(self):
        doc = '''String to sort the title. If absent, title is returned'''
        def fget(self):
            return re.sub('^\s*A\s+|^\s*The\s+|^\s*An\s+', '', self.title).rstrip()
        return property(doc=doc, fget=fget)
