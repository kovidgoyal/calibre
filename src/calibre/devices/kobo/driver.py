#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Timothy Legge <timlegge at gmail.com> and Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os
import sqlite3 as sqlite

from calibre.devices.usbms.books import BookList
from calibre.devices.kobo.books import Book
from calibre.devices.kobo.books import ImageWrapper
from calibre.devices.mime import mime_type_ext
from calibre.devices.usbms.driver import USBMS, debug_print
from calibre import prints
from calibre.devices.usbms.books import CollectionsBookList

class KOBO(USBMS):

    name = 'Kobo Reader Device Interface'
    gui_name = 'Kobo Reader'
    description = _('Communicate with the Kobo Reader')
    author = 'Timothy Legge and Kovid Goyal'
    version = (1, 0, 7)

    dbversion = 0
    fwversion = 0
    has_kepubs = False

    supported_platforms = ['windows', 'osx', 'linux']

    booklist_class = CollectionsBookList

    # Ordered list of supported formats
    FORMATS     = ['epub', 'pdf']
    CAN_SET_METADATA = ['collections']

    VENDOR_ID   = [0x2237]
    PRODUCT_ID  = [0x4161]
    BCD         = [0x0110]

    VENDOR_NAME = ['KOBO_INC', 'KOBO']
    WINDOWS_MAIN_MEM = WINDOWS_CARD_A_MEM = ['.KOBOEREADER', 'EREADER']

    EBOOK_DIR_MAIN = ''
    SUPPORTS_SUB_DIRS = True

    VIRTUAL_BOOK_EXTENSIONS = frozenset(['kobo'])

    EXTRA_CUSTOMIZATION_MESSAGE = _('The Kobo supports only one collection '
            'currently: the \"Im_Reading\" list.  Create a tag called \"Im_Reading\" ')+\
                    'for automatic management'

    EXTRA_CUSTOMIZATION_DEFAULT = ', '.join(['tags'])

    def initialize(self):
        USBMS.initialize(self)
        self.book_class = Book

    def books(self, oncard=None, end_session=True):
        from calibre.ebooks.metadata.meta import path_to_ext

        dummy_bl = BookList(None, None, None)

        if oncard == 'carda' and not self._card_a_prefix:
            self.report_progress(1.0, _('Getting list of books on device...'))
            return dummy_bl
        elif oncard == 'cardb' and not self._card_b_prefix:
            self.report_progress(1.0, _('Getting list of books on device...'))
            return dummy_bl
        elif oncard and oncard != 'carda' and oncard != 'cardb':
            self.report_progress(1.0, _('Getting list of books on device...'))
            return dummy_bl

        prefix = self._card_a_prefix if oncard == 'carda' else \
                 self._card_b_prefix if oncard == 'cardb' \
                 else self._main_prefix

        # Determine the firmware version
        f = open(self.normalize_path(self._main_prefix + '.kobo/version'), 'r')
        fwversion = f.readline().split(',')[2]
        f.close()
        if fwversion != '1.0' and fwversion != '1.4':
            self.has_kepubs = True
        debug_print('Version of firmware: ', fwversion, 'Has kepubs:', self.has_kepubs)

        self.booklist_class.rebuild_collections = self.rebuild_collections

        # get the metadata cache
        bl = self.booklist_class(oncard, prefix, self.settings)
        need_sync = self.parse_metadata_cache(bl, prefix, self.METADATA_CACHE)

        # make a dict cache of paths so the lookup in the loop below is faster.
        bl_cache = {}
        for idx,b in enumerate(bl):
            bl_cache[b.lpath] = idx

        def update_booklist(prefix, path, title, authors, mime, date, ContentType, ImageID, readstatus):
            changed = False
            # if path_to_ext(path) in self.FORMATS:
            try:
                lpath = path.partition(self.normalize_path(prefix))[2]
                if lpath.startswith(os.sep):
                    lpath = lpath[len(os.sep):]
                lpath = lpath.replace('\\', '/')
                # debug_print("LPATH: ", lpath, "  - Title:  " , title)

                playlist_map = {}

                if readstatus == 1:
                    playlist_map[lpath]= "Im_Reading"
                elif readstatus == 2:
                    playlist_map[lpath]= "Read"

                path = self.normalize_path(path)
                # print "Normalized FileName: " + path

                idx = bl_cache.get(lpath, None)
                if idx is not None:
                    bl_cache[lpath] = None
                    if ImageID is not None:
                        imagename = self.normalize_path(self._main_prefix + '.kobo/images/' + ImageID + ' - NickelBookCover.parsed')
                        #print "Image name Normalized: " + imagename
                        if imagename is not None:
                            bl[idx].thumbnail = ImageWrapper(imagename)
                    if (ContentType != '6'and self.has_kepubs == False) or (self.has_kepubs == True):
                        if self.update_metadata_item(bl[idx]):
                            # print 'update_metadata_item returned true'
                            changed = True
                    if lpath in playlist_map and \
                        playlist_map[lpath] not in bl[idx].device_collections:
                            bl[idx].device_collections.append(playlist_map[lpath])
                else:
                    if ContentType == '6' and self.has_kepubs == False:
                        book =  Book(prefix, lpath, title, authors, mime, date, ContentType, ImageID, size=1048576)
                    else:
                        try:
                            book = self.book_from_path(prefix, lpath, title, authors, mime, date, ContentType, ImageID)
                        except:
                            debug_print("prefix: ", prefix, "lpath: ", lpath, "title: ", title, "authors: ", authors, \
                                        "mime: ", mime, "date: ", date, "ContentType: ", ContentType, "ImageID: ", ImageID)
                            raise

                    # print 'Update booklist'
                    book.device_collections = [playlist_map[lpath]] if lpath in playlist_map else []

                    if bl.add_book(book, replace_metadata=False):
                        changed = True
            except: # Probably a path encoding error
                import traceback
                traceback.print_exc()
            return changed

        connection = sqlite.connect(self.normalize_path(self._main_prefix + '.kobo/KoboReader.sqlite'))
        cursor = connection.cursor()

        #query = 'select count(distinct volumeId) from volume_shortcovers'
        #cursor.execute(query)
        #for row in (cursor):
        #    numrows = row[0]
        #cursor.close()

        # Determine the database version
        # 4 - Bluetooth Kobo Rev 2 (1.4)
        # 8 - WIFI KOBO Rev 1
        cursor.execute('select version from dbversion')
        result = cursor.fetchone()
        self.dbversion = result[0]

        query= 'select Title, Attribution, DateCreated, ContentID, MimeType, ContentType, ' \
                'ImageID, ReadStatus from content where BookID is Null'

        cursor.execute (query)

        changed = False
        for i, row in enumerate(cursor):
        #  self.report_progress((i+1) / float(numrows), _('Getting list of books on device...'))

            path = self.path_from_contentid(row[3], row[5], oncard)
            mime = mime_type_ext(path_to_ext(path)) if path.find('kepub') == -1 else 'application/epub+zip'
            # debug_print("mime:", mime)

            if oncard != 'carda' and oncard != 'cardb' and not row[3].startswith("file:///mnt/sd/"):
                changed = update_booklist(self._main_prefix, path, row[0], row[1], mime, row[2], row[5], row[6], row[7])
                # print "shortbook: " + path
            elif oncard == 'carda' and row[3].startswith("file:///mnt/sd/"):
                changed = update_booklist(self._card_a_prefix, path, row[0], row[1], mime, row[2], row[5], row[6], row[7])

            if changed:
                need_sync = True

        cursor.close()
        connection.close()

        # Remove books that are no longer in the filesystem. Cache contains
        # indices into the booklist if book not in filesystem, None otherwise
        # Do the operation in reverse order so indices remain valid
        for idx in sorted(bl_cache.itervalues(), reverse=True):
            if idx is not None:
                need_sync = True
                del bl[idx]

        #print "count found in cache: %d, count of files in metadata: %d, need_sync: %s" % \
        #      (len(bl_cache), len(bl), need_sync)
        if need_sync: #self.count_found_in_bl != len(bl) or need_sync:
            if oncard == 'cardb':
                self.sync_booklists((None, None, bl))
            elif oncard == 'carda':
                self.sync_booklists((None, bl, None))
            else:
                self.sync_booklists((bl, None, None))

        self.report_progress(1.0, _('Getting list of books on device...'))
        return bl

    def delete_via_sql(self, ContentID, ContentType):
        # Delete Order:
        #    1) shortcover_page
        #    2) volume_shorcover
        #    2) content

        connection = sqlite.connect(self.normalize_path(self._main_prefix + '.kobo/KoboReader.sqlite'))
        cursor = connection.cursor()
        t = (ContentID,)
        cursor.execute('select ImageID from content where ContentID = ?', t)

        ImageID = None
        for row in cursor:
            # First get the ImageID to delete the images
            ImageID = row[0]
        cursor.close()

        cursor = connection.cursor()
        if ContentType == 6 and self.dbversion < 8:
            # Delete the shortcover_pages first
            cursor.execute('delete from shortcover_page where shortcoverid in (select ContentID from content where BookID = ?)', t)

        #Delete the volume_shortcovers second
        cursor.execute('delete from volume_shortcovers where volumeid = ?', t)

        # Delete the rows from content_keys
        if self.dbversion >= 8:
            cursor.execute('delete from content_keys where volumeid = ?', t)

        # Delete the chapters associated with the book next
        t = (ContentID,ContentID,)
        cursor.execute('delete from content where BookID  = ? or ContentID = ?', t)

        connection.commit()

        cursor.close()
        if ImageID == None:
            print "Error condition ImageID was not found"
            print "You likely tried to delete a book that the kobo has not yet added to the database"

        connection.close()
        # If all this succeeds we need to delete the images files via the ImageID
        return ImageID

    def delete_images(self, ImageID):
        if ImageID != None:
            path_prefix = '.kobo/images/'
            path = self._main_prefix + path_prefix + ImageID

            file_endings = (' - iPhoneThumbnail.parsed', ' - bbMediumGridList.parsed', ' - NickelBookCover.parsed',)

            for ending in file_endings:
                fpath = path + ending
                fpath = self.normalize_path(fpath)

                if os.path.exists(fpath):
                    # print 'Image File Exists: ' + fpath
                    os.unlink(fpath)

    def delete_books(self, paths, end_session=True):
        for i, path in enumerate(paths):
            self.report_progress((i+1) / float(len(paths)), _('Removing books from device...'))
            path = self.normalize_path(path)
            # print "Delete file normalized path: " + path
            extension =  os.path.splitext(path)[1]
            ContentType = self.get_content_type_from_extension(extension) if extension != '' else self.get_content_type_from_path(path)

            ContentID = self.contentid_from_path(path, ContentType)

            ImageID = self.delete_via_sql(ContentID, ContentType)
            #print " We would now delete the Images for" + ImageID
            self.delete_images(ImageID)

            if os.path.exists(path):
                # Delete the ebook
                # print "Delete the ebook: " + path
                os.unlink(path)

                filepath = os.path.splitext(path)[0]
                for ext in self.DELETE_EXTS:
                    if os.path.exists(filepath + ext):
                        # print "Filename: " + filename
                        os.unlink(filepath + ext)
                    if os.path.exists(path + ext):
                        # print "Filename: " + filename
                        os.unlink(path + ext)

                if self.SUPPORTS_SUB_DIRS:
                    try:
                        # print "removed"
                        os.removedirs(os.path.dirname(path))
                    except:
                        pass
        self.report_progress(1.0, _('Removing books from device...'))

    def remove_books_from_metadata(self, paths, booklists):
        for i, path in enumerate(paths):
            self.report_progress((i+1) / float(len(paths)), _('Removing books from device metadata listing...'))
            for bl in booklists:
                for book in bl:
                    #print "Book Path: " + book.path
                    if path.endswith(book.path):
                        #print "    Remove: " + book.path
                        bl.remove_book(book)
        self.report_progress(1.0, _('Removing books from device metadata listing...'))

    def add_books_to_metadata(self, locations, metadata, booklists):
        metadata = iter(metadata)
        for i, location in enumerate(locations):
            self.report_progress((i+1) / float(len(locations)), _('Adding books to device metadata listing...'))
            info = metadata.next()
            blist = 2 if location[1] == 'cardb' else 1 if location[1] == 'carda' else 0

            # Extract the correct prefix from the pathname. To do this correctly,
            # we must ensure that both the prefix and the path are normalized
            # so that the comparison will work. Book's __init__ will fix up
            # lpath, so we don't need to worry about that here.
            path = self.normalize_path(location[0])
            if self._main_prefix:
                prefix = self._main_prefix if \
                           path.startswith(self.normalize_path(self._main_prefix)) else None
            if not prefix and self._card_a_prefix:
                prefix = self._card_a_prefix if \
                           path.startswith(self.normalize_path(self._card_a_prefix)) else None
            if not prefix and self._card_b_prefix:
                prefix = self._card_b_prefix if \
                           path.startswith(self.normalize_path(self._card_b_prefix)) else None
            if prefix is None:
                prints('in add_books_to_metadata. Prefix is None!', path,
                        self._main_prefix)
                continue
            #print "Add book to metatdata: "
            #print "prefix: " + prefix
            lpath = path.partition(prefix)[2]
            if lpath.startswith('/') or lpath.startswith('\\'):
                lpath = lpath[1:]
            #print "path: " + lpath
            #book = self.book_class(prefix, lpath, other=info)
            book = Book(prefix, lpath, '', '', '', '', '', '', other=info)
            if book.size is None:
                book.size = os.stat(self.normalize_path(path)).st_size
            b = booklists[blist].add_book(book, replace_metadata=True)
            if b:
                b._new_book = True
        self.report_progress(1.0, _('Adding books to device metadata listing...'))

    def contentid_from_path(self, path, ContentType):
        if ContentType == 6:
            if self.has_kepubs == False:
                ContentID = os.path.splitext(path)[0]
                # Remove the prefix on the file.  it could be either
                ContentID = ContentID.replace(self._main_prefix, '')
            else:
                ContentID = path
                ContentID = ContentID.replace(self._main_prefix + self.normalize_path('.kobo/kepub/'), '')

            if self._card_a_prefix is not None:
                ContentID = ContentID.replace(self._card_a_prefix, '')
        elif ContentType == 999: # HTML Files
            ContentID = path
            ContentID = ContentID.replace(self._main_prefix, "/mnt/onboard/")
            if self._card_a_prefix is not None:
                ContentID = ContentID.replace(self._card_a_prefix, "/mnt/sd/")
        else: # ContentType = 16
            ContentID = path
            ContentID = ContentID.replace(self._main_prefix, "file:///mnt/onboard/")
            if self._card_a_prefix is not None:
                ContentID = ContentID.replace(self._card_a_prefix, "file:///mnt/sd/")
        ContentID = ContentID.replace("\\", '/')
        return ContentID

    def get_content_type_from_path(self, path):
        # Strictly speaking the ContentType could be 6 or 10
        # however newspapers have the same storage format
        if path.find('kepub') >= 0:
            ContentType = 6
        return ContentType

    def get_content_type_from_extension(self, extension):
        if extension == '.kobo':
            # Kobo books do not have book files.  They do have some images though
            #print "kobo book"
            ContentType = 6
        elif extension == '.pdf' or extension == '.epub':
            # print "ePub or pdf"
            ContentType = 16
        else: # if extension == '.html' or extension == '.txt':
            ContentType = 999 # Yet another hack: to get around Kobo changing how ContentID is stored
        return ContentType

    def path_from_contentid(self, ContentID, ContentType, oncard):
        path = ContentID

        if oncard == 'cardb':
            print 'path from_contentid cardb'
        elif oncard == 'carda':
            path = path.replace("file:///mnt/sd/", self._card_a_prefix)
            # print "SD Card: " + path
        else:
            if ContentType == "6" and self.has_kepubs == False:
                # This is a hack as the kobo files do not exist
                # but the path is required to make a unique id
                # for calibre's reference
                path = self._main_prefix + path + '.kobo'
                # print "Path: " + path
            elif (ContentType == "6" or ContentType == "10") and self.has_kepubs == True:
                path = self._main_prefix + '.kobo/kepub/' + path
                # print "Internal: " + path
            else:
                # if path.startswith("file:///mnt/onboard/"):
                path = path.replace("file:///mnt/onboard/", self._main_prefix)
                path = path.replace("/mnt/onboard/", self._main_prefix)
                # print "Internal: " + path

        return path

    def get_file(self, path, *args, **kwargs):
        tpath = self.munge_path(path)
        extension =  os.path.splitext(tpath)[1]
        if extension == '.kobo':
            from calibre.devices.errors import UserFeedback
            raise UserFeedback(_("Not Implemented"),
                    _('".kobo" files do not exist on the device as books '
                        'instead, they are rows in the sqlite database. '
                    'Currently they cannot be exported or viewed.'),
                    UserFeedback.WARN)

        return USBMS.get_file(self, path, *args, **kwargs)

    @classmethod
    def book_from_path(cls, prefix, lpath, title, authors, mime, date, ContentType, ImageID):
        from calibre.ebooks.metadata import MetaInformation

        if cls.settings().read_metadata or cls.MUST_READ_METADATA:
            mi = cls.metadata_from_path(cls.normalize_path(os.path.join(prefix, lpath)))
        else:
            from calibre.ebooks.metadata.meta import metadata_from_filename
            mi = metadata_from_filename(cls.normalize_path(os.path.basename(lpath)),
                                        cls.build_template_regexp())
        if mi is None:
            mi = MetaInformation(os.path.splitext(os.path.basename(lpath))[0],
                    [_('Unknown')])
        size = os.stat(cls.normalize_path(os.path.join(prefix, lpath))).st_size
        book =  Book(prefix, lpath, title, authors, mime, date, ContentType, ImageID, size=size, other=mi)
        return book

    def get_device_paths(self):
        paths, prefixes = {}, {}
        for prefix, path, source_id in [
                ('main', 'metadata.calibre', 0),
                ('card_a', 'metadata.calibre', 1),
                ('card_b', 'metadata.calibre', 2)
                ]:
            prefix = getattr(self, '_%s_prefix'%prefix)
            if prefix is not None and os.path.exists(prefix):
                paths[source_id] = os.path.join(prefix, *(path.split('/')))
        return paths

    def update_device_database_collections(self, booklists, collections_attributes, oncard):
#        debug_print('Starting update_device_database_collections', collections_attributes)

        # Force collections_attributes to be 'tags' as no other is currently supported
#        debug_print('KOBO: overriding the provided collections_attributes:', collections_attributes)
        collections_attributes = ['tags']

        collections = booklists.get_collections(collections_attributes)
#        debug_print('Collections', collections)

        # Create a connection to the sqlite database
        # Needs to be outside books collection as in the case of removing
        # the last book from the collection the list of books is empty
        # and the removal of the last book would not occur
        connection = sqlite.connect(self.normalize_path(self._main_prefix + '.kobo/KoboReader.sqlite'))
        cursor = connection.cursor()


        if collections:
            # Process any collections that exist
            for category, books in collections.items():
                if category == 'Im_Reading':
                    # Reset Im_Reading list in the database
                    if oncard == 'carda':
                        query= 'update content set ReadStatus=0, FirstTimeReading = \'true\' where BookID is Null and ReadStatus = 1 and ContentID like \'file:///mnt/sd/%\''
                    elif oncard != 'carda' and oncard != 'cardb':
                        query= 'update content set ReadStatus=0, FirstTimeReading = \'true\' where BookID is Null and ReadStatus = 1 and ContentID not like \'file:///mnt/sd/%\''

                    try:
                        cursor.execute (query)
                    except:
                        debug_print('Database Exception:  Unable to reset Im_Reading list')
                        raise
                    else:
#                       debug_print('Commit: Reset Im_Reading list')
                        connection.commit()

                    for book in books:
#                        debug_print('Title:', book.title, 'lpath:', book.path)
                        book.device_collections = ['Im_Reading']

                        extension =  os.path.splitext(book.path)[1]
                        ContentType = self.get_content_type_from_extension(extension) if extension != '' else self.get_content_type_from_path(book.path)

                        ContentID = self.contentid_from_path(book.path, ContentType)

                        t = (ContentID,)
                        cursor.execute('select DateLastRead from Content where BookID is Null and ContentID = ?', t)
                        result = cursor.fetchone()
                        if result is None:
                            datelastread = '1970-01-01T00:00:00'
                        else:
                            datelastread = result[0] if result[0] is not None else '1970-01-01T00:00:00' 

                        t = (datelastread,ContentID,)

                        try:
                            cursor.execute('update content set ReadStatus=1,FirstTimeReading=\'false\',DateLastRead=? where BookID is Null and ContentID = ?', t)
                        except:
                            debug_print('Database Exception:  Unable create Im_Reading list')
                            raise
                        else:
                            connection.commit()
 #                           debug_print('Database: Commit create Im_Reading list')
                if category == 'Read':
                    # Reset Im_Reading list in the database
                    if oncard == 'carda':
                        query= 'update content set ReadStatus=0, FirstTimeReading = \'true\' where BookID is Null and ReadStatus = 2 and ContentID like \'file:///mnt/sd/%\''
                    elif oncard != 'carda' and oncard != 'cardb':
                        query= 'update content set ReadStatus=0, FirstTimeReading = \'true\' where BookID is Null and ReadStatus = 2 and ContentID not like \'file:///mnt/sd/%\''

                    try:
                        cursor.execute (query)
                    except:
                        debug_print('Database Exception:  Unable to reset Im_Reading list')
                        raise
                    else:
#                       debug_print('Commit: Reset Im_Reading list')
                        connection.commit()

                    for book in books:
#                       debug_print('Title:', book.title, 'lpath:', book.path)
                        book.device_collections = ['Read']

                        extension =  os.path.splitext(book.path)[1]
                        ContentType = self.get_content_type_from_extension(extension) if extension != '' else self.get_content_type_from_path(book.path)

                        ContentID = self.contentid_from_path(book.path, ContentType)
#                        datelastread = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime())

                        t = (ContentID,)

                        try:
                            cursor.execute('update content set ReadStatus=2,FirstTimeReading=\'true\' where BookID is Null and ContentID = ?', t)
                        except:
                            debug_print('Database Exception:  Unable set book as Rinished')
                            raise
                        else:
                            connection.commit()
#                            debug_print('Database: Commit set ReadStatus as Finished')
        else: # No collections
            # Since no collections exist the ReadStatus needs to be reset to 0 (Unread)
            print "Reseting ReadStatus to 0"
            # Reset Im_Reading list in the database
            if oncard == 'carda':
                query= 'update content set ReadStatus=0, FirstTimeReading = \'true\' where BookID is Null and ContentID like \'file:///mnt/sd/%\''
            elif oncard != 'carda' and oncard != 'cardb':
                query= 'update content set ReadStatus=0, FirstTimeReading = \'true\' where BookID is Null and ContentID not like \'file:///mnt/sd/%\''

            try:
                cursor.execute (query)
            except:
                debug_print('Database Exception:  Unable to reset Im_Reading list')
                raise
            else:
#               debug_print('Commit: Reset Im_Reading list')
                connection.commit()

        cursor.close()
        connection.close()

#        debug_print('Finished update_device_database_collections', collections_attributes)

    def sync_booklists(self, booklists, end_session=True):
#        debug_print('KOBO: started sync_booklists')
        paths = self.get_device_paths()

        blists = {}
        for i in paths:
            if booklists[i] is not None:
               #debug_print('Booklist: ', i)
               blists[i] = booklists[i]
        opts = self.settings()
        if opts.extra_customization:
            collections = [x.lower().strip() for x in
                    opts.extra_customization.split(',')]
        else:
            collections = []

        #debug_print('KOBO: collection fields:', collections)
        for i, blist in blists.items():
            if i == 0:
                oncard = 'main'
            else:
                oncard = 'carda'
            self.update_device_database_collections(blist, collections, oncard)

        USBMS.sync_booklists(self, booklists, end_session=end_session)
        #debug_print('KOBO: finished sync_booklists')

    def rebuild_collections(self, booklist, oncard):
        collections_attributes = []
        self.update_device_database_collections(booklist, collections_attributes, oncard)

