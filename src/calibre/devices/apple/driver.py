# -*- coding: utf-8 -*-

__license__   = 'GPL v3'
__copyright__ = '2010, Gregory Riker'
__docformat__ = 'restructuredtext en'


import cStringIO, os, re, shutil, sys, time, zipfile

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
    import appscript

#if iswindows:
#    import win32com.client

class ITUNES(DevicePlugin):

    name = 'Apple device interface'
    gui_name = 'Apple device'
    icon = I('devices/ipad.png')
    description    = _('Communicate with iBooks through iTunes.')
    supported_platforms = ['osx']
    author = 'GRiker'
    driver_version = '0.1'

    OPEN_FEEDBACK_MESSAGE = _(
        'Apple device detected, launching iTunes, please wait...')

    FORMATS = ['epub']

    VENDOR_ID = [0x05ac]
    # Product IDs:
    #  0x129a:iPad
    #  0x1292:iPhone 3G
    #PRODUCT_ID = [0x129a,0x1292]
    PRODUCT_ID = [0x129a]
    BCD = [0x01]

    # Properties
    cached_books = {}
    cache_dir = os.path.join(config_dir, 'caches', 'itunes')
    iTunes= None
    log = Log()
    path_template = 'iTunes/%s - %s.epub'
    presync = False
    update_list = []
    sources = None
    update_msg = None
    update_needed = False
    use_thumbnail_as_cover = False

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
            self.log.info( "ITUNES.add_books_to_metadata()")

        task_count = float(len(self.update_list))

        # Delete any obsolete copies of the book from the booklist
        if self.update_list:
            for (j,p_book) in enumerate(self.update_list):
                #self.log.info("ITUNES.add_books_to_metadata(): looking for %s" % p_book['lib_book'])
                for i,bl_book in enumerate(booklists[0]):
                    #self.log.info("ITUNES.add_books_to_metadata(): evaluating %s" % bl_book.library_id)
                    if bl_book.library_id == p_book['lib_book']:
                        booklists[0].pop(i)
                        #self.log.info("ITUNES.add_books_to_metadata(): removing %s" % p_book['title'])
                        break
                else:
                    self.log.error("ITUNES.add_books_to_metadata(): update_list item '%s' not found in booklists[0]" % p_book['title'])

                self.report_progress(j+1/task_count, _('Updating device metadata listing...'))
            self.report_progress(1.0, _('Updating device metadata listing...'))

        # Add new books to booklists[0]
        for new_book in locations[0]:
            booklists[0].append(new_book)

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
        if DEBUG:
            self.log.info("ITUNES:books(oncard=%s)" % oncard)

        if not oncard:
            # Fetch a list of books from iPod device connected to iTunes
            if isosx:

                # Fetch Library|Books
                library_books = self._get_library_books()

                if 'iPod' in self.sources:
                    device = self.sources['iPod']
                    if 'Books' in self.iTunes.sources[device].playlists.name():
                        booklist = BookList(self.log)
                        cached_books = {}
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
                            this_book.thumbnail = self._generate_thumbnail(this_book.path, book)

                            booklist.add_book(this_book, False)

                            cached_books[this_book.path] = {
                             'title':book.name(),
                             'author':book.artist(),
                             'lib_book':library_books[this_book.path] if this_book.path in library_books else None
                             }

                            self.report_progress(i+1/book_count, _('%d of %d' % (i+1, book_count)))

                        self.report_progress(1.0, _('finished'))
                        self.cached_books = cached_books
                        if DEBUG:
                            self._dump_cached_books()
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
        instantiate iTunes if necessary
        This gets called ~1x/second while device fingerprint is sensed
        '''

        if isosx:
            if self.iTunes:
                # Check for connected book-capable device
                try:
                    names = [s.name() for s in self.iTunes.sources()]
                    kinds = [str(s.kind()).rpartition('.')[2] for s in self.iTunes.sources()]
                    self.sources = sources = dict(zip(kinds,names))
                    if 'iPod' in sources:
                        if DEBUG:
                            sys.stdout.write('.')
                            sys.stdout.flush()
                        return True
                    else:
                        if DEBUG:
                            self.log.info("ITUNES.can_handle(): device ejected")
                        return False
                except:
                    # iTunes connection failed, probably not running anymore
                    self.log.error("ITUNES.can_handle(): lost connection to iTunes")
                    return False
            else:
                # can_handle() is called once before open(), so need to return True
                # to keep things going
                if DEBUG:
                    self.log.info("ITUNES:can_handle(): iTunes not yet instantiated")
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

        return False

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
        if DEBUG:
            self.log.info("ITUNES:card_prefix()")
        return (None,None)

    def delete_books(self, paths, end_session=True):
        '''
        Delete books at paths on device.
        iTunes doesn't let us directly delete a book on the device.
        If the requested paths are deletable (i.e., it's in the Library|Books list),
        delete the paths from the library, then update iPad

        '''
        undeletable_titles = []
        for path in paths:
            if self.cached_books[path]['lib_book']:
                if DEBUG:
                    self.log.info("ITUNES:delete_books(): Deleting '%s' from iTunes library" % (path))
                self._remove_iTunes_dir(self.cached_books[path])
                self.iTunes.delete(self.cached_books[path]['lib_book'])
                self.update_needed = True
                self.update_msg = "Deleted books from device"

            else:
                undeletable_titles.append(self.cached_books[path]['title'])

        if undeletable_titles:
            raise UserFeedback(_('You cannot delete purchased books. To do so delete them from the device itself. The books that could not be deleted are:'), details='\n'.join(undeletable_titles), level=UserFeedback.WARN)

    def eject(self):
        '''
        Un-mount / eject the device from the OS. This does not check if there
        are pending GUI jobs that need to communicate with the device.
        '''
        if DEBUG:
            self.log.info("ITUNES:eject(): ejecting '%s'" % self.sources['iPod'])
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
        if DEBUG:
            self.log.info("ITUNES:free_space()")

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
        if DEBUG:
            self.log.info("ITUNES:get_device_information()")

        return ('iPad','hw v1.0','sw v1.0', 'mime type')

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
        '''

        if isosx:
            # Launch iTunes if not already running
            if DEBUG:
                self.log.info("ITUNES:open(): Instantiating iTunes")

            # Instantiate iTunes
            running_apps = appscript.app('System Events')
            if not 'iTunes' in running_apps.processes.name():
                if DEBUG:
                    self.log.info( "ITUNES:open(): Launching iTunes" )
                self.iTunes = iTunes= appscript.app('iTunes', hide=True)
                iTunes.run()
                if DEBUG:
                    self.log.info( "%s - %s (launched), driver version %s" % \
                        (self.iTunes.name(), self.iTunes.version(), self.driver_version))
            else:
                self.iTunes = appscript.app('iTunes')
                if DEBUG:
                    self.log.info( " %s - %s (already running), driver version %s" % \
                        (self.iTunes.name(), self.iTunes.version(), self.driver_version))

            # Init the iTunes source list
            names = [s.name() for s in self.iTunes.sources()]
            kinds = [str(s.kind()).rpartition('.')[2] for s in self.iTunes.sources()]
            self.sources = dict(zip(kinds,names))

            # Check to see if Library|Books out of sync with Device|Books
            if 'iPod' in self.sources and self.presync:
                lb_count = len(self._get_library_books())
                db_count = len(self._get_device_books())
                pb_count = len(self._get_purchased_book_ids())
                if db_count != lb_count + pb_count:
                    if DEBUG:
                        self.log.info( "ITUNES.open(): pre-syncing iTunes with device")
                        self.log.info( " Library|Books         : %d" % lb_count)
                        self.log.info( " Devices|iPad|Books    : %d" % db_count)
                        self.log.info( " Devices|iPad|Purchased: %d" % pb_count)
                    self._update_device(msg="Presyncing iTunes with device, mismatched book count")
            else:
                if DEBUG:
                    self.log.info( "Skipping pre-sync check")

            # Create thumbs archive
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

        if iswindows:
            # Launch iTunes if not already running
            if DEBUG:
                self.log.info("ITUNES:open(): Instantiating iTunes")

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
                if DEBUG:
                    self.log.info("ITUNES.remove_books_from_metadata(): Removing '%s' from self.cached_books" % path)
                self.cached_books.pop(path)

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
        if DEBUG:
            self.log.info("ITUNES:set_progress_reporter()")
        self.report_progress = report_progress

    def settings(self):
        '''
        Should return an opts object. The opts object should have one attribute
        `format_map` which is an ordered list of formats for the device.
        '''
        if DEBUG:
            self.log.info("ITUNES.settings()")
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
            self._update_device(msg=self.update_msg)
            self.update_needed = False

        # Get actual size of updated books on device
        if self.update_list:
            if DEBUG:
                self.log.info("ITUNES:sync_booklists(): update_list:")
                for ub in self.update_list:
                    self.log.info(" '%s'" % ub['title'])

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
        :metadata: If not None, it is a list of :class:`MetaInformation` objects.
        The idea is to use the metadata to determine where on the device to
        put the book. len(metadata) == len(files). Apart from the regular
        cover (path to cover), there may also be a thumbnail attribute, which should
        be used in preference. The thumbnail attribute is of the form
        (width, height, cover_data as jpeg).
        '''

        new_booklist = []
        self.update_list = []

        if isosx:

            file_count = float(len(files))
            for (i,file) in enumerate(files):

                path = self.path_template % (metadata[i].title, metadata[i].author[0])

                # Delete existing from Library|Books, add to self.update_list
                # for deletion from booklist[0] during add_books_to_metadata
                if path in self.cached_books:
                    self.update_list.append(self.cached_books[path])

                    if DEBUG:
                        self.log.info("ITUNES.upload_books():")
                        self.log.info( " deleting existing '%s'" % (path))
                    self._remove_iTunes_dir(self.cached_books[path])
                    self.iTunes.delete(self.cached_books[path]['lib_book'])

                # Add to iTunes Library|Books
                if isinstance(file,PersistentTemporaryFile):
                    added = self.iTunes.add(appscript.mactypes.File(file._name))
                else:
                    added = self.iTunes.add(appscript.mactypes.File(file))

                thumb = None
                try:
                    if self.use_thumbnail_as_cover:
                        # Use thumbnail data as artwork
                        added.artworks[1].data_.set(metadata[i].thumbnail[2])
                        thumb = metadata[i].thumbnail[2]
                    else:
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

                    # Cache the thumbnail always, could be updated
                    if DEBUG:
                        self.log.info( " refreshing cached thumb for '%s'" % metadata[i].title)
                    archive_path = os.path.join(self.cache_dir, "thumbs.zip")
                    zfw = zipfile.ZipFile(archive_path, mode='a')
                    thumb_path = path.rpartition('.')[0] + '.jpg'
                    zfw.writestr(thumb_path, thumb)
                    zfw.close()
                except:
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
                added.comment.set("added by calibre %s" % strftime('%Y-%m-%d %H:%M:%S'))
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
                self.report_progress(i+1/file_count, _('%d of %d' % (i+1, file_count)))

            self.report_progress(1.0, _('finished'))

            # Tell sync_booklists we need a re-sync
            self.update_needed = True
            self.update_msg = "Added books to device"

        return (new_booklist, [], [])

    # Private methods
    def _dump_booklist(self,booklist, header="booklists[0]"):
        '''
        '''
        self.log.info()
        self.log.info(header)
        self.log.info( "%s" % ('-' * len(header)))
        for i,book in enumerate(booklist):
            self.log.info( "%2d %-25.25s %s" % (i,book.title, book.library_id))
        self.log.info()

    def _dump_cached_books(self):
        '''
        '''
        self.log.info("\n%-40.40s %-12.12s" % ('Device Books','In Library'))
        self.log.info("%-40.40s %-12.12s" % ('------------','----------'))
        for cb in self.cached_books.keys():
            self.log.info("%-40.40s %6.6s" % (self.cached_books[cb]['title'], 'yes' if self.cached_books[cb]['lib_book'] else ' no'))
        self.log.info("\n")

    def _hexdump(self, src, length=16):
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

    def _get_library_books(self):
        '''
        '''
        lib = self.iTunes.sources['library']
        library_books = {}
        if 'Books' in lib.playlists.name():
            lib_books = lib.playlists['Books'].file_tracks()
            for book in lib_books:
                path = self.path_template % (book.name(), book.artist())
                library_books[path] = book
        return library_books

    def _get_device_book_size(self, title, author):
        '''
        Fetch the size of a book stored on the device
        '''
        device_books = self._get_device_books()
        for d_book in device_books:
            if d_book.name() == title and d_book.artist() == author:
                return d_book.size()
        else:
            self.log.error("ITUNES._get_device_book_size(): could not find '%s' by '%s' in device_books" % (title,author))
            return None

    def _get_device_books(self):
        '''
        '''
        if 'iPod' in self.sources:
            device = self.sources['iPod']
            if 'Books' in self.iTunes.sources[device].playlists.name():
                return self.iTunes.sources[device].playlists['Books'].file_tracks()

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
            if DEBUG:
                self.log.info("ITUNES._generate_thumbnail(): cached thumb found for '%s'" % book.name())
            return thumb_data

        try:
            # Resize the cover
            data = book.artworks[1].raw_data().data
            #self._hexdump(data[:256])
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

    def _get_purchased_book_ids(self):
        '''
        '''
        if 'iPod' in self.sources:
            device = self.sources['iPod']
            if 'Purchased' in self.iTunes.sources[device].playlists.name():
                return [pb.database_ID() for pb in self.iTunes.sources[device].playlists['Purchased'].file_tracks()]
            else:
                return []

    def _is_alpha(self,char):
        '''
        '''
        if not re.search('[a-zA-Z]',char):
            return False
        else:
            return True

    def _remove_iTunes_dir(self, cached_book):
        '''
        iTunes does not delete books from storage when removing from database
        '''
        storage_path = os.path.split(cached_book['lib_book'].location().path)
        if DEBUG:
            self.log.info( "ITUNES._remove_iTunes_dir():")
            self.log.info( " removing storage_path: %s" % storage_path[0])
        shutil.rmtree(storage_path[0])

    def _update_device(self, msg='', wait=True):
        '''

        '''
        if DEBUG:
            self.log.info("ITUNES:_update_device(): %s" % msg)
        self.iTunes.update()

        if wait:
            # This works if iTunes has books not yet synced to iPad.
            if DEBUG:
                self.log.info("Waiting for iPad sync to complete ...",)
            while len(self._get_device_books()) != (len(self._get_library_books()) + len(self._get_purchased_book_ids())):
                if DEBUG:
                    sys.stdout.write('.')
                    sys.stdout.flush()
                time.sleep(2)
            print

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
        if DEBUG:
            self.log.info("BookList.add_book(): adding %s" % book)
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
