# -*- coding: utf-8 -*-

__license__   = 'GPL v3'
__copyright__ = '2010, Li Fanxi <lifanxi at freemindworld.com>'
__docformat__ = 'restructuredtext en'

'''
Device driver for Sanda's Bambook
'''

import time, os, hashlib
from itertools import cycle
from calibre.devices.interface import DevicePlugin
from calibre.devices.usbms.deviceconfig import DeviceConfig
from calibre.devices.bambook.libbambookcore import Bambook, text_encoding, CONN_CONNECTED
from calibre.devices.usbms.books import Book, BookList
from calibre.ebooks.metadata.book.json_codec import JsonCodec
from calibre.ptempfile import TemporaryDirectory, TemporaryFile
from calibre.constants import __appname__, __version__

class BAMBOOK(DeviceConfig, DevicePlugin):
    name           = 'Bambook Device Interface'
    description    = _('Communicate with the Sanda Bambook eBook reader.')
    author         = _('Li Fanxi')
    supported_platforms = ['windows', 'linux', 'osx']
    log_packets    = False

    booklist_class = BookList
    book_class = Book

    FORMATS = [ "snb" ]
    VENDOR_ID = 0x230b
    PRODUCT_ID = 0x0001
    BCD = None
    CAN_SET_METADATA = False
    THUMBNAIL_HEIGHT = 155

    icon = I("devices/bambook.png")
#    OPEN_FEEDBACK_MESSAGE = _(
#        'Connecting to Bambook device, please wait ...')
    BACKLOADING_ERROR_MESSAGE = _(
        'Unable to add book to library directly from Bambook. '
        'Please save the book to disk and add the file to library from disk.')

    METADATA_CACHE = '.calibre.bambook'    
    METADATA_FILE_GUID = 'calibremetadata.snb'

    bambook = None
    
    def reset(self, key='-1', log_packets=False, report_progress=None,
            detected_device=None) :
        self.open()
    
    def open(self):
        # Disconnect first if connected
        self.eject()
        # Connect
        self.bambook = Bambook()
        self.bambook.Connect()
        if self.bambook.GetState() != CONN_CONNECTED:
            self.bambook = None
            raise Exception(_("Unable to connect to Bambook."))

    def eject(self):
        if self.bambook:
            self.bambook.Disconnect()
            self.bambook = None

    def post_yank_cleanup(self):
        self.eject()

    def set_progress_reporter(self, report_progress):
        '''
        :param report_progress: Function that is called with a % progress
                                (number between 0 and 100) for various tasks
                                If it is called with -1 that means that the
                                task does not have any progress information

        '''
        self.report_progress = report_progress

    def get_device_information(self, end_session=True):
        """
        Ask device for device information. See L{DeviceInfoQuery}.

        :return: (device name, device version, software version on device, mime type)

        """
        if self.bambook:
            deviceInfo = self.bambook.GetDeviceInfo()
            return (_("Bambook"), "SD928", deviceInfo.firmwareVersion, "MimeType")
            
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

    def total_space(self, end_session=True):
        """
        Get total space available on the mountpoints:
            1. Main memory
            2. Memory Card A
            3. Memory Card B

        :return: A 3 element list with total space in bytes of (1, 2, 3). If a
                 particular device doesn't have any of these locations it should return 0.

        """
        deviceInfo = self.bambook.GetDeviceInfo()
        return (deviceInfo.deviceVolume * 1024, 0, 0)

    def free_space(self, end_session=True):
        """
        Get free space available on the mountpoints:
          1. Main memory
          2. Card A
          3. Card B

        :return: A 3 element list with free space in bytes of (1, 2, 3). If a
                 particular device doesn't have any of these locations it should return -1.

        """
        deviceInfo = self.bambook.GetDeviceInfo()
        return (deviceInfo.spareVolume * 1024, -1, -1)


    def books(self, oncard=None, end_session=True):
        """
        Return a list of ebooks on the device.

        :param oncard:  If 'carda' or 'cardb' return a list of ebooks on the
                        specific storage card, otherwise return list of ebooks
                        in main memory of device. If a card is specified and no
                        books are on the card return empty list.

        :return: A BookList.

        """
        # Bambook has no memroy card
        if oncard:
            return self.booklist_class(None, None, None)

        # Get metadata cache
        prefix = ''
        booklist = self.booklist_class(oncard, prefix, self.settings)
        need_sync = self.parse_metadata_cache(booklist)

        # Get book list from device
        devicebooks = self.bambook.GetBookList()
        books = []
        for book in devicebooks:
            if book.bookGuid == self.METADATA_FILE_GUID:
                continue
            b = self.book_class('', book.bookGuid)
            b.title = book.bookName.decode(text_encoding)
            b.authors = [ book.bookAuthor.decode(text_encoding) ] 
            b.size = 0
            b.datatime = time.gmtime()
            b.lpath = book.bookGuid
            b.thumbnail = None
            b.tags = None
            b.comments = book.bookAbstract.decode(text_encoding)
            books.append(b)

        # make a dict cache of paths so the lookup in the loop below is faster.
        bl_cache = {}
        for idx, b in enumerate(booklist):
            bl_cache[b.lpath] = idx

        def update_booklist(book, prefix):
            changed = False
            try:
                idx = bl_cache.get(book.lpath, None)
                if idx is not None:
                    bl_cache[book.lpath] = None
                    if self.update_metadata_item(book, booklist[idx]):
                        changed = True
                else:
                    if booklist.add_book(book, 
                                   replace_metadata=False):
                        changed = True
            except: # Probably a filename encoding error
                import traceback
                traceback.print_exc()
            return changed

        # Check each book on device whether it has a correspondig item
        # in metadata cache. If not, add it to cache.
        for i, book in enumerate(books):
            self.report_progress(i/float(len(books)), _('Getting list of books on device...'))
            changed = update_booklist(book, prefix)
            if changed:
                need_sync = True

        # Remove books that are no longer in the Bambook. Cache contains
        # indices into the booklist if book not in filesystem, None otherwise
        # Do the operation in reverse order so indices remain valid
        for idx in sorted(bl_cache.itervalues(), reverse=True):
            if idx is not None:
                need_sync = True
                del booklist[idx]

        if need_sync:
            self.sync_booklists((booklist, None, None))

        self.report_progress(1.0, _('Getting list of books on device...'))
        return booklist

    def upload_books(self, files, names, on_card=None, end_session=True,
                     metadata=None):
        '''
        Upload a list of books to the device. If a file already
        exists on the device, it should be replaced.
        This method should raise a :class:`FreeSpaceError` if there is not enough
        free space on the device. The text of the FreeSpaceError must contain the
        word "card" if ``on_card`` is not None otherwise it must contain the word "memory".

        :param files: A list of paths and/or file-like objects. If they are paths and
                      the paths point to temporary files, they may have an additional
                      attribute, original_file_path pointing to the originals. They may have
                      another optional attribute, deleted_after_upload which if True means
                      that the file pointed to by original_file_path will be deleted after
                      being uploaded to the device.
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
        self.report_progress(0, _('Transferring books to device...'))
        paths = []
        if self.bambook:
            for (i, f) in enumerate(files):
                self.report_progress((i+1) / float(len(files)), _('Transferring books to device...'))
                if not hasattr(f, 'read'):
                    if self.bambook.VerifySNB(f):
                        guid = self.bambook.SendFile(f, self.get_guid(metadata[i].uuid))
                        if guid:
                            paths.append(guid)
                        else:
                            print "Send fail"
                    else:
                        print "book invalid"
        ret = zip(paths, cycle([on_card]))
        self.report_progress(1.0, _('Transferring books to device...'))
        return ret

    def add_books_to_metadata(self, locations, metadata, booklists):
        metadata = iter(metadata)
        for i, location in enumerate(locations):
            self.report_progress((i+1) / float(len(locations)), _('Adding books to device metadata listing...'))
            info = metadata.next()

            # Extract the correct prefix from the pathname. To do this correctly,
            # we must ensure that both the prefix and the path are normalized
            # so that the comparison will work. Book's __init__ will fix up
            # lpath, so we don't need to worry about that here.

            book = self.book_class('', location[0], other=info)
            if book.size is None:
                book.size = 0
            b = booklists[0].add_book(book, replace_metadata=True)
            if b:
                b._new_book = True
        self.report_progress(1.0, _('Adding books to device metadata listing...'))

    def delete_books(self, paths, end_session=True):
        '''
        Delete books at paths on device.
        '''
        if self.bambook:
            for i, path in enumerate(paths):
                self.report_progress((i+1) / float(len(paths)), _('Removing books from device...'))
                self.bambook.DeleteFile(path)
            self.report_progress(1.0, _('Removing books from device...'))

    def remove_books_from_metadata(self, paths, booklists):
        '''
        Remove books from the metadata list. This function must not communicate
        with the device.

        :param paths: paths to books on the device.
        :param booklists: A tuple containing the result of calls to
                          (:meth:`books(oncard=None)`,
                          :meth:`books(oncard='carda')`,
                          :meth`books(oncard='cardb')`).

        '''
        for i, path in enumerate(paths):
            self.report_progress((i+1) / float(len(paths)), _('Removing books from device metadata listing...'))
            for bl in booklists:
                for book in bl:
                    if book.lpath == path:
                        bl.remove_book(book)
        self.report_progress(1.0, _('Removing books from device metadata listing...'))

    def sync_booklists(self, booklists, end_session=True):
        '''
        Update metadata on device.

        :param booklists: A tuple containing the result of calls to
                          (:meth:`books(oncard=None)`,
                          :meth:`books(oncard='carda')`,
                          :meth`books(oncard='cardb')`).

        '''
        if not self.bambook:
            return 

        json_codec = JsonCodec()
        
        # Create stub virtual book for sync info
        with TemporaryDirectory() as tdir:
            snbcdir = os.path.join(tdir, 'snbc')
            snbfdir = os.path.join(tdir, 'snbf')
            os.mkdir(snbcdir)
            os.mkdir(snbfdir)
            
            f = open(os.path.join(snbfdir, 'book.snbf'), 'wb')
            f.write('''<book-snbf version="1.0">
  <head>
    <name>calibre同步信息</name>
    <author>calibre</author>
    <language>ZH-CN</language>
    <rights/>
    <publisher>calibre</publisher>
    <generator>''' + __appname__ + ' ' + __version__ + '''</generator>
    <created/>
    <abstract></abstract>
    <cover/>
  </head>
</book-snbf>
''')
            f.close()
            f = open(os.path.join(snbfdir, 'toc.snbf'), 'wb')
            f.write('''<toc-snbf>
  <head>
    <chapters>0</chapters>
  </head>
  <body>
  </body>
</toc-snbf>
''');
            f.close()
            cache_name = os.path.join(snbcdir, self.METADATA_CACHE)
            with open(cache_name, 'wb') as f:
                json_codec.encode_to_file(f, booklists[0])
                
            with TemporaryFile('.snb') as f:
                if self.bambook.PackageSNB(f, tdir):
                    if not self.bambook.SendFile(f, self.METADATA_FILE_GUID):
                        print "Upload failed"
                else:
                    print "Package failed"

        # Clear the _new_book indication, as we are supposed to be done with
        # adding books at this point
        for blist in booklists:
            if blist is not None:
                for book in blist:
                    book._new_book = False

        self.report_progress(1.0, _('Sending metadata to device...'))

    def get_file(self, path, outfile, end_session=True):
        '''
        Read the file at ``path`` on the device and write it to outfile.

        :param outfile: file object like ``sys.stdout`` or the result of an
                       :func:`open` call.

        '''
        if self.bambook:
            with TemporaryDirectory() as tdir:
                if self.bambook.GetFile(path, tdir):
                    filepath = os.path.join(tdir, path)
                    f = file(filepath, 'rb')
                    outfile.write(f.read())
                    f.close()
                else:
                    print "Unable to get file from Bambook:", path

    # @classmethod
    # def config_widget(cls):
    #     '''
    #     Should return a QWidget. The QWidget contains the settings for the device interface
    #     '''
    #     raise NotImplementedError()

    # @classmethod
    # def save_settings(cls, settings_widget):
    #     '''
    #     Should save settings to disk. Takes the widget created in
    #     :meth:`config_widget` and saves all settings to disk.
    #     '''
    #     raise NotImplementedError()

    # @classmethod
    # def settings(cls):
    #     '''
    #     Should return an opts object. The opts object should have at least one attribute
    #     `format_map` which is an ordered list of formats for the device.
    #     '''
    #     raise NotImplementedError()

    def parse_metadata_cache(self, bl):
        need_sync = True
        if not self.bambook:
            return need_sync

        # Get the metadata virtual book from Bambook
        with TemporaryDirectory() as tdir:
            if self.bambook.GetFile(self.METADATA_FILE_GUID, tdir):
                cache_name = os.path.join(tdir, self.METADATA_CACHE)
                if self.bambook.ExtractSNBContent(os.path.join(tdir, self.METADATA_FILE_GUID), 
                                                  'snbc/' + self.METADATA_CACHE, 
                                                  cache_name):
                    json_codec = JsonCodec()
                    if os.access(cache_name, os.R_OK):
                        try:
                            with open(cache_name, 'rb') as f:
                                json_codec.decode_from_file(f, bl, self.book_class, '')
                                need_sync = False
                        except:
                            import traceback
                            traceback.print_exc()
                            bl = []
        return need_sync

    @classmethod
    def update_metadata_item(cls, book, blb):
        # Currently, we do not have enough information
        # from Bambook SDK to judge whether a book has
        # been changed, we assume all books has been 
        # changed.
        changed = True
        # if book.bookName.decode(text_encoding) != blb.title:
        #     changed = True
        # if book.bookAuthor.decode(text_encoding) != blb.authors[0]:
        #     changed = True
        # if book.bookAbstract.decode(text_encoding) != blb.comments:
        #     changed = True
        return changed

    @staticmethod
    def get_guid(uuid):
        guid = hashlib.md5(uuid).hexdigest()[0:15] + ".snb"
        return guid
