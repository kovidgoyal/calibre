# -*- coding: utf-8 -*-

__license__   = 'GPL v3'
__copyright__ = '2010, Gregory Riker'
__docformat__ = 'restructuredtext en'


import cStringIO, ctypes, datetime, os, re, shutil, subprocess, sys, tempfile, time
from calibre.constants import __appname__, __version__, DEBUG
from calibre import fit_image
from calibre.constants import isosx, iswindows
from calibre.devices.errors import UserFeedback
from calibre.devices.usbms.deviceconfig import DeviceConfig
from calibre.devices.interface import DevicePlugin
from calibre.ebooks.BeautifulSoup import BeautifulSoup
from calibre.ebooks.metadata import authors_to_string, MetaInformation
from calibre.ebooks.metadata.book.base import Metadata
from calibre.ebooks.metadata.epub import set_metadata
from calibre.library.server.utils import strftime
from calibre.utils.config import config_dir, prefs
from calibre.utils.date import isoformat, now, parse_date
from calibre.utils.logging import Log
from calibre.utils.zipfile import ZipFile

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

class DriverBase(DeviceConfig, DevicePlugin):
    # Needed for config_widget to work
    FORMATS = ['epub', 'pdf']
    SUPPORTS_SUB_DIRS = True   # To enable second checkbox in customize widget

    @classmethod
    def _config_base_name(cls):
        return 'iTunes'

class ITUNES(DriverBase):
    '''
    Calling sequences:
    Initialization:
        can_handle() or can_handle_windows()
        reset()
        open()
        card_prefix()
        can_handle()
        set_progress_reporter()
        get_device_information()
        card_prefix()
        free_space()
        (Job 1 Get device information finishes)
        can_handle()
        set_progress_reporter()
        books() (once for each storage point)
        settings()
        settings()
        can_handle() (~1x per second OSX while idle)
    Delete:
        delete_books()
        remove_books_from_metadata()
        use_plugboard_ext()
        set_plugboard()
        sync_booklists()
        card_prefix()
        free_space()
    Upload:
        settings()
        set_progress_reporter()
        upload_books()
        add_books_to_metadata()
        use_plugboard_ext()
        set_plugboard()
        set_progress_reporter()
        sync_booklists()
        card_prefix()
        free_space()
    '''

    name = 'Apple device interface'
    gui_name = _('Apple device')
    icon = I('devices/ipad.png')
    description    = _('Communicate with iTunes/iBooks.')
    supported_platforms = ['osx','windows']
    author = 'GRiker'
    #: The version of this plugin as a 3-tuple (major, minor, revision)
    version        = (0,9,0)

    OPEN_FEEDBACK_MESSAGE = _(
        'Apple device detected, launching iTunes, please wait ...')

    # Product IDs:
    #  0x1291   iPod Touch
    #  0x1293   iPod Touch 2G
    #  0x1299   iPod Touch 3G
    #  0x1292   iPhone 3G
    #  0x1294   iPhone 3GS
    #  0x1297   iPhone 4
    #  0x129a   iPad
    VENDOR_ID = [0x05ac]
    PRODUCT_ID = [0x1292,0x1293,0x1294,0x1297,0x1299,0x129a]
    BCD = [0x01]

    # Plugboard ID
    DEVICE_PLUGBOARD_NAME = 'APPLE'

    # iTunes enumerations
    Audiobooks = [
        'Audible file',
        'MPEG audio file',
        'Protected AAC audio file'
        ]
    ArtworkFormat = [
        'Unknown',
        'JPEG',
        'PNG',
        'BMP'
        ]
    PlaylistKind = [
        'Unknown',
        'Library',
        'User',
        'CD',
        'Device',
        'Radio Tuner'
        ]
    PlaylistSpecialKind = [
        'Unknown',
        'Purchased Music',
        'Party Shuffle',
        'Podcasts',
        'Folder',
        'Video',
        'Music',
        'Movies',
        'TV Shows',
        'Books',
        ]
    SearchField = [
        'All',
        'Visible',
        'Artists',
        'Albums',
        'Composers',
        'SongNames',
        ]
    Sources = [
        'Unknown',
        'Library',
        'iPod',
        'AudioCD',
        'MP3CD',
        'Device',
        'RadioTuner',
        'SharedLibrary'
        ]

    # Cover art size limits
    MAX_COVER_WIDTH = 510
    MAX_COVER_HEIGHT = 680

    # Properties
    cached_books = {}
    cache_dir = os.path.join(config_dir, 'caches', 'itunes')
    calibre_library_path = prefs['library_path']
    archive_path = os.path.join(cache_dir, "thumbs.zip")
    description_prefix = "added by calibre"
    ejected = False
    iTunes= None
    iTunes_media = None
    library_orphans = None
    log = Log()
    manual_sync_mode = False
    path_template = 'iTunes/%s - %s.%s'
    plugboards = None
    plugboard_func = None
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
        if DEBUG:
            self.log.info("ITUNES.add_books_to_metadata()")

        task_count = float(len(self.update_list))

        # Delete any obsolete copies of the book from the booklist
        if self.update_list:
            if False:
                self._dump_booklist(booklists[0], header='before',indent=2)
                self._dump_update_list(header='before',indent=2)
                self._dump_cached_books(header='before',indent=2)

            for (j,p_book) in enumerate(self.update_list):
                if False:
                    if isosx:
                        self.log.info("  looking for '%s' by %s uuid:%s" %
                            (p_book['title'],p_book['author'], p_book['uuid']))
                    elif iswindows:
                        self.log.info(" looking for '%s' by %s (%s)" %
                                        (p_book['title'],p_book['author'], p_book['uuid']))

                # Purge the booklist, self.cached_books
                for i,bl_book in enumerate(booklists[0]):
                    if bl_book.uuid == p_book['uuid']:
                        # Remove from booklists[0]
                        booklists[0].pop(i)
                        if False:
                            if isosx:
                                self.log.info("  removing old %s %s from booklists[0]" %
                                    (p_book['title'], str(p_book['lib_book'])[-9:]))
                            elif iswindows:
                                self.log.info(" removing old '%s' from booklists[0]" %
                                                (p_book['title']))

                        # If >1 matching uuid, remove old title
                        matching_uuids = 0
                        for cb in self.cached_books:
                            if self.cached_books[cb]['uuid'] == p_book['uuid']:
                                matching_uuids += 1

                        if matching_uuids > 1:
                            for cb in self.cached_books:
                                if self.cached_books[cb]['uuid'] == p_book['uuid']:
                                    if self.cached_books[cb]['title'] == p_book['title'] and \
                                       self.cached_books[cb]['author'] == p_book['author']:
                                        if DEBUG:
                                            self._dump_cached_book(self.cached_books[cb],header="removing from self.cached_books:", indent=2)
                                        self.cached_books.pop(cb)
                                        break
                            break
                if self.report_progress is not None:
                    self.report_progress(j+1/task_count, _('Updating device metadata listing...'))

            if self.report_progress is not None:
                self.report_progress(1.0, _('Updating device metadata listing...'))

        # Add new books to booklists[0]
        for new_book in locations[0]:
            if DEBUG:
                self.log.info("  adding '%s' by '%s' to booklists[0]" %
                    (new_book.title, new_book.author))
            booklists[0].append(new_book)

        if False:
            self._dump_booklist(booklists[0],header='after',indent=2)
            self._dump_cached_books(header='after',indent=2)

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
                self.log.info("ITUNES:books():")
                if self.settings().use_subdirs:
                    self.log.info(" Cover fetching/caching enabled")
                else:
                    self.log.info(" Cover fetching/caching disabled")

            # Fetch a list of books from iPod device connected to iTunes
            if 'iPod' in self.sources:
                booklist = BookList(self.log)
                cached_books = {}

                if isosx:
                    library_books = self._get_library_books()
                    device_books = self._get_device_books()
                    book_count = float(len(device_books))
                    for (i,book) in enumerate(device_books):
                        this_book = Book(book.name(), book.artist())
                        format = 'pdf' if book.kind().startswith('PDF') else 'epub'
                        this_book.path = self.path_template % (book.name(), book.artist(),format)
                        try:
                            this_book.datetime = parse_date(str(book.date_added())).timetuple()
                        except:
                            this_book.datetime = time.gmtime()
                        this_book.db_id = None
                        this_book.device_collections = []
                        this_book.library_id = library_books[this_book.path] if this_book.path in library_books else None
                        this_book.size = book.size()
                        this_book.uuid = book.composer()
                        # Hack to discover if we're running in GUI environment
                        if self.report_progress is not None:
                            this_book.thumbnail = self._generate_thumbnail(this_book.path, book)
                        else:
                            this_book.thumbnail = None
                        booklist.add_book(this_book, False)

                        cached_books[this_book.path] = {
                         'title':book.name(),
                         'author':[book.artist()],
                         'lib_book':library_books[this_book.path] if this_book.path in library_books else None,
                         'dev_book':book,
                         'uuid': book.composer()
                         }

                        if self.report_progress is not None:
                            self.report_progress(i+1/book_count, _('%d of %d') % (i+1, book_count))
                    self._purge_orphans(library_books, cached_books)

                elif iswindows:
                    try:
                        pythoncom.CoInitialize()
                        self.iTunes = win32com.client.Dispatch("iTunes.Application")
                        library_books = self._get_library_books()
                        device_books = self._get_device_books()
                        book_count = float(len(device_books))
                        for (i,book) in enumerate(device_books):
                            this_book = Book(book.Name, book.Artist)
                            format = 'pdf' if book.KindAsString.startswith('PDF') else 'epub'
                            this_book.path = self.path_template % (book.Name, book.Artist,format)
                            try:
                                this_book.datetime = parse_date(str(book.DateAdded)).timetuple()
                            except:
                                this_book.datetime = time.gmtime()
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
                             'lib_book':library_books[this_book.path] if this_book.path in library_books else None,
                             'uuid': book.Composer,
                             'format': 'pdf' if book.KindAsString.startswith('PDF') else 'epub'
                             }

                            if self.report_progress is not None:
                                self.report_progress(i+1/book_count,
                                        _('%d of %d') % (i+1, book_count))
                        self._purge_orphans(library_books, cached_books)

                    finally:
                        pythoncom.CoUninitialize()

                if self.report_progress is not None:
                    self.report_progress(1.0, _('finished'))
                self.cached_books = cached_books
                if DEBUG:
                    self._dump_booklist(booklist, 'returning from books()', indent=2)
                    self._dump_cached_books('returning from books()',indent=2)
                return booklist
        else:
            return BookList(self.log)

    def can_handle(self, device_info, debug=False):
        '''
        Unix version of :method:`can_handle_windows`

        :param device_info: Is a tupe of (vid, pid, bcd, manufacturer, product,
        serial number)

        Confirm that:
            - iTunes is running
            - there is an iDevice connected
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
                            self.log.warning(" waiting for connected iPad, attempt #%d" % (10 - attempts))
                    else:
                        if DEBUG:
                            self.log.info(' found connected iPad')
                        break
                else:
                    # iTunes running, but not connected iPad
                    if DEBUG:
                        self.log.info(' self.ejected = True')
                    self.ejected = True
                    return False

            self._discover_manual_sync_mode(wait = 2 if self.initial_status == 'launched' else 0)
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
                    self._discover_manual_sync_mode()
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
                                self.log.warning(" waiting for connected iPad, attempt #%d" % (10 - attempts))
                        else:
                            if DEBUG:
                                self.log.info(' found connected iPad in iTunes')
                            break
                    else:
                        # iTunes running, but not connected iPad
                        if DEBUG:
                            self.log.info(' iDevice has been ejected')
                        self.ejected = True
                        return False

                self.log.info(' found connected iPad in sources')
                self._discover_manual_sync_mode(wait=1.0)

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

    @classmethod
    def config_widget(cls):
        '''
        Return a QWidget with settings for the device interface
        '''
        cw = DriverBase.config_widget()
        # Turn off the Save template
        cw.opt_save_template.setVisible(False)
        cw.label.setVisible(False)
        # Repurpose the metadata checkbox
        cw.opt_read_metadata.setText(_("Use Series as Category in iTunes/iBooks"))
        # Repurpose the use_subdirs checkbox
        cw.opt_use_subdirs.setText(_("Cache covers from iTunes/iBooks"))
        return cw

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
        self.log.info("ITUNES:delete_books()")
        for path in paths:
            if self.cached_books[path]['lib_book']:
                if DEBUG:
                    self.log.info(" Deleting '%s' from iTunes library" % (path))

                if isosx:
                    self._remove_from_iTunes(self.cached_books[path])
                    if self.manual_sync_mode:
                        self._remove_from_device(self.cached_books[path])
                elif iswindows:
                    try:
                        pythoncom.CoInitialize()
                        self.iTunes = win32com.client.Dispatch("iTunes.Application")
                        self._remove_from_iTunes(self.cached_books[path])
                        if self.manual_sync_mode:
                            self._remove_from_device(self.cached_books[path])
                    finally:
                        pythoncom.CoUninitialize()

                if not self.manual_sync_mode:
                    self.update_needed = True
                    self.update_msg = "Deleted books from device"
                else:
                    self.log.info(" skipping sync phase, manual_sync_mode: True")
            else:
                if self.manual_sync_mode:
                    metadata = MetaInformation(self.cached_books[path]['title'],
                                               [self.cached_books[path]['author']])
                    metadata.uuid = self.cached_books[path]['uuid']

                    if isosx:
                        self._remove_existing_copy(self.cached_books[path],metadata)
                    elif iswindows:
                        try:
                            pythoncom.CoInitialize()
                            self.iTunes = win32com.client.Dispatch("iTunes.Application")
                            self._remove_existing_copy(self.cached_books[path],metadata)
                        finally:
                            pythoncom.CoUninitialize()

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
            if 'iPod' in self.sources:
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
        if DEBUG:
            self.log.info("ITUNES.open()")

        # Confirm/create thumbs archive
        if not os.path.exists(self.cache_dir):
            if DEBUG:
                self.log.info(" creating thumb cache '%s'" % self.cache_dir)
            os.makedirs(self.cache_dir)

        if not os.path.exists(self.archive_path):
            self.log.info(" creating zip archive")
            zfw = ZipFile(self.archive_path, mode='w')
            zfw.writestr("iTunes Thumbs Archive",'')
            zfw.close()
        else:
            if DEBUG:
                self.log.info(" existing thumb cache at '%s'" % self.archive_path)

    def remove_books_from_metadata(self, paths, booklists):
        '''
        Remove books from the metadata list. This function must not communicate
        with the device.
        @param paths: paths to books on the device.
        @param booklists:  A tuple containing the result of calls to
                                (L{books}(oncard=None), L{books}(oncard='carda'),
                                L{books}(oncard='cardb')).

        NB: This will not find books that were added by a different installation of calibre
            as uuids are different
        '''
        if DEBUG:
            self.log.info("ITUNES.remove_books_from_metadata()")
        for path in paths:
            if DEBUG:
                self._dump_cached_book(self.cached_books[path], indent=2)
                self.log.info("  looking for '%s' by '%s' uuid:%s" %
                                (self.cached_books[path]['title'],
                                 self.cached_books[path]['author'],
                                 self.cached_books[path]['uuid']))

            # Purge the booklist, self.cached_books, thumb cache
            for i,bl_book in enumerate(booklists[0]):
                if False:
                    self.log.info(" evaluating '%s' by '%s' uuid:%s" %
                                  (bl_book.title, bl_book.author,bl_book.uuid))

                found = False
                if bl_book.uuid == self.cached_books[path]['uuid']:
                    if False:
                        self.log.info("  matched with uuid")
                    booklists[0].pop(i)
                    found = True
                elif bl_book.title == self.cached_books[path]['title'] and \
                     bl_book.author[0] == self.cached_books[path]['author']:
                    if False:
                        self.log.info("  matched with title + author")
                    booklists[0].pop(i)
                    found = True

                if found:
                    # Remove from self.cached_books
                    for cb in self.cached_books:
                        if self.cached_books[cb]['uuid'] == self.cached_books[path]['uuid']:
                            self.cached_books.pop(cb)
                            break

                    # Remove from thumb from thumb cache
                    thumb_path = path.rpartition('.')[0] + '.jpg'
                    zf = ZipFile(self.archive_path,'a')
                    fnames = zf.namelist()
                    try:
                        thumb = [x for x in fnames if thumb_path in x][0]
                    except:
                        thumb = None
                    if thumb:
                        if DEBUG:
                            self.log.info("  deleting '%s' from cover cache" % (thumb_path))
                            zf.delete(thumb_path)
                    else:
                        if DEBUG:
                            self.log.info("  '%s' not found in cover cache" % thumb_path)
                    zf.close()

                    break
            else:
                if DEBUG:
                    self.log.error("  unable to find '%s' by '%s' (%s)" %
                                    (bl_book.title, bl_book.author,bl_book.uuid))

        if False:
            self._dump_booklist(booklists[0], indent = 2)
            self._dump_cached_books(indent=2)

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
            self.log.info("ITUNES.reset()")

    def set_progress_reporter(self, report_progress):
        '''
        @param report_progress: Function that is called with a % progress
                                (number between 0 and 100) for various tasks
                                If it is called with -1 that means that the
                                task does not have any progress information
        '''
        self.report_progress = report_progress

    def set_plugboards(self, plugboards, pb_func):
        # This method is called with the plugboard that matches the format
        # declared in use_plugboard_ext and a device name of ITUNES
        if DEBUG:
            self.log.info("ITUNES.set_plugboard()")
            #self.log.info('  using plugboard %s' % plugboards)
        self.plugboards = plugboards
        self.plugboard_func = pb_func

    def sync_booklists(self, booklists, end_session=True):
        '''
        Update metadata on device.
        @param booklists: A tuple containing the result of calls to
                                (L{books}(oncard=None), L{books}(oncard='carda'),
                                L{books}(oncard='cardb')).
        '''

        if DEBUG:
            self.log.info("ITUNES.sync_booklists()")

        if self.update_needed:
            if DEBUG:
                self.log.info(' calling _update_device')
            self._update_device(msg=self.update_msg, wait=False)
            self.update_needed = False

        # Inform user of any problem books
        if self.problem_titles:
            raise UserFeedback(self.problem_msg,
                                  details='\n'.join(self.problem_titles), level=UserFeedback.WARN)
        self.problem_titles = []
        self.problem_msg = None
        self.update_list = []

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
        :metadata: If not None, it is a list of :class:`Metadata` objects.
        The idea is to use the metadata to determine where on the device to
        put the book. len(metadata) == len(files). Apart from the regular
        cover (path to cover), there may also be a thumbnail attribute, which should
        be used in preference. The thumbnail attribute is of the form
        (width, height, cover_data as jpeg).
        '''

        new_booklist = []
        self.update_list = []
        file_count = float(len(files))
        self.problem_titles = []
        self.problem_msg = _("Some cover art could not be converted.\n"
                                     "Click 'Show Details' for a list.")

        if DEBUG:
            self.log.info("ITUNES.upload_books()")
            self._dump_files(files, header='upload_books()',indent=2)
            self._dump_update_list(header='upload_books()',indent=2)

        if isosx:
            for (i,file) in enumerate(files):
                format = file.rpartition('.')[2].lower()
                path = self.path_template % (metadata[i].title, metadata[i].author[0],format)
                self._remove_existing_copy(path, metadata[i])
                fpath = self._get_fpath(file, metadata[i], format, update_md=True)
                db_added, lb_added = self._add_new_copy(fpath, metadata[i])
                thumb = self._cover_to_thumb(path, metadata[i], db_added, lb_added, format)
                this_book = self._create_new_book(fpath, metadata[i], path, db_added, lb_added, thumb, format)
                new_booklist.append(this_book)
                self._update_iTunes_metadata(metadata[i], db_added, lb_added, this_book)

                # Add new_book to self.cached_books
                if DEBUG:
                    self.log.info("ITUNES.upload_books()")
                    self.log.info(" adding '%s' by '%s' uuid:%s to self.cached_books" %
                                  ( metadata[i].title, metadata[i].author, metadata[i].uuid))
                self.cached_books[this_book.path] = {
                   'author': metadata[i].author,
                 'dev_book': db_added,
                   'format': format,
                 'lib_book': lb_added,
                    'title': metadata[i].title,
                     'uuid': metadata[i].uuid }


                # Report progress
                if self.report_progress is not None:
                    self.report_progress(i+1/file_count, _('%d of %d') % (i+1, file_count))

        elif iswindows:
            try:
                pythoncom.CoInitialize()
                self.iTunes = win32com.client.Dispatch("iTunes.Application")

                for (i,file) in enumerate(files):
                    format = file.rpartition('.')[2].lower()
                    path = self.path_template % (metadata[i].title, metadata[i].author[0],format)
                    self._remove_existing_copy(path, metadata[i])
                    fpath = self._get_fpath(file, metadata[i],format, update_md=True)
                    db_added, lb_added = self._add_new_copy(fpath, metadata[i])

                    if self.manual_sync_mode and not db_added:
                        # Problem finding added book, probably title/author change needing to be written to metadata
                        self.problem_msg = ("Title and/or author metadata mismatch with uploaded books.\n"
                                            "Click 'Show Details...' for affected books.")
                        self.problem_titles.append("'%s' by %s" % (metadata[i].title, metadata[i].author[0]))

                    thumb = self._cover_to_thumb(path, metadata[i], db_added, lb_added, format)
                    this_book = self._create_new_book(fpath, metadata[i], path, db_added, lb_added, thumb, format)
                    new_booklist.append(this_book)
                    self._update_iTunes_metadata(metadata[i], db_added, lb_added, this_book)

                    # Add new_book to self.cached_books
                    if DEBUG:
                        self.log.info("ITUNES.upload_books()")
                        self.log.info(" adding '%s' by '%s' uuid:%s to self.cached_books" %
                                      ( metadata[i].title, metadata[i].author, metadata[i].uuid))
                    self.cached_books[this_book.path] = {
                       'author': metadata[i].author[0],
                     'dev_book': db_added,
                       'format': format,
                     'lib_book': lb_added,
                        'title': metadata[i].title,
                         'uuid': metadata[i].uuid}

                    # Report progress
                    if self.report_progress is not None:
                        self.report_progress(i+1/file_count, _('%d of %d') % (i+1, file_count))
            finally:
                pythoncom.CoUninitialize()

        if self.report_progress is not None:
            self.report_progress(1.0, _('finished'))

        # Tell sync_booklists we need a re-sync
        if not self.manual_sync_mode:
            self.update_needed = True
            self.update_msg = "Added books to device"

        if False:
            self._dump_booklist(new_booklist,header="after upload_books()",indent=2)
            self._dump_cached_books(header="after upload_books()",indent=2)
        return (new_booklist, [], [])

    # Private methods
    def _add_device_book(self,fpath, metadata):
        '''
        assumes pythoncom wrapper for windows
        '''
        self.log.info(" ITUNES._add_device_book()")
        if isosx:
            if 'iPod' in self.sources:
                connected_device = self.sources['iPod']
                device = self.iTunes.sources[connected_device]
                for pl in device.playlists():
                    if pl.special_kind() == appscript.k.Books:
                        break
                else:
                    if DEBUG:
                        self.log.error("  Device|Books playlist not found")

                # Add the passed book to the Device|Books playlist
                added = pl.add(appscript.mactypes.File(fpath),to=pl)
                if False:
                    self.log.info("  '%s' added to Device|Books" % metadata.title)
                return added

        elif iswindows:
            if 'iPod' in self.sources:
                connected_device = self.sources['iPod']
                device = self.iTunes.sources.ItemByName(connected_device)

                db_added = None
                for pl in device.Playlists:
                    if pl.Kind == self.PlaylistKind.index('User') and \
                       pl.SpecialKind == self.PlaylistSpecialKind.index('Books'):
                        break
                else:
                    if DEBUG:
                        self.log.info("  no Books playlist found")

                # Add the passed book to the Device|Books playlist
                if pl:
                    file_s = ctypes.c_char_p(fpath)
                    FileArray = ctypes.c_char_p * 1
                    fa = FileArray(file_s)
                    op_status = pl.AddFiles(fa)

                    if DEBUG:
                        sys.stdout.write("  uploading '%s' to Device|Books ..." % metadata.title)
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
                        '''
                        Preferred
                        Disabled because op_status.Tracks never returns a value after adding file
                        This would be the preferred approach (as under OSX)
                        It works in _add_library_book()
                        '''
                        if DEBUG:
                            sys.stdout.write("  waiting for handle to added '%s' ..." % metadata.title)
                            sys.stdout.flush()
                        while not op_status.Tracks:
                            time.sleep(0.5)
                            if DEBUG:
                                sys.stdout.write('.')
                                sys.stdout.flush()

                        if DEBUG:
                            print
                        added = op_status.Tracks[0]
                    else:
                        '''
                        Hackish
                        Search Library|Books for the book we just added
                        PDF file name is added title - need to search for base filename w/o extension
                        '''
                        format = fpath.rpartition('.')[2].lower()
                        base_fn = fpath.rpartition(os.sep)[2]
                        base_fn = base_fn.rpartition('.')[0]
                        db_added = self._find_device_book(
                            { 'title': base_fn if format == 'pdf' else metadata.title,
                             'author': metadata.authors[0],
                               'uuid': metadata.uuid,
                             'format': format})
                    return db_added

    def _add_library_book(self,file, metadata):
        '''
        windows assumes pythoncom wrapper
        '''
        self.log.info(" ITUNES._add_library_book()")
        if isosx:
            added = self.iTunes.add(appscript.mactypes.File(file))

        elif iswindows:
            lib = self.iTunes.LibraryPlaylist
            file_s = ctypes.c_char_p(file)
            FileArray = ctypes.c_char_p * 1
            fa = FileArray(file_s)
            op_status = lib.AddFiles(fa)
            if DEBUG:
                self.log.info("  file added to Library|Books")

            self.log.info("  iTunes adding '%s'" % file)

            if DEBUG:
                sys.stdout.write("  iTunes copying '%s' ..." % metadata.title)
                sys.stdout.flush()

            while op_status.InProgress:
                time.sleep(0.5)
                if DEBUG:
                    sys.stdout.write('.')
                    sys.stdout.flush()
            if DEBUG:
                sys.stdout.write("\n")
                sys.stdout.flush()

            if True:
                '''
                Preferable
                Originally disabled because op_status.Tracks never returned a value
                after adding file.  Seems to be working with iTunes 9.2.1.5 06 Aug 2010
                '''
                if DEBUG:
                    sys.stdout.write("  waiting for handle to added '%s' ..." % metadata.title)
                    sys.stdout.flush()
                while op_status.Tracks is None:
                    time.sleep(0.5)
                    if DEBUG:
                        sys.stdout.write('.')
                        sys.stdout.flush()
                if DEBUG:
                    print
                added = op_status.Tracks[0]
            else:
                '''
                Hackish
                Search Library|Books for the book we just added
                PDF file name is added title - need to search for base filename w/o extension
                '''
                format = file.rpartition('.')[2].lower()
                base_fn = file.rpartition(os.sep)[2]
                base_fn = base_fn.rpartition('.')[0]
                added = self._find_library_book(
                    { 'title': base_fn if format == 'pdf' else metadata.title,
                     'author': metadata.author[0],
                       'uuid': metadata.uuid,
                     'format': format})
        return added

    def _add_new_copy(self, fpath, metadata):
        '''
        '''
        if DEBUG:
            self.log.info(" ITUNES._add_new_copy()")

        db_added = None
        lb_added = None

        if self.manual_sync_mode:
            db_added = self._add_device_book(fpath, metadata)
            if not getattr(fpath, 'deleted_after_upload', False):
                lb_added = self._add_library_book(fpath, metadata)
                if lb_added:
                    if DEBUG:
                        self.log.info("  file added to Library|Books for iTunes<->iBooks tracking")
        else:
            lb_added = self._add_library_book(fpath, metadata)
            if DEBUG:
                self.log.info("  file added to Library|Books for pending sync")

        return db_added, lb_added

    def _cover_to_thumb(self, path, metadata, db_added, lb_added, format):
        '''
        assumes pythoncom wrapper for db_added
        as of iTunes 9.2, iBooks 1.1, can't set artwork for PDF files via automation
        '''
        self.log.info(" ITUNES._cover_to_thumb()")

        thumb = None
        if metadata.cover:

            if format == 'epub':
                # Pre-shrink cover
                # self.MAX_COVER_WIDTH, self.MAX_COVER_HEIGHT
                try:
                    img = PILImage.open(metadata.cover)
                    width = img.size[0]
                    height = img.size[1]
                    scaled, nwidth, nheight = fit_image(width, height, self.MAX_COVER_WIDTH, self.MAX_COVER_HEIGHT)
                    if scaled:
                        if DEBUG:
                            self.log.info("   '%s' scaled from %sx%s to %sx%s" %
                                          (metadata.cover,width,height,nwidth,nheight))
                        img = img.resize((nwidth, nheight), PILImage.ANTIALIAS)
                        cd = cStringIO.StringIO()
                        img.convert('RGB').save(cd, 'JPEG')
                        cover_data = cd.getvalue()
                        cd.close()
                    else:
                        with open(metadata.cover,'r+b') as cd:
                            cover_data = cd.read()
                except:
                    self.problem_titles.append("'%s' by %s" % (metadata.title, metadata.author[0]))
                    self.log.error("  error scaling '%s' for '%s'" % (metadata.cover,metadata.title))
                    return thumb

                if isosx:
                    if lb_added:
                        lb_added.artworks[1].data_.set(cover_data)

                    if db_added:
                        # The following command generates an error, but the artwork does in fact
                        # get sent to the device.  Seems like a bug in Apple's automation interface
                        try:
                            db_added.artworks[1].data_.set(cover_data)
                        except:
                            if DEBUG:
                                self.log.warning("  iTunes automation interface reported an error"
                                                 " when adding artwork to '%s' on the iDevice" % metadata.title)
                            #import traceback
                            #traceback.print_exc()
                            #from calibre import ipython
                            #ipython(user_ns=locals())
                            pass


                elif iswindows:
                    # Write the data to a real file for Windows iTunes
                    tc = os.path.join(tempfile.gettempdir(), "cover.jpg")
                    with open(tc,'wb') as tmp_cover:
                        tmp_cover.write(cover_data)

                    if lb_added:
                        if lb_added.Artwork.Count:
                            lb_added.Artwork.Item(1).SetArtworkFromFile(tc)
                        else:
                            lb_added.AddArtworkFromFile(tc)

                    if db_added:
                        if db_added.Artwork.Count:
                            db_added.Artwork.Item(1).SetArtworkFromFile(tc)
                        else:
                            db_added.AddArtworkFromFile(tc)

            elif format == 'pdf':
                if DEBUG:
                    self.log.info("   unable to set PDF cover via automation interface")

            try:
                # Resize for thumb
                width = metadata.thumbnail[0]
                height = metadata.thumbnail[1]
                im = PILImage.open(metadata.cover)
                im = im.resize((width, height), PILImage.ANTIALIAS)
                of = cStringIO.StringIO()
                im.convert('RGB').save(of, 'JPEG')
                thumb = of.getvalue()
                of.close()

                # Refresh the thumbnail cache
                if DEBUG:
                    self.log.info( "   refreshing cached thumb for '%s'" % metadata.title)
                zfw = ZipFile(self.archive_path, mode='a')
                thumb_path = path.rpartition('.')[0] + '.jpg'
                zfw.writestr(thumb_path, thumb)
            except:
                self.problem_titles.append("'%s' by %s" % (metadata.title, metadata.author[0]))
                self.log.error("   error converting '%s' to thumb for '%s'" % (metadata.cover,metadata.title))
            finally:
                try:
                    zfw.close()
                except:
                    pass
        else:
            if DEBUG:
                self.log.info("   no cover defined in metadata for '%s'" % metadata.title)
        return thumb

    def _create_new_book(self,fpath, metadata, path, db_added, lb_added, thumb, format):
        '''
        '''
        if DEBUG:
            self.log.info(" ITUNES._create_new_book()")

        this_book = Book(metadata.title, authors_to_string(metadata.author))
        this_book.datetime = time.gmtime()
        this_book.db_id = None
        this_book.device_collections = []
        this_book.format = format
        this_book.library_id = lb_added     # ??? GR
        this_book.path = path
        this_book.thumbnail = thumb
        this_book.iTunes_id = lb_added      # ??? GR
        this_book.uuid = metadata.uuid

        if isosx:
            if lb_added:
                this_book.size = self._get_device_book_size(fpath, lb_added.size())
                try:
                    this_book.datetime = parse_date(str(lb_added.date_added())).timetuple()
                except:
                    pass
            elif db_added:
                this_book.size = self._get_device_book_size(fpath, db_added.size())
                try:
                    this_book.datetime = parse_date(str(db_added.date_added())).timetuple()
                except:
                    pass

        elif iswindows:
            if lb_added:
                this_book.size = self._get_device_book_size(fpath, lb_added.Size)
                try:
                    this_book.datetime = parse_date(str(lb_added.DateAdded)).timetuple()
                except:
                    pass
            elif db_added:
                this_book.size = self._get_device_book_size(fpath, db_added.Size)
                try:
                    this_book.datetime = parse_date(str(db_added.DateAdded)).timetuple()
                except:
                    pass

        return this_book

    def _delete_iTunesMetadata_plist(self,fpath):
        '''
        Delete the plist file from the file to force recache
        '''
        zf = ZipFile(fpath,'a')
        fnames = zf.namelist()
        pl_name = 'iTunesMetadata.plist'
        try:
            plist = [x for x in fnames if pl_name in x][0]
        except:
            plist = None
        if plist:
            if DEBUG:
                self.log.info("  _delete_iTunesMetadata_plist():")
                self.log.info("    deleting '%s'\n   from '%s'" % (pl_name,fpath))
                zf.delete(pl_name)
        zf.close()

    def _discover_manual_sync_mode(self, wait=0):
        '''
        Assumes pythoncom for windows
        wait is passed when launching iTunes, as it seems to need a moment to come to its senses
        '''
        if DEBUG:
            self.log.info(" ITUNES._discover_manual_sync_mode()")
        if wait:
            time.sleep(wait)
        if isosx:
            connected_device = self.sources['iPod']
            dev_books = None
            device = self.iTunes.sources[connected_device]
            for pl in device.playlists():
                if pl.special_kind() == appscript.k.Books:
                    dev_books = pl.file_tracks()
                    break
            else:
                self.log.error("   book_playlist not found")

            if len(dev_books):
                first_book = dev_books[0]
                if False:
                    self.log.info("  determing manual mode by modifying '%s' by %s" % (first_book.name(), first_book.artist()))
                try:
                    first_book.bpm.set(0)
                    self.manual_sync_mode = True
                except:
                    self.manual_sync_mode = False
            else:
                if DEBUG:
                    self.log.info("   adding tracer to empty Books|Playlist")
                try:
                    added = pl.add(appscript.mactypes.File(P('tracer.epub')),to=pl)
                    time.sleep(0.5)
                    added.delete()
                    self.manual_sync_mode = True
                except:
                    self.manual_sync_mode = False

        elif iswindows:
            connected_device = self.sources['iPod']
            device = self.iTunes.sources.ItemByName(connected_device)

            dev_books = None
            for pl in device.Playlists:
                if pl.Kind == self.PlaylistKind.index('User') and \
                   pl.SpecialKind == self.PlaylistSpecialKind.index('Books'):
                    dev_books = pl.Tracks
                    break

            if dev_books.Count:
                first_book = dev_books.Item(1)
                #if DEBUG:
                    #self.log.info(" determing manual mode by modifying '%s' by %s" % (first_book.Name, first_book.Artist))
                try:
                    first_book.BPM = 0
                    self.manual_sync_mode = True
                except:
                    self.manual_sync_mode = False
            else:
                if DEBUG:
                    self.log.info("   sending tracer to empty Books|Playlist")
                fpath = P('tracer.epub')
                mi = MetaInformation('Tracer',['calibre'])
                try:
                    added = self._add_device_book(fpath,mi)
                    time.sleep(0.5)
                    added.Delete()
                    self.manual_sync_mode = True
                except:
                    self.manual_sync_mode = False

        self.log.info("   iTunes.manual_sync_mode: %s" % self.manual_sync_mode)

    def _dump_booklist(self, booklist, header=None,indent=0):
        '''
        '''
        if header:
            msg = '\n%sbooklist %s:' % (' '*indent,header)
            self.log.info(msg)
            self.log.info('%s%s' % (' '*indent,'-' * len(msg)))

        for book in booklist:
            if isosx:
                self.log.info("%s%-40.40s %-30.30s %-10.10s %s" %
                 (' '*indent,book.title, book.author, str(book.library_id)[-9:], book.uuid))
            elif iswindows:
                self.log.info("%s%-40.40s %-30.30s" %
                 (' '*indent,book.title, book.author))
        self.log.info()

    def _dump_cached_book(self, cached_book, header=None,indent=0):
        '''
        '''
        if isosx:
            if header:
                msg = '%s%s' % (' '*indent,header)
                self.log.info(msg)
                self.log.info( "%s%s" % (' '*indent, '-' * len(msg)))
                self.log.info("%s%-40.40s %-30.30s %-10.10s %-10.10s %s" %
                 (' '*indent,
                  'title',
                  'author',
                  'lib_book',
                  'dev_book',
                  'uuid'))
            self.log.info("%s%-40.40s %-30.30s %-10.10s %-10.10s %s" %
             (' '*indent,
              cached_book['title'],
              cached_book['author'],
              str(cached_book['lib_book'])[-9:],
              str(cached_book['dev_book'])[-9:],
              cached_book['uuid']))
        elif iswindows:
            if header:
                msg = '%s%s' % (' '*indent,header)
                self.log.info(msg)
                self.log.info( "%s%s" % (' '*indent, '-' * len(msg)))

            self.log.info("%s%-40.40s %-30.30s %s" %
             (' '*indent,
              cached_book['title'],
              cached_book['author'],
              cached_book['uuid']))

    def _dump_cached_books(self, header=None, indent=0):
        '''
        '''
        if header:
            msg = '\n%sself.cached_books %s:' % (' '*indent,header)
            self.log.info(msg)
            self.log.info( "%s%s" % (' '*indent,'-' * len(msg)))
        if isosx:
            for cb in self.cached_books.keys():
                self.log.info("%s%-40.40s %-30.30s %-10.10s %-10.10s %s" %
                 (' '*indent,
                  self.cached_books[cb]['title'],
                  self.cached_books[cb]['author'],
                  str(self.cached_books[cb]['lib_book'])[-9:],
                  str(self.cached_books[cb]['dev_book'])[-9:],
                  self.cached_books[cb]['uuid']))
        elif iswindows:
            for cb in self.cached_books.keys():
                self.log.info("%s%-40.40s %-30.30s %-4.4s %s" %
                 (' '*indent,
                  self.cached_books[cb]['title'],
                  self.cached_books[cb]['author'],
                  self.cached_books[cb]['format'],
                  self.cached_books[cb]['uuid']))

        self.log.info()

    def _dump_epub_metadata(self, fpath):
        '''
        '''
        self.log.info(" ITUNES.__get_epub_metadata()")
        title = None
        author = None
        timestamp = None
        zf = ZipFile(fpath,'r')
        fnames = zf.namelist()
        opf = [x for x in fnames if '.opf' in x][0]
        if opf:
            opf_raw = cStringIO.StringIO(zf.read(opf))
            soup = BeautifulSoup(opf_raw.getvalue())
            opf_raw.close()
            title = soup.find('dc:title').renderContents()
            author = soup.find('dc:creator').renderContents()
            ts = soup.find('meta',attrs={'name':'calibre:timestamp'})
            if ts:
                # Touch existing calibre timestamp
                timestamp = ts['content']

            if not title or not author:
                if DEBUG:
                    self.log.error("   couldn't extract title/author from %s in %s" % (opf,fpath))
                    self.log.error("   title: %s  author: %s timestamp: %s" % (title, author, timestamp))
        else:
            if DEBUG:
                self.log.error("   can't find .opf in %s" % fpath)
        zf.close()
        return (title, author, timestamp)

    def _dump_files(self, files, header=None,indent=0):
        if header:
            msg = '\n%sfiles passed to %s:' % (' '*indent,header)
            self.log.info(msg)
            self.log.info( "%s%s" % (' '*indent,'-' * len(msg)))
        for file in files:
            if getattr(file, 'orig_file_path', None) is not None:
                self.log.info(" %s%s" % (' '*indent,file.orig_file_path))
            elif getattr(file, 'name', None) is not None:
                self.log.info(" %s%s" % (' '*indent,file.name))
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

    def _dump_library_books(self, library_books):
        '''
        '''
        if DEBUG:
            self.log.info("\n library_books:")
        for book in library_books:
            self.log.info("   %s" % book)
        self.log.info()

    def _dump_update_list(self,header=None,indent=0):
        if header:
            msg = '\n%sself.update_list %s' % (' '*indent,header)
            self.log.info(msg)
            self.log.info( "%s%s" % (' '*indent,'-' * len(msg)))

        if isosx:
            for ub in self.update_list:
                self.log.info("%s%-40.40s %-30.30s %-10.10s %s" %
                 (' '*indent,
                  ub['title'],
                  ub['author'],
                  str(ub['lib_book'])[-9:],
                  ub['uuid']))
        elif iswindows:
            for ub in self.update_list:
                self.log.info("%s%-40.40s %-30.30s" %
                 (' '*indent,
                  ub['title'],
                  ub['author']))
        self.log.info()

    def _find_device_book(self, search):
        '''
        Windows-only method to get a handle to device book in the current pythoncom session
        '''
        if iswindows:
            dev_books = self._get_device_books_playlist()
            if DEBUG:
                self.log.info(" ITUNES._find_device_book()")
                self.log.info("  searching for '%s' by '%s' (%s)" %
                              (search['title'], search['author'],search['uuid']))
            attempts = 9
            while attempts:
                # Try by uuid - only one hit
                if 'uuid' in search and search['uuid']:
                    if DEBUG:
                        self.log.info("   searching by uuid '%s' ..." % search['uuid'])
                    hits = dev_books.Search(search['uuid'],self.SearchField.index('All'))
                    if hits:
                        hit = hits[0]
                        self.log.info("   found '%s' by %s (%s)" % (hit.Name, hit.Artist, hit.Composer))
                        return hit

                # Try by author - there could be multiple hits
                if search['author']:
                    if DEBUG:
                        self.log.info("   searching by author '%s' ..." % search['author'])
                    hits = dev_books.Search(search['author'],self.SearchField.index('Artists'))
                    if hits:
                        for hit in hits:
                            if hit.Name == search['title']:
                                if DEBUG:
                                    self.log.info("   found '%s' by %s (%s)" % (hit.Name, hit.Artist, hit.Composer))
                                return hit

                # Search by title if no author available
                if DEBUG:
                    self.log.info("   searching by title '%s' ..." % search['title'])
                hits = dev_books.Search(search['title'],self.SearchField.index('All'))
                if hits:
                    for hit in hits:
                        if hit.Name == search['title']:
                            if DEBUG:
                                self.log.info("   found '%s'" % (hit.Name))
                            return hit

                # PDF just sent, title not updated yet, look for export pattern
                # PDF metadata was rewritten at export as 'safe(title) - safe(author)'
                if search['format'] == 'pdf':
                    title = re.sub(r'[^0-9a-zA-Z ]', '_', search['title'])
                    author = re.sub(r'[^0-9a-zA-Z ]', '_', search['author'])
                    if DEBUG:
                        self.log.info("   searching by name: '%s - %s'" % (title,author))
                    hits = dev_books.Search('%s - %s' % (title,author),
                                             self.SearchField.index('All'))
                    if hits:
                        hit = hits[0]
                        self.log.info("   found '%s' by %s (%s)" % (hit.Name, hit.Artist, hit.Composer))
                        return hit
                    else:
                        if DEBUG:
                            self.log.info("   no PDF hits")

                attempts -= 1
                time.sleep(0.5)
                if DEBUG:
                    self.log.warning("  attempt #%d" % (10 - attempts))

            if DEBUG:
                self.log.error("  no hits")
            return None

    def _find_library_book(self, search):
        '''
        Windows-only method to get a handle to a library book in the current pythoncom session
        '''
        if iswindows:
            if DEBUG:
                self.log.info(" ITUNES._find_library_book()")
                '''
                if 'uuid' in search:
                    self.log.info("  looking for '%s' by %s (%s)" %
                                (search['title'], search['author'], search['uuid']))
                else:
                    self.log.info("  looking for '%s' by %s" %
                                (search['title'], search['author']))
                '''

            for source in self.iTunes.sources:
                if source.Kind == self.Sources.index('Library'):
                    lib = source
                    if DEBUG:
                        self.log.info("  Library source: '%s'  kind: %s" % (lib.Name, self.Sources[lib.Kind]))
                    break
            else:
                if DEBUG:
                    self.log.info("  Library source not found")

            if lib is not None:
                lib_books = None
                for pl in lib.Playlists:
                    if pl.Kind == self.PlaylistKind.index('User') and \
                       pl.SpecialKind == self.PlaylistSpecialKind.index('Books'):
                        if DEBUG:
                            self.log.info("  Books playlist: '%s'" % (pl.Name))
                        lib_books = pl
                        break
                else:
                    if DEBUG:
                        self.log.error("  no Books playlist found")


            attempts = 9
            while attempts:
                # Find book whose Album field = search['uuid']
                if 'uuid' in search and search['uuid']:
                    if DEBUG:
                        self.log.info("   searching by uuid '%s' ..." % search['uuid'])
                    hits = lib_books.Search(search['uuid'],self.SearchField.index('All'))
                    if hits:
                        hit = hits[0]
                        if DEBUG:
                            self.log.info("   found '%s' by %s (%s)" % (hit.Name, hit.Artist, hit.Composer))
                        return hit

                # Search by author if known
                if search['author']:
                    if DEBUG:
                        self.log.info("   searching by author '%s' ..." % search['author'])
                    hits = lib_books.Search(search['author'],self.SearchField.index('Artists'))
                    if hits:
                        for hit in hits:
                            if hit.Name == search['title']:
                                if DEBUG:
                                    self.log.info("   found '%s' by %s (%s)" % (hit.Name, hit.Artist, hit.Composer))
                                return hit

                # Search by title if no author available
                if DEBUG:
                    self.log.info("   searching by title '%s' ..." % search['title'])
                hits = lib_books.Search(search['title'],self.SearchField.index('All'))
                if hits:
                    for hit in hits:
                        if hit.Name == search['title']:
                            if DEBUG:
                                self.log.info("   found '%s'" % (hit.Name))
                            return hit

                # PDF just sent, title not updated yet, look for export pattern
                # PDF metadata was rewritten at export as 'safe(title) - safe(author)'
                if search['format'] == 'pdf':
                    title = re.sub(r'[^0-9a-zA-Z ]', '_', search['title'])
                    author = re.sub(r'[^0-9a-zA-Z ]', '_', search['author'])
                    if DEBUG:
                        self.log.info("   searching by name: %s - %s" % (title,author))
                    hits = lib_books.Search('%s - %s' % (title,author),
                                             self.SearchField.index('All'))
                    if hits:
                        hit = hits[0]
                        self.log.info("   found '%s' by %s (%s)" % (hit.Name, hit.Artist, hit.Composer))
                        return hit
                    else:
                        if DEBUG:
                            self.log.info("   no PDF hits")

                attempts -= 1
                time.sleep(0.5)
                if DEBUG:
                    self.log.warning("   attempt #%d" % (10 - attempts))

            if DEBUG:
                self.log.error("  search for '%s' yielded no hits" % search['title'])
            return None

    def _generate_thumbnail(self, book_path, book):
        '''
        Convert iTunes artwork to thumbnail
        Cache generated thumbnails
        cache_dir = os.path.join(config_dir, 'caches', 'itunes')
        as of iTunes 9.2, iBooks 1.1, can't set artwork for PDF files via automation
        '''

        # self.settings().use_subdirs is a repurposed DeviceConfig field
        # We're using it to skip fetching/caching covers to speed things up
        if not self.settings().use_subdirs:
            thumb_data = None
            return thumb_data

        thumb_path = book_path.rpartition('.')[0] + '.jpg'
        if isosx:
            title = book.name()
        elif iswindows:
            title = book.Name

        try:
            zfr = ZipFile(self.archive_path)
            thumb_data = zfr.read(thumb_path)
            if thumb_data == 'None':
                if False:
                    self.log.info(" ITUNES._generate_thumbnail()\n   returning None from cover cache for '%s'" % title)
                zfr.close()
                return None
        except:
            zfw = ZipFile(self.archive_path, mode='a')
        else:
            if False:
                self.log.info("   returning thumb from cache for '%s'" % title)
            return thumb_data

        if DEBUG:
            self.log.info(" ITUNES._generate_thumbnail():")
        if isosx:

            # Fetch the artwork from iTunes
            try:
                data = book.artworks[1].raw_data().data
            except:
                # If no artwork, write an empty marker to cache
                if DEBUG:
                    self.log.error("  error fetching iTunes artwork for '%s'" % title)
                zfw.writestr(thumb_path, 'None')
                zfw.close()
                return None

            # Generate a thumb
            try:
                img_data = cStringIO.StringIO(data)
                im = PILImage.open(img_data)
                scaled, width, height = fit_image(im.size[0],im.size[1], 60, 80)
                im = im.resize((int(width),int(height)), PILImage.ANTIALIAS)

                thumb = cStringIO.StringIO()
                im.convert('RGB').save(thumb,'JPEG')
                thumb_data = thumb.getvalue()
                thumb.close()
                if False:
                    self.log.info("  generated thumb for '%s', caching" % title)
                # Cache the tagged thumb
                zfw.writestr(thumb_path, thumb_data)
            except:
                if DEBUG:
                    self.log.error("  error generating thumb for '%s', caching empty marker" % book.name())
                    self._dump_hex(data[:32])
                thumb_data = None
                # Cache the empty cover
                zfw.writestr(thumb_path, 'None')
            finally:
                img_data.close()
                zfw.close()

            return thumb_data


        elif iswindows:
            if not book.Artwork.Count:
                if DEBUG:
                    self.log.info("  no artwork available for '%s'" % book.Name)
                zfw.writestr(thumb_path, 'None')
                zfw.close()
                return None

            # Fetch the artwork from iTunes

            try:
                tmp_thumb = os.path.join(tempfile.gettempdir(), "thumb.%s" % self.ArtworkFormat[book.Artwork.Item(1).Format])
                book.Artwork.Item(1).SaveArtworkToFile(tmp_thumb)
                # Resize the cover
                im = PILImage.open(tmp_thumb)
                scaled, width, height = fit_image(im.size[0],im.size[1], 60, 80)
                im = im.resize((int(width),int(height)), PILImage.ANTIALIAS)
                thumb = cStringIO.StringIO()
                im.convert('RGB').save(thumb,'JPEG')
                thumb_data = thumb.getvalue()
                os.remove(tmp_thumb)
                thumb.close()
                if False:
                    self.log.info("  generated thumb for '%s', caching" % book.Name)
                # Cache the tagged thumb
                zfw.writestr(thumb_path, thumb_data)
            except:
                if DEBUG:
                    self.log.error("  error generating thumb for '%s', caching empty marker" % book.Name)
                thumb_data = None
                # Cache the empty cover
                zfw.writestr(thumb_path,'None')

            finally:
                zfw.close()

            return thumb_data

    def _get_device_book_size(self, file, compressed_size):
        '''
        Calculate the exploded size of file
        '''
        exploded_file_size = compressed_size
        format = file.rpartition('.')[2].lower()
        if format == 'epub':
            myZip = ZipFile(file,'r')
            myZipList = myZip.infolist()
            exploded_file_size = 0
            for file in myZipList:
                exploded_file_size += file.file_size
            if False:
                self.log.info(" ITUNES._get_device_book_size()")
                self.log.info("  %d items in archive" % len(myZipList))
                self.log.info("  compressed: %d  exploded: %d" % (compressed_size, exploded_file_size))
            myZip.close()
        return exploded_file_size

    def _get_device_books(self):
        '''
        Assumes pythoncom wrapper for Windows
        '''
        if DEBUG:
            self.log.info("\n ITUNES._get_device_books()")

        device_books = []
        if isosx:
            if 'iPod' in self.sources:
                connected_device = self.sources['iPod']
                device = self.iTunes.sources[connected_device]
                for pl in device.playlists():
                    if pl.special_kind() == appscript.k.Books:
                        if DEBUG:
                            self.log.info("  Book playlist: '%s'" % (pl.name()))
                        books = pl.file_tracks()
                        break
                else:
                    self.log.error("  book_playlist not found")

                for book in books:
                    # This may need additional entries for international iTunes users
                    if book.kind() in self.Audiobooks:
                        if DEBUG:
                            self.log.info("   ignoring '%s' of type '%s'" % (book.name(), book.kind()))
                    else:
                        if DEBUG:
                            self.log.info("   %-30.30s %-30.30s %-40.40s [%s]" %
                                          (book.name(), book.artist(), book.album(), book.kind()))
                        device_books.append(book)
                if DEBUG:
                    self.log.info()

        elif iswindows:
            if 'iPod' in self.sources:
                try:
                    pythoncom.CoInitialize()
                    connected_device = self.sources['iPod']
                    device = self.iTunes.sources.ItemByName(connected_device)

                    dev_books = None
                    for pl in device.Playlists:
                        if pl.Kind == self.PlaylistKind.index('User') and \
                           pl.SpecialKind == self.PlaylistSpecialKind.index('Books'):
                            if DEBUG:
                                self.log.info("  Books playlist: '%s'" % (pl.Name))
                            dev_books = pl.Tracks
                            break
                    else:
                        if DEBUG:
                            self.log.info("  no Books playlist found")

                    for book in dev_books:
                        # This may need additional entries for international iTunes users
                        if book.KindAsString in self.Audiobooks:
                            if DEBUG:
                                self.log.info("   ignoring '%s' of type '%s'" % (book.Name, book.KindAsString))
                        else:
                            if DEBUG:
                                self.log.info("   %-30.30s %-30.30s %-40.40s [%s]" % (book.Name, book.Artist, book.Album, book.KindAsString))
                            device_books.append(book)
                    if DEBUG:
                        self.log.info()

                finally:
                    pythoncom.CoUninitialize()

        return device_books

    def _get_device_books_playlist(self):
        '''
        assumes pythoncom wrapper
        '''
        if iswindows:
            if 'iPod' in self.sources:
                pl = None
                connected_device = self.sources['iPod']
                device = self.iTunes.sources.ItemByName(connected_device)

                for pl in device.Playlists:
                    if pl.Kind == self.PlaylistKind.index('User') and \
                       pl.SpecialKind == self.PlaylistSpecialKind.index('Books'):
                        break
                else:
                    if DEBUG:
                        self.log.error("  no iPad|Books playlist found")
                return pl

    def _get_fpath(self,file, metadata, format, update_md=False):
        '''
        If the database copy will be deleted after upload, we have to
        use file (the PersistentTemporaryFile), which will be around until
        calibre exits.
        If we're using the database copy, delete the plist
        '''
        if DEBUG:
            self.log.info(" ITUNES._get_fpath()")

        fpath = file
        if not getattr(fpath, 'deleted_after_upload', False):
            if getattr(file, 'orig_file_path', None) is not None:
                # Database copy
                fpath = file.orig_file_path
                self._delete_iTunesMetadata_plist(fpath)
            elif getattr(file, 'name', None) is not None:
                # PTF
                fpath = file.name
        else:
            # Recipe - PTF
            if DEBUG:
                self.log.info("   file will be deleted after upload")

        if format == 'epub' and update_md:
            self._update_epub_metadata(fpath, metadata)

        return fpath

    def _get_library_books(self):
        '''
        Populate a dict of paths from iTunes Library|Books
        Windows assumes pythoncom wrapper
        '''
        if DEBUG:
            self.log.info("\n ITUNES._get_library_books()")

        library_books = {}
        library_orphans = {}
        lib = None

        if isosx:
            for source in self.iTunes.sources():
                if source.kind() == appscript.k.library:
                    lib = source
                    if DEBUG:
                        self.log.info("  Library source: '%s'" % (lib.name()))
                    break
            else:
                if DEBUG:
                    self.log.error('  Library source not found')

            if lib is not None:
                lib_books = None
                if lib.playlists():
                    for pl in lib.playlists():
                        if pl.special_kind() == appscript.k.Books:
                            if DEBUG:
                                self.log.info("  Books playlist: '%s'" % (pl.name()))
                            break
                    else:
                        if DEBUG:
                            self.log.info("  no Library|Books playlist found")

                    lib_books = pl.file_tracks()
                    for book in lib_books:
                        # This may need additional entries for international iTunes users
                        if book.kind() in self.Audiobooks:
                            if DEBUG:
                                self.log.info("   ignoring '%s' of type '%s'" % (book.name(), book.kind()))
                        else:
                            # Collect calibre orphans - remnants of recipe uploads
                            format = 'pdf' if book.kind().startswith('PDF') else 'epub'
                            path = self.path_template % (book.name(), book.artist(),format)
                            if str(book.description()).startswith(self.description_prefix):
                                try:
                                    if book.location() == appscript.k.missing_value:
                                        library_orphans[path] = book
                                        if False:
                                            self.log.info("   found iTunes PTF '%s' in Library|Books" % book.name())
                                except:
                                    if DEBUG:
                                        self.log.error("   iTunes returned an error returning .location() with %s" % book.name())

                            library_books[path] = book
                            if DEBUG:
                                self.log.info("   %-30.30s %-30.30s %-40.40s [%s]" %
                                              (book.name(), book.artist(), book.album(), book.kind()))
                else:
                    if DEBUG:
                        self.log.info('  no Library playlists')
            else:
                if DEBUG:
                    self.log.info('  no Library found')

        elif iswindows:
            lib = None
            for source in self.iTunes.sources:
                if source.Kind == self.Sources.index('Library'):
                    lib = source
                    self.log.info("  Library source: '%s' kind: %s" % (lib.Name, self.Sources[lib.Kind]))
                    break
            else:
                self.log.error("  Library source not found")

            if lib is not None:
                lib_books = None
                if lib.Playlists is not None:
                    for pl in lib.Playlists:
                        if pl.Kind == self.PlaylistKind.index('User') and \
                           pl.SpecialKind == self.PlaylistSpecialKind.index('Books'):
                            if DEBUG:
                                self.log.info("  Books playlist: '%s'" % (pl.Name))
                            lib_books = pl.Tracks
                            break
                    else:
                        if DEBUG:
                            self.log.error("  no Library|Books playlist found")
                else:
                    if DEBUG:
                        self.log.error("  no Library playlists found")

                try:
                    for book in lib_books:
                        # This may need additional entries for international iTunes users
                        if book.KindAsString in self.Audiobooks:
                            if DEBUG:
                                self.log.info("   ignoring %-30.30s of type '%s'" % (book.Name, book.KindAsString))
                        else:
                            format = 'pdf' if book.KindAsString.startswith('PDF') else 'epub'
                            path = self.path_template % (book.Name, book.Artist,format)

                            # Collect calibre orphans
                            if book.Description.startswith(self.description_prefix):
                                if not book.Location:
                                    library_orphans[path] = book
                                    if False:
                                        self.log.info("   found iTunes PTF '%s' in Library|Books" % book.Name)

                            library_books[path] = book
                            if DEBUG:
                                self.log.info("   %-30.30s %-30.30s %-40.40s [%s]" % (book.Name, book.Artist, book.Album, book.KindAsString))
                except:
                    if DEBUG:
                        self.log.info(" no books in library")
        self.library_orphans = library_orphans
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
        Check for >1 iPod device connected to iTunes
        '''
        if isosx:
            try:
                names = [s.name() for s in self.iTunes.sources()]
                kinds = [str(s.kind()).rpartition('.')[2] for s in self.iTunes.sources()]
            except:
                # User probably quit iTunes
                return {}
        elif iswindows:
            # Assumes a pythoncom wrapper
            it_sources = ['Unknown','Library','iPod','AudioCD','MP3CD','Device','RadioTuner','SharedLibrary']
            names = [s.name for s in self.iTunes.sources]
            kinds = [it_sources[s.kind] for s in self.iTunes.sources]

        # If more than one connected iDevice, remove all from list to prevent driver initialization
        if kinds.count('iPod') > 1:
            if DEBUG:
                self.log.error("  %d connected iPod devices detected, calibre supports a single connected iDevice" % kinds.count('iPod'))
            while kinds.count('iPod'):
                index = kinds.index('iPod')
                kinds.pop(index)
                names.pop(index)

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
            self.log.info(" ITUNES:_launch_iTunes():\n  Instantiating iTunes")

        if isosx:
            '''
            Launch iTunes if not already running
            '''
            # Instantiate iTunes
            running_apps = appscript.app('System Events')
            if not 'iTunes' in running_apps.processes.name():
                if DEBUG:
                    self.log.info( "ITUNES:_launch_iTunes(): Launching iTunes" )
                try:
                    self.iTunes = iTunes= appscript.app('iTunes', hide=True)
                except:
                    self.iTunes = None
                    raise UserFeedback(' ITUNES._launch_iTunes(): unable to find installed iTunes', details=None, level=UserFeedback.WARN)

                iTunes.run()
                self.initial_status = 'launched'
            else:
                self.iTunes = appscript.app('iTunes')
                self.initial_status = 'already running'

            # Read the current storage path for iTunes media
            cmd = "defaults read com.apple.itunes NSNavLastRootDirectory"
            proc = subprocess.Popen( cmd, shell=True, cwd=os.curdir, stdout=subprocess.PIPE)
            proc.wait()
            media_dir = os.path.expanduser(proc.communicate()[0].strip())
            if os.path.exists(media_dir):
                self.iTunes_media = media_dir
            else:
                self.log.error("  could not confirm valid iTunes.media_dir from %s" % 'com.apple.itunes')
                self.log.error("  media_dir: %s" % media_dir)
            if DEBUG:
                self.log.info("  %s %s" % (__appname__, __version__))
                self.log.info("  [OSX %s - %s (%s), driver version %d.%d.%d]" %
                 (self.iTunes.name(), self.iTunes.version(), self.initial_status,
                  self.version[0],self.version[1],self.version[2]))
                self.log.info("  iTunes_media: %s" % self.iTunes_media)
                self.log.info("  calibre_library_path: %s" % self.calibre_library_path)

        if iswindows:
            '''
            Launch iTunes if not already running
            Assumes pythoncom wrapper

            *** Current implementation doesn't handle UNC paths correctly,
                and python has two incompatible methods to parse UNCs:
                os.path.splitdrive() and os.path.splitunc()
                need to use os.path.normpath on result of splitunc()

                Once you have the //server/share, convert with os.path.normpath('//server/share')
                os.path.splitdrive doesn't work as advertised, so use os.path.splitunc
                os.path.splitunc("//server/share") returns ('//server/share','')
                os.path.splitunc("C:/Documents") returns ('c:','/documents')
                os.path.normpath("//server/share") returns "\\\\server\\share"
            '''
            # Instantiate iTunes
            try:
                self.iTunes = win32com.client.Dispatch("iTunes.Application")
            except:
                self.iTunes = None
                raise UserFeedback(' ITUNES._launch_iTunes(): unable to find installed iTunes', details=None, level=UserFeedback.WARN)

            if not DEBUG:
                self.iTunes.Windows[0].Minimized = True
            self.initial_status = 'launched'

            # Read the current storage path for iTunes media from the XML file
            media_dir = ''
            string = None
            with open(self.iTunes.LibraryXMLPath, 'r') as xml:
                for line in xml:
                    if line.strip().startswith('<key>Music Folder'):
                        soup = BeautifulSoup(line)
                        string = soup.find('string').renderContents()
                        media_dir = os.path.abspath(string[len('file://localhost/'):].replace('%20',' '))
                        break
                if os.path.exists(media_dir):
                    self.iTunes_media = media_dir
                elif hasattr(string,'parent'):
                    self.log.error("  could not extract valid iTunes.media_dir from %s" % self.iTunes.LibraryXMLPath)
                    self.log.error("  %s" % string.parent.prettify())
                    self.log.error("  '%s' not found" % media_dir)
                else:
                    self.log.error("  no media dir found: string: %s" % string)

            if DEBUG:
                self.log.info("  %s %s" % (__appname__, __version__))
                self.log.info("  [Windows %s - %s (%s), driver version %d.%d.%d]" %
                 (self.iTunes.Windows[0].name, self.iTunes.Version, self.initial_status,
                  self.version[0],self.version[1],self.version[2]))
                self.log.info("  iTunes_media: %s" % self.iTunes_media)
                self.log.info("  calibre_library_path: %s" % self.calibre_library_path)

    def _purge_orphans(self,library_books, cached_books):
        '''
        Scan library_books for any paths not on device
        Remove any iTunes orphans originally added by calibre
        This occurs when the user deletes a book in iBooks while disconnected
        '''
        if DEBUG:
            self.log.info(" ITUNES._purge_orphans()")
            #self._dump_library_books(library_books)
            #self.log.info("  cached_books:\n   %s" % "\n   ".join(cached_books.keys()))

        for book in library_books:
            if isosx:
                if book not in cached_books and \
                   str(library_books[book].description()).startswith(self.description_prefix):
                    if DEBUG:
                        self.log.info("  '%s' not found on iDevice, removing from iTunes" % book)
                    btr = {   'title':library_books[book].name(),
                             'author':library_books[book].artist(),
                           'lib_book':library_books[book]}
                    self._remove_from_iTunes(btr)
            elif iswindows:
                if book not in cached_books and \
                   library_books[book].Description.startswith(self.description_prefix):
                    if DEBUG:
                        self.log.info("  '%s' not found on iDevice, removing from iTunes" % book)
                    btr = {   'title':library_books[book].Name,
                             'author':library_books[book].Artist,
                           'lib_book':library_books[book]}
                    self._remove_from_iTunes(btr)
        if DEBUG:
            self.log.info()

    def _remove_existing_copy(self, path, metadata):
        '''
        '''
        if DEBUG:
            self.log.info(" ITUNES._remove_existing_copy()")

        if self.manual_sync_mode:
            # Delete existing from Device|Books, add to self.update_list
            # for deletion from booklist[0] during add_books_to_metadata
            for book in self.cached_books:
                if self.cached_books[book]['uuid'] == metadata.uuid   or \
                   (self.cached_books[book]['title'] == metadata.title and \
                   self.cached_books[book]['author'] == metadata.authors[0]):
                    self.update_list.append(self.cached_books[book])
                    self._remove_from_device(self.cached_books[book])
                    if DEBUG:
                        self.log.info( "  deleting device book '%s'" % (metadata.title))
                    if not getattr(file, 'deleted_after_upload', False):
                        self._remove_from_iTunes(self.cached_books[book])
                        if DEBUG:
                            self.log.info("  deleting library book '%s'" % metadata.title)
                    break
            else:
                if DEBUG:
                    self.log.info("  '%s' not in cached_books" % metadata.title)
        else:
            # Delete existing from Library|Books, add to self.update_list
            # for deletion from booklist[0] during add_books_to_metadata
            for book in self.cached_books:
                if self.cached_books[book]['uuid'] == metadata.uuid   or \
                   (self.cached_books[book]['title'] == metadata.title and \
                    self.cached_books[book]['author'] == metadata.authors[0]):
                    self.update_list.append(self.cached_books[book])
                    self._remove_from_iTunes(self.cached_books[book])
                    if DEBUG:
                        self.log.info( "  deleting library book '%s'" %  metadata.title)
                    break
            else:
                if DEBUG:
                    self.log.info("  '%s' not found in cached_books" % metadata.title)

    def _remove_from_device(self, cached_book):
        '''
        Windows assumes pythoncom wrapper
        '''
        self.log.info(" ITUNES._remove_from_device()")
        if isosx:
            if DEBUG:
                self.log.info("  deleting '%s' from iDevice" % cached_book['title'])
            try:
                cached_book['dev_book'].delete()
            except:
                self.log.error("  error deleting '%s'" % cached_book['title'])
        elif iswindows:
            hit = self._find_device_book(cached_book)
            if hit:
                if DEBUG:
                    self.log.info("  deleting '%s' from iDevice" % cached_book['title'])
                hit.Delete()
            else:
                if DEBUG:
                    self.log.warning("   unable to remove '%s' by '%s' (%s) from device" %
                                     (cached_book['title'],cached_book['author'],cached_book['uuid']))

    def _remove_from_iTunes(self, cached_book):
        '''
        iTunes does not delete books from storage when removing from database
        We only want to delete stored copies if the file is stored in iTunes
        We don't want to delete files stored outside of iTunes.
        Also confirm that storage_path does not point into calibre's storage.
        '''
        if DEBUG:
            self.log.info(" ITUNES._remove_from_iTunes():")

        if isosx:
            try:
                storage_path = os.path.split(cached_book['lib_book'].location().path)
                if cached_book['lib_book'].location().path.startswith(self.iTunes_media) and \
                   not storage_path[0].startswith(self.calibre_library_path):
                    title_storage_path = storage_path[0]
                    if DEBUG:
                        self.log.info("  removing title_storage_path: %s" % title_storage_path)
                    try:
                        shutil.rmtree(title_storage_path)
                    except:
                        self.log.info("  '%s' not empty" % title_storage_path)

                    # Clean up title/author directories
                    author_storage_path = os.path.split(title_storage_path)[0]
                    self.log.info("  author_storage_path: %s" % author_storage_path)
                    author_files = os.listdir(author_storage_path)
                    if '.DS_Store' in author_files:
                        author_files.pop(author_files.index('.DS_Store'))
                    if not author_files:
                        shutil.rmtree(author_storage_path)
                        if DEBUG:
                            self.log.info("  removing empty author_storage_path")
                    else:
                        if DEBUG:
                            self.log.info("  author_storage_path not empty (%d objects):" % len(author_files))
                            self.log.info("  %s" % '\n'.join(author_files))
                else:
                    self.log.info("  '%s' (stored external to iTunes, no files deleted)" % cached_book['title'])

            except:
                # We get here if there was an error with .location().path
                if DEBUG:
                    self.log.info("   '%s' not in iTunes storage" % cached_book['title'])

            try:
                self.iTunes.delete(cached_book['lib_book'])
            except:
                if DEBUG:
                    self.log.info("   unable to remove '%s' from iTunes" % cached_book['title'])

        elif iswindows:
            '''
            Assume we're wrapped in a pythoncom
            Windows stores the book under a common author directory, so we just delete the .epub
            '''
            try:
                book = cached_book['lib_book']
                path = book.Location
            except:
                book = self._find_library_book(cached_book)
                if book:
                    path = book.Location

            if book:
                if self.iTunes_media and path.startswith(self.iTunes_media) and \
                   not path.startswith(self.calibre_library_path):
                    storage_path = os.path.split(path)
                    if DEBUG:
                        self.log.info("   removing '%s' at %s" %
                            (cached_book['title'], path))
                    try:
                        os.remove(path)
                    except:
                        self.log.warning("   '%s' not in iTunes storage" % path)
                    try:
                        os.rmdir(storage_path[0])
                        self.log.info("   removed folder '%s'" % storage_path[0])
                    except:
                        self.log.info("   folder '%s' not found or not empty" % storage_path[0])

                    # Delete from iTunes database
                else:
                    self.log.info("   '%s' (stored external to iTunes, no files deleted)" % cached_book['title'])
            else:
                if DEBUG:
                    self.log.info("   '%s' not found in iTunes" % cached_book['title'])
            try:
                book.Delete()
            except:
                if DEBUG:
                    self.log.info("   unable to remove '%s' from iTunes" % cached_book['title'])

    def title_sorter(self, title):
        return re.sub('^\s*A\s+|^\s*The\s+|^\s*An\s+', '', title).rstrip()

    def _update_epub_metadata(self, fpath, metadata):
        '''
        '''
        self.log.info(" ITUNES._update_epub_metadata()")

        # Fetch plugboard updates
        metadata_x = self._xform_metadata_via_plugboard(metadata, 'epub')

        # Refresh epub metadata
        with open(fpath,'r+b') as zfo:
            # Touch the OPF timestamp
            zf_opf = ZipFile(fpath,'r')
            fnames = zf_opf.namelist()
            opf = [x for x in fnames if '.opf' in x][0]
            if opf:
                opf_raw = cStringIO.StringIO(zf_opf.read(opf))
                soup = BeautifulSoup(opf_raw.getvalue())
                opf_raw.close()

                # Touch existing calibre timestamp
                md = soup.find('metadata')
                if md:
                    ts = md.find('meta',attrs={'name':'calibre:timestamp'})
                    if ts:
                        timestamp = ts['content']
                        old_ts = parse_date(timestamp)
                        metadata.timestamp = datetime.datetime(old_ts.year, old_ts.month, old_ts.day, old_ts.hour,
                                                   old_ts.minute, old_ts.second, old_ts.microsecond+1, old_ts.tzinfo)
                    else:
                        metadata.timestamp = isoformat(now())
                        if DEBUG:
                            self.log.info("   add timestamp: %s" % metadata.timestamp)
                else:
                    metadata.timestamp = isoformat(now())
                    if DEBUG:
                        self.log.warning("   missing <metadata> block in OPF file")
                        self.log.info("   add timestamp: %s" % metadata.timestamp)

                # Force the language declaration for iBooks 1.1
                #metadata.language = get_lang().replace('_', '-')

                # Updates from metadata plugboard (ignoring publisher)
                metadata.language = metadata_x.language

                if DEBUG:
                    if metadata.language != metadata_x.language:
                        self.log.info("   rewriting language: <dc:language>%s</dc:language>" % metadata.language)

            zf_opf.close()

            # If 'News' in tags, tweak the title/author for friendlier display in iBooks
            if _('News') in metadata.tags or \
               _('Catalog') in metadata.tags:
                if metadata.title.find('[') > 0:
                    metadata.title = metadata.title[:metadata.title.find('[')-1]
                date_as_author = '%s, %s %s, %s' % (strftime('%A'), strftime('%B'), strftime('%d').lstrip('0'), strftime('%Y'))
                metadata.author = metadata.authors = [date_as_author]
                sort_author =  re.sub('^\s*A\s+|^\s*The\s+|^\s*An\s+', '', metadata.title).rstrip()
                metadata.author_sort = '%s %s' % (sort_author, strftime('%Y-%m-%d'))

            # Remove any non-alpha category tags
            for tag in metadata.tags:
                if not self._is_alpha(tag[0]):
                    metadata.tags.remove(tag)

            # If windows & series, nuke tags so series used as Category during _update_iTunes_metadata()
            if iswindows and metadata.series:
                metadata.tags = None

            set_metadata(zfo, metadata, update_timestamp=True)

    def _update_device(self, msg='', wait=True):
        '''
        Trigger a sync, wait for completion
        '''
        if DEBUG:
            self.log.info(" ITUNES:_update_device():\n %s" % msg)

        if isosx:
            self.iTunes.update()

            if wait:
                # This works if iTunes has books not yet synced to iPad.
                if DEBUG:
                    sys.stdout.write("  waiting for iPad sync to complete ...")
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
                        sys.stdout.write("  waiting for iPad sync to complete ...")
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

    def _update_iTunes_metadata(self, metadata, db_added, lb_added, this_book):
        '''
        '''
        if DEBUG:
            self.log.info(" ITUNES._update_iTunes_metadata()")

        STRIP_TAGS = re.compile(r'<[^<]*?/?>')

        # Update metadata from plugboard
        # If self.plugboard is None (no transforms), original metadata is returned intact
        metadata_x = self._xform_metadata_via_plugboard(metadata, this_book.format)

        if isosx:
            if lb_added:
                lb_added.name.set(metadata_x.title)
                lb_added.album.set(metadata_x.title)
                lb_added.artist.set(authors_to_string(metadata_x.authors))
                lb_added.composer.set(metadata_x.uuid)
                lb_added.description.set("%s %s" % (self.description_prefix,strftime('%Y-%m-%d %H:%M:%S')))
                lb_added.enabled.set(True)
                lb_added.sort_artist.set(metadata_x.author_sort.title())
                lb_added.sort_name.set(metadata.title_sort)


            if db_added:
                db_added.name.set(metadata_x.title)
                db_added.album.set(metadata_x.title)
                db_added.artist.set(authors_to_string(metadata_x.authors))
                db_added.composer.set(metadata_x.uuid)
                db_added.description.set("%s %s" % (self.description_prefix,strftime('%Y-%m-%d %H:%M:%S')))
                db_added.enabled.set(True)
                db_added.sort_artist.set(metadata_x.author_sort.title())
                db_added.sort_name.set(metadata.title_sort)

            if metadata_x.comments:
                if lb_added:
                    lb_added.comment.set(STRIP_TAGS.sub('',metadata_x.comments))
                if db_added:
                    db_added.comment.set(STRIP_TAGS.sub('',metadata_x.comments))

            if metadata_x.rating:
                if lb_added:
                    lb_added.rating.set(metadata_x.rating*10)
                # iBooks currently doesn't allow setting rating ... ?
                try:
                    if db_added:
                        db_added.rating.set(metadata_x.rating*10)
                except:
                    pass

            # Set genre from series if available, else first alpha tag
            # Otherwise iTunes grabs the first dc:subject from the opf metadata
            # self.settings().read_metadata is used as a surrogate for "Use Series name as Genre"
            if metadata_x.series and self.settings().read_metadata:
                if DEBUG:
                    self.log.info(" ITUNES._update_iTunes_metadata()")
                    self.log.info("   using Series name as Genre")

                # Format the index as a sort key
                index = metadata_x.series_index
                integer = int(index)
                fraction = index-integer
                series_index = '%04d%s' % (integer, str('%0.4f' % fraction).lstrip('0'))
                if lb_added:
                    lb_added.sort_name.set("%s %s" % (self.title_sorter(metadata_x.series), series_index))
                    lb_added.episode_ID.set(metadata_x.series)
                    lb_added.episode_number.set(metadata_x.series_index)

                    # If no plugboard transform applied to tags, change the Genre/Category to Series
                    if metadata.tags == metadata_x.tags:
                        lb_added.genre.set(self.title_sorter(metadata_x.series))
                    else:
                        for tag in metadata_x.tags:
                            if self._is_alpha(tag[0]):
                                lb_added.genre.set(tag)
                                break

                if db_added:
                    db_added.sort_name.set("%s %s" % (self.title_sorter(metadata_x.series), series_index))
                    db_added.episode_ID.set(metadata_x.series)
                    db_added.episode_number.set(metadata_x.series_index)

                    # If no plugboard transform applied to tags, change the Genre/Category to Series
                    if metadata.tags == metadata_x.tags:
                        db_added.genre.set(self.title_sorter(metadata_x.series))
                    else:
                        for tag in metadata_x.tags:
                            if self._is_alpha(tag[0]):
                                db_added.genre.set(tag)
                                break


            elif metadata_x.tags is not None:
                if DEBUG:
                    self.log.info("   %susing Tag as Genre" %
                                  "no Series name available, " if self.settings().read_metadata else '')
                for tag in metadata_x.tags:
                    if self._is_alpha(tag[0]):
                        if lb_added:
                            lb_added.genre.set(tag)
                        if db_added:
                            db_added.genre.set(tag)
                        break

        elif iswindows:
            if lb_added:
                lb_added.Name = metadata_x.title
                lb_added.Album = metadata_x.title
                lb_added.Artist = authors_to_string(metadata_x.authors)
                lb_added.Composer = metadata_x.uuid
                lb_added.Description = ("%s %s" % (self.description_prefix,strftime('%Y-%m-%d %H:%M:%S')))
                lb_added.Enabled = True
                lb_added.SortArtist = metadata_x.author_sort.title()
                lb_added.SortName = metadata.title_sort

            if db_added:
                db_added.Name = metadata_x.title
                db_added.Album = metadata_x.title
                db_added.Artist = authors_to_string(metadata_x.authors)
                db_added.Composer = metadata_x.uuid
                db_added.Description = ("%s %s" % (self.description_prefix,strftime('%Y-%m-%d %H:%M:%S')))
                db_added.Enabled = True
                db_added.SortArtist = metadata_x.author_sort.title()
                db_added.SortName = metadata.title_sort

            if metadata_x.comments:
                if lb_added:
                    lb_added.Comment = (STRIP_TAGS.sub('',metadata_x.comments))
                if db_added:
                    db_added.Comment = (STRIP_TAGS.sub('',metadata_x.comments))

            if metadata_x.rating:
                if lb_added:
                    lb_added.AlbumRating = (metadata_x.rating*10)
                # iBooks currently doesn't allow setting rating ... ?
                try:
                    if db_added:
                        db_added.AlbumRating = (metadata_x.rating*10)
                except:
                    if DEBUG:
                        self.log.warning("  iTunes automation interface reported an error"
                                         " setting AlbumRating on iDevice")

            # Set Genre from first alpha tag, overwrite with series if available
            # Otherwise iBooks uses first <dc:subject> from opf
            # iTunes balks on setting EpisodeNumber, but it sticks (9.1.1.12)

            if metadata_x.series and self.settings().read_metadata:
                if DEBUG:
                    self.log.info("   using Series name as Genre")
                # Format the index as a sort key
                index = metadata_x.series_index
                integer = int(index)
                fraction = index-integer
                series_index = '%04d%s' % (integer, str('%0.4f' % fraction).lstrip('0'))
                if lb_added:
                    lb_added.SortName = "%s %s" % (self.title_sorter(metadata_x.series), series_index)
                    lb_added.EpisodeID = metadata_x.series
                    try:
                        lb_added.EpisodeNumber = metadata_x.series_index
                    except:
                        pass

                    # If no plugboard transform applied to tags, change the Genre/Category to Series
                    if metadata.tags == metadata_x.tags:
                        lb_added.Genre = self.title_sorter(metadata_x.series)
                    else:
                        for tag in metadata_x.tags:
                            if self._is_alpha(tag[0]):
                                lb_added.Genre = tag
                                break

                if db_added:
                    db_added.SortName = "%s %s" % (self.title_sorter(metadata_x.series), series_index)
                    db_added.EpisodeID = metadata_x.series
                    try:
                        db_added.EpisodeNumber = metadata_x.series_index
                    except:
                        if DEBUG:
                            self.log.warning("  iTunes automation interface reported an error"
                                             " setting EpisodeNumber on iDevice")

                    # If no plugboard transform applied to tags, change the Genre/Category to Series
                    if metadata.tags == metadata_x.tags:
                        db_added.Genre = self.title_sorter(metadata_x.series)
                    else:
                        for tag in metadata_x.tags:
                            if self._is_alpha(tag[0]):
                                db_added.Genre = tag
                                break

            elif metadata_x.tags is not None:
                if DEBUG:
                    self.log.info("   using Tag as Genre")
                for tag in metadata_x.tags:
                    if self._is_alpha(tag[0]):
                        if lb_added:
                            lb_added.Genre = tag
                        if db_added:
                            db_added.Genre = tag
                        break

    def _xform_metadata_via_plugboard(self, book, format):
        ''' Transform book metadata from plugboard templates '''
        if DEBUG:
            self.log.info("  ITUNES._update_metadata_from_plugboard()")

        if self.plugboard_func:
            pb = self.plugboard_func(self.DEVICE_PLUGBOARD_NAME, format, self.plugboards)
            newmi = book.deepcopy_metadata()
            newmi.template_to_attribute(book, pb)
            if DEBUG:
                self.log.info(" transforming %s using %s:" % (format, pb))
                self.log.info("       title: %s %s" % (book.title, ">>> %s" %
                                           newmi.title if book.title != newmi.title else ''))
                self.log.info("  title_sort: %s %s" % (book.title_sort, ">>> %s" %
                                           newmi.title_sort if book.title_sort != newmi.title_sort else ''))
                self.log.info("     authors: %s %s" % (book.authors, ">>> %s" %
                                           newmi.authors if book.authors != newmi.authors else ''))
                self.log.info(" author_sort: %s %s" % (book.author_sort, ">>> %s" %
                                           newmi.author_sort if book.author_sort != newmi.author_sort else ''))
                self.log.info("    language: %s %s" % (book.language, ">>> %s" %
                                           newmi.language if book.language != newmi.language else ''))
                self.log.info("   publisher: %s %s" % (book.publisher, ">>> %s" %
                                           newmi.publisher if book.publisher != newmi.publisher else ''))
                self.log.info("        tags: %s %s" % (book.tags, ">>> %s" %
                                           newmi.tags if book.tags != newmi.tags else ''))
        else:
            newmi = book
        return newmi


class ITUNES_ASYNC(ITUNES):
    '''
    This subclass allows the user to interact directly with iTunes via a menu option
    'Connect to iTunes' in Send to device.
    '''
    name = 'iTunes interface'
    gui_name = 'Apple iTunes'
    icon = I('devices/itunes.png')
    description    = _('Communicate with iTunes.')

    # Plugboard ID
    DEVICE_PLUGBOARD_NAME = 'APPLE'

    connected = False

    def __init__(self,path):
        if DEBUG:
            self.log.info("ITUNES_ASYNC:__init__()")

        if isosx and appscript is None:
            self.connected = False
            raise UserFeedback('OSX 10.5 or later required', details=None, level=UserFeedback.WARN)
            return
        else:
            self.connected = True

        if isosx:
            self._launch_iTunes()

        if iswindows:
            try:
                pythoncom.CoInitialize()
                self._launch_iTunes()
            except:
                raise UserFeedback('unable to launch iTunes', details=None, level=UserFeedback.WARN)
            finally:
                pythoncom.CoUninitialize()

        self.manual_sync_mode = False

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
                self.log.info("ITUNES_ASYNC:books()")
                if self.settings().use_subdirs:
                    self.log.info(" Cover fetching/caching enabled")
                else:
                    self.log.info(" Cover fetching/caching disabled")

            # Fetch a list of books from iTunes

            booklist = BookList(self.log)
            cached_books = {}

            if isosx:
                library_books = self._get_library_books()
                book_count = float(len(library_books))
                for (i,book) in enumerate(library_books):
                    format = 'pdf' if library_books[book].kind().startswith('PDF') else 'epub'
                    this_book = Book(library_books[book].name(), library_books[book].artist())
                    this_book.path = self.path_template % (library_books[book].name(),
                                                           library_books[book].artist(),
                                                           format)
                    try:
                        this_book.datetime = parse_date(str(library_books[book].date_added())).timetuple()
                    except:
                        this_book.datetime = time.gmtime()
                    this_book.db_id = None
                    this_book.device_collections = []
                    #this_book.library_id = library_books[this_book.path] if this_book.path in library_books else None
                    this_book.library_id = library_books[book]
                    this_book.size = library_books[book].size()
                    this_book.uuid = library_books[book].composer()
                    # Hack to discover if we're running in GUI environment
                    if self.report_progress is not None:
                        this_book.thumbnail = self._generate_thumbnail(this_book.path, library_books[book])
                    else:
                        this_book.thumbnail = None
                    booklist.add_book(this_book, False)

                    cached_books[this_book.path] = {
                     'title':library_books[book].name(),
                     'author':[library_books[book].artist()],
                     'lib_book':library_books[book],
                     'dev_book':None,
                     'uuid': library_books[book].composer(),
                     'format': format
                     }

                    if self.report_progress is not None:
                        self.report_progress(i+1/book_count, _('%d of %d') % (i+1, book_count))

            elif iswindows:
                try:
                    pythoncom.CoInitialize()
                    self.iTunes = win32com.client.Dispatch("iTunes.Application")
                    library_books = self._get_library_books()
                    book_count = float(len(library_books))
                    for (i,book) in enumerate(library_books):
                        this_book = Book(library_books[book].Name, library_books[book].Artist)
                        format = 'pdf' if library_books[book].KindAsString.startswith('PDF') else 'epub'
                        this_book.path = self.path_template % (library_books[book].Name,
                                                               library_books[book].Artist,
                                                               format)
                        try:
                            this_book.datetime = parse_date(str(library_books[book].DateAdded)).timetuple()
                        except:
                            this_book.datetime = time.gmtime()
                        this_book.db_id = None
                        this_book.device_collections = []
                        this_book.library_id = library_books[book]
                        this_book.size = library_books[book].Size
                        this_book.uuid = library_books[book].Composer
                        # Hack to discover if we're running in GUI environment
                        if self.report_progress is not None:
                            this_book.thumbnail = self._generate_thumbnail(this_book.path, library_books[book])
                        else:
                            this_book.thumbnail = None
                        booklist.add_book(this_book, False)

                        cached_books[this_book.path] = {
                         'title':library_books[book].Name,
                         'author':library_books[book].Artist,
                         'lib_book':library_books[book],
                         'uuid': library_books[book].Composer,
                         'format': format
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
                self._dump_booklist(booklist, 'returning from books()', indent=2)
                self._dump_cached_books('returning from books()',indent=2)
            return booklist

        else:
            return BookList(self.log)

    def eject(self):
        '''
        Un-mount / eject the device from the OS. This does not check if there
        are pending GUI jobs that need to communicate with the device.
        '''
        if DEBUG:
            self.log.info("ITUNES_ASYNC:eject()")
        self.iTunes = None
        self.connected = False

    def free_space(self, end_session=True):
        """
        Get free space available on the mountpoints:
          1. Main memory
          2. Card A
          3. Card B

        @return: A 3 element list with free space in bytes of (1, 2, 3). If a
        particular device doesn't have any of these locations it should return -1.
        """
        if DEBUG:
            self.log.info("ITUNES_ASYNC:free_space()")
        free_space = 0
        if isosx:
            s = os.statvfs(os.sep)
            free_space = s.f_bavail * s.f_frsize
        elif iswindows:
            free_bytes = ctypes.c_ulonglong(0)
            ctypes.windll.kernel32.GetDiskFreeSpaceExW(ctypes.c_wchar_p(os.sep), None, None, ctypes.pointer(free_bytes))
            free_space = free_bytes.value
        return (free_space,-1,-1)

    def get_device_information(self, end_session=True):
        """
        Ask device for device information. See L{DeviceInfoQuery}.
        @return: (device name, device version, software version on device, mime type)
        """
        if DEBUG:
            self.log.info("ITUNES_ASYNC:get_device_information()")

        return ('iTunes','hw v1.0','sw v1.0', 'mime type normally goes here')

    def is_usb_connected(self, devices_on_system, debug=False,
            only_presence=False):
        return self.connected, self

    def sync_booklists(self, booklists, end_session=True):
        '''
        Update metadata on device.
        @param booklists: A tuple containing the result of calls to
                                (L{books}(oncard=None), L{books}(oncard='carda'),
                                L{books}(oncard='cardb')).
        '''

        if DEBUG:
            self.log.info("ITUNES_ASYNC.sync_booklists()")

        # Inform user of any problem books
        if self.problem_titles:
            raise UserFeedback(self.problem_msg,
                                  details='\n'.join(self.problem_titles), level=UserFeedback.WARN)
        self.problem_titles = []
        self.problem_msg = None
        self.update_list = []

    def unmount_device(self):
        '''
        '''
        if DEBUG:
            self.log.info("ITUNES_ASYNC:unmount_device()")
        self.connected = False

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

class Book(Metadata):
    '''
    A simple class describing a book in the iTunes Books Library.
    See ebooks.metadata.book.base
    '''
    def __init__(self,title,author):

        Metadata.__init__(self, title, authors=[author])

