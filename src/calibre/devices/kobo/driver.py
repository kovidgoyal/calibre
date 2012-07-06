#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Timothy Legge <timlegge@gmail.com> and Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os, time, calendar
from contextlib import closing
from calibre.devices.usbms.books import BookList
from calibre.devices.kobo.books import Book
from calibre.devices.kobo.books import ImageWrapper
from calibre.devices.kobo.bookmark import Bookmark
from calibre.devices.mime import mime_type_ext
from calibre.devices.usbms.driver import USBMS, debug_print
from calibre import prints
from calibre.devices.usbms.books import CollectionsBookList
from calibre.ptempfile import PersistentTemporaryFile

class KOBO(USBMS):

    name = 'Kobo Reader Device Interface'
    gui_name = 'Kobo Reader'
    description = _('Communicate with the Kobo Reader')
    author = 'Timothy Legge'
    version = (1, 0, 13)

    dbversion = 0
    fwversion = 0
    supported_dbversion = 33
    has_kepubs = False

    supported_platforms = ['windows', 'osx', 'linux']

    booklist_class = CollectionsBookList

    # Ordered list of supported formats
    FORMATS     = ['epub', 'pdf', 'txt', 'cbz', 'cbr']
    CAN_SET_METADATA = ['collections']

    VENDOR_ID   = [0x2237]
    PRODUCT_ID  = [0x4161, 0x4163, 0x4165]
    BCD         = [0x0110, 0x0323, 0x0326]

    VENDOR_NAME = ['KOBO_INC', 'KOBO']
    WINDOWS_MAIN_MEM = WINDOWS_CARD_A_MEM = ['.KOBOEREADER', 'EREADER']

    EBOOK_DIR_MAIN = ''
    SUPPORTS_SUB_DIRS = True
    SUPPORTS_ANNOTATIONS = True

    VIRTUAL_BOOK_EXTENSIONS = frozenset(['kobo'])

    EXTRA_CUSTOMIZATION_MESSAGE = [
            _('The Kobo supports several collections including ')+\
                    'Read, Closed, Im_Reading. ' +\
            _('Create tags for automatic management'),
            _('Upload covers for books (newer readers)') +
            ':::'+_('Normally, the KOBO readers get the cover image from the'
                ' ebook file itself. With this option, calibre will send a '
                'separate cover image to the reader, useful if you '
                'have modified the cover.'),
            _('Upload Black and White Covers'),
            _('Show expired books') +
            ':::'+_('A bug in an earlier version left non kepubs book records'
                ' in the database.  With this option Calibre will show the '
                'expired records and allow you to delete them with '
                'the new delete logic.'),
            _('Show Previews') +
            ':::'+_('Kobo previews are included on the Touch and some other versions'
                ' by default they are no longer displayed as there is no good reason to '
                'see them.  Enable if you wish to see/delete them.'),
            _('Show Recommendations') +
            ':::'+_('Kobo now shows recommendations on the device.  In some case these have '
                'files but in other cases they are just pointers to the web site to buy. '
                'Enable if you wish to see/delete them.'),
            _('Attempt to support newer firmware') +
            ':::'+_('Kobo routinely updates the firmware and the '
                'database version.  With this option Calibre will attempt '
                'to perform full read-write functionality - Here be Dragons!! '
                'Enable only if you are comfortable with restoring your kobo '
                'to factory defaults and testing software'),
            ]

    EXTRA_CUSTOMIZATION_DEFAULT = [
            ', '.join(['tags']),
            True,
            True,
            True,
            False,
            False,
            False
            ]

    OPT_COLLECTIONS    = 0
    OPT_UPLOAD_COVERS  = 1
    OPT_UPLOAD_GRAYSCALE_COVERS  = 2
    OPT_SHOW_EXPIRED_BOOK_RECORDS = 3
    OPT_SHOW_PREVIEWS = 4
    OPT_SHOW_RECOMMENDATIONS = 5
    OPT_SUPPORT_NEWER_FIRMWARE = 6

    def initialize(self):
        USBMS.initialize(self)
        self.book_class = Book
        self.dbversion = 7

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
        try:
            with open(self.normalize_path(self._main_prefix + '.kobo/version'),
                    'rb') as f:
                self.fwversion = f.readline().split(',')[2]
        except:
            self.fwversion = 'unknown'

        if self.fwversion != '1.0' and self.fwversion != '1.4':
            self.has_kepubs = True
        debug_print('Version of driver: ', self.version, 'Has kepubs:', self.has_kepubs)
        debug_print('Version of firmware: ', self.fwversion, 'Has kepubs:', self.has_kepubs)

        self.booklist_class.rebuild_collections = self.rebuild_collections

        # get the metadata cache
        bl = self.booklist_class(oncard, prefix, self.settings)
        need_sync = self.parse_metadata_cache(bl, prefix, self.METADATA_CACHE)

        # make a dict cache of paths so the lookup in the loop below is faster.
        bl_cache = {}
        for idx,b in enumerate(bl):
            bl_cache[b.lpath] = idx

        def update_booklist(prefix, path, title, authors, mime, date, ContentType, ImageID, readstatus, MimeType, expired, favouritesindex, accessibility):
            changed = False
            try:
                lpath = path.partition(self.normalize_path(prefix))[2]
                if lpath.startswith(os.sep):
                    lpath = lpath[len(os.sep):]
                lpath = lpath.replace('\\', '/')
                # debug_print("LPATH: ", lpath, "  - Title:  " , title)

                playlist_map = {}

                if lpath not in playlist_map:
                    playlist_map[lpath] = []

                if readstatus == 1:
                    playlist_map[lpath].append('Im_Reading')
                elif readstatus == 2:
                    playlist_map[lpath].append('Read')
                elif readstatus == 3:
                    playlist_map[lpath].append('Closed')

                # Related to a bug in the Kobo firmware that leaves an expired row for deleted books
                # this shows an expired Collection so the user can decide to delete the book
                if expired == 3:
                    playlist_map[lpath].append('Expired')
                # A SHORTLIST is supported on the touch but the data field is there on most earlier models
                if favouritesindex == 1:
                    playlist_map[lpath].append('Shortlist')

                # Label Previews
                if accessibility == 6:
                    playlist_map[lpath].append('Preview')
                elif accessibility == 4:
                    playlist_map[lpath].append('Recommendation')

                path = self.normalize_path(path)
                # print "Normalized FileName: " + path

                idx = bl_cache.get(lpath, None)
                if idx is not None:
                    bl_cache[lpath] = None
                    if ImageID is not None:
                        imagename = self.normalize_path(self._main_prefix + '.kobo/images/' + ImageID + ' - NickelBookCover.parsed')
                        if not os.path.exists(imagename):
                            # Try the Touch version if the image does not exist
                            imagename = self.normalize_path(self._main_prefix + '.kobo/images/' + ImageID + ' - N3_LIBRARY_FULL.parsed')

                        #print "Image name Normalized: " + imagename
                        if not os.path.exists(imagename):
                            debug_print("Strange - The image name does not exist - title: ", title)
                        if imagename is not None:
                            bl[idx].thumbnail = ImageWrapper(imagename)
                    if (ContentType != '6' and MimeType != 'Shortcover'):
                        if os.path.exists(self.normalize_path(os.path.join(prefix, lpath))):
                            if self.update_metadata_item(bl[idx]):
                                # print 'update_metadata_item returned true'
                                changed = True
                        else:
                             debug_print("    Strange:  The file: ", prefix, lpath, " does mot exist!")
                    if lpath in playlist_map and \
                        playlist_map[lpath] not in bl[idx].device_collections:
                            bl[idx].device_collections = playlist_map.get(lpath,[])
                else:
                    if ContentType == '6' and MimeType == 'Shortcover':
                        book =  Book(prefix, lpath, title, authors, mime, date, ContentType, ImageID, size=1048576)
                    else:
                        try:
                            if os.path.exists(self.normalize_path(os.path.join(prefix, lpath))):
                                book = self.book_from_path(prefix, lpath, title, authors, mime, date, ContentType, ImageID)
                            else:
                                debug_print("    Strange:  The file: ", prefix, lpath, " does mot exist!")
                                title = "FILE MISSING: " + title
                                book =  Book(prefix, lpath, title, authors, mime, date, ContentType, ImageID, size=1048576)

                        except:
                            debug_print("prefix: ", prefix, "lpath: ", lpath, "title: ", title, "authors: ", authors, \
                                        "mime: ", mime, "date: ", date, "ContentType: ", ContentType, "ImageID: ", ImageID)
                            raise

                    # print 'Update booklist'
                    book.device_collections = playlist_map.get(lpath,[])# if lpath in playlist_map else []

                    if bl.add_book(book, replace_metadata=False):
                        changed = True
            except: # Probably a path encoding error
                import traceback
                traceback.print_exc()
            return changed

        import sqlite3 as sqlite
        with closing(sqlite.connect(
            self.normalize_path(self._main_prefix +
                '.kobo/KoboReader.sqlite'))) as connection:

            # return bytestrings if the content cannot the decoded as unicode
            connection.text_factory = lambda x: unicode(x, "utf-8", "ignore")

            cursor = connection.cursor()

            cursor.execute('select version from dbversion')
            result = cursor.fetchone()
            self.dbversion = result[0]

            debug_print("Database Version: ", self.dbversion)

            opts = self.settings()
            if self.dbversion >= 33:
                query= ('select Title, Attribution, DateCreated, ContentID, MimeType, ContentType, ' \
                    'ImageID, ReadStatus, ___ExpirationStatus, FavouritesIndex, Accessibility, IsDownloaded from content where ' \
                    'BookID is Null %(previews)s %(recomendations)s and not ((___ExpirationStatus=3 or ___ExpirationStatus is Null) %(expiry)s') % dict(expiry=' and ContentType = 6)' \
                    if opts.extra_customization[self.OPT_SHOW_EXPIRED_BOOK_RECORDS] else ')', \
                    previews=' and Accessibility <> 6' \
                    if opts.extra_customization[self.OPT_SHOW_PREVIEWS] == False else '', \
                    recomendations=' and IsDownloaded in (\'true\', 1)' \
                    if opts.extra_customization[self.OPT_SHOW_RECOMMENDATIONS] == False else '')
            elif self.dbversion >= 16 and self.dbversion < 33:
                query= ('select Title, Attribution, DateCreated, ContentID, MimeType, ContentType, ' \
                    'ImageID, ReadStatus, ___ExpirationStatus, FavouritesIndex, Accessibility, "1" as IsDownloaded from content where ' \
                    'BookID is Null and not ((___ExpirationStatus=3 or ___ExpirationStatus is Null) %(expiry)s') % dict(expiry=' and ContentType = 6)' \
                    if opts.extra_customization[self.OPT_SHOW_EXPIRED_BOOK_RECORDS] else ')')
            elif self.dbversion < 16 and self.dbversion >= 14:
                query= ('select Title, Attribution, DateCreated, ContentID, MimeType, ContentType, ' \
                    'ImageID, ReadStatus, ___ExpirationStatus, FavouritesIndex, "-1" as Accessibility, "1" as IsDownloaded from content where ' \
                    'BookID is Null and not ((___ExpirationStatus=3 or ___ExpirationStatus is Null) %(expiry)s') % dict(expiry=' and ContentType = 6)' \
                    if opts.extra_customization[self.OPT_SHOW_EXPIRED_BOOK_RECORDS] else ')')
            elif self.dbversion < 14 and self.dbversion >= 8:
                query= ('select Title, Attribution, DateCreated, ContentID, MimeType, ContentType, ' \
                    'ImageID, ReadStatus, ___ExpirationStatus, "-1" as FavouritesIndex, "-1" as Accessibility, "1" as IsDownloaded from content where ' \
                    'BookID is Null and not ((___ExpirationStatus=3 or ___ExpirationStatus is Null) %(expiry)s') % dict(expiry=' and ContentType = 6)' \
                    if opts.extra_customization[self.OPT_SHOW_EXPIRED_BOOK_RECORDS] else ')')
            else:
                query= 'select Title, Attribution, DateCreated, ContentID, MimeType, ContentType, ' \
                    'ImageID, ReadStatus, "-1" as ___ExpirationStatus, "-1" as FavouritesIndex, "-1" as Accessibility, "1" as IsDownloaded from content where BookID is Null'

            try:
                cursor.execute (query)
            except Exception as e:
                err = str(e)
                if not ('___ExpirationStatus' in err or 'FavouritesIndex' in err or
                        'Accessibility' in err or 'IsDownloaded' in err):
                    raise
                query= ('select Title, Attribution, DateCreated, ContentID, MimeType, ContentType, '
                    'ImageID, ReadStatus, "-1" as ___ExpirationStatus, "-1" as '
                    'FavouritesIndex, "-1" as Accessibility from content where '
                    'BookID is Null')
                cursor.execute(query)

            changed = False
            for i, row in enumerate(cursor):
            #  self.report_progress((i+1) / float(numrows), _('Getting list of books on device...'))
                if not hasattr(row[3], 'startswith') or row[3].startswith("file:///usr/local/Kobo/help/"):
                    # These are internal to the Kobo device and do not exist
                    continue
                path = self.path_from_contentid(row[3], row[5], row[4], oncard)
                mime = mime_type_ext(path_to_ext(path)) if path.find('kepub') == -1 else 'application/epub+zip'
                # debug_print("mime:", mime)

                if oncard != 'carda' and oncard != 'cardb' and not row[3].startswith("file:///mnt/sd/"):
                    changed = update_booklist(self._main_prefix, path, row[0], row[1], mime, row[2], row[5], row[6], row[7], row[4], row[8], row[9], row[10])
                    # print "shortbook: " + path
                elif oncard == 'carda' and row[3].startswith("file:///mnt/sd/"):
                    changed = update_booklist(self._card_a_prefix, path, row[0], row[1], mime, row[2], row[5], row[6], row[7], row[4], row[8], row[9], row[10])

                if changed:
                    need_sync = True

            cursor.close()

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

        import sqlite3 as sqlite
        debug_print('delete_via_sql: ContentID: ', ContentID, 'ContentType: ', ContentType)
        with closing(sqlite.connect(self.normalize_path(self._main_prefix +
            '.kobo/KoboReader.sqlite'))) as connection:

            # return bytestrings if the content cannot the decoded as unicode
            connection.text_factory = lambda x: unicode(x, "utf-8", "ignore")

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
            t = (ContentID,)
            # Kobo does not delete the Book row (ie the row where the BookID is Null)
            # The next server sync should remove the row
            cursor.execute('delete from content where BookID = ?', t)
            if ContentType == 6:
                try:
                    cursor.execute('update content set ReadStatus=0, FirstTimeReading = \'true\', ___PercentRead=0, ___ExpirationStatus=3 ' \
                        'where BookID is Null and ContentID =?',t)
                except Exception as e:
                    if 'no such column' not in str(e):
                        raise
                    try:
                        cursor.execute('update content set ReadStatus=0, FirstTimeReading = \'true\', ___PercentRead=0 ' \
                            'where BookID is Null and ContentID =?',t)
                    except Exception as e:
                        if 'no such column' not in str(e):
                            raise
                        cursor.execute('update content set ReadStatus=0, FirstTimeReading = \'true\' ' \
                            'where BookID is Null and ContentID =?',t)
            else:
                cursor.execute('delete from content where BookID is Null and ContentID =?',t)

            connection.commit()

            cursor.close()
            if ImageID == None:
                print "Error condition ImageID was not found"
                print "You likely tried to delete a book that the kobo has not yet added to the database"

        # If all this succeeds we need to delete the images files via the ImageID
        return ImageID

    def delete_images(self, ImageID):
        if ImageID != None:
            path_prefix = '.kobo/images/'
            path = self._main_prefix + path_prefix + ImageID

            file_endings = (' - iPhoneThumbnail.parsed', ' - bbMediumGridList.parsed', ' - NickelBookCover.parsed', ' - N3_LIBRARY_FULL.parsed', ' - N3_LIBRARY_GRID.parsed', ' - N3_LIBRARY_LIST.parsed', ' - N3_SOCIAL_CURRENTREAD.parsed', ' - N3_FULL.parsed',)

            for ending in file_endings:
                fpath = path + ending
                fpath = self.normalize_path(fpath)

                if os.path.exists(fpath):
                    # print 'Image File Exists: ' + fpath
                    os.unlink(fpath)

    def delete_books(self, paths, end_session=True):
        if self.modify_database_check("delete_books") == False:
            return 

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
        if self.modify_datbase_check("remove_books_from_metatata") == False:
            return 

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
            extension =  os.path.splitext(path)[1]
            if extension == '.kobo':
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
        elif extension == '.rtf' or extension == '.txt' or extension == '.htm' or extension == '.html':
            # print "txt"
            if self.fwversion == '1.0' or self.fwversion == '1.4' or self.fwversion == '1.7.4':
                ContentType = 999
            else:
                ContentType = 901
        else: # if extension == '.html' or extension == '.txt':
            ContentType = 901 # Yet another hack: to get around Kobo changing how ContentID is stored
        return ContentType

    def path_from_contentid(self, ContentID, ContentType, MimeType, oncard):
        path = ContentID

        if oncard == 'cardb':
            print 'path from_contentid cardb'
        elif oncard == 'carda':
            path = path.replace("file:///mnt/sd/", self._card_a_prefix)
            # print "SD Card: " + path
        else:
            if ContentType == "6" and MimeType == 'Shortcover':
                # This is a hack as the kobo files do not exist
                # but the path is required to make a unique id
                # for calibre's reference
                path = self._main_prefix + path + '.kobo'
                # print "Path: " + path
            elif (ContentType == "6" or ContentType == "10") and MimeType == 'application/x-kobo-epub+zip':
                if path.startswith("file:///mnt/onboard/"):
                    path = self._main_prefix + path.replace("file:///mnt/onboard/", '')
                else:
                    path = self._main_prefix + '.kobo/kepub/' + path
                # print "Internal: " + path
            else:
                # if path.startswith("file:///mnt/onboard/"):
                path = path.replace("file:///mnt/onboard/", self._main_prefix)
                path = path.replace("/mnt/onboard/", self._main_prefix)
                # print "Internal: " + path

        return path

    def modify_database_check(self, function):
        # Checks to see whether the database version is supported
        # and whether the user has chosen to support the firmware version
        if self.dbversion > self.supported_dbversion:
            # Unsupported database 
            opts = self.settings()
            if not opts.extra_customization[self.OPT_SUPPORT_NEWER_FIRMWARE]:
                debug_print('The database has been upgraded past supported version')
                debug_print('The database has been upgraded past supported version')
                self.report_progress(1.0, _('Removing books from device...'))
                return False
            else:
                # The user chose to edit the database anyway
                return True
        else:
            # Supported database version
            return True

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

    def reset_readstatus(self, connection, oncard):
        cursor = connection.cursor()

        # Reset Im_Reading list in the database
        if oncard == 'carda':
            query= 'update content set ReadStatus=0, FirstTimeReading = \'true\' where BookID is Null and ContentID like \'file:///mnt/sd/%\''
        elif oncard != 'carda' and oncard != 'cardb':
            query= 'update content set ReadStatus=0, FirstTimeReading = \'true\' where BookID is Null and ContentID not like \'file:///mnt/sd/%\''

        try:
            cursor.execute (query)
        except:
            debug_print('    Database Exception:  Unable to reset ReadStatus list')
            raise
        else:
            connection.commit()
            # debug_print('    Commit: Reset ReadStatus list')

        cursor.close()

    def set_readstatus(self, connection, ContentID, ReadStatus):
        cursor = connection.cursor()
        t = (ContentID,)
        cursor.execute('select DateLastRead from Content where BookID is Null and ContentID = ?', t)
        result = cursor.fetchone()
        if result is None:
            datelastread = '1970-01-01T00:00:00'
        else:
            datelastread = result[0] if result[0] is not None else '1970-01-01T00:00:00'

        t = (ReadStatus,datelastread,ContentID,)

        try:
            cursor.execute('update content set ReadStatus=?,FirstTimeReading=\'false\',DateLastRead=? where BookID is Null and ContentID = ?', t)
        except:
            debug_print('    Database Exception:  Unable update ReadStatus')
            raise
        else:
            connection.commit()
            # debug_print('    Commit: Setting ReadStatus List')
        cursor.close()

    def reset_favouritesindex(self, connection, oncard):
        # Reset FavouritesIndex list in the database
        if oncard == 'carda':
            query= 'update content set FavouritesIndex=-1 where BookID is Null and ContentID like \'file:///mnt/sd/%\''
        elif oncard != 'carda' and oncard != 'cardb':
            query= 'update content set FavouritesIndex=-1 where BookID is Null and ContentID not like \'file:///mnt/sd/%\''

        cursor = connection.cursor()
        try:
            cursor.execute (query)
        except Exception as e:
            debug_print('    Database Exception:  Unable to reset Shortlist list')
            if 'no such column' not in str(e):
                raise
        else:
            connection.commit()
            # debug_print('    Commit: Reset FavouritesIndex list')

    def set_favouritesindex(self, connection, ContentID):
        cursor = connection.cursor()

        t = (ContentID,)

        try:
            cursor.execute('update content set FavouritesIndex=1 where BookID is Null and ContentID = ?', t)
        except Exception as e:
            debug_print('    Database Exception:  Unable set book as Shortlist')
            if 'no such column' not in str(e):
                raise
        else:
            connection.commit()
            # debug_print('    Commit: Set FavouritesIndex')

    def update_device_database_collections(self, booklists, collections_attributes, oncard):
        if self.modify_database_check("update_device_database_collections") == False:
            return 

        # Only process categories in this list
        supportedcategories = {
            "Im_Reading":1,
            "Read":2,
            "Closed":3,
            "Shortlist":4,
            # "Preview":99, # Unsupported as we don't want to change it
        }

        # Define lists for the ReadStatus
        readstatuslist = {
            "Im_Reading":1,
            "Read":2,
            "Closed":3,
        }

        accessibilitylist = {
            "Preview":6,
            "Recommendation":4,
       }
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

        import sqlite3 as sqlite
        with closing(sqlite.connect(self.normalize_path(self._main_prefix +
            '.kobo/KoboReader.sqlite'))) as connection:

            # return bytestrings if the content cannot the decoded as unicode
            connection.text_factory = lambda x: unicode(x, "utf-8", "ignore")

            if collections:

                # Need to reset the collections outside the particular loops
                # otherwise the last item will not be removed
                self.reset_readstatus(connection, oncard)
                if self.dbversion >= 14:
                    self.reset_favouritesindex(connection, oncard)

                # Process any collections that exist
                for category, books in collections.items():
                    if category in supportedcategories:
                        # debug_print("Category: ", category, " id = ", readstatuslist.get(category))
                        for book in books:
                            # debug_print('    Title:', book.title, 'category: ', category)
                            if category not in book.device_collections:
                                book.device_collections.append(category)

                            extension =  os.path.splitext(book.path)[1]
                            ContentType = self.get_content_type_from_extension(extension) if extension != '' else self.get_content_type_from_path(book.path)

                            ContentID = self.contentid_from_path(book.path, ContentType)

                            if category in readstatuslist.keys():
                                # Manage ReadStatus
                                self.set_readstatus(connection, ContentID, readstatuslist.get(category))
                            elif category == 'Shortlist' and self.dbversion >= 14:
                                # Manage FavouritesIndex/Shortlist
                                self.set_favouritesindex(connection, ContentID)
                            elif category in accessibilitylist.keys():
                                # Do not manage the Accessibility List
                                pass
            else: # No collections
                # Since no collections exist the ReadStatus needs to be reset to 0 (Unread)
                debug_print("No Collections - reseting ReadStatus")
                self.reset_readstatus(connection, oncard)
                if self.dbversion >= 14:
                    debug_print("No Collections - reseting FavouritesIndex")
                    self.reset_favouritesindex(connection, oncard)

#        debug_print('Finished update_device_database_collections', collections_attributes)

    def sync_booklists(self, booklists, end_session=True):
#        debug_print('KOBO: started sync_booklists')
        paths = self.get_device_paths()

        blists = {}
        for i in paths:
            try:
                if booklists[i] is not None:
                    #debug_print('Booklist: ', i)
                    blists[i] = booklists[i]
            except IndexError:
                pass
        opts = self.settings()
        if opts.extra_customization:
            collections = [x.lower().strip() for x in
                    opts.extra_customization[self.OPT_COLLECTIONS].split(',')]
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

    def upload_cover(self, path, filename, metadata, filepath):
        '''
        Upload book cover to the device. Default implementation does nothing.

        :param path: The full path to the directory where the associated book is located.
        :param filename: The name of the book file without the extension.
        :param metadata: metadata belonging to the book. Use metadata.thumbnail
                         for cover
        :param filepath: The full path to the ebook file

        '''

        opts = self.settings()
        if not opts.extra_customization[self.OPT_UPLOAD_COVERS]:
            # Building thumbnails disabled
            debug_print('KOBO: not uploading cover')
            return

        if not opts.extra_customization[self.OPT_UPLOAD_GRAYSCALE_COVERS]:
            uploadgrayscale = False
        else:
            uploadgrayscale = True

        debug_print('KOBO: uploading cover')
        try:
            self._upload_cover(path, filename, metadata, filepath, uploadgrayscale)
        except:
            debug_print('FAILED to upload cover', filepath)

    def _upload_cover(self, path, filename, metadata, filepath, uploadgrayscale):
        from calibre.utils.magick.draw import save_cover_data_to
        if metadata.cover:
            cover = self.normalize_path(metadata.cover.replace('/', os.sep))

            if os.path.exists(cover):
                # Get ContentID for Selected Book
                extension =  os.path.splitext(filepath)[1]
                ContentType = self.get_content_type_from_extension(extension) if extension != '' else self.get_content_type_from_path(filepath)
                ContentID = self.contentid_from_path(filepath, ContentType)

                import sqlite3 as sqlite
                with closing(sqlite.connect(self.normalize_path(self._main_prefix +
                    '.kobo/KoboReader.sqlite'))) as connection:

                    # return bytestrings if the content cannot the decoded as unicode
                    connection.text_factory = lambda x: unicode(x, "utf-8", "ignore")

                    cursor = connection.cursor()
                    t = (ContentID,)
                    cursor.execute('select ImageId from Content where BookID is Null and ContentID = ?', t)
                    result = cursor.fetchone()
                    if result is None:
                        debug_print("No rows exist in the database - cannot upload")
                        return
                    else:
                        ImageID = result[0]
#                        debug_print("ImageId: ", result[0])

                    cursor.close()

                if ImageID != None:
                    path_prefix = '.kobo/images/'
                    path = self._main_prefix + path_prefix + ImageID

                    file_endings = {' - iPhoneThumbnail.parsed':(103,150),
                            ' - bbMediumGridList.parsed':(93,135),
                            ' - NickelBookCover.parsed':(500,725),
                            ' - N3_LIBRARY_FULL.parsed':(355,530),
                            ' - N3_LIBRARY_GRID.parsed':(149,233),
                            ' - N3_LIBRARY_LIST.parsed':(60,90),
                            ' - N3_FULL.parsed':(600,800),
                            ' - N3_SOCIAL_CURRENTREAD.parsed':(120,186)}

                    for ending, resize in file_endings.items():
                        fpath = path + ending
                        fpath = self.normalize_path(fpath.replace('/', os.sep))

                        if os.path.exists(fpath):
                            with open(cover, 'rb') as f:
                                data = f.read()

                            # Return the data resized and in Grayscale if
                            # required
                            data = save_cover_data_to(data, 'dummy.jpg',
                                    grayscale=uploadgrayscale,
                                    resize_to=resize, return_data=True)

                            with open(fpath, 'wb') as f:
                                f.write(data)

                else:
                    debug_print("ImageID could not be retreived from the database")

    def prepare_addable_books(self, paths):
        '''
        The Kobo supports an encrypted epub refered to as a kepub
        Unfortunately Kobo decided to put the files on the device
        with no file extension.  I just hope that decision causes
        them as much grief as it does me :-)

        This has to make a temporary copy of the book files with a
        epub extension to allow Calibre's normal processing to
        deal with the file appropriately
        '''
        for idx, path in enumerate(paths):
            if path.find('kepub') >= 0:
                with closing(open(path)) as r:
                    tf = PersistentTemporaryFile(suffix='.epub')
                    tf.write(r.read())
                    paths[idx] = tf.name
        return paths

    def create_annotations_path(self, mdata, device_path=None):
        if device_path:
            return device_path
        return USBMS.create_annotations_path(self, mdata)

    def get_annotations(self, path_map):
        EPUB_FORMATS = [u'epub']
        epub_formats = set(EPUB_FORMATS)

        def get_storage():
            storage = []
            if self._main_prefix:
                storage.append(os.path.join(self._main_prefix, self.EBOOK_DIR_MAIN))
            if self._card_a_prefix:
                storage.append(os.path.join(self._card_a_prefix, self.EBOOK_DIR_CARD_A))
            if self._card_b_prefix:
                storage.append(os.path.join(self._card_b_prefix, self.EBOOK_DIR_CARD_B))
            return storage

        def resolve_bookmark_paths(storage, path_map):
            pop_list = []
            book_ext = {}
            for id in path_map:
                file_fmts = set()
                for fmt in path_map[id]['fmts']:
                    file_fmts.add(fmt)
                bookmark_extension = None
                if file_fmts.intersection(epub_formats):
                    book_extension = list(file_fmts.intersection(epub_formats))[0]
                    bookmark_extension = 'epub'

                if bookmark_extension:
                    for vol in storage:
                        bkmk_path = path_map[id]['path']
                        bkmk_path = bkmk_path
                        if os.path.exists(bkmk_path):
                            path_map[id] = bkmk_path
                            book_ext[id] = book_extension
                            break
                    else:
                        pop_list.append(id)
                else:
                    pop_list.append(id)

            # Remove non-existent bookmark templates
            for id in pop_list:
                path_map.pop(id)
            return path_map, book_ext

        storage = get_storage()
        path_map, book_ext = resolve_bookmark_paths(storage, path_map)

        bookmarked_books = {}
        for id in path_map:
            extension =  os.path.splitext(path_map[id])[1]
            ContentType = self.get_content_type_from_extension(extension) if extension != '' else self.get_content_type_from_path(path_map[id])
            ContentID = self.contentid_from_path(path_map[id], ContentType)

            bookmark_ext = extension

            db_path = self.normalize_path(self._main_prefix + '.kobo/KoboReader.sqlite')
            myBookmark = Bookmark(db_path, ContentID, path_map[id], id, book_ext[id], bookmark_ext)
            bookmarked_books[id] = self.UserAnnotation(type='kobo_bookmark', value=myBookmark)

        # This returns as job.result in gui2.ui.annotations_fetched(self,job)
        return bookmarked_books

    def generate_annotation_html(self, bookmark):
        from calibre.ebooks.BeautifulSoup import BeautifulSoup, Tag, NavigableString
        # Returns <div class="user_annotations"> ... </div>
        #last_read_location = bookmark.last_read_location
        #timestamp = bookmark.timestamp
        percent_read = bookmark.percent_read
        debug_print("Date: ",  bookmark.last_read)
        if bookmark.last_read is not None:
            try:
                last_read = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(calendar.timegm(time.strptime(bookmark.last_read, "%Y-%m-%dT%H:%M:%S"))))
            except:
                last_read = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(calendar.timegm(time.strptime(bookmark.last_read, "%Y-%m-%dT%H:%M:%S.%f"))))
        else:
            #self.datetime = time.gmtime()
            last_read = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())

        # debug_print("Percent read: ", percent_read)
        ka_soup = BeautifulSoup()
        dtc = 0
        divTag = Tag(ka_soup,'div')
        divTag['class'] = 'user_annotations'

        # Add the last-read location
        spanTag = Tag(ka_soup, 'span')
        spanTag['style'] = 'font-weight:normal'
        if bookmark.book_format == 'epub':
            spanTag.insert(0,NavigableString(
                _("<hr /><b>Book Last Read:</b> %(time)s<br /><b>Percentage Read:</b> %(pr)d%%<hr />") % \
                            dict(time=last_read,
                            #loc=last_read_location,
                            pr=percent_read)))
        else:
            spanTag.insert(0,NavigableString(
                _("<hr /><b>Book Last Read:</b> %(time)s<br /><b>Percentage Read:</b> %(pr)d%%<hr />") % \
                            dict(time=last_read,
                            #loc=last_read_location,
                            pr=percent_read)))

        divTag.insert(dtc, spanTag)
        dtc += 1
        divTag.insert(dtc, Tag(ka_soup,'br'))
        dtc += 1

        if bookmark.user_notes:
            user_notes = bookmark.user_notes
            annotations = []

            # Add the annotations sorted by location
            for location in sorted(user_notes):
                if user_notes[location]['type'] == 'Bookmark':
                    annotations.append(
                        _('<b>Chapter %(chapter)d:</b> %(chapter_title)s<br /><b>%(typ)s</b><br /><b>Chapter Progress:</b> %(chapter_progress)s%%<br />%(annotation)s<br /><hr />') % \
                            dict(chapter=user_notes[location]['chapter'],
                                dl=user_notes[location]['displayed_location'],
                                typ=user_notes[location]['type'],
                                chapter_title=user_notes[location]['chapter_title'],
                                chapter_progress=user_notes[location]['chapter_progress'],
                                annotation=user_notes[location]['annotation'] if user_notes[location]['annotation'] is not None else ""))
                elif user_notes[location]['type'] == 'Highlight':
                    annotations.append(
                        _('<b>Chapter %(chapter)d:</b> %(chapter_title)s<br /><b>%(typ)s</b><br /><b>Chapter Progress:</b> %(chapter_progress)s%%<br /><b>Highlight:</b> %(text)s<br /><hr />') % \
                            dict(chapter=user_notes[location]['chapter'],
                                dl=user_notes[location]['displayed_location'],
                                typ=user_notes[location]['type'],
                                chapter_title=user_notes[location]['chapter_title'],
                                chapter_progress=user_notes[location]['chapter_progress'],
                                text=user_notes[location]['text']))
                elif user_notes[location]['type'] == 'Annotation':
                    annotations.append(
                        _('<b>Chapter %(chapter)d:</b> %(chapter_title)s<br /><b>%(typ)s</b><br /><b>Chapter Progress:</b> %(chapter_progress)s%%<br /><b>Highlight:</b> %(text)s<br /><b>Notes:</b> %(annotation)s<br /><hr />') % \
                            dict(chapter=user_notes[location]['chapter'],
                                dl=user_notes[location]['displayed_location'],
                                typ=user_notes[location]['type'],
                                chapter_title=user_notes[location]['chapter_title'],
                                chapter_progress=user_notes[location]['chapter_progress'],
                                text=user_notes[location]['text'],
                                annotation=user_notes[location]['annotation']))
                else:
                    annotations.append(
                        _('<b>Chapter %(chapter)d:</b> %(chapter_title)s<br /><b>%(typ)s</b><br /><b>Chapter Progress:</b> %(chapter_progress)s%%<br /><b>Highlight:</b> %(text)s<br /><b>Notes:</b> %(annotation)s<br /><hr />') % \
                            dict(chapter=user_notes[location]['chapter'],
                                dl=user_notes[location]['displayed_location'],
                                typ=user_notes[location]['type'],
                                chapter_title=user_notes[location]['chapter_title'],
                                chapter_progress=user_notes[location]['chapter_progress'],
                                text=user_notes[location]['text'], \
                                annotation=user_notes[location]['annotation']))

            for annotation in annotations:
                divTag.insert(dtc, annotation)
                dtc += 1

        ka_soup.insert(0,divTag)
        return ka_soup

    def add_annotation_to_library(self, db, db_id, annotation):
        from calibre.ebooks.BeautifulSoup import Tag
        bm = annotation
        ignore_tags = set(['Catalog', 'Clippings'])

        if bm.type == 'kobo_bookmark':
            mi = db.get_metadata(db_id, index_is_id=True)
            user_notes_soup = self.generate_annotation_html(bm.value)
            if mi.comments:
                a_offset = mi.comments.find('<div class="user_annotations">')
                ad_offset = mi.comments.find('<hr class="annotations_divider" />')

                if a_offset >= 0:
                    mi.comments = mi.comments[:a_offset]
                if ad_offset >= 0:
                    mi.comments = mi.comments[:ad_offset]
                if set(mi.tags).intersection(ignore_tags):
                    return
                if mi.comments:
                    hrTag = Tag(user_notes_soup,'hr')
                    hrTag['class'] = 'annotations_divider'
                    user_notes_soup.insert(0, hrTag)

                mi.comments += unicode(user_notes_soup.prettify())
            else:
                mi.comments = unicode(user_notes_soup.prettify())
            # Update library comments
            db.set_comment(db_id, mi.comments)

            # Add bookmark file to db_id
            db.add_format_with_hooks(db_id, bm.value.bookmark_extension,
                                            bm.value.path, index_is_id=True)
