# -*- coding: utf-8 -*-

__license__   = 'GPL v3'
__copyright__ = '2010, Gregory Riker'
__docformat__ = 'restructuredtext en'


import cStringIO, os, re, shutil, sys, tempfile, time, zipfile

from calibre.constants import DEBUG
from calibre import fit_image
from calibre.constants import isosx, iswindows
from calibre.devices.interface import DevicePlugin
from calibre.ebooks.metadata import MetaInformation
from calibre.library.server.utils import strftime
from calibre.ptempfile import PersistentTemporaryFile
from calibre.utils.config import Config, config_dir
from calibre.utils.date import parse_date
from calibre.utils.logging import Log
from calibre.devices.errors import UserFeedback

from PIL import Image as PILImage

if isosx:
    try:
        import appscript
        appscript
    except:
        # appscript fails to load on 10.4
        appscript = None

if iswindows:
    import pythoncom, win32com.client
    Sources = [
                'Unknown',
                'Library',
                'iPod',
                'AudioCD',
                'MP3CD',
                'Device',
                'RadioTuner',
                'SharedLibrary']

    ArtworkFormat = [
                'Unknown',
                'JPEG',
                'PNG',
                'BMP'
                ]

class ITUNES(DevicePlugin):
    '''
            try:
                pythoncom.CoInitialize()
            finally:
                pythoncom.CoUninitialize()
    '''

    name = 'Apple device interface'
    gui_name = 'Apple device'
    icon = I('devices/ipad.png')
    description    = _('Communicate with iBooks through iTunes.')
    supported_platforms = ['osx','windows']
    author = 'GRiker'
    #: The version of this plugin as a 3-tuple (major, minor, revision)
    version        = (1, 0, 0)

    OPEN_FEEDBACK_MESSAGE = _(
        'Apple device detected, launching iTunes, please wait ...')

    FORMATS = ['epub']

    # Product IDs:
    #  0x1292:iPhone 3G
    #  0x129a:iPad
    VENDOR_ID = [0x05ac]
    PRODUCT_ID = [0x129a]
    BCD = [0x01]

    # Properties
    cached_books = {}
    cache_dir = os.path.join(config_dir, 'caches', 'itunes')
    ejected = False
    iTunes= None
    log = Log()
    path_template = 'iTunes/%s - %s.epub'
    problem_titles = []
    problem_msg = None
    report_progress = None
    update_list = []
    sources = None
    update_msg = None
    update_needed = False

    # Public methods
    def add_books_to_metadata(self, locations, metadata, booklists):
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

        task_count = float(len(self.update_list))

        # Delete any obsolete copies of the book from the booklist
        if self.update_list:
            if isosx:
                if DEBUG:
                    self.log.info( "ITUNES.add_books_to_metadata()")
                    self._dump_update_list('add_books_to_metadata()')
                for (j,p_book) in enumerate(self.update_list):
                    self.log.info("ITUNES.add_books_to_metadata(): looking for %s" %
                        str(p_book['lib_book'])[-9:])
                    for i,bl_book in enumerate(booklists[0]):
                        if bl_book.library_id == p_book['lib_book']:
                            booklists[0].pop(i)
                            self.log.info("ITUNES.add_books_to_metadata(): removing %s %s" %
                                (p_book['title'], str(p_book['lib_book'])[-9:]))
                            break
                    else:
                        self.log.error(" update_list item '%s' by %s %s not found in booklists[0]" %
                            (p_book['title'], p_book['author'],str(p_book['lib_book'])[-9:]))

                    if self.report_progress is not None:
                        self.report_progress(j+1/task_count, _('Updating device metadata listing...'))

            elif iswindows:
                if DEBUG:
                    self.log.info("ITUNES.add_books_to_metadata()")
                for (j,p_book) in enumerate(self.update_list):
                    #self.log.info(" looking for '%s' by %s" % (p_book['title'],p_book['author']))
                    for i,bl_book in enumerate(booklists[0]):
                        #self.log.info(" evaluating '%s' by %s" % (bl_book.title,bl_book.author[0]))
                        if bl_book.title == p_book['title'] and \
                           bl_book.author[0] == p_book['author']:
                            booklists[0].pop(i)
                            self.log.info(" removing outdated version of '%s'" % p_book['title'])
                            break
                    else:
                        self.log.error(" update_list item '%s' not found in booklists[0]" % p_book['title'])

                    if self.report_progress is not None:
                        self.report_progress(j+1/task_count, _('Updating device metadata listing...'))

            if self.report_progress is not None:
                self.report_progress(1.0, _('Updating device metadata listing...'))

        # Add new books to booklists[0]
        for new_book in locations[0]:
            if DEBUG:
                self.log.info(" adding '%s' by '%s' to booklists[0]" %
                    (new_book.title, new_book.author))
            booklists[0].append(new_book)
        if DEBUG:
            self._dump_booklist(booklists[0],'after add_books_to_metadata()')

    def books(self, oncard=None, end_session=True):
        """
        Return a list of ebooks on the device.
        @param oncard:  If 'carda' or 'cardb' return a list of ebooks on the
                        specific storage card, otherwise return list of ebooks
                        in main memory of device. If a card is specified and no
                        books are on the card return empty list.
        @return: A BookList.

        Implementation notes:
        iTunes does not sync purchased books, they are only on the device.  They are visible, but
        they are not backed up to iTunes.  Since calibre can't manage them, don't show them in the
        list of device books.

        """
        if not oncard:
            if DEBUG:
                self.log.info("ITUNES:books(oncard=%s)" % oncard)

            # Fetch a list of books from iPod device connected to iTunes

            # Fetch Library|Books
            library_books = self._get_library_books()

            if 'iPod' in self.sources:
                #device = self.sources['iPod']
                booklist = BookList(self.log)
                cached_books = {}

                if isosx:
                    device_books = self._get_device_books()
                    book_count = float(len(device_books))
                    for (i,book) in enumerate(device_books):
                        this_book = Book(book.name(), book.artist())
                        this_book.path = self.path_template % (book.name(), book.artist())
                        this_book.datetime = parse_date(str(book.date_added())).timetuple()
                        this_book.db_id = None
                        this_book.device_collections = []
                        this_book.library_id = library_books[this_book.path] if this_book.path in library_books else None
                        this_book.size = book.size()
                        # Hack to discover if we're running in GUI environment
                        if self.report_progress is not None:
                            this_book.thumbnail = self._generate_thumbnail(this_book.path, book)
                        else:
                            this_book.thumbnail = None
                        booklist.add_book(this_book, False)

                        cached_books[this_book.path] = {
                         'title':book.name(),
                         'author':[book.artist()],
                         'lib_book':library_books[this_book.path] if this_book.path in library_books else None
                         }

                        if self.report_progress is not None:
                            self.report_progress(i+1/book_count, _('%d of %d') % (i+1, book_count))

                elif iswindows:
                    try:
                        pythoncom.CoInitialize()
                        self.iTunes = win32com.client.Dispatch("iTunes.Application")
                        device_books = self._get_device_books()
                        book_count = float(len(device_books))
                        for (i,book) in enumerate(device_books):
                            this_book = Book(book.Name, book.Artist)
                            this_book.path = self.path_template % (book.Name, book.Artist)
                            this_book.datetime = parse_date(str(book.DateAdded)).timetuple()
                            this_book.db_id = None
                            this_book.device_collections = []
                            this_book.library_id = library_books[this_book.path] if this_book.path in library_books else None
                            this_book.size = book.Size
                            # Hack to discover if we're running in GUI environment
                            if self.report_progress is not None:
                                this_book.thumbnail = self._generate_thumbnail(this_book.path, book)
                            else:
                                this_book.thumbnail = None
                            booklist.add_book(this_book, False)

                            cached_books[this_book.path] = {
                             'title':book.Name,
                             'author':book.Artist,
                             'lib_book':library_books[this_book.path] if this_book.path in library_books else None
                             }

                            if self.report_progress is not None:
                                self.report_progress(i+1/book_count,
                                        _('%d of %d') % (i+1, book_count))

                    finally:
                        pythoncom.CoUninitialize()

                if self.report_progress is not None:
                    self.report_progress(1.0, _('finished'))
                self.cached_books = cached_books
                if DEBUG:
                    self._dump_booklist(booklist, 'returning from books():')
                    self._dump_cached_books('returning from books():')
                return booklist
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
        instantiate iTunes if necessary
        This gets called ~1x/second while device fingerprint is sensed
        '''
        if appscript is None:
            return False

        if self.iTunes:
            # Check for connected book-capable device
            self.sources = self._get_sources()
            if 'iPod' in self.sources:
                #if DEBUG:
                    #sys.stdout.write('.')
                    #sys.stdout.flush()
                return True
            else:
                if DEBUG:
                    sys.stdout.write('-')
                    sys.stdout.flush()
                return False
        else:
            # Called at entry
            # We need to know if iTunes sees the iPad
            # It may have been ejected
            if DEBUG:
                self.log.info("ITUNES.can_handle()")

            self._launch_iTunes()
            self.sources = self._get_sources()
            if (not 'iPod' in self.sources) or (self.sources['iPod'] == ''):
                attempts = 9
                while attempts:
                    # If iTunes was just launched, device may not be detected yet
                    self.sources = self._get_sources()
                    if (not 'iPod' in self.sources) or (self.sources['iPod'] == ''):
                        attempts -= 1
                        time.sleep(0.5)
                        if DEBUG:
                            self.log.warning(" waiting for identified iPad, attempt #%d" % (10 - attempts))
                    else:
                        if DEBUG:
                            self.log.info(' found connected iPad in iTunes')
                        break
                else:
                    # iTunes running, but not connected iPad
                    if DEBUG:
                        self.log.info(' self.ejected = True')
                    self.ejected = True
                    return False
            else:
                self.log.info(' found connected iPad in sources')

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

        iPad implementation notes:
        It is necessary to use this method to check for the presence of a connected
        iPad, as we have to return True if we can handle device interaction, or False if not.

        '''
        if self.iTunes:
            # We've previously run, so the user probably ejected the device
            try:
                pythoncom.CoInitialize()
                self.sources = self._get_sources()
                if 'iPod' in self.sources:
                    if DEBUG:
                        sys.stdout.write('.')
                        sys.stdout.flush()
                    if DEBUG:
                        self.log.info('ITUNES.can_handle_windows:\n confirming connected iPad')
                    self.ejected = False
                    return True
                else:
                    if DEBUG:
                        self.log.info("ITUNES.can_handle_windows():\n device ejected")
                    self.ejected = True
                    return False
            except:
                # iTunes connection failed, probably not running anymore

                self.log.error("ITUNES.can_handle_windows():\n lost connection to iTunes")
                return False
            finally:
                pythoncom.CoUninitialize()

        else:
            # This is called at entry
            # We need to know if iTunes sees the iPad
            # It may have been ejected
            if DEBUG:
                self.log.info("ITUNES:can_handle_windows():\n Launching iTunes")

            try:
                pythoncom.CoInitialize()
                self._launch_iTunes()
                self.sources = self._get_sources()
                if (not 'iPod' in self.sources) or (self.sources['iPod'] == ''):
                    attempts = 9
                    while attempts:
                        # If iTunes was just launched, device may not be detected yet
                        self.sources = self._get_sources()
                        if (not 'iPod' in self.sources) or (self.sources['iPod'] == ''):
                            attempts -= 1
                            time.sleep(0.5)
                            if DEBUG:
                                self.log.warning(" waiting for identified iPad, attempt #%d" % (10 - attempts))
                        else:
                            if DEBUG:
                                self.log.info(' found connected iPad in iTunes')
                            break
                    else:
                        # iTunes running, but not connected iPad
                        if DEBUG:
                            self.log.info(' self.ejected = True')
                        self.ejected = True
                        return False
                else:
                    self.log.info(' found connected iPad in sources')
            finally:
                pythoncom.CoUninitialize()

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
        return (None,None)

    def delete_books(self, paths, end_session=True):
        '''
        Delete books at paths on device.
        iTunes doesn't let us directly delete a book on the device.
        If the requested paths are deletable (i.e., it's in the Library|Books list),
        delete the paths from the library, then resync iPad

        '''
        self.problem_titles = []
        self.problem_msg = _("Some books not found in iTunes database.\n"
                              "Delete using the iBooks app.\n"
                              "Click 'Show Details' for a list.")
        for path in paths:
            if self.cached_books[path]['lib_book']:
                if DEBUG:
                    self.log.info("ITUNES:delete_books(): Deleting '%s' from iTunes library" % (path))

                if isosx:
                    self._remove_from_iTunes(self.cached_books[path])
                elif iswindows:
                    try:
                        pythoncom.CoInitialize()
                        self.iTunes = win32com.client.Dispatch("iTunes.Application")
                        self._remove_from_iTunes(self.cached_books[path])
                    finally:
                        pythoncom.CoUninitialize()

                self.update_needed = True
                self.update_msg = "Deleted books from device"
            else:
                self.problem_titles.append("'%s' by %s" %
                 (self.cached_books[path]['title'],self.cached_books[path]['author']))

    def eject(self):
        '''
        Un-mount / eject the device from the OS. This does not check if there
        are pending GUI jobs that need to communicate with the device.
        '''
        if DEBUG:
            self.log.info("ITUNES:eject(): ejecting '%s'" % self.sources['iPod'])
        if isosx:
            self.iTunes.eject(self.sources['iPod'])
        elif iswindows:
            try:
                pythoncom.CoInitialize()
                self.iTunes = win32com.client.Dispatch("iTunes.Application")
                self.iTunes.sources.ItemByName(self.sources['iPod']).EjectIPod()
            finally:
                pythoncom.CoUninitialize()

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

        In Windows, a sync-in-progress blocks this call until sync is complete
        """
        if DEBUG:
            self.log.info("ITUNES:free_space()")

        free_space = 0
        if isosx:
            if 'iPod' in self.sources:
                connected_device = self.sources['iPod']
                free_space = self.iTunes.sources[connected_device].free_space()

        elif iswindows:
            if 'iPod' in self.sources:

                while True:
                    try:
                        try:
                            pythoncom.CoInitialize()
                            self.iTunes = win32com.client.Dispatch("iTunes.Application")
                            connected_device = self.sources['iPod']
                            free_space = self.iTunes.sources.ItemByName(connected_device).FreeSpace
                        finally:
                            pythoncom.CoUninitialize()
                            break
                    except:
                        self.log.error(' waiting for free_space() call to go through')

        return (free_space,-1,-1)

    def get_device_information(self, end_session=True):
        """
        Ask device for device information. See L{DeviceInfoQuery}.
        @return: (device name, device version, software version on device, mime type)
        """
        if DEBUG:
            self.log.info("ITUNES:get_device_information()")

        return ('iDevice','hw v1.0','sw v1.0', 'mime type normally goes here')

    def get_file(self, path, outfile, end_session=True):
        '''
        Read the file at C{path} on the device and write it to outfile.
        @param outfile: file object like C{sys.stdout} or the result of an C{open} call
        '''
        if DEBUG:
            self.log.info("ITUNES.get_file(): exporting '%s'" % path)
        outfile.write(open(self.cached_books[path]['lib_book'].location().path).read())

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

        Note that most of the initialization is necessarily performed in can_handle(), as
        we need to talk to iTunes to discover if there's a connected iPod
        '''

        # Confirm/create thumbs archive
        archive_path = os.path.join(self.cache_dir, "thumbs.zip")

        if not os.path.exists(self.cache_dir):
            if DEBUG:
                self.log.info(" creating thumb cache '%s'" % self.cache_dir)
            os.makedirs(self.cache_dir)

        if not os.path.exists(archive_path):
            self.log.info(" creating zip archive")
            zfw = zipfile.ZipFile(archive_path, mode='w')
            zfw.writestr("iTunes Thumbs Archive",'')
            zfw.close()
        else:
            if DEBUG:
                self.log.info(" existing thumb cache at '%s'" % archive_path)

    def remove_books_from_metadata(self, paths, booklists):
        '''
        Remove books from the metadata list. This function must not communicate
        with the device.
        @param paths: paths to books on the device.
        @param booklists:  A tuple containing the result of calls to
                                (L{books}(oncard=None), L{books}(oncard='carda'),
                                L{books}(oncard='cardb')).
        '''
        if DEBUG:
            self.log.info("ITUNES.remove_books_from_metadata():")
        for path in paths:
            if self.cached_books[path]['lib_book']:
                # Remove from the booklist
                for i,book in enumerate(booklists[0]):
                    if book.path == path:
                        self.log.info(" removing '%s' from calibre booklist, index: %d" % (path, i))
                        booklists[0].pop(i)
                        break
                else:
                    self.log.error("ITUNES.remove_books_from_metadata(): '%s' not found in self.cached_book" % path)

                # Remove from cached_books
                self.cached_books.pop(path)
                if DEBUG:
                    self.log.info("ITUNES.remove_books_from_metadata(): Removing '%s' from self.cached_books" % path)
                    self._dump_cached_books('remove_books_from_metadata()')
            else:
                self.log.warning("ITUNES.remove_books_from_metadata(): skipping purchased book, can't remove via automation interface")

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
        if DEBUG:
            self.log.info("ITUNE.reset()")

    def set_progress_reporter(self, report_progress):
        '''
        @param report_progress: Function that is called with a % progress
                                (number between 0 and 100) for various tasks
                                If it is called with -1 that means that the
                                task does not have any progress information
        '''
        self.report_progress = report_progress

    def settings(self):
        '''
        Should return an opts object. The opts object should have one attribute
        `format_map` which is an ordered list of formats for the device.
        '''
        klass = self if isinstance(self, type) else self.__class__
        c = Config('device_drivers_%s' % klass.__name__, _('settings for device drivers'))
        c.add_opt('format_map', default=self.FORMATS,
            help=_('Ordered list of formats the device will accept'))
        return c.parse()

    def sync_booklists(self, booklists, end_session=True):
        '''
        Update metadata on device.
        @param booklists: A tuple containing the result of calls to
                                (L{books}(oncard=None), L{books}(oncard='carda'),
                                L{books}(oncard='cardb')).
        '''
        if DEBUG:
            self.log.info("ITUNES:sync_booklists():")
        if self.update_needed:
            if DEBUG:
                self.log.info(' calling _update_device')
            self._update_device(msg=self.update_msg)
            self.update_needed = False

        # Get actual size of updated books on device
        if self.update_list:
            if DEBUG:
                self._dump_update_list(header='sync_booklists()')
            if isosx:
                for updated_book in self.update_list:
                    size_on_device = self._get_device_book_size(updated_book['title'],
                                                                updated_book['author'][0])
                    if size_on_device:
                        for book in booklists[0]:
                            if book.title == updated_book['title'] and \
                               book.author == updated_book['author']:
                                break
                        else:
                            self.log.error("ITUNES:sync_booklists(): could not update book size for '%s'" % updated_book['title'])

                    else:
                        self.log.error("ITUNES:sync_booklists(): could not find '%s' on device" % updated_book['title'])

            elif iswindows:
                try:
                    pythoncom.CoInitialize()
                    self.iTunes = win32com.client.Dispatch("iTunes.Application")

                    for updated_book in self.update_list:
                        size_on_device = self._get_device_book_size(updated_book['title'], updated_book['author'])
                        if size_on_device:
                            for book in booklists[0]:
                                if book.title == updated_book['title'] and \
                                   book.author[0] == updated_book['author']:
                                    book.size = size_on_device
                                    break
                            else:
                                self.log.error("ITUNES:sync_booklists(): could not update book size for '%s'" % updated_book['title'])

                        else:
                            self.log.error("ITUNES:sync_booklists(): could not find '%s' on device" % updated_book['title'])
                finally:
                    pythoncom.CoUninitialize()

            self.update_list = []

        # Inform user of any problem books
        if self.problem_titles:
            raise UserFeedback(self.problem_msg,
                                  details='\n'.join(self.problem_titles), level=UserFeedback.WARN)
        self.problem_titles = []
        self.problem_msg = None

    def total_space(self, end_session=True):
        """
        Get total space available on the mountpoints:
            1. Main memory
            2. Memory Card A
            3. Memory Card B

        @return: A 3 element list with total space in bytes of (1, 2, 3). If a
        particular device doesn't have any of these locations it should return 0.
        """
        if DEBUG:
            self.log.info("ITUNES:total_space()")
        capacity = 0
        if isosx:
            if 'iPod' in self.sources:
                connected_device = self.sources['iPod']
                capacity = self.iTunes.sources[connected_device].capacity()

        return (capacity,-1,-1)

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

        new_booklist = []
        self.update_list = []
        strip_tags = re.compile(r'<[^<]*?/?>')
        file_count = float(len(files))
        self.problem_titles = []
        self.problem_msg = _("Some cover art could not be converted.\n"
                                     "Click 'Show Details' for a list.")

        if isosx:
            if DEBUG:
                self.log.info("ITUNES.upload_books():")
                self._dump_files(files, header='upload_books()')
                self._dump_cached_books('upload_books()')
                self._dump_update_list('upload_books()')
            for (i,file) in enumerate(files):
                path = self.path_template % (metadata[i].title, metadata[i].author[0])
                # Delete existing from Library|Books, add to self.update_list
                # for deletion from booklist[0] during add_books_to_metadata
                if path in self.cached_books:
                    if DEBUG:
                        self.log.info(" adding '%s' by %s to self.update_list" %
                                      (self.cached_books[path]['title'],self.cached_books[path]['author']))

                    # *** Second time a book is updated the author is a list ***
                    self.update_list.append(self.cached_books[path])

                    if DEBUG:
                        self.log.info( " deleting existing '%s'" % (path))
                    self._remove_from_iTunes(self.cached_books[path])

                # Add to iTunes Library|Books
                if isinstance(file,PersistentTemporaryFile):
                    added = self.iTunes.add(appscript.mactypes.File(file._name))
                else:
                    added = self.iTunes.add(appscript.mactypes.File(file))

                thumb = None
                if metadata[i].cover:
                    try:
                        # Use cover data as artwork
                        cover_data = open(metadata[i].cover,'rb')
                        added.artworks[1].data_.set(cover_data.read())

                        # Resize for thumb
                        width = metadata[i].thumbnail[0]
                        height = metadata[i].thumbnail[1]
                        im = PILImage.open(metadata[i].cover)
                        im = im.resize((width, height), PILImage.ANTIALIAS)
                        of = cStringIO.StringIO()
                        im.convert('RGB').save(of, 'JPEG')
                        thumb = of.getvalue()

                        # Refresh the thumbnail cache
                        if DEBUG:
                            self.log.info( " refreshing cached thumb for '%s'" % metadata[i].title)
                        archive_path = os.path.join(self.cache_dir, "thumbs.zip")
                        zfw = zipfile.ZipFile(archive_path, mode='a')
                        thumb_path = path.rpartition('.')[0] + '.jpg'
                        zfw.writestr(thumb_path, thumb)
                        zfw.close()
                    except:
                        self.problem_titles.append("'%s' by %s" % (metadata[i].title, metadata[i].author[0]))
                        self.log.error("ITUNES.upload_books(): error converting '%s' to thumb for '%s'" % (metadata[i].cover,metadata[i].title))

                # Create a new Book
                this_book = Book(metadata[i].title, metadata[i].author[0])
                this_book.datetime = parse_date(str(added.date_added())).timetuple()
                this_book.db_id = None
                this_book.device_collections = []
                this_book.library_id = added
                this_book.path = path
                this_book.size = added.size()   # Updated later from actual storage size
                this_book.thumbnail = thumb
                this_book.iTunes_id = added

                new_booklist.append(this_book)

                # Flesh out the iTunes metadata
                added.description.set("added by calibre %s" % strftime('%Y-%m-%d %H:%M:%S'))
                if metadata[i].comments:
                    added.comment.set(strip_tags.sub('',metadata[i].comments))
                if metadata[i].rating:
                    added.rating.set(metadata[i].rating*10)
                added.sort_artist.set(metadata[i].author_sort.title())
                added.sort_name.set(this_book.title_sorter)

                # Set genre from metadata
                # iTunes grabs the first dc:subject from the opf metadata,
                # But we can manually override with first tag starting with alpha
                for tag in metadata[i].tags:
                    if self._is_alpha(tag[0]):
                        added.genre.set(tag)
                        break

                # Add new_book to self.cached_paths
                self.cached_books[this_book.path] = {
                 'title': this_book.title,
                 'author': this_book.author,
                 'lib_book': added
                 }

                # Report progress
                if self.report_progress is not None:
                    self.report_progress(i+1/file_count, _('%d of %d') % (i+1, file_count))
        elif iswindows:
            try:
                pythoncom.CoInitialize()
                self.iTunes = win32com.client.Dispatch("iTunes.Application")
                lib = self.iTunes.sources.ItemByName('Library')
                lib_playlists = [pl.Name for pl in lib.Playlists]
                if not 'Books' in lib_playlists:
                    self.log.error(" no 'Books' playlist in Library")
                library_books = lib.Playlists.ItemByName('Books')

                for (i,file) in enumerate(files):
                    path = self.path_template % (metadata[i].title, metadata[i].author[0])
                    # Delete existing from Library|Books, add to self.update_list
                    # for deletion from booklist[0] during add_books_to_metadata
                    if path in self.cached_books:
                        self.update_list.append(self.cached_books[path])

                        if DEBUG:
                            self.log.info("ITUNES.upload_books():")
                            self.log.info( " deleting existing '%s'" % (path))
                        self._remove_from_iTunes(self.cached_books[path])
                    else:
                        if DEBUG:
                            self.log.info(" '%s' not in cached_books" % metadata[i].title)

                    # Add to iTunes Library|Books
                    if isinstance(file,PersistentTemporaryFile):
                        op_status = library_books.AddFile(file._name)
                        self.log.info("ITUNES.upload_books():\n iTunes adding '%s'" % file._name)
                    else:
                        op_status = library_books.AddFile(file)
                        self.log.info(" iTunes adding '%s'" % file)

                    if DEBUG:
                        sys.stdout.write(" iTunes copying '%s' ..." % metadata[i].title)
                        sys.stdout.flush()
                    while op_status.InProgress:
                        time.sleep(0.5)
                        if DEBUG:
                            sys.stdout.write('.')
                            sys.stdout.flush()
                    if DEBUG:
                        sys.stdout.write("\n")
                        sys.stdout.flush()

                    if False:
                        # According to the Apple API, .Tracks should be populated once the xfer
                        # is complete, but I can't seem to make that work.
                        if DEBUG:
                            sys.stdout.write(" waiting for handle to '%s' ..." % metadata[i].title)
                            sys.stdout.flush()
                        while not op_status.Tracks:
                            time.sleep(0.5)
                            if DEBUG:
                                sys.stdout.write('.')
                                sys.stdout.flush()
                        if DEBUG:
                            print
                        added = op_status.Tracks.Item[1]
                    else:
                        # This approach simply scans Library|Books for the book we just added
                        added = self._find_library_book(
                            {'title': metadata[i].title,'author': metadata[i].author[0]})

                        if not added:
                            self.log.error("ITUNES.upload_books():\n could not find added book in iTunes")

                    thumb = None
                    # Use cover data as artwork
                    if metadata[i].cover:
                        if added.Artwork.Count:
                            added.Artwork.Item(1).SetArtworkFromFile(metadata[i].cover)
                        else:
                            added.AddArtworkFromFile(metadata[i].cover)

                        try:
                            # Resize for thumb
                            width = metadata[i].thumbnail[0]
                            height = metadata[i].thumbnail[1]
                            im = PILImage.open(metadata[i].cover)
                            im = im.resize((width, height), PILImage.ANTIALIAS)
                            of = cStringIO.StringIO()
                            im.convert('RGB').save(of, 'JPEG')
                            thumb = of.getvalue()

                            # Refresh the thumbnail cache
                            if DEBUG:
                                self.log.info( " refreshing cached thumb for '%s'" % metadata[i].title)
                            archive_path = os.path.join(self.cache_dir, "thumbs.zip")
                            zfw = zipfile.ZipFile(archive_path, mode='a')
                            thumb_path = path.rpartition('.')[0] + '.jpg'
                            zfw.writestr(thumb_path, thumb)
                            zfw.close()
                        except:
                            self.problem_titles.append("'%s' by %s" % (metadata[i].title, metadata[i].author[0]))
                            self.log.error("ITUNES.upload_books():\n error converting '%s' to thumb for '%s'" % (metadata[i].cover,metadata[i].title))

                    # Create a new Book
                    this_book = Book(metadata[i].title, metadata[i].author[0])
                    this_book.datetime = parse_date(str(added.DateAdded)).timetuple()
                    this_book.db_id = None
                    this_book.device_collections = []
                    this_book.library_id = added
                    this_book.path = path
                    this_book.size = added.Size   # Updated later from actual storage size
                    this_book.thumbnail = thumb
                    this_book.iTunes_id = added

                    new_booklist.append(this_book)

                    # Flesh out the iTunes metadata
                    added.Description = ("added by calibre %s" % strftime('%Y-%m-%d %H:%M:%S'))
                    if metadata[i].comments:
                        added.Comment = (strip_tags.sub('',metadata[i].comments))
                    if metadata[i].rating:
                        added.AlbumRating = (metadata[i].rating*10)
                    added.SortArtist = (metadata[i].author_sort.title())
                    added.SortName = (this_book.title_sorter)

                    # Set genre from metadata
                    # iTunes grabs the first dc:subject from the opf metadata,
                    # But we can manually override with first tag starting with alpha
                    for tag in metadata[i].tags:
                        if self._is_alpha(tag[0]):
                            added.Category = (tag)
                            break

                    # Add new_book to self.cached_paths
                    self.cached_books[this_book.path] = {
                     'title': metadata[i].title,
                     'author': metadata[i].author[0],
                     'lib_book': added
                     }

                    # Report progress
                    if self.report_progress is not None:
                        self.report_progress(i+1/file_count, _('%d of %d') % (i+1, file_count))
            finally:
                pythoncom.CoUninitialize()

        if self.report_progress is not None:
            self.report_progress(1.0, _('finished'))

        # Tell sync_booklists we need a re-sync
        self.update_needed = True
        self.update_msg = "Added books to device"

        return (new_booklist, [], [])

    # Private methods
    def _dump_booklist(self, booklist, header=None):
        '''
        '''
        if header:
            msg = '\nbooklist, %s' % header
            self.log.info(msg)
            self.log.info('%s' % ('-' * len(msg)))

        for book in booklist:
            if isosx:
                self.log.info("%-40.40s %-30.30s %-10.10s" %
                 (book.title, book.author, str(book.library_id)[-9:]))
            elif iswindows:
                self.log.info("%-40.40s %-30.30s" %
                 (book.title, book.author))

    def _dump_cached_books(self, header=None):
        '''
        '''
        if header:
            msg = '\nself.cached_books, %s' % header
            self.log.info(msg)
            self.log.info( "%s" % ('-' * len(msg)))
        if isosx:
            for cb in self.cached_books.keys():
                self.log.info("%-40.40s %-30.30s %-10.10s" %
                 (self.cached_books[cb]['title'],
                  self.cached_books[cb]['author'],
                  str(self.cached_books[cb]['lib_book'])[-9:]))
        elif iswindows:
            for cb in self.cached_books.keys():
                self.log.info("%-40.40s %-30.30s" %
                 (self.cached_books[cb]['title'],
                  self.cached_books[cb]['author']))

        self.log.info()

    def _dump_hex(self, src, length=16):
        '''
        '''
        FILTER=''.join([(len(repr(chr(x)))==3) and chr(x) or '.' for x in range(256)])
        N=0; result=''
        while src:
           s,src = src[:length],src[length:]
           hexa = ' '.join(["%02X"%ord(x) for x in s])
           s = s.translate(FILTER)
           result += "%04X   %-*s   %s\n" % (N, length*3, hexa, s)
           N+=length
        print result

    def _dump_files(self, files, header=None):
        if header:
            msg = '\nfiles passed to %s:' % header
            self.log.info(msg)
            self.log.info( "%s" % ('-' * len(msg)))
        for file in files:
            self.log.info(file)
        self.log.info()

    def _dump_update_list(self,header=None):
        if header:
            msg = '\nself.update_list called from %s' % header
            self.log.info(msg)
            self.log.info( "%s" % ('-' * len(msg)))

        if isosx:
            for ub in self.update_list:
                self.log.info("%-40.40s %-30.30s %-10.10s" %
                 (ub['title'],
                  ub['author'],
                  str(ub['lib_book'])[-9:]))
        elif iswindows:
            for ub in self.update_list:
                self.log.info("%-40.40s %-30.30s" %
                 (ub['title'],
                  ub['author']))
        self.log.info()

    def _find_device_book(self, cached_book):
        '''
        Windows-only method to get a handle to a device book in the current pythoncom session
        '''
        SearchField = ['All','Visible','Artists','Titles','Composers','SongNames']
        if iswindows:
            dev_books = self.iTunes.sources.ItemByName(self.sources['iPod']).Playlists.ItemByName('Books')
            hits = dev_books.Search(cached_book['title'],SearchField.index('Titles'))
            if hits:
                for hit in hits:
                    if hit.Artist == cached_book['author']:
                        return hit
            return None

    def _find_library_book(self, cached_book):
        '''
        Windows-only method to get a handle to a library book in the current pythoncom session
        '''
        SearchField = ['All','Visible','Artists','Titles','Composers','SongNames']
        if iswindows:
            if DEBUG:
                self.log.info("ITUNES._find_library_book()")
                self.log.info(" looking for '%s' by %s" % (cached_book['title'], cached_book['author']))
            lib_books = self.iTunes.sources.ItemByName('Library').Playlists.ItemByName('Books')

            attempts = 9
            while attempts:
                # Find all books by this author, then match title
                hits = lib_books.Search(cached_book['author'],SearchField.index('Artists'))
                if hits:
                    for hit in hits:
                        self.log.info(" evaluating '%s' by %s" % (hit.Name, hit.Artist))
                        if hit.Name == cached_book['title']:
                            self.log.info(" matched '%s' by %s" % (hit.Name, hit.Artist))
                            return hit
                attempts -= 1
                time.sleep(0.5)
                if DEBUG:
                    self.log.warning(" attempt #%d" % (10 - attempts))

            if DEBUG:
                self.log.error(" search yielded no hits")
            return None

    def _generate_thumbnail(self, book_path, book):
        '''
        Convert iTunes artwork to thumbnail
        Cache generated thumbnails
        cache_dir = os.path.join(config_dir, 'caches', 'itunes')
        '''

        archive_path = os.path.join(self.cache_dir, "thumbs.zip")
        thumb_path = book_path.rpartition('.')[0] + '.jpg'

        try:
            zfr = zipfile.ZipFile(archive_path)
            thumb_data = zfr.read(thumb_path)
            zfr.close()
        except:
            zfw = zipfile.ZipFile(archive_path, mode='a')
        else:
#             if DEBUG:
#                 if isosx:
#                     self.log.info("ITUNES._generate_thumbnail(): cached thumb found for '%s'" % book.name())
#                 elif iswindows:
#                     self.log.info("ITUNES._generate_thumbnail(): cached thumb found for '%s'" % book.Name)

            return thumb_data

        if isosx:
            try:
                # Resize the cover
                data = book.artworks[1].raw_data().data
                #self._dump_hex(data[:256])
                im = PILImage.open(cStringIO.StringIO(data))
                scaled, width, height = fit_image(im.size[0],im.size[1], 60, 80)
                im = im.resize((int(width),int(height)), PILImage.ANTIALIAS)
                thumb = cStringIO.StringIO()
                im.convert('RGB').save(thumb,'JPEG')

                # Cache the tagged thumb
                if DEBUG:
                    self.log.info("ITUNES._generate_thumbnail(): generated thumb for '%s', caching" % book.name())
                zfw.writestr(thumb_path, thumb.getvalue())
                zfw.close()
                return thumb.getvalue()
            except:
                self.log.error("ITUNES._generate_thumbnail(): error generating thumb for '%s'" % book.name())
                return None

        elif iswindows:

            if DEBUG:
                self.log.info("ITUNES._generate_thumbnail()")
            if not book.Artwork.Count:
                if DEBUG:
                    self.log.info(" no artwork available")
                return None

            # Save the cover from iTunes
            tmp_thumb = os.path.join(tempfile.gettempdir(), "thumb.%s" % ArtworkFormat[book.Artwork.Item(1).Format])
            book.Artwork.Item(1).SaveArtworkToFile(tmp_thumb)
            try:
                # Resize the cover
                im = PILImage.open(tmp_thumb)
                scaled, width, height = fit_image(im.size[0],im.size[1], 60, 80)
                im = im.resize((int(width),int(height)), PILImage.ANTIALIAS)
                thumb = cStringIO.StringIO()
                im.convert('RGB').save(thumb,'JPEG')
                os.remove(tmp_thumb)

                # Cache the tagged thumb
                if DEBUG:
                    self.log.info(" generated thumb for '%s', caching" % book.Name)
                zfw.writestr(thumb_path, thumb.getvalue())
                zfw.close()
                return thumb.getvalue()
            except:
                self.log.error(" error generating thumb for '%s'" % book.Name)
                return None

    def _get_device_book_size(self, title, author):
        '''
        Fetch the size of a book stored on the device

        Windows: If sync-in-progress, this call blocked until sync completes
        '''
        if DEBUG:
            self.log.info("ITUNES._get_device_book_size():\n looking for title: '%s' author: '%s'" %
                (title,author))

        device_books = self._get_device_books()

        if isosx:
            for d_book in device_books:
                if d_book.name() == title and d_book.artist() == author:
                    if DEBUG:
                        self.log.info(' found it')
                    return d_book.size()
            else:
                self.log.error("ITUNES._get_device_book_size():"
                               " could not find '%s' by '%s' in device_books" % (title,author))
                return None
        elif iswindows:
            for d_book in device_books:
                if d_book.Name == title and d_book.Artist == author:
                    self.log.info(" found it")
                    return d_book.Size
            else:
                self.log.error(" could not find '%s' by '%s' in device_books" % (title,author))
                return None

    def _get_device_books(self):
        '''
        Assumes pythoncom wrapper
        '''
        if isosx:
            if 'iPod' in self.sources:
                connected_device = self.sources['iPod']
                if 'Books' in self.iTunes.sources[connected_device].playlists.name():
                    return self.iTunes.sources[connected_device].playlists['Books'].file_tracks()
            return []

        elif iswindows:
            if 'iPod' in self.sources:
                connected_device = self.sources['iPod']
                dev = self.iTunes.sources.ItemByName(connected_device)
                dev_playlists = [pl.Name for pl in dev.Playlists]
                if 'Books' in dev_playlists:
                    return self.iTunes.sources.ItemByName(connected_device).Playlists.ItemByName('Books').Tracks
                else:
                    return []
            if DEBUG:
                self.log.warning('ITUNES._get_device_book(): No iPod device connected')
            return []

    def _get_library_books(self):
        '''
        Populate a dict of paths from iTunes Library|Books
        '''
        library_books = {}

        if isosx:
            lib = self.iTunes.sources['library']
            if 'Books' in lib.playlists.name():
                lib_books = lib.playlists['Books'].file_tracks()
                for book in lib_books:
                    path = self.path_template % (book.name(), book.artist())
                    library_books[path] = book

        elif iswindows:
            try:
                pythoncom.CoInitialize()
                self.iTunes = win32com.client.Dispatch("iTunes.Application")
                lib = self.iTunes.sources.ItemByName('Library')
                lib_playlists = [pl.Name for pl in lib.Playlists]
                if 'Books' in lib_playlists:
                    lib_books = lib.Playlists.ItemByName('Books').Tracks
                    for book in lib_books:
                        path = self.path_template % (book.Name, book.Artist)
                        library_books[path] = book
            finally:
                pythoncom.CoUninitialize()

        return library_books

    def _get_purchased_book_ids(self):
        '''
        Return Device|Purchased
        '''
        if 'iPod' in self.sources:
            connected_device = self.sources['iPod']
            if isosx:
                if 'Purchased' in self.iTunes.sources[connected_device].playlists.name():
                    return [pb.database_ID() for pb in self.iTunes.sources[connected_device].playlists['Purchased'].file_tracks()]
                else:
                    return []
            elif iswindows:
                dev = self.iTunes.sources.ItemByName(connected_device)
                if dev.Playlists is not None:
                    dev_playlists = [pl.Name for pl in dev.Playlists]
                    if 'Purchased' in dev_playlists:
                        return self.iTunes.sources.ItemByName(connected_device).Playlists.ItemByName('Purchased').Tracks
                else:
                    return []

    def _get_sources(self):
        '''
        Return a dict of sources
        '''
        if isosx:
            names = [s.name() for s in self.iTunes.sources()]
            kinds = [str(s.kind()).rpartition('.')[2] for s in self.iTunes.sources()]
            return dict(zip(kinds,names))
        elif iswindows:
            # Assumes a pythoncom wrapper
            it_sources = ['Unknown','Library','iPod','AudioCD','MP3CD','Device','RadioTuner','SharedLibrary']
            names = [s.name for s in self.iTunes.sources]
            kinds = [it_sources[s.kind] for s in self.iTunes.sources]
            return dict(zip(kinds,names))

    def _is_alpha(self,char):
        '''
        '''
        if not re.search('[a-zA-Z]',char):
            return False
        else:
            return True

    def _launch_iTunes(self):
        '''
        '''
        if DEBUG:
            self.log.info("ITUNES:_launch_iTunes():\n Instantiating iTunes")

        if isosx:
            '''
            Launch iTunes if not already running
            '''
            # Instantiate iTunes
            running_apps = appscript.app('System Events')
            if not 'iTunes' in running_apps.processes.name():
                if DEBUG:
                    self.log.info( "ITUNES:open(): Launching iTunes" )
                self.iTunes = iTunes= appscript.app('iTunes', hide=True)
                iTunes.run()
                initial_status = 'launched'
            else:
                self.iTunes = appscript.app('iTunes')
                initial_status = 'already running'

            if DEBUG:
                self.log.info( " [%s - %s (%s), driver version %d.%d.%d]" %
                 (self.iTunes.name(), self.iTunes.version(), initial_status,
                  self.version[0],self.version[1],self.version[2]))

        if iswindows:
            '''
            Launch iTunes if not already running
            Assumes pythoncom wrapper
            '''
            # Instantiate iTunes
            self.iTunes = win32com.client.Dispatch("iTunes.Application")
            if not DEBUG:
                self.iTunes.Windows[0].Minimized = True
            initial_status = 'launched'

            if DEBUG:
                self.log.info( " [%s - %s (%s), driver version %d.%d.%d]" %
                 (self.iTunes.Windows[0].name, self.iTunes.Version, initial_status,
                  self.version[0],self.version[1],self.version[2]))

    def _remove_from_iTunes(self, cached_book):
        '''
        iTunes does not delete books from storage when removing from database
        '''
        if isosx:
            storage_path = os.path.split(cached_book['lib_book'].location().path)
            title_storage_path = storage_path[0]
            if DEBUG:
                self.log.info("ITUNES._remove_from_iTunes():")
                self.log.info(" removing title_storage_path: %s" % title_storage_path)
            try:
                shutil.rmtree(title_storage_path)
            except:
                self.log.info(" '%s' not empty" % title_storage_path)

            # Clean up title/author directories
            author_storage_path = os.path.split(title_storage_path)[0]
            self.log.info(" author_storage_path: %s" % author_storage_path)
            author_files = os.listdir(author_storage_path)
            if '.DS_Store' in author_files:
                author_files.pop(author_files.index('.DS_Store'))
            if not author_files:
                shutil.rmtree(author_storage_path)
                if DEBUG:
                    self.log.info(" removing empty author_storage_path")
            else:
                if DEBUG:
                    self.log.info(" author_storage_path not empty (%d objects):" % len(author_files))
                    self.log.info(" %s" % '\n'.join(author_files))

            self.iTunes.delete(cached_book['lib_book'])

        elif iswindows:
            '''
            Assume we're wrapped in a pythoncom
            Windows stores the book under a common author directory, so we just delete the .epub
            '''
            if DEBUG:
                self.log.info("ITUNES._remove_from_iTunes(): '%s'" % cached_book['title'])
            book = self._find_library_book(cached_book)
            if book:
                if DEBUG:
                    self.log.info("ITUNES._remove_from_iTunes():\n deleting '%s' at %s" %
                        (cached_book['title'], book.Location))
                folder = os.path.split(book.Location)[0]
                path = book.Location
                book.Delete()
                try:
                    os.remove(path)
                except:
                    self.log.warning(" could not find '%s' in iTunes storage" % path)
                try:
                    os.rmdir(folder)
                    self.log.info(" removed folder '%s'" % folder)
                except:
                    self.log.info(" folder '%s' not found or not empty" % folder)
            else:
                self.log.warning(" could not find '%s' in iTunes storage" % cached_book['title'])

    def _update_device(self, msg='', wait=True):
        '''
        Trigger a sync, wait for completion
        '''
        if DEBUG:
            self.log.info("ITUNES:_update_device():\n %s" % msg)

        if isosx:
            self.iTunes.update()

            if wait:
                # This works if iTunes has books not yet synced to iPad.
                if DEBUG:
                    sys.stdout.write(" waiting for iPad sync to complete ...")
                    sys.stdout.flush()
                while len(self._get_device_books()) != (len(self._get_library_books()) + len(self._get_purchased_book_ids())):
                    if DEBUG:
                        sys.stdout.write('.')
                        sys.stdout.flush()
                    time.sleep(2)
                print
        elif iswindows:
            try:
                pythoncom.CoInitialize()
                self.iTunes = win32com.client.Dispatch("iTunes.Application")
                self.iTunes.UpdateIPod()
                if wait:
                    if DEBUG:
                        sys.stdout.write(" waiting for iPad sync to complete ...")
                        sys.stdout.flush()
                    while True:
                        db_count = len(self._get_device_books())
                        lb_count = len(self._get_library_books())
                        pb_count = len(self._get_purchased_book_ids())
                        if db_count != lb_count + pb_count:
                            if DEBUG:
                                #sys.stdout.write(' %d != %d + %d\n' % (db_count,lb_count,pb_count))
                                sys.stdout.write('.')
                                sys.stdout.flush()
                            time.sleep(2)
                        else:
                            sys.stdout.write('\n')
                            sys.stdout.flush()
                            break

            finally:
                pythoncom.CoUninitialize()


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
    log = None

    def __init__(self, log):
        self.log = log

    def supports_collections(self):
        ''' Return True if the the device supports collections for this book list. '''
        return False

    def add_book(self, book, replace_metadata):
        '''
        Add the book to the booklist. Intent is to maintain any device-internal
        metadata. Return True if booklists must be sync'ed
        '''
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
