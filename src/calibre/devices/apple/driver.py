# -*- coding: utf-8 -*-

__license__ = 'GPL v3'
__copyright__ = '2010, Gregory Riker'
__docformat__ = 'restructuredtext en'


import cStringIO, ctypes, datetime, os, platform, re, shutil, sys, tempfile, time

from calibre.constants import __appname__, __version__, cache_dir, DEBUG as CALIBRE_DEBUG
from calibre import fit_image, confirm_config_name, strftime as _strftime
from calibre.constants import isosx, iswindows, cache_dir as _cache_dir
from calibre.devices.errors import OpenFeedback, UserFeedback
from calibre.devices.usbms.deviceconfig import DeviceConfig
from calibre.devices.interface import DevicePlugin
from calibre.ebooks.metadata import (author_to_author_sort, authors_to_string,
    MetaInformation, title_sort)
from calibre.ebooks.metadata.book.base import Metadata
from calibre.utils.config import config_dir, dynamic, prefs
from calibre.utils.date import now, parse_date
from calibre.utils.zipfile import ZipFile

DEBUG = False
#DEBUG = CALIBRE_DEBUG

def strftime(fmt='%Y/%m/%d %H:%M:%S', dt=None):

    if not hasattr(dt, 'timetuple'):
        dt = now()
    dt = dt.timetuple()
    try:
        return _strftime(fmt, dt)
    except:
        return _strftime(fmt, now().timetuple())

_log = None
def logger():
    global _log
    if _log is None:
        from calibre.utils.logging import ThreadSafeLog
        _log = ThreadSafeLog()
    return _log


class AppleOpenFeedback(OpenFeedback):

    def __init__(self, plugin):
        OpenFeedback.__init__(self, u'')
        self.plugin = plugin

    def custom_dialog(self, parent):
        from PyQt4.Qt import (QDialog, QDialogButtonBox, QIcon,
                              QLabel, QPushButton, QVBoxLayout)

        class Dialog(QDialog):

            def __init__(self, p, cd, pixmap='dialog_information.png'):
                QDialog.__init__(self, p)
                self.cd = cd
                self.setWindowTitle("Apple iDevice detected")
                self.l = l = QVBoxLayout()
                self.setLayout(l)
                msg = QLabel()
                msg.setText(_(
                            '<p>If you do not want calibre to recognize your Apple iDevice '
                            'when it is connected to your computer, '
                            'click <b>Disable Apple Driver</b>.</p>'
                            '<p>To transfer books to your iDevice, '
                            'click <b>Disable Apple Driver</b>, '
                            "then use the 'Connect to iTunes' method recommended in the "
                            '<a href="http://www.mobileread.com/forums/showthread.php?t=118559">Calibre + iDevices FAQ</a>, '
                            'using the <em>Connect/Share</em>|<em>Connect to iTunes</em> menu item.</p>'
                            '<p>Enabling the Apple driver for direct connection to iDevices '
                            'is an unsupported advanced user mode.</p>'
                            '<p></p>'
                            ))
                msg.setOpenExternalLinks(True)
                msg.setWordWrap(True)
                l.addWidget(msg)

                self.bb = QDialogButtonBox()
                disable_driver = QPushButton(_("Disable Apple driver"))
                disable_driver.setDefault(True)
                self.bb.addButton(disable_driver, QDialogButtonBox.RejectRole)

                enable_driver = QPushButton(_("Enable Apple driver"))
                self.bb.addButton(enable_driver, QDialogButtonBox.AcceptRole)
                l.addWidget(self.bb)
                self.bb.accepted.connect(self.accept)
                self.bb.rejected.connect(self.reject)

                self.setWindowIcon(QIcon(I(pixmap)))
                self.resize(self.sizeHint())

                self.finished.connect(self.do_it)

            def do_it(self, return_code):
                from calibre.utils.logging import default_log
                if return_code == self.Accepted:
                    default_log.info(" Apple driver ENABLED")
                    dynamic[confirm_config_name(self.cd.plugin.DISPLAY_DISABLE_DIALOG)] = False
                else:
                    from calibre.customize.ui import disable_plugin
                    default_log.info(" Apple driver DISABLED")
                    disable_plugin(self.cd.plugin)

        return Dialog(parent, self)


class DriverBase(DeviceConfig, DevicePlugin):
    # Needed for config_widget to work
    FORMATS = ['epub', 'pdf']
    USER_CAN_ADD_NEW_FORMATS = False
    KEEP_TEMP_FILES_AFTER_UPLOAD = True
    CAN_DO_DEVICE_DB_PLUGBOARD = True

    # Hide the standard customization widgets
    SUPPORTS_SUB_DIRS = False
    MUST_READ_METADATA = True
    SUPPORTS_USE_AUTHOR_SORT = False

    EXTRA_CUSTOMIZATION_MESSAGE = [
            _('Use Series as Category in iTunes/iBooks') +
            ':::' + _('Enable to use the series name as the iTunes Genre, '
                    'iBooks Category'),
            _('Cache covers from iTunes/iBooks') +
                ':::' +
                _('Enable to cache and display covers from iTunes/iBooks'),
            _(u'"Copy files to iTunes Media folder %s" is enabled in iTunes Preferences|Advanced') % u'\u2026' +
                ':::' +
                _("<p>This setting should match your iTunes <i>Preferences</i>|<i>Advanced</i> setting.</p>"
                  "<p>Disabling will store copies of books transferred to iTunes in your calibre configuration directory.</p>"
                  "<p>Enabling indicates that iTunes is configured to store copies in your iTunes Media folder.</p>")
    ]
    EXTRA_CUSTOMIZATION_DEFAULT = [
                True,
                True,
                False,
    ]

    @classmethod
    def _config_base_name(cls):
        return 'iTunes'


class ITUNES(DriverBase):
    '''
    Calling sequences:
    Initialization:
        can_handle() | can_handle_windows()
         _launch_iTunes()
        reset()
        open()
        card_prefix()
        can_handle()
         _launch_iTunes()
         _discover_manual_sync_mode()
        set_progress_reporter()
        get_device_information()
        card_prefix()
        free_space()
        (Job 1 Get device information finishes)
        can_handle()
        set_progress_reporter()
        books() (once for each storage point)
         (create self.cached_books)
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
         _remove_existing_copy()
          _remove_from_device()
          _remove_from_iTunes()
         _add_new_copy()
          _add_library_book()
         _update_iTunes_metadata()
        add_books_to_metadata()
        use_plugboard_ext()
        set_plugboard()
        set_progress_reporter()
        sync_booklists()
        card_prefix()
        free_space()
    '''

    name = 'Apple iTunes interface'
    gui_name = _('Apple device')
    icon = I('devices/ipad.png')
    description = _('Communicate with iTunes/iBooks.')
    supported_platforms = ['osx', 'windows']
    author = 'GRiker'
    #: The version of this plugin as a 3-tuple (major, minor, revision)
    version = (1, 1, 1)

    DISPLAY_DISABLE_DIALOG = "display_disable_apple_driver_dialog"

    # EXTRA_CUSTOMIZATION_MESSAGE indexes
    USE_SERIES_AS_CATEGORY = 0
    CACHE_COVERS = 1
    USE_ITUNES_STORAGE = 2

    OPEN_FEEDBACK_MESSAGE = _(
        'Apple iDevice detected, launching iTunes, please wait ...')
    BACKLOADING_ERROR_MESSAGE = _(
        "Cannot copy books directly from iDevice. "
        "Drag from iTunes Library to desktop, then add to calibre's Library window.")
    UNSUPPORTED_DIRECT_CONNECT_MODE_MESSAGE = _(
        "*** Unsupported direct connect mode. "
        "See http://www.mobileread.com/forums/showthread.php?t=118559 "
        "for instructions on using 'Connect to iTunes' ***")
    ITUNES_SANDBOX_LOCKOUT_MESSAGE = _(
        '<p>Unable to communicate with iTunes.</p>'
        '<p>Refer to this '
        '<a href="http://www.mobileread.com/forums/showpost.php?p=2113958&postcount=3">forum post</a> '
        'for more information.</p>'
        '<p></p>')

    VENDOR_ID = []
    PRODUCT_ID = []
    BCD = []

    # Plugboard ID
    DEVICE_PLUGBOARD_NAME = 'APPLE'

    # iTunes enumerations
    Audiobooks = [
        'AAC audio file',
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
    cache_dir = os.path.join(_cache_dir(), 'itunes')
    archive_path = os.path.join(cache_dir, "thumbs.zip")
    calibre_library_path = prefs['library_path']
    description_prefix = "added by calibre"
    ejected = False
    iTunes = None
    iTunes_local_storage = None
    library_orphans = None
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

    @property
    def cache_dir(self):
        return os.path.join(cache_dir(), 'itunes')

    @property
    def archive_path(self):
        return os.path.join(self.cache_dir, "thumbs.zip")

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
            logger().info("%s.add_books_to_metadata()" % self.__class__.__name__)

        task_count = float(len(self.update_list))

        # Delete any obsolete copies of the book from the booklist
        if self.update_list:
            if False:
                self._dump_booklist(booklists[0], header='before', indent=2)
                self._dump_update_list(header='before', indent=2)
                self._dump_cached_books(header='before', indent=2)

            for (j, p_book) in enumerate(self.update_list):
                if False:
                    if isosx:
                        logger().info("  looking for '%s' by %s uuid:%s" %
                            (p_book['title'], p_book['author'], p_book['uuid']))
                    elif iswindows:
                        logger().info(" looking for '%s' by %s (%s)" %
                                        (p_book['title'], p_book['author'], p_book['uuid']))

                # Purge the booklist, self.cached_books
                for i, bl_book in enumerate(booklists[0]):
                    if bl_book.uuid == p_book['uuid']:
                        # Remove from booklists[0]
                        booklists[0].pop(i)
                        if False:
                            if isosx:
                                logger().info("  removing old %s %s from booklists[0]" %
                                    (p_book['title'], str(p_book['lib_book'])[-9:]))
                            elif iswindows:
                                logger().info(" removing old '%s' from booklists[0]" %
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
                                            self._dump_cached_book(self.cached_books[cb], header="removing from self.cached_books:", indent=2)
                                        self.cached_books.pop(cb)
                                        break
                            break
                if self.report_progress is not None:
                    self.report_progress((j + 1) / task_count, _('Updating device metadata listing...'))

            if self.report_progress is not None:
                self.report_progress(1.0, _('Updating device metadata listing...'))

        # Add new books to booklists[0]
        # Charles thinks this should be
        # for new_book in metadata[0]:
        for new_book in locations[0]:
            if DEBUG:
                logger().info("  adding '%s' by '%s' to booklists[0]" %
                    (new_book.title, new_book.author))
            booklists[0].append(new_book)

        if False:
            self._dump_booklist(booklists[0], header='after', indent=2)
            self._dump_cached_books(header='after', indent=2)

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
                logger().info("%s.books():" % self.__class__.__name__)
                if self.settings().extra_customization[self.CACHE_COVERS]:
                    logger().info(" Cover fetching/caching enabled")
                else:
                    logger().info(" Cover fetching/caching disabled")

            # Fetch a list of books from iDevice connected to iTunes
            if 'iPod' in self.sources:
                booklist = BookList(logger())
                cached_books = {}

                if isosx:
                    library_books = self._get_library_books()
                    device_books = self._get_device_books()
                    book_count = float(len(device_books))
                    for (i, book) in enumerate(device_books):
                        this_book = Book(book.name(), book.artist())
                        format = 'pdf' if book.kind().startswith('PDF') else 'epub'
                        this_book.path = self.path_template % (book.name(), book.artist(), format)
                        try:
                            this_book.datetime = parse_date(str(book.date_added())).timetuple()
                        except:
                            this_book.datetime = time.gmtime()
                        this_book.device_collections = []
                        this_book.library_id = library_books[this_book.path] if this_book.path in library_books else None
                        this_book.size = book.size()
                        this_book.uuid = book.composer()
                        this_book.cid = None
                        # Hack to discover if we're running in GUI environment
                        if self.report_progress is not None:
                            this_book.thumbnail = self._generate_thumbnail(this_book.path, book)
                        else:
                            this_book.thumbnail = None
                        booklist.add_book(this_book, False)

                        cached_books[this_book.path] = {
                         'title': book.name(),
                         'author': book.artist(),
                         'authors': book.artist().split(' & '),
                         'lib_book': library_books[this_book.path] if this_book.path in library_books else None,
                         'dev_book': book,
                         'uuid': book.composer()
                         }

                        if self.report_progress is not None:
                            self.report_progress((i + 1) / book_count,
                                _('%(num)d of %(tot)d') % dict(num=i + 1, tot=book_count))
                    self._purge_orphans(library_books, cached_books)

                elif iswindows:
                    import pythoncom, win32com.client
                    try:
                        pythoncom.CoInitialize()
                        self.iTunes = win32com.client.Dispatch("iTunes.Application")
                        library_books = self._get_library_books()
                        device_books = self._get_device_books()
                        book_count = float(len(device_books))
                        for (i, book) in enumerate(device_books):
                            this_book = Book(book.Name, book.Artist)
                            format = 'pdf' if book.KindAsString.startswith('PDF') else 'epub'
                            this_book.path = self.path_template % (book.Name, book.Artist, format)
                            try:
                                this_book.datetime = parse_date(str(book.DateAdded)).timetuple()
                            except:
                                this_book.datetime = time.gmtime()
                            this_book.device_collections = []
                            this_book.library_id = library_books[this_book.path] if this_book.path in library_books else None
                            this_book.size = book.Size
                            this_book.cid = None
                            # Hack to discover if we're running in GUI environment
                            if self.report_progress is not None:
                                this_book.thumbnail = self._generate_thumbnail(this_book.path, book)
                            else:
                                this_book.thumbnail = None
                            booklist.add_book(this_book, False)

                            cached_books[this_book.path] = {
                             'title': book.Name,
                             'author': book.Artist,
                             'authors': book.Artist.split(' & '),
                             'lib_book': library_books[this_book.path] if this_book.path in library_books else None,
                             'uuid': book.Composer,
                             'format': 'pdf' if book.KindAsString.startswith('PDF') else 'epub'
                             }

                            if self.report_progress is not None:
                                self.report_progress((i + 1) / book_count,
                                        _('%(num)d of %(tot)d') % dict(num=i + 1,
                                            tot=book_count))
                        self._purge_orphans(library_books, cached_books)

                    finally:
                        pythoncom.CoUninitialize()

                if self.report_progress is not None:
                    self.report_progress(1.0, _('finished'))
                self.cached_books = cached_books
                if DEBUG:
                    self._dump_booklist(booklist, 'returning from books()', indent=2)
                    self._dump_cached_books('returning from books()', indent=2)
                return booklist
        else:
            return BookList(logger())

    def can_handle(self, device_info, debug=False):
        '''
        OSX version of :method:`can_handle_windows`

        :param device_info: Is a tupe of (vid, pid, bcd, manufacturer, product,
        serial number)

        Confirm that:
            - iTunes is running
            - there is an iDevice connected
        This gets called first when the device fingerprint is read, so it needs to
        instantiate iTunes if necessary
        This gets called ~1x/second while device fingerprint is sensed
        '''
        try:
            import appscript
            appscript
        except:
            appscript = None
        if appscript is None:
            return False

        if self.iTunes:
            # Check for connected book-capable device
            self.sources = self._get_sources()
            if 'iPod' in self.sources and not self.ejected:
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
                logger().info("%s.can_handle()" % self.__class__.__name__)

            self._launch_iTunes()
            self.sources = self._get_sources()
            if (not 'iPod' in self.sources) or (self.sources['iPod'] == ''):
                attempts = 9
                while attempts:
                    # If iTunes was just launched, device may not be detected yet
                    self.sources = self._get_sources()
                    if (not 'iPod' in self.sources) or (self.sources['iPod'] == ''):
                        attempts -= 1
                        time.sleep(1.0)
                        if DEBUG:
                            logger().warning(" waiting for connected iDevice, attempt #%d" % (10 - attempts))
                    else:
                        if DEBUG:
                            logger().info(' found connected iDevice')
                        break
                else:
                    # iTunes running, but not connected iPad
                    if DEBUG:
                        logger().info(' self.ejected = True')
                    self.ejected = True
                    return False

            self._discover_manual_sync_mode(wait=2 if self.initial_status == 'launched' else 0)
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
        import pythoncom

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
                        logger().info("%s.can_handle_windows:\n confirming connected iPad" % self.__class__.__name__)
                    self.ejected = False
                    self._discover_manual_sync_mode()
                    return True
                else:
                    if DEBUG:
                        logger().info("%s.can_handle_windows():\n device ejected" % self.__class__.__name__)
                    self.ejected = True
                    return False
            except:
                # iTunes connection failed, probably not running anymore

                logger().error("%s.can_handle_windows():\n lost connection to iTunes" % self.__class__.__name__)
                return False
            finally:
                pythoncom.CoUninitialize()

        else:
            if DEBUG:
                logger().info("%s.can_handle_windows():\n Launching iTunes" % self.__class__.__name__)

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
                            time.sleep(1.0)
                            if DEBUG:
                                logger().warning(" waiting for connected iDevice, attempt #%d" % (10 - attempts))
                        else:
                            if DEBUG:
                                logger().info(' found connected iPad in iTunes')
                            break
                    else:
                        # iTunes running, but not connected iPad
                        if DEBUG:
                            logger().info(' iDevice has been ejected')
                        self.ejected = True
                        return False

                logger().info(' found connected iPad in sources')
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
        return (None, None)

    @classmethod
    def config_widget(cls):
        '''
        Return a QWidget with settings for the device interface
        '''
        cw = DriverBase.config_widget()
        # Turn off the Save template
        cw.opt_save_template.setVisible(False)
        cw.label.setVisible(False)
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
        logger().info("%s.delete_books()" % self.__class__.__name__)
        for path in paths:
            if self.cached_books[path]['lib_book']:
                if DEBUG:
                    logger().info(" Deleting '%s' from iTunes library" % (path))

                if isosx:
                    self._remove_from_iTunes(self.cached_books[path])
                    if self.manual_sync_mode:
                        self._remove_from_device(self.cached_books[path])
                elif iswindows:
                    import pythoncom, win32com.client
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
                    logger().info(" skipping sync phase, manual_sync_mode: True")
            else:
                if self.manual_sync_mode:
                    metadata = MetaInformation(self.cached_books[path]['title'],
                                               self.cached_books[path]['authors'])
                    metadata.author = self.cached_books[path]['author']
                    metadata.uuid = self.cached_books[path]['uuid']
                    if not metadata.uuid:
                        metadata.uuid = "unknown"

                    if isosx:
                        self._remove_existing_copy(self.cached_books[path], metadata)
                    elif iswindows:
                        try:
                            pythoncom.CoInitialize()
                            self.iTunes = win32com.client.Dispatch("iTunes.Application")
                            self._remove_existing_copy(self.cached_books[path], metadata)
                        finally:
                            pythoncom.CoUninitialize()

                else:
                    self.problem_titles.append("'%s' by %s" %
                     (self.cached_books[path]['title'], self.cached_books[path]['author']))

    def eject(self):
        '''
        Un-mount / eject the device from the OS. This does not check if there
        are pending GUI jobs that need to communicate with the device.
        '''
        if DEBUG:
            logger().info("%s:eject(): ejecting '%s'" % (self.__class__.__name__, self.sources['iPod']))
        if isosx:
            self.iTunes.eject(self.sources['iPod'])
        elif iswindows:
            if 'iPod' in self.sources:
                import pythoncom, win32com.client

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
            logger().info("%s.free_space()" % self.__class__.__name__)

        free_space = 0
        if isosx:
            if 'iPod' in self.sources:
                connected_device = self.sources['iPod']
                free_space = self.iTunes.sources[connected_device].free_space()

        elif iswindows:
            if 'iPod' in self.sources:
                import pythoncom, win32com.client

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
                        logger().error(' waiting for free_space() call to go through')

        return (free_space, -1, -1)

    def get_device_information(self, end_session=True):
        """
        Ask device for device information. See L{DeviceInfoQuery}.
        @return: (device name, device version, software version on device, mime type)
        """
        if DEBUG:
            logger().info("%s.get_device_information()" % self.__class__.__name__)

        return (self.sources['iPod'], 'hw v1.0', 'sw v1.0', 'unknown mime type')

    def get_file(self, path, outfile, end_session=True):
        '''
        Read the file at C{path} on the device and write it to outfile.
        @param outfile: file object like C{sys.stdout} or the result of an C{open} call
        '''
        if DEBUG:
            logger().info("%s.get_file(): exporting '%s'" % (self.__class__.__name__, path))

        try:
            outfile.write(open(self.cached_books[path]['lib_book'].location().path).read())
        except:
            # Clean up
            logger().info(" unable to extract books from iDevices")
            logger().info(" deleting empty ", outfile.name)
            outfile.close()
            os.remove(outfile.name)
            raise UserFeedback("Unable to extract books from iDevices", details=None, level=UserFeedback.WARN)

    def open(self, connected_device, library_uuid):
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

        if self.iTunes is None:
            raise OpenFeedback(self.ITUNES_SANDBOX_LOCKOUT_MESSAGE)

        if DEBUG:
            vendor_id = "0x%x" % connected_device[0]
            product_id = "0x%x" % connected_device[1]
            bcd = "0x%x" % connected_device[2]
            mfg = connected_device[3]
            model = connected_device[4]
            logger().info("%s.open(MFG: %s, VENDOR_ID: %s, MODEL: %s, BCD: %s, PRODUCT_ID: %s)" %
                          (self.__class__.__name__,
                           mfg,
                           vendor_id,
                           model,
                           bcd,
                           product_id
                           ))

        if False:
            # Display a dialog recommending using 'Connect to iTunes' if user hasn't
            # previously disabled the dialog
            if dynamic.get(confirm_config_name(self.DISPLAY_DISABLE_DIALOG), True):
                raise AppleOpenFeedback(self)
            else:
                if DEBUG:
                    logger().info(" %s" % self.UNSUPPORTED_DIRECT_CONNECT_MODE_MESSAGE)

        # Log supported DEVICE_IDs and BCDs
        if DEBUG:
            logger().info(" BCD: %s" % ['0x%x' % x for x in sorted(self.BCD)])
            logger().info(" PRODUCT_ID: %s" % ['0x%x' % x for x in sorted(self.PRODUCT_ID)])

        # Confirm/create thumbs archive
        if not os.path.exists(self.cache_dir):
            if DEBUG:
                logger().info(" creating thumb cache at '%s'" % self.cache_dir)
            os.makedirs(self.cache_dir)

        if not os.path.exists(self.archive_path):
            logger().info(" creating zip archive")
            zfw = ZipFile(self.archive_path, mode='w')
            zfw.writestr("iTunes Thumbs Archive", '')
            zfw.close()
        else:
            if DEBUG:
                logger().info(" existing thumb cache at '%s'" % self.archive_path)

        # If enabled in config options, create/confirm an iTunes storage folder
        if not self.settings().extra_customization[self.USE_ITUNES_STORAGE]:
            self.iTunes_local_storage = os.path.join(config_dir, 'iTunes storage')
            if not os.path.exists(self.iTunes_local_storage):
                if DEBUG:
                    logger()(" creating iTunes_local_storage at '%s'" % self.iTunes_local_storage)
                os.mkdir(self.iTunes_local_storage)
            else:
                if DEBUG:
                    logger()(" existing iTunes_local_storage at '%s'" % self.iTunes_local_storage)

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
            logger().info("%s.remove_books_from_metadata()" % self.__class__.__name__)
        for path in paths:
            if DEBUG:
                self._dump_cached_book(self.cached_books[path], indent=2)
                logger().info("  looking for '%s' by '%s' uuid:%s" %
                                (self.cached_books[path]['title'],
                                 self.cached_books[path]['author'],
                                 repr(self.cached_books[path]['uuid'])))

            # Purge the booklist, self.cached_books, thumb cache
            for i, bl_book in enumerate(booklists[0]):
                if False:
                    logger().info("  evaluating '%s' by '%s' uuid:%s" %
                                  (bl_book.title, bl_book.author, bl_book.uuid))

                found = False
                if bl_book.uuid and bl_book.uuid == self.cached_books[path]['uuid']:
                    if True:
                        logger().info("  --matched uuid")
                    booklists[0].pop(i)
                    found = True
                elif bl_book.title == self.cached_books[path]['title'] and \
                     bl_book.author == self.cached_books[path]['author']:
                    if True:
                        logger().info("  --matched title + author")
                    booklists[0].pop(i)
                    found = True

                if found:
                    # Remove from self.cached_books
                    for cb in self.cached_books:
                        if (self.cached_books[cb]['uuid'] == self.cached_books[path]['uuid'] and
                            self.cached_books[cb]['author'] == self.cached_books[path]['author'] and
                            self.cached_books[cb]['title'] == self.cached_books[path]['title']):
                            self.cached_books.pop(cb)
                            break
                    else:
                        logger().error(" '%s' not found in self.cached_books" % self.cached_books[path]['title'])

                    # Remove from thumb from thumb cache
                    thumb_path = path.rpartition('.')[0] + '.jpg'
                    zf = ZipFile(self.archive_path, 'a')
                    fnames = zf.namelist()
                    try:
                        thumb = [x for x in fnames if thumb_path in x][0]
                    except:
                        thumb = None
                    if thumb:
                        if DEBUG:
                            logger().info("  deleting '%s' from cover cache" % (thumb_path))
                            zf.delete(thumb_path)
                    else:
                        if DEBUG:
                            logger().info("  '%s' not found in cover cache" % thumb_path)
                    zf.close()

                    break
            else:
                if DEBUG:
                    logger().error("  unable to find '%s' by '%s' (%s)" %
                                    (self.cached_books[path]['title'],
                                     self.cached_books[path]['author'],
                                     self.cached_books[path]['uuid']))

        if False:
            self._dump_booklist(booklists[0], indent=2)
            self._dump_cached_books(indent=2)

    def reset(self, key='-1', log_packets=False, report_progress=None,
            detected_device=None):
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
            logger().info("%s.reset()" % self.__class__.__name__)
        if report_progress:
            self.set_progress_reporter(report_progress)

    def set_progress_reporter(self, report_progress):
        '''
        @param report_progress: Function that is called with a % progress
                                (number between 0 and 100) for various tasks
                                If it is called with -1 that means that the
                                task does not have any progress information
        '''
        if DEBUG:
            logger().info("%s.set_progress_reporter()" % self.__class__.__name__)

        self.report_progress = report_progress

    def set_plugboards(self, plugboards, pb_func):
        # This method is called with the plugboard that matches the format
        # declared in use_plugboard_ext and a device name of ITUNES
        if DEBUG:
            logger().info("%s.set_plugboard()" % self.__class__.__name__)
            #logger().info('  plugboard: %s' % plugboards)
        self.plugboards = plugboards
        self.plugboard_func = pb_func

    def shutdown(self):
        if False and DEBUG:
            logger().info("%s.shutdown()\n" % self.__class__.__name__)

    def sync_booklists(self, booklists, end_session=True):
        '''
        Update metadata on device.
        @param booklists: A tuple containing the result of calls to
                                (L{books}(oncard=None), L{books}(oncard='carda'),
                                L{books}(oncard='cardb')).
        '''

        if DEBUG:
            logger().info("%s.sync_booklists()" % self.__class__.__name__)

        if self.update_needed:
            if DEBUG:
                logger().info(' calling _update_device')
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
            logger().info("%s.total_space()" % self.__class__.__name__)
        capacity = 0
        if isosx:
            if 'iPod' in self.sources:
                connected_device = self.sources['iPod']
                capacity = self.iTunes.sources[connected_device].capacity()

        return (capacity, -1, -1)

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
            logger().info("%s.upload_books()" % self.__class__.__name__)

        if isosx:
            for (i, fpath) in enumerate(files):
                format = fpath.rpartition('.')[2].lower()
                path = self.path_template % (metadata[i].title,
                                             authors_to_string(metadata[i].authors),
                                             format)
                self._remove_existing_copy(path, metadata[i])
                db_added, lb_added = self._add_new_copy(fpath, metadata[i])
                thumb = self._cover_to_thumb(path, metadata[i], db_added, lb_added, format)
                this_book = self._create_new_book(fpath, metadata[i], path, db_added, lb_added, thumb, format)
                new_booklist.append(this_book)
                self._update_iTunes_metadata(metadata[i], db_added, lb_added, this_book)

                # Add new_book to self.cached_books
                if DEBUG:
                    logger().info("%s.upload_books()" % self.__class__.__name__)
                    logger().info(" adding '%s' by '%s' uuid:%s to self.cached_books" %
                                  (metadata[i].title,
                                   authors_to_string(metadata[i].authors),
                                   metadata[i].uuid))
                self.cached_books[this_book.path] = {
                   'author': authors_to_string(metadata[i].authors),
                  'authors': metadata[i].authors,
                 'dev_book': db_added,
                   'format': format,
                 'lib_book': lb_added,
                    'title': metadata[i].title,
                     'uuid': metadata[i].uuid}

                # Report progress
                if self.report_progress is not None:
                    self.report_progress((i + 1) / file_count,
                        _('%(num)d of %(tot)d') % dict(num=i + 1, tot=file_count))

        elif iswindows:
            import pythoncom, win32com.client

            try:
                pythoncom.CoInitialize()
                self.iTunes = win32com.client.Dispatch("iTunes.Application")

                for (i, fpath) in enumerate(files):
                    format = fpath.rpartition('.')[2].lower()
                    path = self.path_template % (metadata[i].title,
                                                 authors_to_string(metadata[i].authors),
                                                 format)
                    self._remove_existing_copy(path, metadata[i])
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
                        logger().info("%s.upload_books()" % self.__class__.__name__)
                        logger().info(" adding '%s' by '%s' uuid:%s to self.cached_books" %
                                      (metadata[i].title,
                                       authors_to_string(metadata[i].authors),
                                       metadata[i].uuid))
                    self.cached_books[this_book.path] = {
                       'author': authors_to_string(metadata[i].authors),
                      'authors': metadata[i].authors,
                     'dev_book': db_added,
                       'format': format,
                     'lib_book': lb_added,
                        'title': metadata[i].title,
                         'uuid': metadata[i].uuid}

                    # Report progress
                    if self.report_progress is not None:
                        self.report_progress((i + 1) / file_count,
                                _('%(num)d of %(tot)d') % dict(num=i + 1, tot=file_count))
            finally:
                pythoncom.CoUninitialize()

        if self.report_progress is not None:
            self.report_progress(1.0, _('finished'))

        # Tell sync_booklists we need a re-sync
        if not self.manual_sync_mode:
            self.update_needed = True
            self.update_msg = "Added books to device"

        if False:
            self._dump_booklist(new_booklist, header="after upload_books()", indent=2)
            self._dump_cached_books(header="after upload_books()", indent=2)
        return (new_booklist, [], [])

    # Private methods
    def _add_device_book(self, fpath, metadata):
        '''
        assumes pythoncom wrapper for windows
        '''
        logger().info(" %s._add_device_book()" % self.__class__.__name__)
        if isosx:
            import appscript
            if 'iPod' in self.sources:
                connected_device = self.sources['iPod']
                device = self.iTunes.sources[connected_device]
                for pl in device.playlists():
                    if pl.special_kind() == appscript.k.Books:
                        break
                else:
                    if DEBUG:
                        logger().error("  Device|Books playlist not found")

                # Add the passed book to the Device|Books playlist
                attempts = 2
                delay = 1.0
                while attempts:
                    try:
                        added = pl.add(appscript.mactypes.File(fpath), to=pl)
                        if False:
                            logger().info("  '%s' added to Device|Books" % metadata.title)
                        break
                    except:
                        attempts -= 1
                        if DEBUG:
                            logger().warning("  failed to add book, waiting %.1f seconds to try again (attempt #%d)" %
                                     (delay, (3 - attempts)))
                        time.sleep(delay)
                else:
                    if DEBUG:
                        logger().error(" failed to add '%s' to Device|Books" % metadata.title)
                    raise UserFeedback("Unable to add '%s' in direct connect mode" % metadata.title,
                                        details=None, level=UserFeedback.ERROR)
                self._wait_for_writable_metadata(added)
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
                        logger().info("  no Books playlist found")

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
                            {'title': base_fn if format == 'pdf' else metadata.title,
                             'author': authors_to_string(metadata.authors),
                               'uuid': metadata.uuid,
                             'format': format})
                    return db_added

    def _add_library_book(self, file, metadata):
        '''
        windows assumes pythoncom wrapper
        '''
        if DEBUG:
            logger().info(" %s._add_library_book()" % self.__class__.__name__)
        if isosx:
            import appscript
            added = self.iTunes.add(appscript.mactypes.File(file))

        elif iswindows:
            lib = self.iTunes.LibraryPlaylist
            file_s = ctypes.c_char_p(file)
            FileArray = ctypes.c_char_p * 1
            fa = FileArray(file_s)
            op_status = lib.AddFiles(fa)
            if DEBUG:
                logger().info("  file added to Library|Books")

            logger().info("  iTunes adding '%s'" % file)

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
                    {'title': base_fn if format == 'pdf' else metadata.title,
                     'author': authors_to_string(metadata.authors),
                       'uuid': metadata.uuid,
                     'format': format})
        return added

    def _add_new_copy(self, fpath, metadata):
        '''
        fp = cached_book['lib_book'].location().path
        fp = cached_book['lib_book'].Location
        '''
        if DEBUG:
            logger().info(" %s._add_new_copy()" % self.__class__.__name__)

        if fpath.rpartition('.')[2].lower() == 'epub':
            self._update_epub_metadata(fpath, metadata)

        db_added = None
        lb_added = None

        if self.manual_sync_mode:
            '''
            DC mode. Add to iBooks only.
            '''
            db_added = self._add_device_book(fpath, metadata)
        else:
            # If using iTunes_local_storage, copy the file, redirect iTunes to use local copy
            if not self.settings().extra_customization[self.USE_ITUNES_STORAGE]:
                local_copy = os.path.join(self.iTunes_local_storage, str(metadata.uuid) + os.path.splitext(fpath)[1])
                shutil.copyfile(fpath, local_copy)
                fpath = local_copy

            lb_added = self._add_library_book(fpath, metadata)
            if not lb_added:
                raise UserFeedback("iTunes Media folder inaccessible",
                                   details="Failed to add '%s' to iTunes" % metadata.title,
                                   level=UserFeedback.WARN)

        return db_added, lb_added

    def _cover_to_thumb(self, path, metadata, db_added, lb_added, format):
        '''
        assumes pythoncom wrapper for db_added
        as of iTunes 9.2, iBooks 1.1, can't set artwork for PDF files via automation
        '''
        from PIL import Image as PILImage

        if DEBUG:
            logger().info(" %s._cover_to_thumb()" % self.__class__.__name__)

        thumb = None
        if metadata.cover:

            if format == 'epub':
                '''
                Pre-shrink cover
                self.MAX_COVER_WIDTH, self.MAX_COVER_HEIGHT
                '''
                try:
                    img = PILImage.open(metadata.cover)
                    width = img.size[0]
                    height = img.size[1]
                    scaled, nwidth, nheight = fit_image(width, height, self.MAX_COVER_WIDTH, self.MAX_COVER_HEIGHT)
                    if scaled:
                        if DEBUG:
                            logger().info("   cover scaled from %sx%s to %sx%s" %
                                          (width, height, nwidth, nheight))
                        img = img.resize((nwidth, nheight), PILImage.ANTIALIAS)
                        cd = cStringIO.StringIO()
                        img.convert('RGB').save(cd, 'JPEG')
                        cover_data = cd.getvalue()
                        cd.close()
                    else:
                        with open(metadata.cover, 'r+b') as cd:
                            cover_data = cd.read()
                except:
                    self.problem_titles.append("'%s' by %s" % (metadata.title, authors_to_string(metadata.authors)))
                    logger().error("  error scaling '%s' for '%s'" % (metadata.cover, metadata.title))

                    import traceback
                    traceback.print_exc()

                    return thumb

                if isosx:
                    '''
                    The following commands generate an error, but the artwork does in fact
                    get sent to the device.  Seems like a bug in Apple's automation interface?
                    Could also be a problem with the integrity of the cover data?
                    '''
                    if lb_added:
                        try:
                            lb_added.artworks[1].data_.set(cover_data)
                        except:
                            if DEBUG:
                                logger().warning("  iTunes automation interface reported an error"
                                                 " adding artwork to '%s' in the iTunes Library" % metadata.title)
                            pass

                    if db_added:
                        try:
                            db_added.artworks[1].data_.set(cover_data)
                            logger().info("   writing '%s' cover to iDevice" % metadata.title)
                        except:
                            if DEBUG:
                                logger().warning("  iTunes automation interface reported an error"
                                                 " adding artwork to '%s' on the iDevice" % metadata.title)
                            #import traceback
                            #traceback.print_exc()
                            #from calibre import ipython
                            #ipython(user_ns=locals())
                            pass

                elif iswindows:
                    ''' Write the data to a real file for Windows iTunes '''
                    tc = os.path.join(tempfile.gettempdir(), "cover.jpg")
                    with open(tc, 'wb') as tmp_cover:
                        tmp_cover.write(cover_data)

                    if lb_added:
                        try:
                            if lb_added.Artwork.Count:
                                lb_added.Artwork.Item(1).SetArtworkFromFile(tc)
                            else:
                                lb_added.AddArtworkFromFile(tc)
                        except:
                            if DEBUG:
                                logger().warning("  iTunes automation interface reported an error"
                                                 " when adding artwork to '%s' in the iTunes Library" % metadata.title)
                            pass

                    if db_added:
                        if db_added.Artwork.Count:
                            db_added.Artwork.Item(1).SetArtworkFromFile(tc)
                        else:
                            db_added.AddArtworkFromFile(tc)

            elif format == 'pdf':
                if DEBUG:
                    logger().info("   unable to set PDF cover via automation interface")

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
                    logger().info("   refreshing cached thumb for '%s'" % metadata.title)
                zfw = ZipFile(self.archive_path, mode='a')
                thumb_path = path.rpartition('.')[0] + '.jpg'
                zfw.writestr(thumb_path, thumb)
            except:
                self.problem_titles.append("'%s' by %s" % (metadata.title, authors_to_string(metadata.authors)))
                logger().error("   error converting '%s' to thumb for '%s'" % (metadata.cover, metadata.title))
            finally:
                try:
                    zfw.close()
                except:
                    pass
        else:
            if DEBUG:
                logger().info("   no cover defined in metadata for '%s'" % metadata.title)
        return thumb

    def _create_new_book(self, fpath, metadata, path, db_added, lb_added, thumb, format):
        '''
        '''
        if DEBUG:
            logger().info(" %s._create_new_book()" % self.__class__.__name__)

        this_book = Book(metadata.title, authors_to_string(metadata.authors))
        this_book.datetime = time.gmtime()
        #this_book.cid = metadata.id
        this_book.cid = None
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

    def _discover_manual_sync_mode(self, wait=0):
        '''
        Assumes pythoncom for windows
        wait is passed when launching iTunes, as it seems to need a moment to come to its senses
        '''
        if DEBUG:
            logger().info(" %s._discover_manual_sync_mode()" % self.__class__.__name__)
        if wait:
            time.sleep(wait)
        if isosx:
            import appscript
            connected_device = self.sources['iPod']
            dev_books = None
            device = self.iTunes.sources[connected_device]
            for pl in device.playlists():
                if pl.special_kind() == appscript.k.Books:
                    dev_books = pl.file_tracks()
                    break
            else:
                logger().error("   book_playlist not found")

            if dev_books is not None and len(dev_books):
                first_book = dev_books[0]
                if False:
                    logger().info("  determining manual mode by modifying '%s' by %s" % (first_book.name(), first_book.artist()))
                try:
                    first_book.bpm.set(0)
                    self.manual_sync_mode = True
                except:
                    self.manual_sync_mode = False
            else:
                if DEBUG:
                    logger().info("   adding tracer to empty Books|Playlist")
                try:
                    added = pl.add(appscript.mactypes.File(P('tracer.epub')), to=pl)
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

            if dev_books is not None and dev_books.Count:
                first_book = dev_books.Item(1)
                #if DEBUG:
                    #logger().info(" determing manual mode by modifying '%s' by %s" % (first_book.Name, first_book.Artist))
                try:
                    first_book.BPM = 0
                    self.manual_sync_mode = True
                except:
                    self.manual_sync_mode = False
            else:
                if DEBUG:
                    logger().info("   sending tracer to empty Books|Playlist")
                fpath = P('tracer.epub')
                mi = MetaInformation('Tracer', ['calibre'])
                try:
                    added = self._add_device_book(fpath, mi)
                    time.sleep(0.5)
                    added.Delete()
                    self.manual_sync_mode = True
                except:
                    self.manual_sync_mode = False

        if DEBUG:
            logger().info("   iTunes.manual_sync_mode: %s" % self.manual_sync_mode)

    def _dump_booklist(self, booklist, header=None, indent=0):
        '''
        '''
        if header:
            msg = '\n%sbooklist %s:' % (' ' * indent, header)
            logger().info(msg)
            logger().info('%s%s' % (' ' * indent, '-' * len(msg)))

        for book in booklist:
            if isosx:
                logger().info("%s%-40.40s %-30.30s %-40.40s %-10.10s" %
                 (' ' * indent, book.title, book.author, book.uuid, str(book.library_id)[-9:]))
            elif iswindows:
                logger().info("%s%-40.40s %-30.30s" %
                 (' ' * indent, book.title, book.author))
        logger().info()

    def _dump_cached_book(self, cached_book, header=None, indent=0):
        '''
        '''
        if isosx:
            if header:
                msg = '%s%s' % (' ' * indent, header)
                logger().info(msg)
                logger().info("%s%s" % (' ' * indent, '-' * len(msg)))
                logger().info("%s%-40.40s %-30.30s %-10.10s %-10.10s %s" %
                 (' ' * indent,
                  'title',
                  'author',
                  'lib_book',
                  'dev_book',
                  'uuid'))
            logger().info("%s%-40.40s %-30.30s %-10.10s %-10.10s %s" %
             (' ' * indent,
              cached_book['title'],
              cached_book['author'],
              str(cached_book['lib_book'])[-9:],
              str(cached_book['dev_book'])[-9:],
              cached_book['uuid']))
        elif iswindows:
            if header:
                msg = '%s%s' % (' ' * indent, header)
                logger().info(msg)
                logger().info("%s%s" % (' ' * indent, '-' * len(msg)))

            logger().info("%s%-40.40s %-30.30s %s" %
             (' ' * indent,
              cached_book['title'],
              cached_book['author'],
              cached_book['uuid']))

    def _dump_cached_books(self, header=None, indent=0):
        '''
        '''
        if header:
            msg = '\n%sself.cached_books %s:' % (' ' * indent, header)
            logger().info(msg)
            logger().info("%s%s" % (' ' * indent, '-' * len(msg)))
        if isosx:
            for cb in self.cached_books.keys():
                logger().info("%s%-40.40s %-30.30s %-40.40s %-10.10s %-10.10s" %
                 (' ' * indent,
                  self.cached_books[cb]['title'],
                  self.cached_books[cb]['author'],
                  self.cached_books[cb]['uuid'],
                  str(self.cached_books[cb]['lib_book'])[-9:],
                  str(self.cached_books[cb]['dev_book'])[-9:],
                  ))
        elif iswindows:
            for cb in self.cached_books.keys():
                logger().info("%s%-40.40s %-30.30s %-4.4s %s" %
                 (' ' * indent,
                  self.cached_books[cb]['title'],
                  self.cached_books[cb]['author'],
                  self.cached_books[cb]['format'],
                  self.cached_books[cb]['uuid']))

        logger().info()

    def _dump_epub_metadata(self, fpath):
        '''
        '''
        from calibre.ebooks.BeautifulSoup import BeautifulSoup

        logger().info(" %s.__get_epub_metadata()" % self.__class__.__name__)
        title = None
        author = None
        timestamp = None
        zf = ZipFile(fpath, 'r')
        fnames = zf.namelist()
        opf = [x for x in fnames if '.opf' in x][0]
        if opf:
            opf_raw = cStringIO.StringIO(zf.read(opf))
            soup = BeautifulSoup(opf_raw.getvalue())
            opf_raw.close()
            title = soup.find('dc:title').renderContents()
            author = soup.find('dc:creator').renderContents()
            ts = soup.find('meta', attrs={'name': 'calibre:timestamp'})
            if ts:
                # Touch existing calibre timestamp
                timestamp = ts['content']

            if not title or not author:
                if DEBUG:
                    logger().error("   couldn't extract title/author from %s in %s" % (opf, fpath))
                    logger().error("   title: %s  author: %s timestamp: %s" % (title, author, timestamp))
        else:
            if DEBUG:
                logger().error("   can't find .opf in %s" % fpath)
        zf.close()
        return (title, author, timestamp)

    def _dump_hex(self, src, length=16):
        '''
        '''
        FILTER = ''.join([(len(repr(chr(x))) == 3) and chr(x) or '.' for x in range(256)])
        N = 0
        result = ''
        while src:
            s, src = src[:length], src[length:]
            hexa = ' '.join(["%02X" % ord(x) for x in s])
            s = s.translate(FILTER)
            result += "%04X   %-*s   %s\n" % (N, length * 3, hexa, s)
            N += length
        print result

    def _dump_library_books(self, library_books):
        '''
        '''
        if DEBUG:
            logger().info("\n library_books:")
        for book in library_books:
            logger().info("   %s" % book)
        logger().info()

    def _dump_update_list(self, header=None, indent=0):
        if header and self.update_list:
            msg = '\n%sself.update_list %s' % (' ' * indent, header)
            logger().info(msg)
            logger().info("%s%s" % (' ' * indent, '-' * len(msg)))

        if isosx:
            for ub in self.update_list:
                logger().info("%s%-40.40s %-30.30s %-10.10s %s" %
                 (' ' * indent,
                  ub['title'],
                  ub['author'],
                  str(ub['lib_book'])[-9:],
                  ub['uuid']))
        elif iswindows:
            for ub in self.update_list:
                logger().info("%s%-40.40s %-30.30s" %
                 (' ' * indent,
                  ub['title'],
                  ub['author']))

    def _find_device_book(self, search):
        '''
        Windows-only method to get a handle to device book in the current pythoncom session
        '''
        if iswindows:
            dev_books = self._get_device_books_playlist()
            if DEBUG:
                logger().info(" %s._find_device_book()" % self.__class__.__name__)
                logger().info("  searching for '%s' by '%s' (%s)" %
                              (search['title'], search['author'], search['uuid']))
            attempts = 9
            while attempts:
                # Try by uuid - only one hit
                if 'uuid' in search and search['uuid']:
                    if DEBUG:
                        logger().info("   searching by uuid '%s' ..." % search['uuid'])
                    hits = dev_books.Search(search['uuid'], self.SearchField.index('All'))
                    if hits:
                        hit = hits[0]
                        logger().info("   found '%s' by %s (%s)" % (hit.Name, hit.Artist, hit.Composer))
                        return hit

                # Try by author - there could be multiple hits
                if search['author']:
                    if DEBUG:
                        logger().info("   searching by author '%s' ..." % search['author'])
                    hits = dev_books.Search(search['author'], self.SearchField.index('Artists'))
                    if hits:
                        for hit in hits:
                            if hit.Name == search['title']:
                                if DEBUG:
                                    logger().info("   found '%s' by %s (%s)" % (hit.Name, hit.Artist, hit.Composer))
                                return hit

                # Search by title if no author available
                if DEBUG:
                    logger().info("   searching by title '%s' ..." % search['title'])
                hits = dev_books.Search(search['title'], self.SearchField.index('All'))
                if hits:
                    for hit in hits:
                        if hit.Name == search['title']:
                            if DEBUG:
                                logger().info("   found '%s'" % (hit.Name))
                            return hit

                # PDF just sent, title not updated yet, look for export pattern
                # PDF metadata was rewritten at export as 'safe(title) - safe(author)'
                if search['format'] == 'pdf':
                    title = re.sub(r'[^0-9a-zA-Z ]', '_', search['title'])
                    author = re.sub(r'[^0-9a-zA-Z ]', '_', search['author'])
                    if DEBUG:
                        logger().info("   searching by name: '%s - %s'" % (title, author))
                    hits = dev_books.Search('%s - %s' % (title, author),
                                             self.SearchField.index('All'))
                    if hits:
                        hit = hits[0]
                        logger().info("   found '%s' by %s (%s)" % (hit.Name, hit.Artist, hit.Composer))
                        return hit
                    else:
                        if DEBUG:
                            logger().info("   no PDF hits")

                attempts -= 1
                time.sleep(0.5)
                if DEBUG:
                    logger().warning("  attempt #%d" % (10 - attempts))

            if DEBUG:
                logger().error("  no hits")
            return None

    def _find_library_book(self, search):
        '''
        Windows-only method to get a handle to a library book in the current pythoncom session
        '''
        if iswindows:
            if DEBUG:
                logger().info(" %s._find_library_book()" % self.__class__.__name__)
                '''
                if 'uuid' in search:
                    logger().info("  looking for '%s' by %s (%s)" %
                                (search['title'], search['author'], search['uuid']))
                else:
                    logger().info("  looking for '%s' by %s" %
                                (search['title'], search['author']))
                '''

            for source in self.iTunes.sources:
                if source.Kind == self.Sources.index('Library'):
                    lib = source
                    if DEBUG:
                        logger().info("  Library source: '%s'  kind: %s" % (lib.Name, self.Sources[lib.Kind]))
                    break
            else:
                if DEBUG:
                    logger().info("  Library source not found")

            if lib is not None:
                lib_books = None
                for pl in lib.Playlists:
                    if pl.Kind == self.PlaylistKind.index('User') and \
                       pl.SpecialKind == self.PlaylistSpecialKind.index('Books'):
                        if DEBUG:
                            logger().info("  Books playlist: '%s'" % (pl.Name))
                        lib_books = pl
                        break
                else:
                    if DEBUG:
                        logger().error("  no Books playlist found")

            attempts = 9
            while attempts:
                # Find book whose Album field = search['uuid']
                if 'uuid' in search and search['uuid']:
                    if DEBUG:
                        logger().info("   searching by uuid '%s' ..." % search['uuid'])
                    hits = lib_books.Search(search['uuid'], self.SearchField.index('All'))
                    if hits:
                        hit = hits[0]
                        if DEBUG:
                            logger().info("   found '%s' by %s (%s)" % (hit.Name, hit.Artist, hit.Composer))
                        return hit

                # Search by author if known
                if search['author']:
                    if DEBUG:
                        logger().info("   searching by author '%s' ..." % search['author'])
                    hits = lib_books.Search(search['author'], self.SearchField.index('Artists'))
                    if hits:
                        for hit in hits:
                            if hit.Name == search['title']:
                                if DEBUG:
                                    logger().info("   found '%s' by %s (%s)" % (hit.Name, hit.Artist, hit.Composer))
                                return hit

                # Search by title if no author available
                if DEBUG:
                    logger().info("   searching by title '%s' ..." % search['title'])
                hits = lib_books.Search(search['title'], self.SearchField.index('All'))
                if hits:
                    for hit in hits:
                        if hit.Name == search['title']:
                            if DEBUG:
                                logger().info("   found '%s'" % (hit.Name))
                            return hit

                # PDF just sent, title not updated yet, look for export pattern
                # PDF metadata was rewritten at export as 'safe(title) - safe(author)'
                if search['format'] == 'pdf':
                    title = re.sub(r'[^0-9a-zA-Z ]', '_', search['title'])
                    author = re.sub(r'[^0-9a-zA-Z ]', '_', search['author'])
                    if DEBUG:
                        logger().info("   searching by name: %s - %s" % (title, author))
                    hits = lib_books.Search('%s - %s' % (title, author),
                                             self.SearchField.index('All'))
                    if hits:
                        hit = hits[0]
                        logger().info("   found '%s' by %s (%s)" % (hit.Name, hit.Artist, hit.Composer))
                        return hit
                    else:
                        if DEBUG:
                            logger().info("   no PDF hits")

                attempts -= 1
                time.sleep(0.5)
                if DEBUG:
                    logger().warning("   attempt #%d" % (10 - attempts))

            if DEBUG:
                logger().error("  search for '%s' yielded no hits" % search['title'])
            return None

    def _generate_thumbnail(self, book_path, book):
        '''
        Convert iTunes artwork to thumbnail
        Cache generated thumbnails
        cache_dir = os.path.join(config_dir, 'caches', 'itunes')
        as of iTunes 9.2, iBooks 1.1, can't set artwork for PDF files via automation
        '''
        from PIL import Image as PILImage

        if not self.settings().extra_customization[self.CACHE_COVERS]:
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
                    logger().info(" %s._generate_thumbnail()\n   returning None from cover cache for '%s'" %
                                    (self.__class__.__name__, title))
                zfr.close()
                return None
        except:
            zfw = ZipFile(self.archive_path, mode='a')
        else:
            if False:
                logger().info("   returning thumb from cache for '%s'" % title)
            return thumb_data

        if DEBUG:
            logger().info(" %s._generate_thumbnail('%s'):" % (self.__class__.__name__, title))
        if isosx:

            # Fetch the artwork from iTunes
            try:
                data = book.artworks[1].raw_data().data
            except:
                # If no artwork, write an empty marker to cache
                if DEBUG:
                    logger().error("  error fetching iTunes artwork for '%s'" % title)
                zfw.writestr(thumb_path, 'None')
                zfw.close()
                return None

            # Generate a thumb
            try:
                img_data = cStringIO.StringIO(data)
                im = PILImage.open(img_data)
                scaled, width, height = fit_image(im.size[0], im.size[1], 60, 80)
                im = im.resize((int(width), int(height)), PILImage.ANTIALIAS)

                thumb = cStringIO.StringIO()
                im.convert('RGB').save(thumb, 'JPEG')
                thumb_data = thumb.getvalue()
                thumb.close()
                if False:
                    logger().info("  generated thumb for '%s', caching" % title)
                # Cache the tagged thumb
                zfw.writestr(thumb_path, thumb_data)
            except:
                if DEBUG:
                    logger().error("  error generating thumb for '%s', caching empty marker" % book.name())
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
                    logger().info("  no artwork available for '%s'" % book.Name)
                zfw.writestr(thumb_path, 'None')
                zfw.close()
                return None

            # Fetch the artwork from iTunes

            try:
                tmp_thumb = os.path.join(tempfile.gettempdir(), "thumb.%s" % self.ArtworkFormat[book.Artwork.Item(1).Format])
                book.Artwork.Item(1).SaveArtworkToFile(tmp_thumb)
                # Resize the cover
                im = PILImage.open(tmp_thumb)
                scaled, width, height = fit_image(im.size[0], im.size[1], 60, 80)
                im = im.resize((int(width), int(height)), PILImage.ANTIALIAS)
                thumb = cStringIO.StringIO()
                im.convert('RGB').save(thumb, 'JPEG')
                thumb_data = thumb.getvalue()
                os.remove(tmp_thumb)
                thumb.close()
                if False:
                    logger().info("  generated thumb for '%s', caching" % book.Name)
                # Cache the tagged thumb
                zfw.writestr(thumb_path, thumb_data)
            except:
                if DEBUG:
                    logger().error("  error generating thumb for '%s', caching empty marker" % book.Name)
                thumb_data = None
                # Cache the empty cover
                zfw.writestr(thumb_path, 'None')

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
            myZip = ZipFile(file, 'r')
            myZipList = myZip.infolist()
            exploded_file_size = 0
            for file in myZipList:
                exploded_file_size += file.file_size
            if False:
                logger().info(" %s._get_device_book_size()" % self.__class__.__name__)
                logger().info("  %d items in archive" % len(myZipList))
                logger().info("  compressed: %d  exploded: %d" % (compressed_size, exploded_file_size))
            myZip.close()
        return exploded_file_size

    def _get_device_books(self):
        '''
        Assumes pythoncom wrapper for Windows
        '''
        if DEBUG:
            logger().info("\n %s._get_device_books()" % self.__class__.__name__)

        device_books = []
        if isosx:
            import appscript
            if 'iPod' in self.sources:
                connected_device = self.sources['iPod']
                device = self.iTunes.sources[connected_device]
                dev_books = None
                for pl in device.playlists():
                    if pl.special_kind() == appscript.k.Books:
                        if DEBUG:
                            logger().info("  Book playlist: '%s'" % (pl.name()))
                        dev_books = pl.file_tracks()
                        break
                else:
                    logger().error("  book_playlist not found")

                for book in dev_books:
                    if book.kind() in self.Audiobooks:
                        if DEBUG:
                            logger().info("   ignoring '%s' of type '%s'" % (book.name(), book.kind()))
                    else:
                        if DEBUG:
                            logger().info("  %-40.40s %-30.30s %-40.40s [%s]" %
                                          (book.name(), book.artist(), book.composer(), book.kind()))
                        device_books.append(book)
                if DEBUG:
                    logger().info()

        elif iswindows:
            import pythoncom

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
                                logger().info("  Books playlist: '%s'" % (pl.Name))
                            dev_books = pl.Tracks
                            break
                    else:
                        if DEBUG:
                            logger().info("  no Books playlist found")

                    for book in dev_books:
                        if book.KindAsString in self.Audiobooks:
                            if DEBUG:
                                logger().info("   ignoring '%s' of type '%s'" % (book.Name, book.KindAsString))
                        else:
                            if DEBUG:
                                logger().info("   %-40.40s %-30.30s %-40.40s [%s]" % (book.Name, book.Artist, book.Composer, book.KindAsString))
                            device_books.append(book)
                    if DEBUG:
                        logger().info()

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
                        logger().error("  no iPad|Books playlist found")
                return pl

    def _get_library_books(self):
        '''
        Populate a dict of paths from iTunes Library|Books
        Windows assumes pythoncom wrapper
        '''
        if DEBUG:
            logger().info("\n %s._get_library_books()" % self.__class__.__name__)

        library_books = {}
        library_orphans = {}
        lib = None

        if isosx:
            import appscript
            for source in self.iTunes.sources():
                if source.kind() == appscript.k.library:
                    lib = source
                    if DEBUG:
                        logger().info("  Library source: '%s'" % (lib.name()))
                    break
            else:
                if DEBUG:
                    logger().error('  Library source not found')

            if lib is not None:
                lib_books = None
                if lib.playlists():
                    for pl in lib.playlists():
                        if pl.special_kind() == appscript.k.Books:
                            if DEBUG:
                                logger().info("  Books playlist: '%s'" % (pl.name()))
                            break
                    else:
                        if DEBUG:
                            logger().info("  no Library|Books playlist found")

                    lib_books = pl.file_tracks()
                    for book in lib_books:
                        # This may need additional entries for international iTunes users
                        if book.kind() in self.Audiobooks:
                            if DEBUG:
                                logger().info("   ignoring '%s' of type '%s'" % (book.name(), book.kind()))
                        else:
                            # Collect calibre orphans - remnants of recipe uploads
                            format = 'pdf' if book.kind().startswith('PDF') else 'epub'
                            path = self.path_template % (book.name(), book.artist(), format)
                            if str(book.description()).startswith(self.description_prefix):
                                try:
                                    if book.location() == appscript.k.missing_value:
                                        library_orphans[path] = book
                                        if False:
                                            logger().info("   found iTunes PTF '%s' in Library|Books" % book.name())
                                except:
                                    if DEBUG:
                                        logger().error("   iTunes returned an error returning .location() with %s" % book.name())

                            library_books[path] = book
                            if DEBUG:
                                logger().info("   %-30.30s %-30.30s %-40.40s [%s]" %
                                              (book.name(), book.artist(), book.album(), book.kind()))
                else:
                    if DEBUG:
                        logger().info('  no Library playlists')
            else:
                if DEBUG:
                    logger().info('  no Library found')

        elif iswindows:
            lib = None
            for source in self.iTunes.sources:
                if source.Kind == self.Sources.index('Library'):
                    lib = source
                    logger().info("  Library source: '%s' kind: %s" % (lib.Name, self.Sources[lib.Kind]))
                    break
            else:
                logger().error("  Library source not found")

            if lib is not None:
                lib_books = None
                if lib.Playlists is not None:
                    for pl in lib.Playlists:
                        if pl.Kind == self.PlaylistKind.index('User') and \
                           pl.SpecialKind == self.PlaylistSpecialKind.index('Books'):
                            if DEBUG:
                                logger().info("  Books playlist: '%s'" % (pl.Name))
                            lib_books = pl.Tracks
                            break
                    else:
                        if DEBUG:
                            logger().error("  no Library|Books playlist found")
                else:
                    if DEBUG:
                        logger().error("  no Library playlists found")

                try:
                    for book in lib_books:
                        # This may need additional entries for international iTunes users
                        if book.KindAsString in self.Audiobooks:
                            if DEBUG:
                                logger().info("   ignoring %-30.30s of type '%s'" % (book.Name, book.KindAsString))
                        else:
                            format = 'pdf' if book.KindAsString.startswith('PDF') else 'epub'
                            path = self.path_template % (book.Name, book.Artist, format)

                            # Collect calibre orphans
                            if book.Description.startswith(self.description_prefix):
                                if not book.Location:
                                    library_orphans[path] = book
                                    if False:
                                        logger().info("   found iTunes PTF '%s' in Library|Books" % book.Name)

                            library_books[path] = book
                            if DEBUG:
                                logger().info("   %-30.30s %-30.30s %-40.40s [%s]" % (book.Name, book.Artist, book.Album, book.KindAsString))
                except:
                    if DEBUG:
                        logger().info(" no books in library")

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
            it_sources = ['Unknown', 'Library', 'iPod', 'AudioCD', 'MP3CD', 'Device', 'RadioTuner', 'SharedLibrary']
            names = [s.name for s in self.iTunes.sources]
            kinds = [it_sources[s.kind] for s in self.iTunes.sources]

        # If more than one connected iDevice, remove all from list to prevent driver initialization
        if kinds.count('iPod') > 1:
            if DEBUG:
                logger().error("  %d connected iPod devices detected, calibre supports a single connected iDevice" % kinds.count('iPod'))
            while kinds.count('iPod'):
                index = kinds.index('iPod')
                kinds.pop(index)
                names.pop(index)

        return dict(zip(kinds, names))

    def _is_alpha(self, char):
        '''
        '''
        if not re.search('[a-zA-Z]', char):
            return False
        else:
            return True

    def _launch_iTunes(self):
        '''
        '''
        if DEBUG:
            logger().info(" %s._launch_iTunes():\n  Instantiating iTunes" % self.__class__.__name__)

        if isosx:
            import appscript
            as_name = appscript.__name__
            as_version = appscript.__version__
            '''
            Launch iTunes if not already running
            '''
            # Instantiate iTunes
            running_apps = appscript.app('System Events')
            if not 'iTunes' in running_apps.processes.name():
                if DEBUG:
                    logger().info("%s:_launch_iTunes(): Launching iTunes" % self.__class__.__name__)
                try:
                    self.iTunes = iTunes = appscript.app('iTunes', hide=True)
                except:
                    self.iTunes = None
                    raise UserFeedback(' %s._launch_iTunes(): unable to find installed iTunes' %
                                         self.__class__.__name__, details=None, level=UserFeedback.WARN)

                iTunes.run()
                self.initial_status = 'launched'
            else:
                self.iTunes = appscript.app('iTunes')
                self.initial_status = 'already running'

            '''
            Test OSA communication with iTunes.
            If unable to communicate with iTunes, set self.iTunes to None, then
            report to user in open()
            '''
            as_binding = "dynamic"
            try:
                # Try dynamic binding - works with iTunes <= 10.6.1
                self.iTunes.name()
            except:
                # Try static binding
                import itunes
                self.iTunes = appscript.app('iTunes', terms=itunes)
                try:
                    self.iTunes.name()
                    as_binding = "static"
                except:
                    self.iTunes = None
                    if DEBUG:
                        logger().info("   unable to communicate with iTunes via %s %s using any binding" % (as_name, as_version))
                    return

            '''
            # Read the current storage path for iTunes media
            cmd = "defaults read com.apple.itunes NSNavLastRootDirectory"
            proc = subprocess.Popen( cmd, shell=True, cwd=os.curdir, stdout=subprocess.PIPE)
            proc.wait()
            media_dir = os.path.expanduser(proc.communicate()[0].strip())
            if os.path.exists(media_dir):
                self.iTunes_media = media_dir
            else:
                logger().error("  could not confirm valid iTunes.media_dir from %s" % 'com.apple.itunes')
                logger().error("  media_dir: %s" % media_dir)
            '''

            if DEBUG:
                logger().info("  %s %s" % (__appname__, __version__))
                logger().info("  [OSX %s, %s %s (%s), %s driver version %d.%d.%d]" %
                 (platform.mac_ver()[0],
                  self.iTunes.name(), self.iTunes.version(), self.initial_status,
                  self.__class__.__name__, self.version[0], self.version[1], self.version[2]))
                logger().info("  communicating with iTunes via %s %s using %s binding" % (as_name, as_version, as_binding))
                logger().info("  calibre_library_path: %s" % self.calibre_library_path)

        if iswindows:
            import win32com.client

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
                raise OpenFeedback('Unable to launch iTunes.\n' +
                                   'Try launching calibre as Administrator')

            if not DEBUG:
                self.iTunes.Windows[0].Minimized = True
            self.initial_status = 'launched'

            try:
                # Pre-emptive test to confirm functional iTunes automation interface
                logger().info("  automation interface with iTunes %s established" % self.iTunes.Version)
            except:
                self.iTunes = None
                raise OpenFeedback('Unable to connect to iTunes.\n' +
                             ' iTunes automation interface non-responsive, ' +
                             'recommend reinstalling iTunes')

            '''
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
                    logger().error("  could not extract valid iTunes.media_dir from %s" % self.iTunes.LibraryXMLPath)
                    logger().error("  %s" % string.parent.prettify())
                    logger().error("  '%s' not found" % media_dir)
                else:
                    logger().error("  no media dir found: string: %s" % string)
            '''

            if DEBUG:
                logger().info("  %s %s" % (__appname__, __version__))
                logger().info("  [Windows %s - %s (%s), driver version %d.%d.%d]" %
                 (self.iTunes.Windows[0].name, self.iTunes.Version, self.initial_status,
                  self.version[0], self.version[1], self.version[2]))
                logger().info("  calibre_library_path: %s" % self.calibre_library_path)

    def _purge_orphans(self, library_books, cached_books):
        '''
        Scan library_books for any paths not on device
        Remove any iTunes orphans originally added by calibre
        This occurs when the user deletes a book in iBooks while disconnected
        '''
        PURGE_ORPHANS = False

        if DEBUG:
            logger().info(" %s._purge_orphans()" % self.__class__.__name__)
            #self._dump_library_books(library_books)
            #logger().info("  cached_books:\n   %s" % "\n   ".join(cached_books.keys()))

        for book in library_books:
            if isosx:
                if book not in cached_books and \
                   str(library_books[book].description()).startswith(self.description_prefix):
                    if PURGE_ORPHANS:
                        if DEBUG:
                            logger().info("  '%s' not found on iDevice, removing from iTunes" % book)
                        btr = {
                                     'title': library_books[book].name(),
                                 'author': library_books[book].artist(),
                               'lib_book': library_books[book]}
                        self._remove_from_iTunes(btr)
                    else:
                        if DEBUG:
                            logger().info("  '%s' found in iTunes, but not on iDevice" % (book))

            elif iswindows:
                if book not in cached_books and \
                   library_books[book].Description.startswith(self.description_prefix):
                    if PURGE_ORPHANS:
                        if DEBUG:
                            logger().info("  '%s' not found on iDevice, removing from iTunes" % book)
                        btr = {
                                     'title': library_books[book].Name,
                                 'author': library_books[book].Artist,
                               'lib_book': library_books[book]}
                        self._remove_from_iTunes(btr)
                    else:
                        if DEBUG:
                            logger().info("  '%s' found in iTunes, but not on iDevice" % (book))

    def _remove_existing_copy(self, path, metadata):
        '''
        '''
        if DEBUG:
            logger().info(" %s._remove_existing_copy()" % self.__class__.__name__)

        if self.manual_sync_mode:
            # Delete existing from Device|Books, add to self.update_list
            # for deletion from booklist[0] during add_books_to_metadata
            for book in self.cached_books:
                if (self.cached_books[book]['uuid'] == metadata.uuid or
                    (self.cached_books[book]['title'] == metadata.title and
                     self.cached_books[book]['author'] == metadata.author)):
                    self.update_list.append(self.cached_books[book])
                    self._remove_from_device(self.cached_books[book])
                    self._remove_from_iTunes(self.cached_books[book])
                    break
            else:
                if DEBUG:
                    logger().info("  '%s' not in cached_books" % metadata.title)
        else:
            # Delete existing from Library|Books, add to self.update_list
            # for deletion from booklist[0] during add_books_to_metadata
            for book in self.cached_books:
                if (self.cached_books[book]['uuid'] == metadata.uuid or
                    (self.cached_books[book]['title'] == metadata.title and \
                     self.cached_books[book]['author'] == metadata.author)):
                    self.update_list.append(self.cached_books[book])
                    if DEBUG:
                        logger().info("  deleting library book '%s'" % metadata.title)
                    self._remove_from_iTunes(self.cached_books[book])
                    break
            else:
                if DEBUG:
                    logger().info("  '%s' not found in cached_books" % metadata.title)

    def _remove_from_device(self, cached_book):
        '''
        Windows assumes pythoncom wrapper
        '''
        if DEBUG:
            logger().info(" %s._remove_from_device()" % self.__class__.__name__)
        if isosx:
            if DEBUG:
                logger().info("  deleting '%s' from iDevice" % cached_book['title'])
            try:
                cached_book['dev_book'].delete()
            except:
                logger().error("  error deleting '%s'" % cached_book['title'])
        elif iswindows:
            hit = self._find_device_book(cached_book)
            if hit:
                if DEBUG:
                    logger().info("  deleting '%s' from iDevice" % cached_book['title'])
                hit.Delete()
            else:
                if DEBUG:
                    logger().warning("   unable to remove '%s' by '%s' (%s) from device" %
                                     (cached_book['title'], cached_book['author'], cached_book['uuid']))

    def _remove_from_iTunes(self, cached_book):
        '''
        iTunes does not delete books from storage when removing from database via automation
        '''
        if DEBUG:
            logger().info(" %s._remove_from_iTunes():" % self.__class__.__name__)

        if isosx:
            ''' Manually remove the book from iTunes storage '''
            try:
                fp = cached_book['lib_book'].location().path
                if DEBUG:
                    logger().info("  processing %s" % fp)
                if fp.startswith(prefs['library_path']):
                    logger().info("  '%s' stored in calibre database, not removed" % cached_book['title'])
                elif not self.settings().extra_customization[self.USE_ITUNES_STORAGE] and \
                  fp.startswith(self.iTunes_local_storage) and \
                  os.path.exists(fp):
                    # Delete the copy in iTunes_local_storage
                    os.remove(fp)
                    if DEBUG:
                        logger()("   removing from iTunes_local_storage")
                else:
                    # Delete from iTunes Media folder
                    if os.path.exists(fp):
                        os.remove(fp)
                        if DEBUG:
                            logger().info("   deleting from iTunes storage")
                        author_storage_path = os.path.split(fp)[0]
                        try:
                            os.rmdir(author_storage_path)
                            if DEBUG:
                                logger().info("   removing empty author directory")
                        except:
                            author_files = os.listdir(author_storage_path)
                            if '.DS_Store' in author_files:
                                author_files.pop(author_files.index('.DS_Store'))
                            if not author_files:
                                os.rmdir(author_storage_path)
                                if DEBUG:
                                    logger().info("   removing empty author directory")
                    else:
                        logger().info("   '%s' does not exist at storage location" % cached_book['title'])

            except:
                # We get here if there was an error with .location().path
                if DEBUG:
                    logger().info("   '%s' by %s not found in iTunes storage" %
                                    (cached_book['title'], cached_book['author']))

            # Delete the book from the iTunes database
            try:
                self.iTunes.delete(cached_book['lib_book'])
                if DEBUG:
                    logger().info("   removing from iTunes database")
            except:
                if DEBUG:
                    logger().info("   unable to remove from iTunes database")

        elif iswindows:
            '''
            Assume we're wrapped in a pythoncom
            Windows stores the book under a common author directory, so we just delete the .epub
            '''
            fp = None
            try:
                book = cached_book['lib_book']
                fp = book.Location
            except:
                book = self._find_library_book(cached_book)
                if book:
                    fp = book.Location

            if book:
                if DEBUG:
                    logger().info("  processing %s" % fp)
                if fp.startswith(prefs['library_path']):
                    logger().info("  '%s' stored in calibre database, not removed" % cached_book['title'])
                elif not self.settings().extra_customization[self.USE_ITUNES_STORAGE] and \
                  fp.startswith(self.iTunes_local_storage) and \
                  os.path.exists(fp):
                    # Delete the copy in iTunes_local_storage
                    os.remove(fp)
                    if DEBUG:
                        logger()("   removing from iTunes_local_storage")
                else:
                    # Delete from iTunes Media folder
                    if os.path.exists(fp):
                        os.remove(fp)
                        if DEBUG:
                            logger().info("   deleting from iTunes storage")
                        author_storage_path = os.path.split(fp)[0]
                        try:
                            os.rmdir(author_storage_path)
                            if DEBUG:
                                logger().info("   removing empty author directory")
                        except:
                            pass
                    else:
                        logger().info("   '%s' does not exist at storage location" % cached_book['title'])
            else:
                if DEBUG:
                    logger().info("   '%s' not found in iTunes storage" % cached_book['title'])

            # Delete the book from the iTunes database
            try:
                book.Delete()
                if DEBUG:
                    logger().info("   removing from iTunes database")
            except:
                if DEBUG:
                    logger().info("   unable to remove from iTunes database")

    def title_sorter(self, title):
        return re.sub('^\s*A\s+|^\s*The\s+|^\s*An\s+', '', title).rstrip()

    def _update_epub_metadata(self, fpath, metadata):
        '''
        '''
        from calibre.ebooks.metadata.epub import set_metadata
        from lxml import etree

        if DEBUG:
            logger().info(" %s._update_epub_metadata()" % self.__class__.__name__)

        # Fetch plugboard updates
        metadata_x = self._xform_metadata_via_plugboard(metadata, 'epub')

        # Refresh epub metadata
        with open(fpath, 'r+b') as zfo:
            if False:
                try:
                    zf_opf = ZipFile(fpath, 'r')
                    fnames = zf_opf.namelist()
                    opf = [x for x in fnames if '.opf' in x][0]
                except:
                    raise UserFeedback("'%s' is not a valid EPUB" % metadata.title,
                                       None,
                                       level=UserFeedback.WARN)

                #Touch the OPF timestamp
                opf_tree = etree.fromstring(zf_opf.read(opf))
                md_els = opf_tree.xpath('.//*[local-name()="metadata"]')
                if md_els:
                    ts = md_els[0].find('.//*[@name="calibre:timestamp"]')
                    if ts is not None:
                        timestamp = ts.get('content')
                        old_ts = parse_date(timestamp)
                        metadata.timestamp = datetime.datetime(old_ts.year, old_ts.month, old_ts.day, old_ts.hour,
                                                   old_ts.minute, old_ts.second, old_ts.microsecond + 1, old_ts.tzinfo)
                        if DEBUG:
                            logger().info("   existing timestamp: %s" % metadata.timestamp)
                    else:
                        metadata.timestamp = now()
                        if DEBUG:
                            logger().info("   add timestamp: %s" % metadata.timestamp)

                else:
                    metadata.timestamp = now()
                    if DEBUG:
                        logger().warning("   missing <metadata> block in OPF file")
                        logger().info("   add timestamp: %s" % metadata.timestamp)

                zf_opf.close()

            # If 'News' in tags, tweak the title/author for friendlier display in iBooks
            if _('News') in metadata_x.tags or \
               _('Catalog') in metadata_x.tags:
                if metadata_x.title.find('[') > 0:
                    metadata_x.title = metadata_x.title[:metadata_x.title.find('[') - 1]
                date_as_author = '%s, %s %s, %s' % (strftime('%A'), strftime('%B'), strftime('%d').lstrip('0'), strftime('%Y'))
                metadata_x.author = metadata_x.authors = [date_as_author]
                sort_author = re.sub('^\s*A\s+|^\s*The\s+|^\s*An\s+', '', metadata_x.title).rstrip()
                metadata_x.author_sort = '%s %s' % (sort_author, strftime('%Y-%m-%d'))

            # Remove any non-alpha category tags
            for tag in metadata_x.tags:
                if not self._is_alpha(tag[0]):
                    metadata_x.tags.remove(tag)

            # If windows & series, nuke tags so series used as Category during _update_iTunes_metadata()
            if iswindows and metadata_x.series:
                metadata_x.tags = None

            set_metadata(zfo, metadata_x, apply_null=True, update_timestamp=True)

    def _update_device(self, msg='', wait=True):
        '''
        Trigger a sync, wait for completion
        '''
        if DEBUG:
            logger().info(" %s:_update_device():\n %s" % (self.__class__.__name__, msg))

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
            import pythoncom, win32com.client

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
            logger().info(" %s._update_iTunes_metadata()" % self.__class__.__name__)

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
                lb_added.description.set("%s %s" % (self.description_prefix, strftime('%Y-%m-%d %H:%M:%S')))
                lb_added.enabled.set(True)
                lb_added.sort_artist.set(icu_title(metadata_x.author_sort))
                lb_added.sort_name.set(metadata_x.title_sort)
                lb_added.year.set(metadata_x.pubdate.year)

            if db_added:
                db_added.name.set(metadata_x.title)
                db_added.album.set(metadata_x.title)
                db_added.artist.set(authors_to_string(metadata_x.authors))
                db_added.composer.set(metadata_x.uuid)
                db_added.description.set("%s %s" % (self.description_prefix, strftime('%Y-%m-%d %H:%M:%S')))
                db_added.enabled.set(True)
                db_added.sort_artist.set(icu_title(metadata_x.author_sort))
                db_added.sort_name.set(metadata_x.title_sort)
                db_added.year.set(metadata_x.pubdate.year)

            if metadata_x.comments:
                if lb_added:
                    lb_added.comment.set(STRIP_TAGS.sub('', metadata_x.comments))
                if db_added:
                    db_added.comment.set(STRIP_TAGS.sub('', metadata_x.comments))

            if metadata_x.rating:
                if lb_added:
                    lb_added.rating.set(metadata_x.rating * 10)
                # iBooks currently doesn't allow setting rating ... ?
                try:
                    if db_added:
                        db_added.rating.set(metadata_x.rating * 10)
                except:
                    pass

            # Set genre from series if available, else first alpha tag
            # Otherwise iTunes grabs the first dc:subject from the opf metadata
            # If title_sort applied in plugboard, that overrides using series/index as title_sort
            if metadata_x.series and self.settings().extra_customization[self.USE_SERIES_AS_CATEGORY]:
                if DEBUG:
                    logger().info(" %s._update_iTunes_metadata()" % self.__class__.__name__)
                    logger().info("   using Series name '%s' as Genre" % metadata_x.series)

                # Format the index as a sort key
                index = metadata_x.series_index
                integer = int(index)
                fraction = index - integer
                series_index = '%04d%s' % (integer, str('%0.4f' % fraction).lstrip('0'))
                if lb_added:
                    # If no title_sort plugboard tweak, create sort_name from series/index
                    if metadata.title_sort == metadata_x.title_sort:
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
                    logger().warning("  waiting for db_added to become writeable ")
                    time.sleep(1.0)
                    # If no title_sort plugboard tweak, create sort_name from series/index
                    if metadata.title_sort == metadata_x.title_sort:
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
                    logger().info("   %susing Tag as Genre" %
                     "no Series name available, " if self.settings().extra_customization[self.USE_SERIES_AS_CATEGORY] else '')
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
                lb_added.Description = ("%s %s" % (self.description_prefix, strftime('%Y-%m-%d %H:%M:%S')))
                lb_added.Enabled = True
                lb_added.SortArtist = icu_title(metadata_x.author_sort)
                lb_added.SortName = metadata_x.title_sort
                lb_added.Year = metadata_x.pubdate.year

            if db_added:
                logger().warning("  waiting for db_added to become writeable ")
                time.sleep(1.0)
                db_added.Name = metadata_x.title
                db_added.Album = metadata_x.title
                db_added.Artist = authors_to_string(metadata_x.authors)
                db_added.Composer = metadata_x.uuid
                db_added.Description = ("%s %s" % (self.description_prefix, strftime('%Y-%m-%d %H:%M:%S')))
                db_added.Enabled = True
                db_added.SortArtist = icu_title(metadata_x.author_sort)
                db_added.SortName = metadata_x.title_sort
                db_added.Year = metadata_x.pubdate.year

            if metadata_x.comments:
                if lb_added:
                    lb_added.Comment = (STRIP_TAGS.sub('', metadata_x.comments))
                if db_added:
                    db_added.Comment = (STRIP_TAGS.sub('', metadata_x.comments))

            if metadata_x.rating:
                if lb_added:
                    lb_added.AlbumRating = (metadata_x.rating * 10)
                # iBooks currently doesn't allow setting rating ... ?
                try:
                    if db_added:
                        db_added.AlbumRating = (metadata_x.rating * 10)
                except:
                    if DEBUG:
                        logger().warning("  iTunes automation interface reported an error"
                                         " setting AlbumRating on iDevice")

            # Set Genre from first alpha tag, overwrite with series if available
            # Otherwise iBooks uses first <dc:subject> from opf
            # iTunes balks on setting EpisodeNumber, but it sticks (9.1.1.12)

            if metadata_x.series and self.settings().extra_customization[self.USE_SERIES_AS_CATEGORY]:
                if DEBUG:
                    logger().info("   using Series name as Genre")
                # Format the index as a sort key
                index = metadata_x.series_index
                integer = int(index)
                fraction = index - integer
                series_index = '%04d%s' % (integer, str('%0.4f' % fraction).lstrip('0'))
                if lb_added:
                    # If no title_sort plugboard tweak, create sort_name from series/index
                    if metadata.title_sort == metadata_x.title_sort:
                        lb_added.SortName = "%s %s" % (self.title_sorter(metadata_x.series), series_index)
                    lb_added.EpisodeID = metadata_x.series

                    try:
                        lb_added.TrackNumber = metadata_x.series_index
                    except:
                        if DEBUG:
                            logger().warning("  iTunes automation interface reported an error"
                                             " setting TrackNumber in iTunes")
                    try:
                        lb_added.EpisodeNumber = metadata_x.series_index
                    except:
                        if DEBUG:
                            logger().warning("  iTunes automation interface reported an error"
                                             " setting EpisodeNumber in iTunes")

                    # If no plugboard transform applied to tags, change the Genre/Category to Series
                    if metadata.tags == metadata_x.tags:
                        lb_added.Genre = self.title_sorter(metadata_x.series)
                    else:
                        for tag in metadata_x.tags:
                            if self._is_alpha(tag[0]):
                                lb_added.Genre = tag
                                break

                if db_added:
                    # If no title_sort plugboard tweak, create sort_name from series/index
                    if metadata.title_sort == metadata_x.title_sort:
                        db_added.SortName = "%s %s" % (self.title_sorter(metadata_x.series), series_index)
                    db_added.EpisodeID = metadata_x.series

                    try:
                        db_added.TrackNumber = metadata_x.series_index
                    except:
                        if DEBUG:
                            logger().warning("  iTunes automation interface reported an error"
                                             " setting TrackNumber on iDevice")
                    try:
                        db_added.EpisodeNumber = metadata_x.series_index
                    except:
                        if DEBUG:
                            logger().warning("  iTunes automation interface reported an error"
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
                    logger().info("   using Tag as Genre")
                for tag in metadata_x.tags:
                    if self._is_alpha(tag[0]):
                        if lb_added:
                            lb_added.Genre = tag
                        if db_added:
                            db_added.Genre = tag
                        break

    def _wait_for_writable_metadata(self, db_added, delay=2.0):
        '''
        Ensure iDevice metadata is writable. DC mode only
        '''
        if DEBUG:
            logger().info(" %s._wait_for_writable_metadata()" % self.__class__.__name__)

        attempts = 9
        while attempts:
            try:
                if isosx:
                    db_added.bpm.set(0)
                elif iswindows:
                    db_added.BPM = 0
                break
            except:
                attempts -= 1
                time.sleep(delay)
                if DEBUG:
                    logger().warning("  waiting %.1f seconds for iDevice metadata to become writable (attempt #%d)" %
                                     (delay, (10 - attempts)))
        else:
            if DEBUG:
                logger().error(" failed to write device metadata")

    def _xform_metadata_via_plugboard(self, book, format):
        ''' Transform book metadata from plugboard templates '''
        if DEBUG:
            logger().info(" %s._xform_metadata_via_plugboard()" % self.__class__.__name__)

        if self.plugboard_func:
            pb = self.plugboard_func(self.DEVICE_PLUGBOARD_NAME, format, self.plugboards)
            newmi = book.deepcopy_metadata()
            newmi.template_to_attribute(book, pb)
            if pb is not None and DEBUG:
                #logger().info(" transforming %s using %s:" % (format, pb))
                logger().info("       title: '%s' %s" % (book.title, ">>> '%s'" %
                                           newmi.title if book.title != newmi.title else ''))
                logger().info("  title_sort: %s %s" % (book.title_sort, ">>> %s" %
                                           newmi.title_sort if book.title_sort != newmi.title_sort else ''))
                logger().info("     authors: %s %s" % (book.authors, ">>> %s" %
                                           newmi.authors if book.authors != newmi.authors else ''))
                logger().info(" author_sort: %s %s" % (book.author_sort, ">>> %s" %
                                           newmi.author_sort if book.author_sort != newmi.author_sort else ''))
                logger().info("    language: %s %s" % (book.language, ">>> %s" %
                                           newmi.language if book.language != newmi.language else ''))
                logger().info("   publisher: %s %s" % (book.publisher, ">>> %s" %
                                           newmi.publisher if book.publisher != newmi.publisher else ''))
                logger().info("        tags: %s %s" % (book.tags, ">>> %s" %
                                           newmi.tags if book.tags != newmi.tags else ''))
            else:
                if DEBUG:
                    logger()("  matching plugboard not found")

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
    description = _('Communicate with iTunes.')

    # Plugboard ID
    DEVICE_PLUGBOARD_NAME = 'APPLE'

    connected = False

    def __init__(self, path):
        if DEBUG:
            logger().info("%s.__init__()" % self.__class__.__name__)

        try:
            import appscript
            appscript
        except:
            appscript = None

        if isosx and appscript is None:
            self.connected = False
            raise UserFeedback('OSX 10.5 or later required', details=None, level=UserFeedback.WARN)
            return
        else:
            self.connected = True

        if isosx:
            self._launch_iTunes()

        if iswindows:
            import pythoncom

            try:
                pythoncom.CoInitialize()
                self._launch_iTunes()
            except:
                import traceback
                traceback.print_exc()
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
                logger().info("%s.books()" % self.__class__.__name__)
                if self.settings().extra_customization[self.CACHE_COVERS]:
                    logger().info(" Cover fetching/caching enabled")
                else:
                    logger().info(" Cover fetching/caching disabled")

            # Fetch a list of books from iTunes

            booklist = BookList(logger())
            cached_books = {}

            if isosx:
                library_books = self._get_library_books()
                book_count = float(len(library_books))
                for (i, book) in enumerate(library_books):
                    format = 'pdf' if library_books[book].kind().startswith('PDF') else 'epub'
                    this_book = Book(library_books[book].name(), library_books[book].artist())
                    #this_book.path = library_books[book].location().path
                    this_book.path = self.path_template % (library_books[book].name(),
                                                           library_books[book].artist(),
                                                           format)
                    try:
                        this_book.datetime = parse_date(str(library_books[book].date_added())).timetuple()
                    except:
                        this_book.datetime = time.gmtime()
                    this_book.device_collections = []
                    #this_book.library_id = library_books[this_book.path] if this_book.path in library_books else None
                    this_book.library_id = library_books[book]
                    this_book.size = library_books[book].size()
                    this_book.uuid = library_books[book].composer()
                    this_book.cid = None
                    # Hack to discover if we're running in GUI environment
                    if self.report_progress is not None:
                        this_book.thumbnail = self._generate_thumbnail(this_book.path, library_books[book])
                    else:
                        this_book.thumbnail = None
                    booklist.add_book(this_book, False)

                    cached_books[this_book.path] = {
                     'title': library_books[book].name(),
                     'author': library_books[book].artist().split(' & '),
                     'lib_book': library_books[book],
                     'dev_book': None,
                     'uuid': library_books[book].composer(),
                     'format': format
                     }

                    if self.report_progress is not None:
                        self.report_progress((i + 1) / book_count,
                                _('%(num)d of %(tot)d') % dict(num=i + 1, tot=book_count))

            elif iswindows:
                import pythoncom, win32com.client

                try:
                    pythoncom.CoInitialize()
                    self.iTunes = win32com.client.Dispatch("iTunes.Application")
                    library_books = self._get_library_books()
                    book_count = float(len(library_books))
                    for (i, book) in enumerate(library_books):
                        this_book = Book(library_books[book].Name, library_books[book].Artist)
                        format = 'pdf' if library_books[book].KindAsString.startswith('PDF') else 'epub'
                        this_book.path = self.path_template % (library_books[book].Name,
                                                               library_books[book].Artist,
                                                               format)
                        try:
                            this_book.datetime = parse_date(str(library_books[book].DateAdded)).timetuple()
                        except:
                            this_book.datetime = time.gmtime()
                        this_book.device_collections = []
                        this_book.library_id = library_books[book]
                        this_book.size = library_books[book].Size
                        this_book.uuid = library_books[book].Composer
                        this_book.cid = None
                        # Hack to discover if we're running in GUI environment
                        if self.report_progress is not None:
                            this_book.thumbnail = self._generate_thumbnail(this_book.path, library_books[book])
                        else:
                            this_book.thumbnail = None
                        booklist.add_book(this_book, False)

                        cached_books[this_book.path] = {
                         'title': library_books[book].Name,
                         'author': library_books[book].Artist.split(' & '),
                         'lib_book': library_books[book],
                         'uuid': library_books[book].Composer,
                         'format': format
                         }

                        if self.report_progress is not None:
                            self.report_progress((i + 1) / book_count,
                                    _('%(num)d of %(tot)d') % dict(num=i + 1,
                                        tot=book_count))

                finally:
                    pythoncom.CoUninitialize()

            if self.report_progress is not None:
                self.report_progress(1.0, _('finished'))
            self.cached_books = cached_books
            if DEBUG:
                self._dump_booklist(booklist, 'returning from books()', indent=2)
                self._dump_cached_books('returning from books()', indent=2)
            return booklist

        else:
            return BookList(logger())

    def eject(self):
        '''
        Un-mount / eject the device from the OS. This does not check if there
        are pending GUI jobs that need to communicate with the device.
        '''
        if DEBUG:
            logger().info("%s.eject()" % self.__class__.__name__)
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
            logger().info("%s.free_space()" % self.__class__.__name__)
        free_space = 0
        if isosx:
            s = os.statvfs(os.sep)
            free_space = s.f_bavail * s.f_frsize
        elif iswindows:
            free_bytes = ctypes.c_ulonglong(0)
            ctypes.windll.kernel32.GetDiskFreeSpaceExW(ctypes.c_wchar_p(os.sep), None, None, ctypes.pointer(free_bytes))
            free_space = free_bytes.value
        return (free_space, -1, -1)

    def get_device_information(self, end_session=True):
        """
        Ask device for device information. See L{DeviceInfoQuery}.
        @return: (device name, device version, software version on device, mime type)
        """
        if DEBUG:
            logger().info("%s.get_device_information()" % self.__class__.__name__)

        return ('iTunes', 'hw v1.0', 'sw v1.0', 'mime type normally goes here')

    def is_usb_connected(self, devices_on_system, debug=False,
            only_presence=False):
        return self.connected, self

    def open(self, connected_device, library_uuid):
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
        if self.iTunes is None:
            raise OpenFeedback(self.ITUNES_SANDBOX_LOCKOUT_MESSAGE)

        if DEBUG:
            logger().info("%s.open(connected_device: %s)" %
                            (self.__class__.__name__, repr(connected_device)))

        # Confirm/create thumbs archive
        if not os.path.exists(self.cache_dir):
            if DEBUG:
                logger().info(" creating thumb cache '%s'" % self.cache_dir)
            os.makedirs(self.cache_dir)

        if not os.path.exists(self.archive_path):
            logger().info(" creating zip archive")
            zfw = ZipFile(self.archive_path, mode='w')
            zfw.writestr("iTunes Thumbs Archive", '')
            zfw.close()
        else:
            if DEBUG:
                logger().info(" existing thumb cache at '%s'" % self.archive_path)

        # If enabled in config options, create/confirm an iTunes storage folder
        if not self.settings().extra_customization[self.USE_ITUNES_STORAGE]:
            self.iTunes_local_storage = os.path.join(config_dir, 'iTunes storage')
            if not os.path.exists(self.iTunes_local_storage):
                if DEBUG:
                    logger()(" creating iTunes_local_storage at '%s'" % self.iTunes_local_storage)
                os.mkdir(self.iTunes_local_storage)
            else:
                if DEBUG:
                    logger()(" existing iTunes_local_storage at '%s'" % self.iTunes_local_storage)

    def sync_booklists(self, booklists, end_session=True):
        '''
        Update metadata on device.
        @param booklists: A tuple containing the result of calls to
                                (L{books}(oncard=None), L{books}(oncard='carda'),
                                L{books}(oncard='cardb')).
        '''

        if DEBUG:
            logger().info("%s.sync_booklists()" % self.__class__.__name__)

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
            logger().info("%s.unmount_device()" % self.__class__.__name__)
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
    def __init__(self, title, author):
        Metadata.__init__(self, title, authors=author.split(' & '))
        self.author = author
        self.author_sort = author_to_author_sort(author)

    @property
    def title_sorter(self):
        return title_sort(self.title)
