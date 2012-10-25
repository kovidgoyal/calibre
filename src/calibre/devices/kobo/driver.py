#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010-2012, Timothy Legge <timlegge@gmail.com>, Kovid Goyal <kovid@kovidgoyal.net> and David Forrester <davidfor@internode.on.net>'
__docformat__ = 'restructuredtext en'

'''
Driver for Kobo ereaders. Supports all e-ink devices.

Originally developed by Timothy Legge <timlegge@gmail.com>.
Extended to support Touch firmware 2.0.0 and later and newer devices by David Forrester <davidfor@internode.on.net>
'''

import os, time
from contextlib import closing
from calibre.devices.usbms.books import BookList
from calibre.devices.usbms.books import CollectionsBookList
from calibre.devices.kobo.books import KTCollectionsBookList
from calibre.devices.kobo.books import Book
from calibre.devices.kobo.books import ImageWrapper
from calibre.devices.mime import mime_type_ext
from calibre.devices.usbms.driver import USBMS, debug_print
from calibre import prints
from calibre.ptempfile import PersistentTemporaryFile
from calibre.constants import DEBUG
from calibre.utils.config import prefs


class KOBO(USBMS):

    name = 'Kobo Reader Device Interface'
    gui_name = 'Kobo Reader'
    description = _('Communicate with the Kobo Reader')
    author = 'Timothy Legge and David Forrester'
    version = (2, 0, 2)

    dbversion = 0
    fwversion = 0
    supported_dbversion = 65
    has_kepubs = False

    supported_platforms = ['windows', 'osx', 'linux']

    booklist_class = CollectionsBookList

    # Ordered list of supported formats
    FORMATS     = ['epub', 'pdf', 'txt', 'cbz', 'cbr']
    CAN_SET_METADATA = ['collections']

    VENDOR_ID   = [0x2237]
    PRODUCT_ID  = [0x4161, 0x4165]
    BCD         = [0x0110, 0x0323, 0x0326]

    VENDOR_NAME = ['KOBO_INC', 'KOBO']
    WINDOWS_MAIN_MEM = WINDOWS_CARD_A_MEM = ['.KOBOEREADER', 'EREADER']

    EBOOK_DIR_MAIN = ''
    SUPPORTS_SUB_DIRS = True
    SUPPORTS_ANNOTATIONS = True

    # "kepubs" do not have an extension. The name looks like a GUID. Using an empty string seems to work. 
    VIRTUAL_BOOK_EXTENSIONS = frozenset(['kobo', ''])

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
        if self.modify_database_check("remove_books_from_metatata") == False:
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
            book = self.book_class(prefix, lpath, other=info)
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
                self.report_progress(1.0, _('Removing books from device...'))
                from calibre.devices.errors import UserFeedback
                raise UserFeedback(_("Kobo database version unsupported - See details"),
                    _('Your Kobo is running an updated firmware/database version.'
                    ' As calibre does not know about this updated firmware,'
                    ' database editing is disabled, to prevent corruption.'
                    ' You can still send books to your Kobo with calibre, '
                    ' but deleting books and managing collections is disabled.'
                    ' If you are willing to experiment and know how to reset'
                    ' your Kobo to Factory defaults, you can override this'
                    ' check by right clicking the device icon in calibre and'
                    ' selecting "Configure this device" and then the '
                    ' "Attempt to support newer firmware" option.'
                    ' Doing so may require you to perform a factory reset of'
                    ' your Kobo.'
                     ),
                     UserFeedback.WARN)

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
        book =  cls.book_class(prefix, lpath, title, authors, mime, date, ContentType, ImageID, size=size, other=mi)
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


    def get_collections_attributes(self):
        collections = []
        opts = self.settings()
        if opts.extra_customization and len(opts.extra_customization[self.OPT_COLLECTIONS]) > 0:
            collections = [x.lower().strip() for x in opts.extra_customization[self.OPT_COLLECTIONS].split(',')]
        return collections

    def sync_booklists(self, booklists, end_session=True):
        debug_print('KOBO: started sync_booklists')
        paths = self.get_device_paths()

        blists = {}
        for i in paths:
            try:
                if booklists[i] is not None:
                    #debug_print('Booklist: ', i)
                    blists[i] = booklists[i]
            except IndexError:
                pass
        collections = self.get_collections_attributes()

        #debug_print('KOBO: collection fields:', collections)
        for i, blist in blists.items():
            if i == 0:
                oncard = 'main'
            else:
                oncard = 'carda'
            self.update_device_database_collections(blist, collections, oncard)

        USBMS.sync_booklists(self, booklists, end_session=end_session)
        debug_print('KOBO: finished sync_booklists')

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
        from calibre.devices.kobo.bookmark import Bookmark
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
            debug_print("get_annotations - ContentID: ",  ContentID, "ContentType: ", ContentType)

            bookmark_ext = extension

            db_path = self.normalize_path(self._main_prefix + '.kobo/KoboReader.sqlite')
            myBookmark = Bookmark(db_path, ContentID, path_map[id], id, book_ext[id], bookmark_ext)
            bookmarked_books[id] = self.UserAnnotation(type='kobo_bookmark', value=myBookmark)

        # This returns as job.result in gui2.ui.annotations_fetched(self,job)
        return bookmarked_books

    def generate_annotation_html(self, bookmark):
        import calendar
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
                try:
                    last_read = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(calendar.timegm(time.strptime(bookmark.last_read, "%Y-%m-%dT%H:%M:%S.%f"))))
                except:
                    last_read = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(calendar.timegm(time.strptime(bookmark.last_read, "%Y-%m-%dT%H:%M:%SZ"))))
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
            debug_print("KOBO:add_annotation_to_library - Title: ",  mi.title)
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


class KOBOTOUCH(KOBO):
    name = 'KoboTouch'
    gui_name = 'Kobo Touch'
    author = 'David Forrester'
    description = 'Communicate with the Kobo Touch, Glo and Mini firmware. Based on the existing Kobo driver by %s.' % (KOBO.author)

    supported_dbversion = 65
    min_supported_dbversion = 53

    booklist_class = KTCollectionsBookList
    book_class = Book

    MAX_PATH_LEN = 185  # 250 - (len(" - N3_LIBRARY_SHELF.parsed") + len("F:\.kobo\images\"))

    EXTRA_CUSTOMIZATION_MESSAGE = [
            _('The Kobo Touch from firmware V2.0.0 supports bookshelves.')+\
                    'These are created on the Kobo Touch. ' +\
                    _('Specify a tags type column for automatic management'),
            _('Create Bookshelves') +
            ':::'+_('Create new bookshelves on the Kobo Touch if they do not exist. This is only for firmware V2.0.0 or later.'),
            _('Delete Empty Bookshelves') +
            ':::'+_('Delete any empty bookshelves from the Kobo Touch when syncing is finished. This is only for firmware V2.0.0 or later.'),
            _('Upload covers for books') +
            ':::'+_('Normally, the KOBO readers get the cover image from the'
                ' ebook file itself. With this option, calibre will send a '
                'separate cover image to the reader, useful if you '
                'have modified the cover.'),
            _('Upload Black and White Covers'),
            _('Always upload covers') +
            ':::'+_('If the Upload covers option is selected, the driver will only replace covers already on the device.'
                    ' Select this option if you want covers uploaded the first time you send the book to the device.'),
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
                'to factory defaults and testing software. '
                'This driver supports firmware V2.0.x and DBVersion up to ' + unicode(supported_dbversion)),
            _('Title to test when debugging') +
            ':::'+_('Part of title of a book that can be used when doing some tests for debugging. '
                    'The test is to see if the string is contained in the title of a book. '
                    'The better the match, the less extraneous output.'),
            ]

    EXTRA_CUSTOMIZATION_DEFAULT = [
            u'',
            False,
            False,
            False,
            False,
            False,
            False,
            False,
            False,
            False,
            u''
            ]

    OPT_COLLECTIONS                 = 0
    OPT_CREATE_BOOKSHELVES          = 1
    OPT_DELETE_BOOKSHELVES          = 2
    OPT_UPLOAD_COVERS               = 3
    OPT_UPLOAD_GRAYSCALE_COVERS     = 4
    OPT_ALWAYS_UPLOAD_COVERS        = 5
    OPT_SHOW_EXPIRED_BOOK_RECORDS   = 6
    OPT_SHOW_PREVIEWS               = 7
    OPT_SHOW_RECOMMENDATIONS        = 8
    OPT_SUPPORT_NEWER_FIRMWARE      = 9
    OPT_DEBUGGING_TITLE             = 10

    opts = None

    TIMESTAMP_STRING = "%Y-%m-%dT%H:%M:%SZ"

    PRODUCT_ID  = [0x4163, 0x4173, 0x4183]
    BCD         = [0x0110, 0x0326]

    # Image file name endings. Made up of: image size, min_dbversion, max_dbversion,
    COVER_FILE_ENDINGS = {
                          ' - N3_LIBRARY_FULL.parsed':[(355,473),0, 99,],   # Used for Details screen
                          ' - N3_LIBRARY_GRID.parsed':[(149,198),0, 99,],   # Used for library lists
                          ' - N3_LIBRARY_LIST.parsed':[(60,90),0, 53,],
#                          ' - N3_LIBRARY_SHELF.parsed': [(40,60),0, 52,],
                          ' - N3_FULL.parsed':[(600,800),0, 99,],           # Used for screensaver, home screen 
                          }
    #Following are the sizes used with pre2.1.4 firmware
#    COVER_FILE_ENDINGS = {
#                          ' - N3_LIBRARY_FULL.parsed':[(355,530),0, 99,],   # Used for Details screen
##                          ' - N3_LIBRARY_FULL.parsed':[(600,800),0, 99,],
#                          ' - N3_LIBRARY_GRID.parsed':[(149,233),0, 99,],   # Used for library lists
#                          ' - N3_LIBRARY_LIST.parsed':[(60,90),0, 53,],
#                          ' - N3_LIBRARY_SHELF.parsed': [(40,60),0, 52,],
#                          ' - N3_FULL.parsed':[(600,800),0, 99,],           # Used for screensaver if "Full screen" is checked. 
#                          }

    def initialize(self):
        super(KOBOTOUCH, self).initialize()
        self.bookshelvelist = []

    def books(self, oncard=None, end_session=True):
        debug_print("KoboTouch:books - oncard='%s'"%oncard)
        from calibre.ebooks.metadata.meta import path_to_ext

        dummy_bl = self.booklist_class(None, None, None)

        if oncard == 'carda' and not self._card_a_prefix:
            self.report_progress(1.0, _('Getting list of books on device...'))
            debug_print("KoboTouch:books - Asked to process 'carda', but do not have one!")
            return dummy_bl
        elif oncard == 'cardb' and not self._card_b_prefix:
            self.report_progress(1.0, _('Getting list of books on device...'))
            debug_print("KoboTouch:books - Asked to process 'cardb', but do not have one!")
            return dummy_bl
        elif oncard and oncard != 'carda' and oncard != 'cardb':
            self.report_progress(1.0, _('Getting list of books on device...'))
            debug_print("KoboTouch:books - unknown card")
            return dummy_bl

        prefix = self._card_a_prefix if oncard == 'carda' else \
                 self._card_b_prefix if oncard == 'cardb' \
                 else self._main_prefix
        debug_print("KoboTouch:books - prefix='%s'"%oncard)

        # Determine the firmware version
        try:
            with open(self.normalize_path(self._main_prefix + '.kobo/version'),
                    'rb') as f:
                self.fwversion = f.readline().split(',')[2]
        except:
            self.fwversion = 'unknown'

        if self.fwversion != '1.0' and self.fwversion != '1.4':
            self.has_kepubs = True
        debug_print('Version of driver:', self.version, 'Has kepubs:', self.has_kepubs)
        debug_print('Version of firmware:', self.fwversion, 'Has kepubs:', self.has_kepubs)

        self.booklist_class.rebuild_collections = self.rebuild_collections

        # get the metadata cache
        bl = self.booklist_class(oncard, prefix, self.settings)

        opts = self.settings()
        debug_print(opts.extra_customization)
        if opts.extra_customization:
            debugging_title = opts.extra_customization[self.OPT_DEBUGGING_TITLE]
            debug_print("KoboTouch:books - set_debugging_title to", debugging_title )
            bl.set_debugging_title(debugging_title)
        debug_print("KoboTouch:books - length bl=%d"%len(bl))
        need_sync = self.parse_metadata_cache(bl, prefix, self.METADATA_CACHE)
        debug_print("KoboTouch:books - length bl after sync=%d"%len(bl))

        # make a dict cache of paths so the lookup in the loop below is faster.
        bl_cache = {}
        for idx,b in enumerate(bl):
            bl_cache[b.lpath] = idx

        def update_booklist(prefix, path, title, authors, mime, date, ContentID, ContentType, ImageID, readstatus, MimeType, expired, favouritesindex, accessibility, isdownloaded, bookshelves):
            show_debug = self.is_debugging_title(title)
#            show_debug = authors == 'L. Frank Baum'
            if show_debug:
                debug_print("KoboTouch:update_booklist - title='%s'"%title, "ContentType=%s"%ContentType, "isdownloaded=", isdownloaded)
                debug_print("         prefix=%s, mime=%s, date=%s, readstatus=%d, MimeType=%s, expired=%d, favouritesindex=%d, accessibility=%d, isdownloaded=%s"%
                (prefix, mime, date, readstatus, MimeType, expired, favouritesindex, accessibility, isdownloaded,))
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

                # The follwing is in flux:
                # - FW2.0.0, DBVersion 53,55 accessibility == 1
                # - FW2.1.2 beta, DBVersion == 56, accessibility == -1:
                # So, the following should be OK
                if isdownloaded == 'false':
                    if self.dbversion < 56 and accessibility <= 1 or self.dbversion >= 56 and accessibility == -1:
                        playlist_map[lpath].append('Deleted')
                        if show_debug:
                            debug_print("KoboTouch:update_booklist - have a deleted book")
                # Label Previews
                if accessibility == 6:
                    playlist_map[lpath].append('Preview')
                elif accessibility == 4:
                    playlist_map[lpath].append('Recommendation')

                if len(bookshelves) > 0:
                    playlist_map[lpath].extend(bookshelves)

                if show_debug:
                    debug_print('KoboTouch:update_booklist - playlist_map=', playlist_map)

                path = self.normalize_path(path)
                # print "Normalized FileName: " + path

                idx = bl_cache.get(lpath, None)
                if idx is not None:# and not (accessibility == 1 and isdownloaded == 'false'):
                    if show_debug:
                        debug_print("KoboTouch:update_booklist - idx=%d"%idx)
                        debug_print('KoboTouch:update_booklist - bl[idx].device_collections=', bl[idx].device_collections)
                        debug_print('KoboTouch:update_booklist - playlist_map=', playlist_map)
                        debug_print('KoboTouch:update_booklist - bookshelves=', bookshelves)
                        debug_print('KoboTouch:update_booklist - series="%s"' % bl[idx].series)
                        debug_print('KoboTouch:update_booklist - the book=', bl[idx])
                        debug_print('KoboTouch:update_booklist - the authors=', bl[idx].authors)
                        debug_print('KoboTouch:update_booklist - application_id=', bl[idx].application_id)
                    bl_cache[lpath] = None
                    if bl[idx].title_sort is not None:
                        bl[idx].title = bl[idx].title_sort
                    if ImageID is not None:
                        imagename = self.imagefilename_from_imageID(ImageID)
                        if imagename is not None:
                            bl[idx].thumbnail = ImageWrapper(imagename)
                    if (ContentType == '6' and MimeType != 'application/x-kobo-epub+zip'):
                        if os.path.exists(self.normalize_path(os.path.join(prefix, lpath))):
                            if self.update_metadata_item(bl[idx]):
                                print 'update_metadata_item returned true'
                                changed = True
                        else:
                            debug_print("    Strange:  The file: ", prefix, lpath, " does not exist!")
                            debug_print("KoboTouch:update_booklist - book size=", bl[idx].size)

                    if show_debug:
                        debug_print("KoboTouch:update_booklist - ContentID='%s'"%ContentID)
                    bl[idx].contentID = ContentID

                    if lpath in playlist_map:
                        bl[idx].device_collections  = playlist_map.get(lpath,[])
                        changed = True
                    bl[idx].current_shelves = bookshelves

                    if show_debug:
                        debug_print('KoboTouch:update_booklist - updated bl[idx].device_collections=', bl[idx].device_collections)
                        debug_print('KoboTouch:update_booklist - playlist_map=', playlist_map, 'changed=', changed)
#                        debug_print('KoboTouch:update_booklist - book=', bl[idx])
                        debug_print("KoboTouch:update_booklist - book class=%s"%bl[idx].__class__)
                else:
                    if show_debug:
                        debug_print('KoboTouch:update_booklist - idx is none')
                    try:
                        if os.path.exists(self.normalize_path(os.path.join(prefix, lpath))):
                            book = self.book_from_path(prefix, lpath, title, authors, mime, date, ContentType, ImageID)
                        else:
                            if isdownloaded == 'true': # A recommendation or preview is OK to not have a file
                                debug_print("    Strange:  The file: ", prefix, lpath, " does not exist!")
                                title = "FILE MISSING: " + title
                            book =  self.book_class(prefix, lpath, title, authors, mime, date, ContentType, ImageID, size=0)
                            if show_debug:
                                debug_print('KoboTouch:update_booklist - book file does not exist. ContentID="%s"'%ContentID)

                    except Exception as e:
                        debug_print("KoboTouch:update_booklist - exception creating book: '%s'"%str(e))
                        debug_print("        prefix: ", prefix, "lpath: ", lpath, "title: ", title, "authors: ", authors, \
                                    "mime: ", mime, "date: ", date, "ContentType: ", ContentType, "ImageID: ", ImageID)
                        raise

                    if show_debug:
                        debug_print('KoboTouch:update_booklist - class:', book.__class__)
#                        debug_print('    resolution:', book.__class__.__mro__)
                        debug_print("    contentid:'%s'"%book.contentID)
                        debug_print("    title:'%s'"%book.title)
                        debug_print("    the book:", book)
                        debug_print("    author_sort:'%s'"%book.author_sort)
                        debug_print("    bookshelves:", bookshelves)

                    # print 'Update booklist'
                    book.device_collections  = playlist_map.get(lpath,[])# if lpath in playlist_map else []
                    book.current_shelves = bookshelves
                    book.contentID = ContentID
#                    debug_print('KoboTouch:update_booklist - title=', title, 'book.device_collections', book.device_collections)

                    if bl.add_book(book, replace_metadata=False):
                        changed = True
                    if show_debug:
                        debug_print('        book.device_collections', book.device_collections)
            except: # Probably a path encoding error
                import traceback
                traceback.print_exc()
            return changed

        def get_bookshelvesforbook(connection, ContentID):
#            debug_print("KoboTouch:get_bookshelvesforbook - " + ContentID)
            bookshelves = []
            if not self.supports_bookshelves():
                return bookshelves

            cursor = connection.cursor()
            query = "select ShelfName from ShelfContent where ContentId = ? and _IsDeleted = 'false'"
            values = (ContentID, )
            cursor.execute(query, values)
            for i, row in enumerate(cursor):
                bookshelves.append(row[0])

            cursor.close()
#            debug_print("KoboTouch:get_bookshelvesforbook - count bookshelves=" + unicode(count_bookshelves))
            return bookshelves

        import sqlite3 as sqlite
        with closing(sqlite.connect(
            self.normalize_path(self._main_prefix +
                '.kobo/KoboReader.sqlite'))) as connection:
            debug_print("KoboTouch:books - reading device database")

            # return bytestrings if the content cannot the decoded as unicode
            connection.text_factory = lambda x: unicode(x, "utf-8", "ignore")

            cursor = connection.cursor()

            cursor.execute('select version from dbversion')
            result = cursor.fetchone()
            self.dbversion = result[0]
            debug_print("Database Version=%d"%self.dbversion)

            self.bookshelvelist = self.get_bookshelflist(connection)
            debug_print("KoboTouch:books - shelf list:", self.bookshelvelist)

            opts = self.settings()
            if self.dbversion >= 33:
                query= ('select Title, Attribution, DateCreated, ContentID, MimeType, ContentType, ' \
                    'ImageID, ReadStatus, ___ExpirationStatus, FavouritesIndex, Accessibility, IsDownloaded from content where ' \
                    'BookID is Null %(previews)s %(recomendations)s and not ((___ExpirationStatus=3 or ___ExpirationStatus is Null) %(expiry)s') % \
                        dict(\
                             expiry=' and ContentType = 6)' if opts.extra_customization[self.OPT_SHOW_EXPIRED_BOOK_RECORDS] else ')', \
                             previews=' and Accessibility <> 6' if opts.extra_customization[self.OPT_SHOW_PREVIEWS] == False else '', \
                             recomendations=' and IsDownloaded in (\'true\', 1)' if opts.extra_customization[self.OPT_SHOW_RECOMMENDATIONS] == False else ''\
                             )
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

            debug_print("KoboTouch:books - query=", query)
            try:
                cursor.execute (query)
            except Exception as e:
                err = str(e)
                if not ('___ExpirationStatus' in err or 'FavouritesIndex' in err or
                        'Accessibility' in err or 'IsDownloaded' in err):
                    raise
                query= ('select Title, Attribution, DateCreated, ContentID, MimeType, ContentType, '
                    'ImageID, ReadStatus, "-1" as ___ExpirationStatus, "-1" as '
                    'FavouritesIndex, "-1" as Accessibility, "1" as IsDownloaded from content where '
                    'BookID is Null')
                cursor.execute(query)

            changed = False
            for i, row in enumerate(cursor):
            #  self.report_progress((i+1) / float(numrows), _('Getting list of books on device...'))
                show_debug = self.is_debugging_title(row[0])
                if show_debug:
                    debug_print("KoboTouch:books - looping on database - row=%d" % i)
                    debug_print("KoboTouch:books - title='%s'"%row[0], "authors=", row[1])
                    debug_print("KoboTouch:books - row=", row)
                if not hasattr(row[3], 'startswith') or row[3].lower().startswith("file:///usr/local/kobo/help/") or row[3].lower().startswith("/usr/local/kobo/help/"):
                    # These are internal to the Kobo device and do not exist
                    continue
                path = self.path_from_contentid(row[3], row[5], row[4], oncard)
                mime = mime_type_ext(path_to_ext(path)) if path.find('kepub') == -1 else 'application/x-kobo-epub+zip'
                # debug_print("mime:", mime)
                if show_debug:
                    debug_print("KoboTouch:books - path='%s'"%path, "  ContentID='%s'"%row[3])

                bookshelves = get_bookshelvesforbook(connection, row[3])

                if oncard != 'carda' and oncard != 'cardb' and not row[3].startswith("file:///mnt/sd/"):
                    changed = update_booklist(self._main_prefix, path, row[0], row[1], mime, row[2], row[3], row[5], row[6], row[7], row[4], row[8], row[9], row[10], row[11], bookshelves)
                    # print "shortbook: " + path
                elif oncard == 'carda' and row[3].startswith("file:///mnt/sd/"):
                    changed = update_booklist(self._card_a_prefix, path, row[0], row[1], mime, row[2], row[3], row[5], row[6], row[7], row[4], row[8], row[9], row[10], row[11], bookshelves)

                if changed:
                    need_sync = True

            cursor.close()

            if not prefs['manage_device_metadata'] == 'on_connect':
                self.dump_bookshelves(connection)
            else:
                debug_print("KoboTouch:books - automatically managing metadata")
        # Remove books that are no longer in the filesystem. Cache contains
        # indices into the booklist if book not in filesystem, None otherwise
        # Do the operation in reverse order so indices remain valid
        for idx in sorted(bl_cache.itervalues(), reverse=True):
            if idx is not None:
                need_sync = True
                del bl[idx]

        #print "count found in cache: %d, count of files in metadata: %d, need_sync: %s" % \
        #      (len(bl_cache), len(bl), need_sync)
        # Bypassing the KOBO sync_booklists as that does things we don't need to do
        if need_sync: #self.count_found_in_bl != len(bl) or need_sync:
            debug_print("KoboTouch:books - about to sync_booklists")
            if oncard == 'cardb':
                USBMS.sync_booklists(self, (None, None, bl))
            elif oncard == 'carda':
                USBMS.sync_booklists(self, (None, bl, None))
            else:
                USBMS.sync_booklists(self, (bl, None, None))

        self.report_progress(1.0, _('Getting list of books on device...'))
        debug_print("KoboTouch:books - end - oncard='%s'"%oncard)
        return bl

    def imagefilename_from_imageID(self, ImageID):
        show_debug = self.is_debugging_title(ImageID)

        for ending, cover_options in self.COVER_FILE_ENDINGS.items():
            fpath = self._main_prefix + '.kobo/images/' + ImageID + ending
            fpath = self.normalize_path(fpath.replace('/', os.sep))
            if show_debug:
                debug_print("KoboTouch:imagefilename_from_imageID - ending=%s, path length=%d" % (ending, len(fpath)))
                debug_print("KoboTouch:imagefilename_from_imageID - fpath=%s" % (fpath))
            if os.path.exists(fpath):
                if show_debug:
                    debug_print("KoboTouch:imagefilename_from_imageID - have cover image fpath=%s" % (fpath))
                return fpath

        if show_debug:
            debug_print("KoboTouch:imagefilename_from_imageID - no cover image found - ImageID=%s" % (ImageID))
        return None

    def upload_books(self, files, names, on_card=None, end_session=True,
                     metadata=None):
        debug_print('KoboTouch:upload_books - %d books'%(len(files)))

        result = super(KOBOTOUCH, self).upload_books(files, names, on_card, end_session, metadata)
#        debug_print('KoboTouch:upload_books - result=', result)

        if self.dbversion >= 53:
            import sqlite3 as sqlite
            try:
                with closing(sqlite.connect(self.normalize_path(self._main_prefix +
                                                                '.kobo/KoboReader.sqlite'))) as connection:
                    connection.text_factory = lambda x: unicode(x, "utf-8", "ignore")
                    cursor = connection.cursor()
                    query = "DELETE FROM content WHERE ContentID = ? AND Accessibility = 1 AND IsDownloaded = 'false'"

                    for fname, cycle in result:
                        show_debug = self.is_debugging_title(fname)
                        contentID = self.contentid_from_path(fname, 6)
                        if show_debug:
                            debug_print('KoboTouch:upload_books: fname=', fname)
                            debug_print('KoboTouch:upload_books: contentID=', contentID)

                        t = (contentID,)
#                        debug_print('KoboTouch:upload_books: Delete record left if deleted on Touch')
                        cursor.execute(query, t)

                    connection.commit()

                    cursor.close()
            except Exception as e:
                debug_print('KoboTouch:upload_books - Exception:  %s'%str(e))

        return result


    def delete_via_sql(self, ContentID, ContentType):
        imageId = super(KOBOTOUCH, self).delete_via_sql(ContentID, ContentType)

        if self.dbversion >= 53:
            import sqlite3 as sqlite
            debug_print('KoboTouch:delete_via_sql: ContentID="%s"'%ContentID, 'ContentType="%s"'%ContentType)
            try:
                with closing(sqlite.connect(self.normalize_path(self._main_prefix +
                                                                '.kobo/KoboReader.sqlite'))) as connection:
                    debug_print('KoboTouch:delete_via_sql: have database connection')
                    # return bytestrings if the content cannot the decoded as unicode
                    connection.text_factory = lambda x: unicode(x, "utf-8", "ignore")

                    cursor = connection.cursor()
                    debug_print('KoboTouch:delete_via_sql: have cursor')
                    t = (ContentID,)
                    #Delete from the Bookshelf
                    debug_print('KoboTouch:delete_via_sql: Delete from the Bookshelf')
                    cursor.execute('delete from ShelfContent where ContentID = ?', t)

                    # ContentType 6 is now for all books.
                    debug_print('KoboTouch:delete_via_sql: BookID is Null')
                    cursor.execute('delete from content where BookID is Null and ContentID =?',t)

                    # Remove the content_settings entry
                    debug_print('KoboTouch:delete_via_sql: detete from content_settings')
                    cursor.execute('delete from content_settings where ContentID =?',t)

                    # Remove the ratings entry
                    debug_print('KoboTouch:delete_via_sql: detete from ratings')
                    cursor.execute('delete from ratings where ContentID =?',t)

                    connection.commit()

                    cursor.close()
                    debug_print('KoboTouch:delete_via_sql: finished SQL')
                debug_print('KoboTouch:delete_via_sql: After SQL, no exception')
            except Exception as e:
                debug_print('KoboTouch:delete_via_sql - Database Exception:  %s'%str(e))

        debug_print('KoboTouch:delete_via_sql: imageId="%s"'%imageId)
        if imageId is None:
            imageId = self.imageid_from_contentid(ContentID)

        return imageId

    def delete_images(self, ImageID):
        debug_print("KoboTouch:delete_images - ImageID=", ImageID)
        if ImageID != None:
            path_prefix = '.kobo/images/'
            path = self._main_prefix + path_prefix + ImageID

            for ending in self.COVER_FILE_ENDINGS.keys():
                fpath = path + ending
                fpath = self.normalize_path(fpath)

                if os.path.exists(fpath):
                    # print 'Image File Exists: ' + fpath
                    os.unlink(fpath)

    def contentid_from_path(self, path, ContentType):
        show_debug = self.is_debugging_title(path) and True
        if show_debug:
            debug_print("KoboTouch:contentid_from_path - path='%s'"%path, "ContentType='%s'"%ContentType)
            debug_print("KoboTouch:contentid_from_path - self._main_prefix='%s'"%self._main_prefix, "self._card_a_prefix='%s'"%self._card_a_prefix)
        if ContentType == 6:
            extension =  os.path.splitext(path)[1]
            if extension == '.kobo':
                ContentID = os.path.splitext(path)[0]
                # Remove the prefix on the file.  it could be either
                ContentID = ContentID.replace(self._main_prefix, '')
            elif extension == '':
                ContentID = path
                ContentID = ContentID.replace(self._main_prefix + self.normalize_path('.kobo/kepub/'), '')
            else:
                ContentID = path
                ContentID = ContentID.replace(self._main_prefix, "file:///mnt/onboard/")

            if show_debug:
                debug_print("KoboTouch:contentid_from_path - 1 ContentID='%s'"%ContentID)

            if self._card_a_prefix is not None:
                ContentID = ContentID.replace(self._card_a_prefix,  "file:///mnt/sd/")
        else: # ContentType = 16
            debug_print("KoboTouch:contentid_from_path ContentType other than 6 - ContentType='%d'"%ContentType, "path='%s'"%path)
            ContentID = path
            ContentID = ContentID.replace(self._main_prefix, "file:///mnt/onboard/")
            if self._card_a_prefix is not None:
                ContentID = ContentID.replace(self._card_a_prefix, "file:///mnt/sd/")
        ContentID = ContentID.replace("\\", '/')
        if show_debug:
            debug_print("KoboTouch:contentid_from_path - end - ContentID='%s'"%ContentID)
        return ContentID

    def get_content_type_from_extension(self, extension):
        debug_print("KoboTouch:get_content_type_from_extension - start")
        # With new firmware, ContentType appears to be 6 for all types of sideloaded books.
        if self.fwversion.startswith('2.'):
            debug_print("KoboTouch:get_content_type_from_extension - V2 firmware")
            ContentType = 6
        else:
            debug_print("KoboTouch:get_content_type_from_extension - calling super")
            ContentType = super(KOBOTOUCH, self).get_content_type_from_extension(extension)
        return ContentType

    def update_device_database_collections(self, booklists, collections_attributes, oncard):
        debug_print("KoboTouch:update_device_database_collections - oncard='%s'"%oncard)
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
            "Deleted":1,
            }

        # specialshelveslist = {
        #     "Shortlist":1,
        #     "Wishlist":2,
        #     }
#        debug_print('KoboTouch:update_device_database_collections - collections_attributes=', collections_attributes)

        opts = self.settings()
        if opts.extra_customization:
            create_bookshelves = opts.extra_customization[self.OPT_CREATE_BOOKSHELVES] and self.supports_bookshelves()
            delete_empty_shelves = opts.extra_customization[self.OPT_DELETE_BOOKSHELVES] and self.supports_bookshelves()
            debugging_title = opts.extra_customization[self.OPT_DEBUGGING_TITLE]
            debug_print("KoboTouch:update_device_database_collections - set_debugging_title to", debugging_title )
            booklists.set_debugging_title(debugging_title)
        else:
            delete_empty_shelves = False

        collections = booklists.get_collections(collections_attributes)
#        debug_print('KoboTouch:update_device_database_collections - Collections:', collections)

        opts = self.settings()
        if opts.extra_customization:
            create_bookshelves = opts.extra_customization[self.OPT_CREATE_BOOKSHELVES] and self.supports_bookshelves()
            delete_empty_shelves = opts.extra_customization[self.OPT_DELETE_BOOKSHELVES] and self.supports_bookshelves()
        else:
            delete_empty_shelves = False
        bookshelf_attribute = len(collections_attributes)

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
#                debug_print("KoboTouch:update_device_database_collections - length collections=" + unicode(len(collections)))

                # Need to reset the collections outside the particular loops
                # otherwise the last item will not be removed
                if self.dbversion < 53:
                    self.reset_readstatus(connection, oncard)
                if self.dbversion >= 14:
                    self.reset_favouritesindex(connection, oncard)

#                debug_print("KoboTouch:update_device_database_collections - length collections=", len(collections))
#                debug_print("KoboTouch:update_device_database_collections - self.bookshelvelist=", self.bookshelvelist)
                # Process any collections that exist
                for category, books in collections.items():
                    debug_print("KoboTouch:update_device_database_collections - category='%s'"%category)
                    if create_bookshelves and not (category in supportedcategories or category in readstatuslist or category in accessibilitylist):
                        self.check_for_bookshelf(connection, category)
#                    if category in self.bookshelvelist:
#                        debug_print("Category: ", category, " id = ", readstatuslist.get(category))
                    for book in books:
#                        debug_print('    Title:', book.title, 'category: ', category)
                        show_debug = self.is_debugging_title(book.title)
                        if show_debug:
                            debug_print('    Title="%s"'%book.title, 'category="%s"'%category)
#                            debug_print(book)
                            debug_print('    class=%s'%book.__class__)
#                            debug_print('    resolution:', book.__class__.__mro__)
#                            debug_print('    subclasses:', book.__class__.__subclasses__())
                            debug_print('    book.contentID="%s"'%book.contentID)

                        category_added = False

                        if book.contentID is None:
                            debug_print('    Do not know ContentID - Title="%s"'%book.title)
                            extension =  os.path.splitext(book.path)[1]
                            ContentType = self.get_content_type_from_extension(extension) if extension != '' else self.get_content_type_from_path(book.path)
                            book.contentID = self.contentid_from_path(book.path, ContentType)

                        if category in self.bookshelvelist and self.supports_bookshelves():
                            if show_debug:
                                debug_print('        length book.device_collections=%d'%len(book.device_collections))
                            if category not in book.device_collections:
                                if show_debug:
                                    debug_print('        Setting bookshelf on device')
                                self.set_bookshelf(connection, book.contentID, category)
                                category_added = True
                        elif category in readstatuslist.keys():
                            # Manage ReadStatus
                            self.set_readstatus(connection, book.contentID, readstatuslist.get(category))
                            category_added = True

                        elif category == 'Shortlist' and self.dbversion >= 14:
                            if show_debug:
                                debug_print('        Have an older version shortlist - %s'%book.title)
                            # Manage FavouritesIndex/Shortlist
                            if not self.supports_bookshelves():
                                if show_debug:
                                    debug_print('            and about to set it - %s'%book.title)
                                self.set_favouritesindex(connection, book.contentID)
                                category_added = True
                        elif category in accessibilitylist.keys():
                            # Do not manage the Accessibility List
                            pass

                        if category_added and category not in book.device_collections:
                            if show_debug:
                                    debug_print('            adding category to book.device_collections', book.device_collections)
                            book.device_collections.append(category)
                        else:
                            if show_debug:
                                    debug_print('            category not added to book.device_collections', book.device_collections)
                    debug_print("KoboTouch:update_device_database_collections - end for category='%s'"%category)

            else: # No collections
                # Since no collections exist the ReadStatus needs to be reset to 0 (Unread)
                debug_print("No Collections - reseting ReadStatus")
                if oncard == 'carda':
                    debug_print("Booklists=", booklists)
                if self.dbversion < 53:
                    self.reset_readstatus(connection, oncard)
                self.remove_from_bookshelves(connection, oncard)
                if self.dbversion >= 14:
                    debug_print("No Collections - reseting FavouritesIndex")
                    self.reset_favouritesindex(connection, oncard)

            if self.supports_bookshelves():
                debug_print("KoboTouch:update_device_database_collections - managing bookshelves.")
                if bookshelf_attribute:
                    debug_print("KoboTouch:update_device_database_collections - bookshelf_attribute=", bookshelf_attribute)
                    for book in booklists:
                        if book.application_id is not None:
#                            debug_print("KoboTouch:update_device_database_collections - about to remove a book from shelves book.title=%s" % book.title)
                            self.remove_book_from_device_bookshelves(connection, book)
                if not prefs['manage_device_metadata'] == 'manual' and delete_empty_shelves:
                    debug_print("KoboTouch:update_device_database_collections - about to clear empty bookshelves")
                    self.delete_empty_bookshelves(connection)

                self.dump_bookshelves(connection)

        debug_print('KoboTouch:update_device_database_collections - Finished ')

    def rebuild_collections(self, booklist, oncard):
        debug_print("KoboTouch:rebuild_collections")
        collections_attributes = self.get_collections_attributes()

        debug_print('KoboTouch:rebuild_collections: collection fields:', collections_attributes)
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
#        debug_print("KoboTouch:upload_cover - path='%s' filename='%s'"%(path, filename))

        opts = self.settings()
        if not opts.extra_customization[self.OPT_UPLOAD_COVERS]:
            # Building thumbnails disabled
#            debug_print('KoboTouch: not uploading cover')
            return

        if not opts.extra_customization[self.OPT_UPLOAD_GRAYSCALE_COVERS]:
            uploadgrayscale = False
        else:
            uploadgrayscale = True
        if not opts.extra_customization[self.OPT_ALWAYS_UPLOAD_COVERS]:
            always_upload_covers = False
        else:
            always_upload_covers = True

#        debug_print('KoboTouch: uploading cover')
        try:
            self._upload_cover(path, filename, metadata, filepath, uploadgrayscale, always_upload_covers)
        except Exception as e:
            debug_print('KoboTouch: FAILED to upload cover=%s Exception=%s'%(filepath, str(e)))


    def imageid_from_contentid(self, ContentID):
        ImageID = ContentID.replace('/', '_')
        ImageID = ImageID.replace(' ', '_')
        ImageID = ImageID.replace(':', '_')
        ImageID = ImageID.replace('.', '_')
        return ImageID

    def _upload_cover(self, path, filename, metadata, filepath, uploadgrayscale, always_upload_covers=False):
        from calibre.utils.magick.draw import save_cover_data_to
        debug_print("KoboTouch:_upload_cover - filename='%s' uploadgrayscale='%s' always_upload_covers='%s'"%(filename, uploadgrayscale, always_upload_covers))

        if metadata.cover:
            show_debug = self.is_debugging_title(filename)
            if show_debug:
                debug_print("KoboTouch:_upload_cover - path='%s'"%path, "filename='%s'"%filename)
                debug_print("        filepath='%s'"%filepath)
            cover = self.normalize_path(metadata.cover.replace('/', os.sep))

            if os.path.exists(cover):
                # Get ContentID for Selected Book
                extension =  os.path.splitext(filepath)[1]
                ContentType = self.get_content_type_from_extension(extension) if extension != '' else self.get_content_type_from_path(filepath)
                ContentID = self.contentid_from_path(filepath, ContentType)

                try:
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
                            ImageID = self.imageid_from_contentid(ContentID)
                            debug_print("KoboTouch:_upload_cover - No rows exist in the database - generated ImageID='%s'" % ImageID)
                        else:
                            ImageID = result[0]
    #                        debug_print("ImageId: ", result[0])

                        cursor.close()

                    if ImageID != None:
                        path_prefix = '.kobo/images/'
                        path = self._main_prefix + path_prefix + ImageID
                        if show_debug:
                            debug_print("KoboTouch:_upload_cover - About to loop over cover endings")

                        for ending, cover_options in self.COVER_FILE_ENDINGS.items():
                            resize, min_dbversion, max_dbversion = cover_options
                            if show_debug:
                                debug_print("KoboTouch:_upload_cover - resize=%s min_dbversion=%d max_dbversion=%d" % (resize, min_dbversion, max_dbversion))
                            if self.dbversion >= min_dbversion and self.dbversion <= max_dbversion:
                                if show_debug:
                                    debug_print("KoboTouch:_upload_cover - creating cover for ending='%s'"%ending)#, "resize'%s'"%resize)
                                fpath = path + ending
                                fpath = self.normalize_path(fpath.replace('/', os.sep))

                                if os.path.exists(fpath) or always_upload_covers:
                                    debug_print("KoboTouch:_upload_cover - path exists or always_upload_covers%s"% always_upload_covers)
                                    with open(cover, 'rb') as f:
                                        data = f.read()

                                    # Return the data resized and in Grayscale if
                                    # required
                                    data = save_cover_data_to(data, 'dummy.jpg',
                                            grayscale=uploadgrayscale,
                                            resize_to=resize, return_data=True)

                                    with open(fpath, 'wb') as f:
                                        f.write(data)
                except Exception as e:
                    err = str(e)
                    debug_print("KoboTouch:_upload_cover - Exception string: %s"%err)
                    raise
            else:
                debug_print("KoboTouch:_upload_cover - ImageID could not be retrieved from the database")

    def remove_book_from_device_bookshelves(self, connection, book):
        show_debug = self.is_debugging_title(book.title)# or True

        remove_shelf_list = set(book.current_shelves) - set(book.device_collections)# - set(["Im_Reading", "Read", "Closed"])

        if show_debug:
            debug_print('KoboTouch:remove_book_from_device_bookshelves - book.application_id="%s"'%book.application_id)
            debug_print('KoboTouch:remove_book_from_device_bookshelves - book.contentID="%s"'%book.contentID)
            debug_print('KoboTouch:remove_book_from_device_bookshelves - book.device_collections=', book.device_collections)
            debug_print('KoboTouch:remove_book_from_device_bookshelves - book.current_shelves=', book.current_shelves)
            debug_print('KoboTouch:remove_book_from_device_bookshelves - remove_shelf_list=', remove_shelf_list)
        
        if len(remove_shelf_list) == 0:
            return

        query = 'DELETE FROM ShelfContent WHERE ContentId = ?'

        values = [book.contentID,]

        if book.device_collections:
            placeholder = '?'
            placeholders = ','.join(placeholder for unused in book.device_collections)
            query += ' and ShelfName not in (%s)' % placeholders
            values.extend(book.device_collections)

        if show_debug:
            debug_print('KoboTouch:remove_book_from_device_bookshelves query="%s"'%query)
            debug_print('KoboTouch:remove_book_from_device_bookshelves values="%s"'%values)

        cursor = connection.cursor()
        cursor.execute(query, values)
        connection.commit()
        cursor.close()

    def delete_empty_bookshelves(self, connection):
        debug_print("KoboTouch:delete_empty_bookshelves - start")

        delete_query = ("DELETE FROM Shelf "
                        "WHERE Shelf._IsSynced = 'false' "
                        "AND Shelf.InternalName not in ('Shortlist', 'Wishlist') "
                        "AND NOT EXISTS "
                        "(SELECT 1 FROM ShelfContent c "
                        "WHERE Shelf.Name = C.ShelfName "
                        "AND c._IsDeleted <> 'true')")

        update_query = ("UPDATE Shelf "
                        "SET _IsDeleted = 'true' "
                        "WHERE Shelf._IsSynced = 'true' "
                        "AND Shelf.InternalName not in ('Shortlist', 'Wishlist') "
                        "AND NOT EXISTS "
                        "(SELECT 1 FROM ShelfContent C "
                        "WHERE Shelf.Name = C.ShelfName "
                        "AND c._IsDeleted <> 'true')")

        cursor = connection.cursor()
        cursor.execute(delete_query)
        cursor.execute(update_query)
        connection.commit()
        cursor.close()

        debug_print("KoboTouch:delete_empty_bookshelves - end")

    def get_bookshelflist(self, connection):
        # Retrieve the list of booksehelves
#        debug_print('KoboTouch:get_bookshelflist')
        bookshelves = []

        if not self.supports_bookshelves():
            return bookshelves

        query = 'SELECT Name FROM Shelf WHERE _IsDeleted = "false"'

        cursor = connection.cursor()
        cursor.execute(query)
#        count_bookshelves = 0
        for i, row in enumerate(cursor):
            bookshelves.append(row[0])
#            count_bookshelves = i + 1

        cursor.close()
#        debug_print("KoboTouch:get_bookshelflist - count bookshelves=" + unicode(count_bookshelves))

        return bookshelves

    def set_bookshelf(self, connection, ContentID, bookshelf):
        show_debug = self.is_debugging_title(ContentID)
        if show_debug:
            debug_print('KoboTouch:set_bookshelf ContentID=' + ContentID)
        test_query = 'SELECT 1 FROM ShelfContent WHERE ShelfName = ? and ContentId = ?'
        test_values = (bookshelf, ContentID, )
        addquery = 'INSERT INTO ShelfContent ("ShelfName","ContentId","DateModified","_IsDeleted","_IsSynced") VALUES (?, ?, ?, "false", "false")'
        add_values = (bookshelf, ContentID, time.strftime(self.TIMESTAMP_STRING, time.gmtime()), )
        updatequery = 'UPDATE ShelfContent SET _IsDeleted = "false" WHERE ShelfName = ? and ContentId = ?'
        update_values = (bookshelf, ContentID, )

        cursor = connection.cursor()
        cursor.execute(test_query, test_values)
        result = cursor.fetchone()
        if result is None:
            if show_debug:
                debug_print('        Did not find a record - adding')
            cursor.execute(addquery, add_values)
            connection.commit()
        else:
            if show_debug:
                debug_print('        Found a record - updating')
            cursor.execute(updatequery, update_values)
            connection.commit()

        cursor.close()

#        debug_print("KoboTouch:set_bookshelf - end")

    def check_for_bookshelf(self, connection, bookshelf_name):
        show_debug = self.is_debugging_title(bookshelf_name)
        if show_debug:
            debug_print('KoboTouch:check_for_bookshelf bookshelf_name="%s"'%bookshelf_name)
        test_query = 'SELECT InternalName, Name, _IsDeleted FROM Shelf WHERE Name = ?'
        test_values = (bookshelf_name, )
        addquery = 'INSERT INTO "main"."Shelf"'\
                    ' ("CreationDate","InternalName","LastModified","Name","_IsDeleted","_IsVisible","_IsSynced")'\
                    ' VALUES (?, ?, ?, ?, ?, ?, ?)'
        add_values = (
                      time.strftime(self.TIMESTAMP_STRING, time.gmtime()),
                      bookshelf_name,
                      time.strftime(self.TIMESTAMP_STRING, time.gmtime()),
                      bookshelf_name,
                      "false",
                      "true",
                      "false",
                      )
        updatequery = 'UPDATE Shelf SET _IsDeleted = "false" WHERE Name = ?'

        cursor = connection.cursor()
        cursor.execute(test_query, test_values)
        result = cursor.fetchone()
        if result is None:
            if show_debug:
                debug_print('        Did not find a record - adding shelf "%s"' % bookshelf_name)
            cursor.execute(addquery, add_values)
        elif result[2] == 'true':
            debug_print('KoboTouch:check_for_bookshelf - Shelf "%s" is deleted - undeleting. result[2]="%s"' % (bookshelf_name, unicode(result[2])))
            cursor.execute(updatequery, test_values)

        connection.commit()
        cursor.close()

        # Update the bookshelf list.
        self.bookshelvelist = self.get_bookshelflist(connection)

#        debug_print("KoboTouch:set_bookshelf - end")

    def remove_from_bookshelves(self, connection, oncard, ContentID=None, bookshelves=None):
        debug_print('KoboTouch:remove_from_bookshelf ContentID=', ContentID)
        if not self.supports_bookshelves():
            return
        query = 'DELETE FROM ShelfContent'

        values = []
        if ContentID is not None:
            query += ' WHERE ContentId = ?'
            values.append(ContentID)
        else:
            if oncard == 'carda':
                query += ' WHERE ContentID like \'file:///mnt/sd/%\''
            elif oncard != 'carda' and oncard != 'cardb':
                query += ' WHERE ContentID not like \'file:///mnt/sd/%\''

        if bookshelves:
            placeholder = '?'
            placeholders = ','.join(placeholder for unused in bookshelves)
            query += ' and ShelfName in (%s)' % placeholders
            values.append(bookshelves)
        debug_print('KoboTouch:remove_from_bookshelf query=', query)
        debug_print('KoboTouch:remove_from_bookshelf values=', values)
        cursor = connection.cursor()
        cursor.execute(query, values)
        connection.commit()
        cursor.close()

        debug_print("KoboTouch:remove_from_bookshelf - end")

    def supports_bookshelves(self):
        return self.dbversion >= self.min_supported_dbversion

#    def is_debugging_title(self, title):
##        debug_print("KoboTouch:is_debugging - title=", title)
#        is_debugging = False
#        opts = self.settings()
#        if opts.extra_customization:
#            debugging_title = opts.extra_customization[self.OPT_DEBUGGING_TITLE]
#            is_debugging = len(debugging_title) > 0 and title.find(debugging_title) >= 0 or len(title) == 0
#
#        return is_debugging

    @classmethod
    def is_debugging_title(cls, title):
        if not DEBUG:
            return False
#        debug_print("KoboTouch:is_debugging - title=", title)
        is_debugging = False
        opts = cls.settings()

        if opts.extra_customization:
            debugging_title = opts.extra_customization[cls.OPT_DEBUGGING_TITLE]
            is_debugging = len(debugging_title) > 0 and title.lower().find(debugging_title.lower()) >= 0 or len(title) == 0

        return is_debugging

    def dump_bookshelves(self, connection):
        if not (DEBUG and self.supports_bookshelves() and False):
            return

        debug_print('KoboTouch:dump_bookshelves - start')
        shelf_query = 'SELECT * FROM Shelf'
        shelfcontent_query = 'SELECT * FROM ShelfContent'
        placeholder = '%s'

        cursor = connection.cursor()

        prints('\nBookshelves on device:')
        cursor.execute(shelf_query)
        i = 0
        for row in cursor:
            placeholders = ', '.join(placeholder for unused in row)
            prints(placeholders%row)
            i += 1
        if i == 0:
            prints("No shelves found!!")
        else:
            prints("Number of shelves=%d"%i)

        prints('\nBooks on shelves on device:')
        cursor.execute(shelfcontent_query)
        i = 0
        for row in cursor:
            placeholders = ', '.join(placeholder for unused in row)
            prints(placeholders%row)
            i += 1
        if i == 0:
            prints("No books are on any shelves!!")
        else:
            prints("Number of shelved books=%d"%i)

        cursor.close()
        debug_print('KoboTouch:dump_bookshelves - end')
