#!/usr/bin/env python2
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import division

__license__   = 'GPL v3'
__copyright__ = '2010-2012, Timothy Legge <timlegge@gmail.com>, Kovid Goyal <kovid@kovidgoyal.net> and David Forrester <davidfor@internode.on.net>'
__docformat__ = 'restructuredtext en'

'''
Driver for Kobo ereaders. Supports all e-ink devices.

Originally developed by Timothy Legge <timlegge@gmail.com>.
Extended to support Touch firmware 2.0.0 and later and newer devices by David Forrester <davidfor@internode.on.net>
'''

import os, time, shutil, re

from contextlib import closing
from calibre.devices.usbms.books import BookList
from calibre.devices.usbms.books import CollectionsBookList
from calibre.devices.kobo.books import KTCollectionsBookList
from calibre.devices.kobo.books import Book
from calibre.devices.kobo.books import ImageWrapper
from calibre.devices.mime import mime_type_ext
from calibre.devices.usbms.driver import USBMS, debug_print
from calibre import prints, fsync
from calibre.ptempfile import PersistentTemporaryFile
from calibre.constants import DEBUG
from calibre.utils.config_base import prefs

EPUB_EXT  = '.epub'
KEPUB_EXT = '.kepub'

# Implementation of QtQHash for strings. This doesn't seem to be in the Python implementation.


def qhash(inputstr):
    instr = b""
    if isinstance(inputstr, bytes):
        instr = inputstr
    elif isinstance(inputstr, unicode):
        instr = inputstr.encode("utf8")
    else:
        return -1

    h = 0x00000000
    for x in bytearray(instr):
        h = (h << 4) + x
        h ^= (h & 0xf0000000) >> 23
        h &= 0x0fffffff

    return h


class DummyCSSPreProcessor(object):

    def __call__(self, data, add_namespace=False):

        return data


class KOBO(USBMS):

    name = 'Kobo Reader Device Interface'
    gui_name = 'Kobo Reader'
    description = _('Communicate with the Kobo Reader')
    author = 'Timothy Legge and David Forrester'
    version = (2, 3, 3)

    dbversion = 0
    fwversion = (0,0,0)
    supported_dbversion = 129
    has_kepubs = False

    supported_platforms = ['windows', 'osx', 'linux']

    booklist_class = CollectionsBookList
    book_class = Book

    # Ordered list of supported formats
    FORMATS     = ['kepub', 'epub', 'pdf', 'txt', 'cbz', 'cbr']
    CAN_SET_METADATA = ['collections']

    VENDOR_ID           = [0x2237]
    BCD                 = [0x0110, 0x0323, 0x0326]
    ORIGINAL_PRODUCT_ID = [0x4165]
    WIFI_PRODUCT_ID     = [0x4161, 0x4162]
    PRODUCT_ID          = ORIGINAL_PRODUCT_ID + WIFI_PRODUCT_ID

    VENDOR_NAME = ['KOBO_INC', 'KOBO']
    WINDOWS_MAIN_MEM = WINDOWS_CARD_A_MEM = ['.KOBOEREADER', 'EREADER']

    EBOOK_DIR_MAIN = ''
    SUPPORTS_SUB_DIRS = True
    SUPPORTS_ANNOTATIONS = True

    # "kepubs" do not have an extension. The name looks like a GUID. Using an empty string seems to work.
    VIRTUAL_BOOK_EXTENSIONS = frozenset(['kobo', ''])

    EXTRA_CUSTOMIZATION_MESSAGE = [
        _('The Kobo supports several collections including ')+ 'Read, Closed, Im_Reading. ' +
        _('Create tags for automatic management'),
        _('Upload covers for books (newer readers)') +
        ':::'+_('Normally, the Kobo readers get the cover image from the'
                ' e-book file itself. With this option, calibre will send a '
                'separate cover image to the reader, useful if you '
                'have modified the cover.'),
        _('Upload Black and White Covers'),
        _('Show expired books') +
        ':::'+_('A bug in an earlier version left non kepubs book records'
                ' in the database.  With this option calibre will show the '
                'expired records and allow you to delete them with '
                'the new delete logic.'),
        _('Show Previews') +
        ':::'+_('Kobo previews are included on the Touch and some other versions'
                ' by default they are no longer displayed as there is no good reason to '
                'see them.  Enable if you wish to see/delete them.'),
        _('Show Recommendations') +
        ':::'+_('Kobo now shows recommendations on the device. In some cases these have '
                'files but in other cases they are just pointers to the web site to buy. '
                'Enable if you wish to see/delete them.'),
        _('Attempt to support newer firmware') +
        ':::'+_('Kobo routinely updates the firmware and the '
                'database version. With this option calibre will attempt '
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

    def __init__(self, *args, **kwargs):
        USBMS.__init__(self, *args, **kwargs)
        self.plugboards = self.plugboard_func = None

    def initialize(self):
        USBMS.initialize(self)
        self.dbversion = 7

    def device_database_path(self):
        return self.normalize_path(self._main_prefix + '.kobo/KoboReader.sqlite')

    def device_database_connection(self):
        import apsw
        db_connection = apsw.Connection(self.device_database_path())

        return db_connection

    def get_database_version(self, connection):
        cursor = connection.cursor()
        cursor.execute('SELECT version FROM dbversion')
        try:
            result = cursor.next()
            dbversion = result[0]
        except StopIteration:
            dbversion = 0

        return dbversion

    def get_firmware_version(self):
        # Determine the firmware version
        try:
            with lopen(self.normalize_path(self._main_prefix + '.kobo/version'), 'rb') as f:
                fwversion = f.readline().split(',')[2]
                fwversion = tuple((int(x) for x in fwversion.split('.')))
        except:
            debug_print("Kobo::get_firmware_version - didn't get firmware version from file'")
            fwversion = (0,0,0)

        return fwversion

    def sanitize_path_components(self, components):
        invalid_filename_chars_re = re.compile(r'[\/\\\?%\*:;\|\"\'><\$!]', re.IGNORECASE | re.UNICODE)
        return [invalid_filename_chars_re.sub('_', x) for x in components]

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

        self.fwversion = self.get_firmware_version()

        if not (self.fwversion == (1,0) or self.fwversion == (1,4)):
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

                        # print "Image name Normalized: " + imagename
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
                            debug_print("prefix: ", prefix, "lpath: ", lpath, "title: ", title, "authors: ", authors,
                                        "mime: ", mime, "date: ", date, "ContentType: ", ContentType, "ImageID: ", ImageID)
                            raise

                    # print 'Update booklist'
                    book.device_collections = playlist_map.get(lpath,[])  # if lpath in playlist_map else []

                    if bl.add_book(book, replace_metadata=False):
                        changed = True
            except:  # Probably a path encoding error
                import traceback
                traceback.print_exc()
            return changed

        with closing(self.device_database_connection()) as connection:

            self.dbversion = self.get_database_version(connection)
            debug_print("Database Version: ", self.dbversion)

            cursor = connection.cursor()
            opts = self.settings()
            if self.dbversion >= 33:
                query= ('select Title, Attribution, DateCreated, ContentID, MimeType, ContentType, '
                    'ImageID, ReadStatus, ___ExpirationStatus, FavouritesIndex, Accessibility, IsDownloaded from content where '
                    'BookID is Null %(previews)s %(recomendations)s and not ((___ExpirationStatus=3 or ___ExpirationStatus is Null) %(expiry)s') % dict(
                        expiry=' and ContentType = 6)' if opts.extra_customization[self.OPT_SHOW_EXPIRED_BOOK_RECORDS] else ')',
                    previews=' and Accessibility <> 6' if not self.show_previews else '',
                    recomendations=' and IsDownloaded in (\'true\', 1)' if opts.extra_customization[self.OPT_SHOW_RECOMMENDATIONS] is False else '')
            elif self.dbversion >= 16 and self.dbversion < 33:
                query= ('select Title, Attribution, DateCreated, ContentID, MimeType, ContentType, '
                    'ImageID, ReadStatus, ___ExpirationStatus, FavouritesIndex, Accessibility, "1" as IsDownloaded from content where '
                    'BookID is Null and not ((___ExpirationStatus=3 or ___ExpirationStatus is Null) %(expiry)s') % dict(expiry=' and ContentType = 6)'
                    if opts.extra_customization[self.OPT_SHOW_EXPIRED_BOOK_RECORDS] else ')')
            elif self.dbversion < 16 and self.dbversion >= 14:
                query= ('select Title, Attribution, DateCreated, ContentID, MimeType, ContentType, '
                    'ImageID, ReadStatus, ___ExpirationStatus, FavouritesIndex, "-1" as Accessibility, "1" as IsDownloaded from content where '
                    'BookID is Null and not ((___ExpirationStatus=3 or ___ExpirationStatus is Null) %(expiry)s') % dict(expiry=' and ContentType = 6)'
                    if opts.extra_customization[self.OPT_SHOW_EXPIRED_BOOK_RECORDS] else ')')
            elif self.dbversion < 14 and self.dbversion >= 8:
                query= ('select Title, Attribution, DateCreated, ContentID, MimeType, ContentType, '
                    'ImageID, ReadStatus, ___ExpirationStatus, "-1" as FavouritesIndex, "-1" as Accessibility, "1" as IsDownloaded from content where '
                    'BookID is Null and not ((___ExpirationStatus=3 or ___ExpirationStatus is Null) %(expiry)s') % dict(expiry=' and ContentType = 6)'
                    if opts.extra_customization[self.OPT_SHOW_EXPIRED_BOOK_RECORDS] else ')')
            else:
                query = ('select Title, Attribution, DateCreated, ContentID, MimeType, ContentType, '
                         'ImageID, ReadStatus, "-1" as ___ExpirationStatus, "-1" as FavouritesIndex, '
                         '"-1" as Accessibility, "1" as IsDownloaded from content where BookID is Null')

            try:
                cursor.execute(query)
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

        # print "count found in cache: %d, count of files in metadata: %d, need_sync: %s" % \
        #      (len(bl_cache), len(bl), need_sync)
        if need_sync:  # self.count_found_in_bl != len(bl) or need_sync:
            if oncard == 'cardb':
                self.sync_booklists((None, None, bl))
            elif oncard == 'carda':
                self.sync_booklists((None, bl, None))
            else:
                self.sync_booklists((bl, None, None))

        self.report_progress(1.0, _('Getting list of books on device...'))
        return bl

    def filename_callback(self, path, mi):
        #        debug_print("Kobo:filename_callback:Path - {0}".format(path))

        idx = path.rfind('.')
        ext = path[idx:]
        if ext == KEPUB_EXT:
            path = path + EPUB_EXT
#            debug_print("Kobo:filename_callback:New path - {0}".format(path))

        return path

    def delete_via_sql(self, ContentID, ContentType):
        # Delete Order:
        #    1) shortcover_page
        #    2) volume_shorcover
        #    2) content

        debug_print('delete_via_sql: ContentID: ', ContentID, 'ContentType: ', ContentType)
        with closing(self.device_database_connection()) as connection:

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

            # Delete the volume_shortcovers second
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
                    cursor.execute('update content set ReadStatus=0, FirstTimeReading = \'true\', ___PercentRead=0, ___ExpirationStatus=3 '
                        'where BookID is Null and ContentID =?',t)
                except Exception as e:
                    if 'no such column' not in str(e):
                        raise
                    try:
                        cursor.execute('update content set ReadStatus=0, FirstTimeReading = \'true\', ___PercentRead=0 '
                            'where BookID is Null and ContentID =?',t)
                    except Exception as e:
                        if 'no such column' not in str(e):
                            raise
                        cursor.execute('update content set ReadStatus=0, FirstTimeReading = \'true\' '
                            'where BookID is Null and ContentID =?',t)
            else:
                cursor.execute('delete from content where BookID is Null and ContentID =?',t)

            cursor.close()
            if ImageID is None:
                print "Error condition ImageID was not found"
                print "You likely tried to delete a book that the kobo has not yet added to the database"

        # If all this succeeds we need to delete the images files via the ImageID
        return ImageID

    def delete_images(self, ImageID, book_path):
        if ImageID is not None:
            path_prefix = '.kobo/images/'
            path = self._main_prefix + path_prefix + ImageID

            file_endings = (' - iPhoneThumbnail.parsed', ' - bbMediumGridList.parsed', ' - NickelBookCover.parsed', ' - N3_LIBRARY_FULL.parsed',
                            ' - N3_LIBRARY_GRID.parsed', ' - N3_LIBRARY_LIST.parsed', ' - N3_SOCIAL_CURRENTREAD.parsed', ' - N3_FULL.parsed',)

            for ending in file_endings:
                fpath = path + ending
                fpath = self.normalize_path(fpath)

                if os.path.exists(fpath):
                    # print 'Image File Exists: ' + fpath
                    os.unlink(fpath)

    def delete_books(self, paths, end_session=True):
        if self.modify_database_check("delete_books") is False:
            return

        for i, path in enumerate(paths):
            self.report_progress((i+1) / float(len(paths)), _('Removing books from device...'))
            path = self.normalize_path(path)
            # print "Delete file normalized path: " + path
            extension =  os.path.splitext(path)[1]
            ContentType = self.get_content_type_from_extension(extension) if extension != '' else self.get_content_type_from_path(path)

            ContentID = self.contentid_from_path(path, ContentType)

            ImageID = self.delete_via_sql(ContentID, ContentType)
            # print " We would now delete the Images for" + ImageID
            self.delete_images(ImageID, path)

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
        if self.modify_database_check("remove_books_from_metatata") is False:
            return

        for i, path in enumerate(paths):
            self.report_progress((i+1) / float(len(paths)), _('Removing books from device metadata listing...'))
            for bl in booklists:
                for book in bl:
                    # print "Book Path: " + book.path
                    if path.endswith(book.path):
                        # print "    Remove: " + book.path
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
            # print "Add book to metatdata: "
            # print "prefix: " + prefix
            lpath = path.partition(prefix)[2]
            if lpath.startswith('/') or lpath.startswith('\\'):
                lpath = lpath[1:]
            # print "path: " + lpath
            book = self.book_class(prefix, lpath, other=info)
            if book.size is None or book.size == 0:
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
        elif ContentType == 999:  # HTML Files
            ContentID = path
            ContentID = ContentID.replace(self._main_prefix, "/mnt/onboard/")
            if self._card_a_prefix is not None:
                ContentID = ContentID.replace(self._card_a_prefix, "/mnt/sd/")
        else:  # ContentType = 16
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
            # print "kobo book"
            ContentType = 6
        elif extension == '.pdf' or extension == '.epub':
            # print "ePub or pdf"
            ContentType = 16
        elif extension == '.rtf' or extension == '.txt' or extension == '.htm' or extension == '.html':
            # print "txt"
            if self.fwversion == (1,0) or self.fwversion == (1,4) or self.fwversion == (1,7,4):
                ContentType = 999
            else:
                ContentType = 901
        else:  # if extension == '.html' or extension == '.txt':
            ContentType = 901  # Yet another hack: to get around Kobo changing how ContentID is stored
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
                    ' your Kobo.') + ((
                    '\nDevice database version: %s.'
                    '\nDevice firmware version: %s') % (self.dbversion, self.fwversion))
                    , UserFeedback.WARN)

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
                    _('".kobo" files do not exist on the device as books; '
                        'instead they are rows in the sqlite database. '
                    'Currently they cannot be exported or viewed.'),
                    UserFeedback.WARN)

        return USBMS.get_file(self, path, *args, **kwargs)

    @classmethod
    def book_from_path(cls, prefix, lpath, title, authors, mime, date, ContentType, ImageID):
        #        debug_print("KOBO:book_from_path - title=%s"%title)
        from calibre.ebooks.metadata import MetaInformation

        if cls.read_metadata or cls.MUST_READ_METADATA:
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
        paths = {}
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
            cursor.execute(query)
        except:
            debug_print('    Database Exception:  Unable to reset ReadStatus list')
            raise
        finally:
            cursor.close()

    def set_readstatus(self, connection, ContentID, ReadStatus):
        cursor = connection.cursor()
        t = (ContentID,)
        cursor.execute('select DateLastRead from Content where BookID is Null and ContentID = ?', t)
        try:
            result = cursor.next()
            datelastread = result[0] if result[0] is not None else '1970-01-01T00:00:00'
        except StopIteration:
            datelastread = '1970-01-01T00:00:00'

        t = (ReadStatus,datelastread,ContentID,)

        try:
            cursor.execute('update content set ReadStatus=?,FirstTimeReading=\'false\',DateLastRead=? where BookID is Null and ContentID = ?', t)
        except:
            debug_print('    Database Exception:  Unable update ReadStatus')
            raise

        cursor.close()

    def reset_favouritesindex(self, connection, oncard):
        # Reset FavouritesIndex list in the database
        if oncard == 'carda':
            query= 'update content set FavouritesIndex=-1 where BookID is Null and ContentID like \'file:///mnt/sd/%\''
        elif oncard != 'carda' and oncard != 'cardb':
            query= 'update content set FavouritesIndex=-1 where BookID is Null and ContentID not like \'file:///mnt/sd/%\''

        cursor = connection.cursor()
        try:
            cursor.execute(query)
        except Exception as e:
            debug_print('    Database Exception:  Unable to reset Shortlist list')
            if 'no such column' not in str(e):
                raise
        finally:
            cursor.close()

    def set_favouritesindex(self, connection, ContentID):
        cursor = connection.cursor()

        t = (ContentID,)

        try:
            cursor.execute('update content set FavouritesIndex=1 where BookID is Null and ContentID = ?', t)
        except Exception as e:
            debug_print('    Database Exception:  Unable set book as Shortlist')
            if 'no such column' not in str(e):
                raise
        finally:
            cursor.close()

    def update_device_database_collections(self, booklists, collections_attributes, oncard):
        debug_print("Kobo:update_device_database_collections - oncard='%s'"%oncard)
        if self.modify_database_check("update_device_database_collections") is False:
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
#        debug_print('Kobo:update_device_database_collections - Collections:', collections)

        # Create a connection to the sqlite database
        # Needs to be outside books collection as in the case of removing
        # the last book from the collection the list of books is empty
        # and the removal of the last book would not occur

        with closing(self.device_database_connection()) as connection:

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
            else:  # No collections
                # Since no collections exist the ReadStatus needs to be reset to 0 (Unread)
                debug_print("No Collections - reseting ReadStatus")
                self.reset_readstatus(connection, oncard)
                if self.dbversion >= 14:
                    debug_print("No Collections - reseting FavouritesIndex")
                    self.reset_favouritesindex(connection, oncard)

#        debug_print('Finished update_device_database_collections', collections_attributes)

    def get_collections_attributes(self):
        collections = [x.lower().strip() for x in self.collections_columns.split(',')]
        return collections

    @property
    def collections_columns(self):
        opts = self.settings()
        return opts.extra_customization[self.OPT_COLLECTIONS]

    @property
    def read_metadata(self):
        return self.settings().read_metadata

    @property
    def show_previews(self):
        opts = self.settings()
        return opts.extra_customization[self.OPT_SHOW_PREVIEWS] is False

    def sync_booklists(self, booklists, end_session=True):
        debug_print('KOBO:sync_booklists - start')
        paths = self.get_device_paths()

        blists = {}
        for i in paths:
            try:
                if booklists[i] is not None:
                    # debug_print('Booklist: ', i)
                    blists[i] = booklists[i]
            except IndexError:
                pass
        collections = self.get_collections_attributes()

        # debug_print('KOBO: collection fields:', collections)
        for i, blist in blists.items():
            if i == 0:
                oncard = 'main'
            else:
                oncard = 'carda'
            self.update_device_database_collections(blist, collections, oncard)

        USBMS.sync_booklists(self, booklists, end_session=end_session)
        debug_print('KOBO:sync_booklists - end')

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
        from calibre.utils.img import save_cover_data_to
        if metadata.cover:
            cover = self.normalize_path(metadata.cover.replace('/', os.sep))

            if os.path.exists(cover):
                # Get ContentID for Selected Book
                extension =  os.path.splitext(filepath)[1]
                ContentType = self.get_content_type_from_extension(extension) if extension != '' else self.get_content_type_from_path(filepath)
                ContentID = self.contentid_from_path(filepath, ContentType)

                with closing(self.device_database_connection()) as connection:

                    cursor = connection.cursor()
                    t = (ContentID,)
                    cursor.execute('select ImageId from Content where BookID is Null and ContentID = ?', t)
                    try:
                        result = cursor.next()
#                        debug_print("ImageId: ", result[0])
                        ImageID = result[0]
                    except StopIteration:
                        debug_print("No rows exist in the database - cannot upload")
                        return
                    finally:
                        cursor.close()

                if ImageID is not None:
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
                            with lopen(cover, 'rb') as f:
                                data = f.read()

                            # Return the data resized and in Grayscale if
                            # required
                            data = save_cover_data_to(data, grayscale=uploadgrayscale, resize_to=resize)

                            with lopen(fpath, 'wb') as f:
                                f.write(data)
                                fsync(f)

                else:
                    debug_print("ImageID could not be retreived from the database")

    def prepare_addable_books(self, paths):
        '''
        The Kobo supports an encrypted epub refered to as a kepub
        Unfortunately Kobo decided to put the files on the device
        with no file extension.  I just hope that decision causes
        them as much grief as it does me :-)

        This has to make a temporary copy of the book files with a
        epub extension to allow calibre's normal processing to
        deal with the file appropriately
        '''
        for idx, path in enumerate(paths):
            if path.find('kepub') >= 0:
                with closing(lopen(path, 'rb')) as r:
                    tf = PersistentTemporaryFile(suffix='.epub')
                    shutil.copyfileobj(r, tf)
#                    tf.write(r.read())
                    paths[idx] = tf.name
        return paths

    @classmethod
    def config_widget(self):
        # TODO: Cleanup the following
        self.current_friendly_name = self.gui_name

        from calibre.gui2.device_drivers.tabbed_device_config import TabbedDeviceConfig
        return TabbedDeviceConfig(self.settings(), self.FORMATS, self.SUPPORTS_SUB_DIRS,
                    self.MUST_READ_METADATA, self.SUPPORTS_USE_AUTHOR_SORT,
                    self.EXTRA_CUSTOMIZATION_MESSAGE, self,
                    extra_customization_choices=self.EXTRA_CUSTOMIZATION_CHOICES)

    def migrate_old_settings(self, old_settings):

        OPT_COLLECTIONS    = 0
        OPT_UPLOAD_COVERS  = 1
        OPT_UPLOAD_GRAYSCALE_COVERS  = 2
        OPT_SHOW_EXPIRED_BOOK_RECORDS = 3
        OPT_SHOW_PREVIEWS = 4
        OPT_SHOW_RECOMMENDATIONS = 5
        OPT_SUPPORT_NEWER_FIRMWARE = 6

        p = {}
        p['format_map'] = old_settings.format_map
        p['save_template'] = old_settings.save_template
        p['use_subdirs'] = old_settings.use_subdirs
        p['read_metadata'] = old_settings.read_metadata
        p['use_author_sort'] = old_settings.use_author_sort
        p['extra_customization'] = old_settings.extra_customization

        p['collections_columns'] = old_settings.extra_customization[OPT_COLLECTIONS]

        p['upload_covers'] = old_settings.extra_customization[OPT_UPLOAD_COVERS]
        p['upload_grayscale'] = old_settings.extra_customization[OPT_UPLOAD_GRAYSCALE_COVERS]

        p['show_expired_books'] = old_settings.extra_customization[OPT_SHOW_EXPIRED_BOOK_RECORDS]
        p['show_previews'] = old_settings.extra_customization[OPT_SHOW_PREVIEWS]
        p['show_recommendations'] = old_settings.extra_customization[OPT_SHOW_RECOMMENDATIONS]

        p['support_newer_firmware'] = old_settings.extra_customization[OPT_SUPPORT_NEWER_FIRMWARE]

        return p

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
        with closing(self.device_database_connection()) as connection:
            for id in path_map:
                extension =  os.path.splitext(path_map[id])[1]
                ContentType = self.get_content_type_from_extension(extension) if extension != '' else self.get_content_type_from_path(path_map[id])
                ContentID = self.contentid_from_path(path_map[id], ContentType)
                debug_print("get_annotations - ContentID: ",  ContentID, "ContentType: ", ContentType)

                bookmark_ext = extension

                myBookmark = Bookmark(connection, ContentID, path_map[id], id, book_ext[id], bookmark_ext)
                bookmarked_books[id] = self.UserAnnotation(type='kobo_bookmark', value=myBookmark)

        # This returns as job.result in gui2.ui.annotations_fetched(self,job)
        return bookmarked_books

    def generate_annotation_html(self, bookmark):
        import calendar
        from calibre.ebooks.BeautifulSoup import BeautifulSoup, Tag, NavigableString
        # Returns <div class="user_annotations"> ... </div>
        # last_read_location = bookmark.last_read_location
        # timestamp = bookmark.timestamp
        percent_read = bookmark.percent_read
        debug_print("Kobo::generate_annotation_html - last_read: ",  bookmark.last_read)
        if bookmark.last_read is not None:
            try:
                last_read = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(calendar.timegm(time.strptime(bookmark.last_read, "%Y-%m-%dT%H:%M:%S"))))
            except:
                try:
                    last_read = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(calendar.timegm(time.strptime(bookmark.last_read, "%Y-%m-%dT%H:%M:%S.%f"))))
                except:
                    try:
                        last_read = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(calendar.timegm(time.strptime(bookmark.last_read, "%Y-%m-%dT%H:%M:%SZ"))))
                    except:
                        last_read = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())
        else:
            # self.datetime = time.gmtime()
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
                _("<hr /><b>Book last read:</b> %(time)s<br /><b>Percentage read:</b> %(pr)d%%<hr />") % dict(
                    time=last_read,
                    # loc=last_read_location,
                    pr=percent_read)))
        else:
            spanTag.insert(0,NavigableString(
                _("<hr /><b>Book last read:</b> %(time)s<br /><b>Percentage read:</b> %(pr)d%%<hr />") % dict(
                    time=last_read,
                    # loc=last_read_location,
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
                        _('<b>Chapter %(chapter)d:</b> %(chapter_title)s<br /><b>%(typ)s</b>'
                          '<br /><b>Chapter Progress:</b> %(chapter_progress)s%%<br />%(annotation)s<br /><hr />') % dict(
                            chapter=user_notes[location]['chapter'],
                            dl=user_notes[location]['displayed_location'],
                            typ=user_notes[location]['type'],
                            chapter_title=user_notes[location]['chapter_title'],
                            chapter_progress=user_notes[location]['chapter_progress'],
                            annotation=user_notes[location]['annotation'] if user_notes[location]['annotation'] is not None else ""))
                elif user_notes[location]['type'] == 'Highlight':
                    annotations.append(
                        _('<b>Chapter %(chapter)d:</b> %(chapter_title)s<br /><b>%(typ)s</b><br />'
                          '<b>Chapter progress:</b> %(chapter_progress)s%%<br /><b>Highlight:</b> %(text)s<br /><hr />') % dict(
                              chapter=user_notes[location]['chapter'],
                              dl=user_notes[location]['displayed_location'],
                              typ=user_notes[location]['type'],
                              chapter_title=user_notes[location]['chapter_title'],
                              chapter_progress=user_notes[location]['chapter_progress'],
                              text=user_notes[location]['text']))
                elif user_notes[location]['type'] == 'Annotation':
                    annotations.append(
                        _('<b>Chapter %(chapter)d:</b> %(chapter_title)s<br />'
                          '<b>%(typ)s</b><br /><b>Chapter progress:</b> %(chapter_progress)s%%<br /><b>Highlight:</b> %(text)s<br />'
                          '<b>Notes:</b> %(annotation)s<br /><hr />') % dict(
                              chapter=user_notes[location]['chapter'],
                              dl=user_notes[location]['displayed_location'],
                              typ=user_notes[location]['type'],
                              chapter_title=user_notes[location]['chapter_title'],
                              chapter_progress=user_notes[location]['chapter_progress'],
                              text=user_notes[location]['text'],
                              annotation=user_notes[location]['annotation']))
                else:
                    annotations.append(
                        _('<b>Chapter %(chapter)d:</b> %(chapter_title)s<br />'
                          '<b>%(typ)s</b><br /><b>Chapter progress:</b> %(chapter_progress)s%%<br /><b>Highlight:</b> %(text)s<br />'
                          '<b>Notes:</b> %(annotation)s<br /><hr />') % dict(
                              chapter=user_notes[location]['chapter'],
                              dl=user_notes[location]['displayed_location'],
                              typ=user_notes[location]['type'],
                              chapter_title=user_notes[location]['chapter_title'],
                              chapter_progress=user_notes[location]['chapter_progress'],
                              text=user_notes[location]['text'],
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

        if bm.type == 'kobo_bookmark' and bm.value.last_read:
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
            # NOTE: As it is, this copied the book from the device back to the library. That meant it replaced the
            #     existing file. Taking this out for that reason, but some books have a ANNOT file that could be
            #     copied.
#            db.add_format_with_hooks(db_id, bm.value.bookmark_extension,
#                                            bm.value.path, index_is_id=True)


class KOBOTOUCH(KOBO):
    name        = 'KoboTouch'
    gui_name    = 'Kobo Touch/Glo/Mini/Aura HD/Aura H2O/Glo HD/Touch 2'
    author      = 'David Forrester'
    description = _('Communicate with the Kobo Touch, Glo, Mini, Aura HD, Aura H2O, Glo HD, Touch 2, Aura ONE and Aura Edition 2 ereaders.'
                    ' Based on the existing Kobo driver by %s.') % KOBO.author
#    icon        = I('devices/kobotouch.jpg')

    supported_dbversion             = 141
    min_supported_dbversion         = 53
    min_dbversion_series            = 65
    min_dbversion_externalid        = 65
    min_dbversion_archive           = 71
    min_dbversion_images_on_sdcard  = 77
    min_dbversion_activity          = 77
    min_dbversion_keywords          = 82

    # Starting with firmware version 3.19.x, the last number appears to be is a
    # build number. A number will be recorded here but it can be safely ignored
    # when testing the firmware version.
    max_supported_fwversion         = (4, 4, 9278)
    # The following document firwmare versions where new function or devices were added.
    # Not all are used, but this feels a good place to record it.
    min_fwversion_shelves           = (2, 0, 0)
    min_fwversion_images_on_sdcard  = (2, 4, 1)
    min_fwversion_images_tree       = (2, 9, 0)  # Cover images stored in tree under .kobo-images
    min_aurah2o_fwversion           = (3, 7, 0)
    min_reviews_fwversion           = (3, 12, 0)
    min_glohd_fwversion             = (3, 14, 0)
    min_auraone_fwversion           = (3, 20, 7280)
    min_fwversion_overdrive         = (4,  0, 7523)

    has_kepubs = True

    booklist_class = KTCollectionsBookList
    book_class = Book

    MAX_PATH_LEN = 185  # 250 - (len(" - N3_LIBRARY_SHELF.parsed") + len("F:\.kobo\images\"))
    KOBO_EXTRA_CSSFILE = 'kobo_extra.css'

    EXTRA_CUSTOMIZATION_MESSAGE = []
    EXTRA_CUSTOMIZATION_DEFAULT = []

    opts = None

    TIMESTAMP_STRING = "%Y-%m-%dT%H:%M:%SZ"

    AURA_PRODUCT_ID     = [0x4203]
    AURA_EDITION2_PRODUCT_ID    = [0x4226]
    AURA_HD_PRODUCT_ID  = [0x4193]
    AURA_H2O_PRODUCT_ID = [0x4213]
    AURA_H2O_EDITION2_PRODUCT_ID = [0x4227]
    AURA_ONE_PRODUCT_ID = [0x4225]
    GLO_PRODUCT_ID      = [0x4173]
    GLO_HD_PRODUCT_ID   = [0x4223]
    MINI_PRODUCT_ID     = [0x4183]
    TOUCH_PRODUCT_ID    = [0x4163]
    TOUCH2_PRODUCT_ID   = [0x4224]
    PRODUCT_ID          = AURA_PRODUCT_ID + AURA_EDITION2_PRODUCT_ID + \
                          AURA_HD_PRODUCT_ID + AURA_H2O_PRODUCT_ID + AURA_H2O_EDITION2_PRODUCT_ID + \
                          GLO_PRODUCT_ID + GLO_HD_PRODUCT_ID + \
                          MINI_PRODUCT_ID + TOUCH_PRODUCT_ID + TOUCH2_PRODUCT_ID + \
                          AURA_ONE_PRODUCT_ID

    BCD = [0x0110, 0x0326]

    # Image file name endings. Made up of: image size, min_dbversion, max_dbversion, isFullSize,
    # Note: "200" has been used just as a much larger number than the current versions. It is just a lazy
    #    way of making it open ended.
    COVER_FILE_ENDINGS = {
                          # Used for screensaver, home screen
                          ' - N3_FULL.parsed':[(600,800),0, 200,True,],            # Used for screensaver, home screen
                          # Used for Details screen before FW2.8.1, then for current book tile on home screen
                          ' - N3_LIBRARY_FULL.parsed':[(355,473),0, 200,False,],
                          # Used for library lists
                          ' - N3_LIBRARY_GRID.parsed':[(149,198),0, 200,False,],   # Used for library lists
                          # Used for library lists
                          ' - N3_LIBRARY_LIST.parsed':[(60,90),0, 53,False,],
                          # Used for Details screen from FW2.8.1
                          ' - AndroidBookLoadTablet_Aspect.parsed':[(355,473), 82, 100,False,],
                          }
    # Glo and Aura share resolution, so the image sizes should be the same.
    GLO_COVER_FILE_ENDINGS = {
                          # Used for screensaver, home screen
                          ' - N3_FULL.parsed':[(758,1024),0, 200,True,],
                          # Used for Details screen before FW2.8.1, then for current book tile on home screen
                          ' - N3_LIBRARY_FULL.parsed':[(355,479),0, 200,False,],
                          # Used for library lists
                          ' - N3_LIBRARY_GRID.parsed':[(149,201),0, 200,False,],
                          # Used for Details screen from FW2.8.1
                          ' - AndroidBookLoadTablet_Aspect.parsed':[(355,479), 88, 100,False,],
                          }
    GLO_HD_COVER_FILE_ENDINGS = {
                          # Used for screensaver, home screen
                          ' - N3_FULL.parsed':        [(1072,1448), 0, 200,True,],
                          # Used for Details screen before FW2.8.1, then for current book tile on home screen
                          ' - N3_LIBRARY_FULL.parsed':[(355,  479), 0, 200,False,],
                          # Used for library lists
                          ' - N3_LIBRARY_GRID.parsed':[(149,  201), 0, 200,False,],
                          # Used for Details screen from FW2.8.1
                          ' - AndroidBookLoadTablet_Aspect.parsed':[(355,  471), 88, 100,False,],
                          }
    AURA_HD_COVER_FILE_ENDINGS = {
                          # Used for screensaver, home screen
                          ' - N3_FULL.parsed':        [(1080,1440), 0, 200,True,],
                          # Used for Details screen before FW2.8.1, then for current book tile on home screen
                          ' - N3_LIBRARY_FULL.parsed':[(355,  471), 0, 200,False,],
                          # Used for library lists
                          ' - N3_LIBRARY_GRID.parsed':[(149,  198), 0, 200,False,],
                          # Used for Details screen from FW2.8.1
                          ' - AndroidBookLoadTablet_Aspect.parsed':[(355,  471), 88, 100,False,],
                          }
    AURA_ONE_COVER_FILE_ENDINGS = {
                          # Used for screensaver, home screen
                          ' - N3_FULL.parsed':        [(1404,1872), 0, 200,True,],
                          # Used for Details screen before FW2.8.1, then for current book tile on home screen
                          ' - N3_LIBRARY_FULL.parsed':[(355,  473), 0, 200,False,],
                          # Used for library lists
                          ' - N3_LIBRARY_GRID.parsed':[(149,  198), 0, 200,False,],  # Used for library lists
                          }
    # Following are the sizes used with pre2.1.4 firmware
#    COVER_FILE_ENDINGS = {
# ' - N3_LIBRARY_FULL.parsed':[(355,530),0, 99,],   # Used for Details screen
# ' - N3_LIBRARY_FULL.parsed':[(600,800),0, 99,],
# ' - N3_LIBRARY_GRID.parsed':[(149,233),0, 99,],   # Used for library lists
#                          ' - N3_LIBRARY_LIST.parsed':[(60,90),0, 53,],
#                          ' - N3_LIBRARY_SHELF.parsed': [(40,60),0, 52,],
# ' - N3_FULL.parsed':[(600,800),0, 99,],           # Used for screensaver if "Full screen" is checked.
#                          }

    def __init__(self, *args, **kwargs):
        KOBO.__init__(self, *args, **kwargs)
        self.plugboards = self.plugboard_func = None

    def initialize(self):
        super(KOBOTOUCH, self).initialize()
        self.bookshelvelist = []

    def get_device_information(self, end_session=True):
        self.set_device_name()
        return super(KOBOTOUCH, self).get_device_information(end_session)

    def open_linux(self):
        super(KOBOTOUCH, self).open_linux()

        # Check the drives have been mounted as expected and swap if needed.
        if self._card_a_prefix is None:
            return

        if not self.is_main_drive(self._main_prefix):
            temp_prefix = self._main_prefix
            self._main_prefix = self._card_a_prefix
            self._card_a_prefix = temp_prefix

    def osx_sort_names(self, names):
        return self.sort_drives(names)

    def windows_sort_drives(self, drives):
        return self.sort_drives(drives)

    def sort_drives(self, drives):
        if len(drives) < 2:
            return drives
        main = drives.get('main', None)
        carda = drives.get('carda', None)
        if main and carda and not self.is_main_drive(main):
            debug_print('KoboTouch::windows_sort_drives - main=%s, carda=%s' % (main, carda))
            drives['main'] = carda
            drives['carda'] = main
        return drives

    def is_main_drive(self, drive):
        debug_print('KoboTouch::is_main_drive - main_drive=%s, path=%s' % (drive, os.path.join(drive, '.kobo')))
        return os.path.exists(self.normalize_path(os.path.join(drive, '.kobo')))

    def books(self, oncard=None, end_session=True):
        debug_print("KoboTouch:books - oncard='%s'"%oncard)
        from calibre.ebooks.metadata.meta import path_to_ext
        self.debugging_title = self.get_debugging_title()

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
        debug_print("KoboTouch:books - oncard='%s', prefix='%s'"%(oncard, prefix))

        self.fwversion = self.get_firmware_version()

        debug_print('Kobo device: %s' % self.gui_name)
        debug_print('Version of driver:', self.version, 'Has kepubs:', self.has_kepubs)
        debug_print('Version of firmware:', self.fwversion, 'Has kepubs:', self.has_kepubs)
        debug_print('Firmware supports cover image tree:', self.fwversion >= self.min_fwversion_images_tree)

        self.booklist_class.rebuild_collections = self.rebuild_collections

        # get the metadata cache
        bl = self.booklist_class(oncard, prefix, self.settings)

        opts = self.settings()
        debug_print("KoboTouch:books - opts.extra_customization=", opts.extra_customization)
        debug_print("KoboTouch:books - driver options=", self)
        debug_print("KoboTouch:books - prefs['manage_device_metadata']=", prefs['manage_device_metadata'])
        debugging_title = self.debugging_title
        debug_print("KoboTouch:books - set_debugging_title to '%s'" % debugging_title)
        bl.set_debugging_title(debugging_title)
        debug_print("KoboTouch:books - length bl=%d"%len(bl))
        need_sync = self.parse_metadata_cache(bl, prefix, self.METADATA_CACHE)
        debug_print("KoboTouch:books - length bl after sync=%d"%len(bl))

        # make a dict cache of paths so the lookup in the loop below is faster.
        bl_cache = {}
        for idx,b in enumerate(bl):
            bl_cache[b.lpath] = idx

        def update_booklist(prefix, path, title, authors, mime, date, ContentID, ContentType, ImageID, readstatus, MimeType, expired, favouritesindex,
                            accessibility, isdownloaded, series, seriesnumber, userid, bookshelves):
            show_debug = self.is_debugging_title(title)
#            show_debug = authors == 'L. Frank Baum'
            if show_debug:
                debug_print("KoboTouch:update_booklist - title='%s'"%title, "ContentType=%s"%ContentType, "isdownloaded=", isdownloaded)
                debug_print(
                    "         prefix=%s, mime=%s, date=%s, readstatus=%d, MimeType=%s, expired=%d, favouritesindex=%d, accessibility=%d, isdownloaded=%s"%
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

                allow_shelves = True
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
                    allow_shelves = False
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
                        allow_shelves = False
                        if show_debug:
                            debug_print("KoboTouch:update_booklist - have a deleted book")
                    elif self.supports_kobo_archive() and (accessibility == 1 or accessibility == 2):
                        playlist_map[lpath].append('Archived')
                        allow_shelves = True

                # Label Previews and Recommendations
                if accessibility == 6:
                    if userid == '':
                        playlist_map[lpath].append('Recommendation')
                        allow_shelves = False
                    else:
                        playlist_map[lpath].append('Preview')
                        allow_shelves = False
                elif accessibility == 4:        # Pre 2.x.x firmware
                    playlist_map[lpath].append('Recommendation')
                    allow_shelves = False
                elif accessibility == 9:        # From 4.0 on Aura One
                    playlist_map[lpath].append('OverDrive')
                    allow_shelves = False

                kobo_collections = playlist_map[lpath][:]

                if allow_shelves:
                    #                    debug_print('KoboTouch:update_booklist - allowing shelves - title=%s' % title)
                    if len(bookshelves) > 0:
                        playlist_map[lpath].extend(bookshelves)

                if show_debug:
                    debug_print('KoboTouch:update_booklist - playlist_map=', playlist_map)

                path = self.normalize_path(path)
                # print "Normalized FileName: " + path

                idx = bl_cache.get(lpath, None)
                if idx is not None:  # and not (accessibility == 1 and isdownloaded == 'false'):
                    if show_debug:
                        self.debug_index = idx
                        debug_print("KoboTouch:update_booklist - idx=%d"%idx)
                        debug_print("KoboTouch:update_booklist - lpath=%s"%lpath)
                        debug_print('KoboTouch:update_booklist - bl[idx].device_collections=', bl[idx].device_collections)
                        debug_print('KoboTouch:update_booklist - playlist_map=', playlist_map)
                        debug_print('KoboTouch:update_booklist - bookshelves=', bookshelves)
                        debug_print('KoboTouch:update_booklist - kobo_collections=', kobo_collections)
                        debug_print('KoboTouch:update_booklist - series="%s"' % bl[idx].series)
                        debug_print('KoboTouch:update_booklist - the book=', bl[idx])
                        debug_print('KoboTouch:update_booklist - the authors=', bl[idx].authors)
                        debug_print('KoboTouch:update_booklist - application_id=', bl[idx].application_id)
                    bl_cache[lpath] = None

                    if ImageID is not None:
                        imagename = self.imagefilename_from_imageID(prefix, ImageID)
                        if imagename is not None:
                            bl[idx].thumbnail = ImageWrapper(imagename)
                    if (ContentType == '6' and MimeType != 'application/x-kobo-epub+zip'):
                        if os.path.exists(self.normalize_path(os.path.join(prefix, lpath))):
                            if self.update_metadata_item(bl[idx]):
                                #                                print 'update_metadata_item returned true'
                                changed = True
                        else:
                            debug_print("    Strange:  The file: ", prefix, lpath, " does not exist!")
                            debug_print("KoboTouch:update_booklist - book size=", bl[idx].size)

                    if show_debug:
                        debug_print("KoboTouch:update_booklist - ContentID='%s'"%ContentID)
                    bl[idx].contentID           = ContentID
                    bl[idx].kobo_series         = series
                    bl[idx].kobo_series_number  = seriesnumber
                    bl[idx].can_put_on_shelves  = allow_shelves

                    if lpath in playlist_map:
                        bl[idx].device_collections  = playlist_map.get(lpath,[])
                        bl[idx].current_shelves     = bookshelves
                        bl[idx].kobo_collections    = kobo_collections

                    if show_debug:
                        debug_print('KoboTouch:update_booklist - updated bl[idx].device_collections=', bl[idx].device_collections)
                        debug_print('KoboTouch:update_booklist - playlist_map=', playlist_map, 'changed=', changed)
#                        debug_print('KoboTouch:update_booklist - book=', bl[idx])
                        debug_print("KoboTouch:update_booklist - book class=%s"%bl[idx].__class__)
                        debug_print("KoboTouch:update_booklist - book title=%s"%bl[idx].title)
                else:
                    if show_debug:
                        debug_print('KoboTouch:update_booklist - idx is none')
                    try:
                        if os.path.exists(self.normalize_path(os.path.join(prefix, lpath))):
                            book = self.book_from_path(prefix, lpath, title, authors, mime, date, ContentType, ImageID)
                        else:
                            if isdownloaded == 'true':  # A recommendation or preview is OK to not have a file
                                debug_print("    Strange:  The file: ", prefix, lpath, " does not exist!")
                                title = "FILE MISSING: " + title
                            book =  self.book_class(prefix, lpath, title, authors, mime, date, ContentType, ImageID, size=0)
                            if show_debug:
                                debug_print('KoboTouch:update_booklist - book file does not exist. ContentID="%s"'%ContentID)

                    except Exception as e:
                        debug_print("KoboTouch:update_booklist - exception creating book: '%s'"%str(e))
                        debug_print("        prefix: ", prefix, "lpath: ", lpath, "title: ", title, "authors: ", authors,
                                    "mime: ", mime, "date: ", date, "ContentType: ", ContentType, "ImageID: ", ImageID)
                        raise

                    if show_debug:
                        debug_print('KoboTouch:update_booklist - class:', book.__class__)
#                        debug_print('    resolution:', book.__class__.__mro__)
                        debug_print("    contentid: '%s'"%book.contentID)
                        debug_print("    title:'%s'"%book.title)
                        debug_print("    the book:", book)
                        debug_print("    author_sort:'%s'"%book.author_sort)
                        debug_print("    bookshelves:", bookshelves)
                        debug_print("    kobo_collections:", kobo_collections)

                    # print 'Update booklist'
                    book.device_collections = playlist_map.get(lpath,[])  # if lpath in playlist_map else []
                    book.current_shelves    = bookshelves
                    book.kobo_collections   = kobo_collections
                    book.contentID          = ContentID
                    book.kobo_series        = series
                    book.kobo_series_number = seriesnumber
                    book.can_put_on_shelves = allow_shelves
#                    debug_print('KoboTouch:update_booklist - title=', title, 'book.device_collections', book.device_collections)

                    if bl.add_book(book, replace_metadata=False):
                        changed = True
                    if show_debug:
                        debug_print('        book.device_collections', book.device_collections)
                        debug_print('        book.title', book.title)
            except:  # Probably a path encoding error
                import traceback
                traceback.print_exc()
            return changed

        def get_bookshelvesforbook(connection, ContentID):
            #            debug_print("KoboTouch:get_bookshelvesforbook - " + ContentID)
            bookshelves = []
            if not self.supports_bookshelves:
                return bookshelves

            cursor = connection.cursor()
            query = "select ShelfName "         \
                    "from ShelfContent "        \
                    "where ContentId = ? "      \
                    "and _IsDeleted = 'false' " \
                    "and ShelfName is not null"         # This should never be nulll, but it is protection against an error cause by a sync to the Kobo server
            values = (ContentID, )
            cursor.execute(query, values)
            for i, row in enumerate(cursor):
                bookshelves.append(row[0])

            cursor.close()
#            debug_print("KoboTouch:get_bookshelvesforbook - count bookshelves=" + unicode(count_bookshelves))
            return bookshelves

        self.debug_index = 0

        with closing(self.device_database_connection()) as connection:
            debug_print("KoboTouch:books - reading device database")

            self.dbversion = self.get_database_version(connection)
            debug_print("Database Version: ", self.dbversion)

            cursor = connection.cursor()

            self.bookshelvelist = self.get_bookshelflist(connection)
            debug_print("KoboTouch:books - shelf list:", self.bookshelvelist)

            columns = 'Title, Attribution, DateCreated, ContentID, MimeType, ContentType, ImageID, ReadStatus'
            if self.dbversion >= 16:
                columns += ', ___ExpirationStatus, FavouritesIndex, Accessibility'
            else:
                columns += ', -1 as ___ExpirationStatus, -1 as FavouritesIndex, -1 as Accessibility'
            if self.dbversion >= 33:
                columns += ', IsDownloaded'
            else:
                columns += ', "1" as IsDownloaded'
            if self.supports_series():
                columns += ", Series, SeriesNumber, ___UserID, ExternalId"
            else:
                columns += ', null as Series, null as SeriesNumber, ___UserID, null as ExternalId'

            where_clause = ''
            if self.supports_kobo_archive() or self.supports_overdrive():
                where_clause = (" WHERE BookID IS NULL "
                        " AND ((Accessibility = -1 AND IsDownloaded in ('true', 1 )) "              # Sideloaded books
                        "      OR (Accessibility IN (%(downloaded_accessibility)s) %(expiry)s) "    # Purchased books
                        "      %(previews)s %(recomendations)s ) "                                  # Previews or Recommendations
                    ) % \
                    dict(
                         expiry="" if self.show_archived_books else "and IsDownloaded in ('true', 1)",
                         previews=" OR (Accessibility in (6) AND ___UserID <> '')" if self.show_previews else "",
                         recomendations=" OR (Accessibility IN (-1, 4, 6) AND ___UserId = '')" if self.show_recommendations else "",
                         downloaded_accessibility="1,2,9" if self.supports_overdrive() else "1,2"
                         )
            elif self.supports_series():
                where_clause = (" WHERE BookID IS NULL "
                    " AND ((Accessibility = -1 AND IsDownloaded IN ('true', 1)) or (Accessibility IN (1,2)) %(previews)s %(recomendations)s )"
                    " AND NOT ((___ExpirationStatus=3 OR ___ExpirationStatus is Null) %(expiry)s)"
                    ) % \
                    dict(
                         expiry=" AND ContentType = 6" if self.show_archived_books else "",
                         previews=" or (Accessibility IN (6) AND ___UserID <> '')" if self.show_previews else "",
                         recomendations=" or (Accessibility in (-1, 4, 6) AND ___UserId = '')" if self.show_recommendations else ""
                         )
            elif self.dbversion >= 33:
                where_clause = (' WHERE BookID IS NULL %(previews)s %(recomendations)s AND NOT'
                    ' ((___ExpirationStatus=3 or ___ExpirationStatus IS NULL) %(expiry)s)'
                    ) % \
                    dict(
                         expiry=' AND ContentType = 6' if self.show_archived_books else '',
                         previews=' AND Accessibility <> 6' if not self.show_previews else '',
                         recomendations=' AND IsDownloaded IN (\'true\', 1)' if not self.show_recommendations else ''
                         )
            elif self.dbversion >= 16:
                where_clause = (' WHERE BookID IS NULL '
                    'AND NOT ((___ExpirationStatus=3 OR ___ExpirationStatus IS Null) %(expiry)s)'
                    ) % \
                    dict(expiry=' and ContentType = 6' if self.show_archived_books else '')
            else:
                where_clause = ' WHERE BookID IS NULL'

            # Note: The card condition should not need the contentId test for the SD
            # card. But the ExternalId does not get set for sideloaded kepubs on the
            # SD card.
            card_condition = ''
            if self.has_externalid():
                card_condition = " AND (externalId IS NOT NULL AND externalId <> '' OR contentId LIKE 'file:///mnt/sd/%')" if oncard == 'carda' else (
                    " AND (externalId IS NULL OR externalId = '') AND contentId NOT LIKE 'file:///mnt/sd/%'")
            else:
                card_condition = " AND contentId LIKE 'file:///mnt/sd/%'" if oncard == 'carda' else " AND contentId NOT LIKE'file:///mnt/sd/%'"

            query = 'SELECT ' + columns + ' FROM content ' + where_clause + card_condition
            debug_print("KoboTouch:books - query=", query)
            try:
                cursor.execute(query)
            except Exception as e:
                err = str(e)
                if not ('___ExpirationStatus' in err or
                        'FavouritesIndex' in err or
                        'Accessibility' in err or
                        'IsDownloaded' in err or
                        'Series' in err or
                        'ExternalId' in err
                        ):
                    raise
                query= ('SELECT Title, Attribution, DateCreated, ContentID, MimeType, ContentType, '
                        'ImageID, ReadStatus, -1 AS ___ExpirationStatus, "-1" AS '
                        'FavouritesIndex, -1 AS Accessibility, 1 AS IsDownloaded, NULL AS Series, NULL AS SeriesNumber '
                        'FROM content '
                        'WHERE BookID IS NULL'
                        )
                cursor.execute(query)

            changed = False
            for i, row in enumerate(cursor):
                #  self.report_progress((i+1) / float(numrows), _('Getting list of books on device...'))
                show_debug = self.is_debugging_title(row[0])
                if show_debug:
                    debug_print("KoboTouch:books - looping on database - row=%d" % i)
                    debug_print("KoboTouch:books - title='%s'"%row[0], "authors=", row[1])
                    debug_print("KoboTouch:books - row=", row)
                if not hasattr(row[3], 'startswith') or row[3].lower().startswith(
                        "file:///usr/local/kobo/help/") or row[3].lower().startswith("/usr/local/kobo/help/"):
                    # These are internal to the Kobo device and do not exist
                    continue
                externalId = None if row[15] and len(row[15]) == 0 else row[15]
                path = self.path_from_contentid(row[3], row[5], row[4], oncard, externalId)
                mime = mime_type_ext(path_to_ext(path)) if path.find('kepub') == -1 else 'application/x-kobo-epub+zip'
                # debug_print("mime:", mime)
                if show_debug:
                    debug_print("KoboTouch:books - path='%s'"%path, "  ContentID='%s'"%row[3], " externalId=%s" % externalId)

                bookshelves = get_bookshelvesforbook(connection, row[3])

                prefix = self._card_a_prefix if oncard == 'carda' else self._main_prefix
                changed = update_booklist(prefix, path, row[0], row[1], mime, row[2], row[3], row[5],
                                          row[6], row[7], row[4], row[8], int(row[9]), row[10], row[11],
                                          row[12], row[13], row[14], bookshelves)

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
                if not os.path.exists(self.normalize_path(os.path.join(prefix, bl[idx].lpath))) or not bl[idx].contentID:
                    need_sync = True
                    del bl[idx]
                else:
                    debug_print("KoboTouch:books - Book in mtadata.calibre, on file system but not database - bl[idx].title:'%s'"%bl[idx].title)

        # print "count found in cache: %d, count of files in metadata: %d, need_sync: %s" % \
        #      (len(bl_cache), len(bl), need_sync)
        # Bypassing the KOBO sync_booklists as that does things we don't need to do
        # Also forcing sync to see if this solves issues with updating shelves and matching books.
        if need_sync or True:  # self.count_found_in_bl != len(bl) or need_sync:
            debug_print("KoboTouch:books - about to sync_booklists")
            if oncard == 'cardb':
                USBMS.sync_booklists(self, (None, None, bl))
            elif oncard == 'carda':
                USBMS.sync_booklists(self, (None, bl, None))
            else:
                USBMS.sync_booklists(self, (bl, None, None))
            debug_print("KoboTouch:books - have done sync_booklists")

        self.report_progress(1.0, _('Getting list of books on device...'))
        debug_print("KoboTouch:books - end - oncard='%s'"%oncard)
        return bl

    def path_from_contentid(self, ContentID, ContentType, MimeType, oncard, externalId):
        path = ContentID

        if not externalId:
            return super(KOBOTOUCH, self).path_from_contentid(ContentID, ContentType, MimeType, oncard)

        if oncard == 'cardb':
            print 'path from_contentid cardb'
        else:
            if (ContentType == "6" or ContentType == "10"):  # and MimeType == 'application/x-kobo-epub+zip':
                if path.startswith("file:///mnt/onboard/"):
                    path = self._main_prefix + path.replace("file:///mnt/onboard/", '')
                elif path.startswith("file:///mnt/sd/"):
                    path = self._card_a_prefix + path.replace("file:///mnt/sd/", '')
                elif externalId:
                    path = self._card_a_prefix + 'koboExtStorage/kepub/' + path
                else:
                    path = self._main_prefix + '.kobo/kepub/' + path
            else:   # Should never get here, but, just in case...
                # if path.startswith("file:///mnt/onboard/"):
                path = path.replace("file:///mnt/onboard/", self._main_prefix)
                path = path.replace("file:///mnt/sd/", self._card_a_prefix)
                path = path.replace("/mnt/onboard/", self._main_prefix)
                # print "Internal: " + path

        return path

    def imagefilename_from_imageID(self, prefix, ImageID):
        show_debug = self.is_debugging_title(ImageID)

        if len(ImageID) > 0:
            path = self.images_path(prefix, ImageID)

            for ending in self.cover_file_endings().keys():
                fpath = path + ending
                if os.path.exists(fpath):
                    if show_debug:
                        debug_print("KoboTouch:imagefilename_from_imageID - have cover image fpath=%s" % (fpath))
                    return fpath

            if show_debug:
                debug_print("KoboTouch:imagefilename_from_imageID - no cover image found - ImageID=%s" % (ImageID))
        return None

    def get_extra_css(self):
        extra_sheet = None
        from cssutils.css import CSSRule

        if self.modifying_css():
            extra_css_path = os.path.join(self._main_prefix, self.KOBO_EXTRA_CSSFILE)
            if os.path.exists(extra_css_path):
                from cssutils import parseFile as cssparseFile
                try:
                    extra_sheet = cssparseFile(extra_css_path)
                    debug_print("KoboTouch:get_extra_css: Using extra CSS in {0} ({1} rules)".format(extra_css_path, len(extra_sheet.cssRules)))
                    if len(extra_sheet.cssRules) ==0:
                        debug_print("KoboTouch:get_extra_css: Extra CSS file has no valid rules. CSS will not be modified.")
                        extra_sheet = None
                except Exception as e:
                    debug_print("KoboTouch:get_extra_css: Problem parsing extra CSS file {0}".format(extra_css_path))
                    debug_print("KoboTouch:get_extra_css: Exception {0}".format(e))

        # create dictionary of features enabled in kobo extra css
        self.extra_css_options = {}
        if extra_sheet:
            # search extra_css for @page rule
            self.extra_css_options['has_atpage'] = len(self.get_extra_css_rules(extra_sheet, CSSRule.PAGE_RULE)) > 0

            # search extra_css for style rule(s) containing widows or orphans
            self.extra_css_options['has_widows_orphans'] = len(self.get_extra_css_rules_widow_orphan(extra_sheet)) > 0
            debug_print('KoboTouch:get_extra_css - CSS options:', self.extra_css_options)

        return extra_sheet

    def get_extra_css_rules(self, sheet, css_rule):
        return [r for r in sheet.cssRules.rulesOfType(css_rule)]

    def get_extra_css_rules_widow_orphan(self, sheet):
        from cssutils.css import CSSRule
        return [r for r in self.get_extra_css_rules(sheet, CSSRule.STYLE_RULE)
                    if (r.style['widows'] or r.style['orphans'])]

    def upload_books(self, files, names, on_card=None, end_session=True,
                     metadata=None):
        debug_print('KoboTouch:upload_books - %d books'%(len(files)))
        debug_print('KoboTouch:upload_books - files=', files)

        if self.modifying_epub():
            self.extra_sheet = self.get_extra_css()
            i = 0
            for file, n, mi in zip(files, names, metadata):
                debug_print("KoboTouch:upload_books: Processing book: {0} by {1}".format(mi.title, " and ".join(mi.authors)))
                debug_print("KoboTouch:upload_books: file=%s, name=%s" % (file, n))
                self.report_progress(i / float(len(files)), "Processing book: {0} by {1}".format(mi.title, " and ".join(mi.authors)))
                mi.kte_calibre_name = n
                self._modify_epub(file, mi)
                i += 1

        self.report_progress(0, 'Working...')

        result = super(KOBOTOUCH, self).upload_books(files, names, on_card, end_session, metadata)
#        debug_print('KoboTouch:upload_books - result=', result)

        if self.dbversion >= 53:
            try:
                with closing(self.device_database_connection()) as connection:
                    cursor = connection.cursor()
                    cleanup_query = "DELETE FROM content WHERE ContentID = ? AND Accessibility = 1 AND IsDownloaded = 'false'"

                    for fname, cycle in result:
                        show_debug = self.is_debugging_title(fname)
                        contentID = self.contentid_from_path(fname, 6)
                        if show_debug:
                            debug_print('KoboTouch:upload_books: fname=', fname)
                            debug_print('KoboTouch:upload_books: contentID=', contentID)

                        cleanup_values = (contentID,)
#                        debug_print('KoboTouch:upload_books: Delete record left if deleted on Touch')
                        cursor.execute(cleanup_query, cleanup_values)

                        self.set_filesize_in_device_database(connection, contentID, fname)

                        if not self.upload_covers:
                            imageID = self.imageid_from_contentid(contentID)
                            self.delete_images(imageID, fname)

                    cursor.close()
            except Exception as e:
                debug_print('KoboTouch:upload_books - Exception:  %s'%str(e))

        return result

    def _modify_epub(self, book_file, metadata, container=None):
        debug_print("KoboTouch:_modify_epub:Processing {0} - {1}".format(metadata.author_sort, metadata.title))

        # Currently only modifying CSS, so if no stylesheet, don't do anything
        if not self.extra_sheet:
            debug_print("KoboTouch:_modify_epub: no CSS file")
            return True

        container, commit_container = self.create_container(book_file, metadata, container)
        if not container:
            return False

        from calibre.ebooks.oeb.base import OEB_STYLES

        is_dirty = False
        for cssname, mt in container.mime_map.iteritems():
            if mt in OEB_STYLES:
                newsheet = container.parsed(cssname)
                oldrules = len(newsheet.cssRules)

                # future css mods may be epub/kepub specific, so pass file extension arg
                fileext = os.path.splitext(book_file)[-1].lower()
                debug_print("KoboTouch:_modify_epub: Modifying {0}".format(cssname))
                if self._modify_stylesheet(newsheet, fileext):
                    debug_print("KoboTouch:_modify_epub:CSS rules {0} -> {1} ({2})".format(oldrules, len(newsheet.cssRules), cssname))
                    container.dirty(cssname)
                    is_dirty = True

        if commit_container:
            debug_print("KoboTouch:_modify_epub: committing container.")
            self.commit_container(container, is_dirty)

        return True

    def _modify_stylesheet(self, sheet, fileext, is_dirty=False):
        from cssutils.css import CSSRule

        # if fileext in (EPUB_EXT, KEPUB_EXT):

        # if kobo extra css contains a @page rule
        # remove any existing @page rules in epub css
        if self.extra_css_options.get('has_atpage', False):
            page_rules = self.get_extra_css_rules(sheet, CSSRule.PAGE_RULE)
            if len(page_rules) > 0:
                debug_print("KoboTouch:_modify_stylesheet: Removing existing @page rules")
                for rule in page_rules:
                    rule.style = ''
                is_dirty = True

        # if kobo extra css contains any widow/orphan style rules
        # remove any existing widow/orphan settings in epub css
        if self.extra_css_options.get('has_widows_orphans', False):
            widow_orphan_rules = self.get_extra_css_rules_widow_orphan(sheet)
            if len(widow_orphan_rules) > 0:
                debug_print("KoboTouch:_modify_stylesheet: Removing existing widows/orphans attribs")
                for rule in widow_orphan_rules:
                    rule.style.removeProperty('widows')
                    rule.style.removeProperty('orphans')
                is_dirty = True

        # append all rules from kobo extra css
        debug_print("KoboTouch:_modify_stylesheet: Append all kobo extra css rules")
        for extra_rule in self.extra_sheet.cssRules:
            sheet.insertRule(extra_rule)
            is_dirty = True

        return is_dirty

    def create_container(self, book_file, metadata, container=None):
        # create new container if not received, else pass through
        if not container:
            commit_container = True
            try:
                from calibre.ebooks.oeb.polish.container import get_container
                debug_print("KoboTouch:create_container: try to create new container")
                container = get_container(book_file)
                container.css_preprocessor = DummyCSSPreProcessor()
            except Exception as e:
                debug_print("KoboTouch:create_container: exception from get_container {0} - {1}".format(metadata.author_sort, metadata.title))
                debug_print("KoboTouch:create_container: exception is: {0}".format(e))
        else:
            commit_container = False
            debug_print("KoboTouch:create_container: received container")
        return container, commit_container

    def commit_container(self, container, is_dirty=True):
        # commit container if changes have been made
        if is_dirty:
            debug_print("KoboTouch:commit_container: commit container.")
            container.commit()

        # Clean-up-AYGO prevents build-up of TEMP exploded epub/kepub files
        debug_print("KoboTouch:commit_container: removing container temp files.")
        try:
            shutil.rmtree(container.root)
        except:
            pass

    def delete_via_sql(self, ContentID, ContentType):
        imageId = super(KOBOTOUCH, self).delete_via_sql(ContentID, ContentType)

        if self.dbversion >= 53:
            debug_print('KoboTouch:delete_via_sql: ContentID="%s"'%ContentID, 'ContentType="%s"'%ContentType)
            try:
                with closing(self.device_database_connection()) as connection:
                    debug_print('KoboTouch:delete_via_sql: have database connection')

                    cursor = connection.cursor()
                    debug_print('KoboTouch:delete_via_sql: have cursor')
                    t = (ContentID,)

                    # Delete the Bookmarks
                    debug_print('KoboTouch:delete_via_sql: Delete from Bookmark')
                    cursor.execute('DELETE FROM Bookmark WHERE VolumeID  = ?', t)

                    # Delete from the Bookshelf
                    debug_print('KoboTouch:delete_via_sql: Delete from the Bookshelf')
                    cursor.execute('delete from ShelfContent where ContentID = ?', t)

                    # ContentType 6 is now for all books.
                    debug_print('KoboTouch:delete_via_sql: BookID is Null')
                    cursor.execute('delete from content where BookID is Null and ContentID =?',t)

                    # Remove the content_settings entry
                    debug_print('KoboTouch:delete_via_sql: delete from content_settings')
                    cursor.execute('delete from content_settings where ContentID =?',t)

                    # Remove the ratings entry
                    debug_print('KoboTouch:delete_via_sql: delete from ratings')
                    cursor.execute('delete from ratings where ContentID =?',t)

                    # Remove any entries for the Activity table - removes tile from new home page
                    if self.has_activity_table():
                        debug_print('KoboTouch:delete_via_sql: delete from Activity')
                        cursor.execute('delete from Activity where Id =?', t)

                    cursor.close()
                    debug_print('KoboTouch:delete_via_sql: finished SQL')
                debug_print('KoboTouch:delete_via_sql: After SQL, no exception')
            except Exception as e:
                debug_print('KoboTouch:delete_via_sql - Database Exception:  %s'%str(e))

        debug_print('KoboTouch:delete_via_sql: imageId="%s"'%imageId)
        if imageId is None:
            imageId = self.imageid_from_contentid(ContentID)

        return imageId

    def delete_images(self, ImageID, book_path):
        debug_print("KoboTouch:delete_images - ImageID=", ImageID)
        if ImageID is not None:
            path = self.images_path(book_path, ImageID)
            debug_print("KoboTouch:delete_images - path=%s" % path)

            for ending in self.cover_file_endings().keys():
                fpath = path + ending
                fpath = self.normalize_path(fpath)
                debug_print("KoboTouch:delete_images - fpath=%s" % fpath)

                if os.path.exists(fpath):
                    debug_print("KoboTouch:delete_images - Image File Exists")
                    os.unlink(fpath)

            try:
                os.removedirs(os.path.dirname(path))
            except:
                pass

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
        else:  # ContentType = 16
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
        if self.fwversion >= (1,9,17) or extension == '.kobo' or extension == '.mobi':
            debug_print("KoboTouch:get_content_type_from_extension - V2 firmware")
            ContentType = 6
        # For older firmware, it depends on the type of file.
        elif extension == '.kobo' or extension == '.mobi':
            ContentType = 6
        else:
            ContentType = 901
        return ContentType

    def update_device_database_collections(self, booklists, collections_attributes, oncard):
        debug_print("KoboTouch:update_device_database_collections - oncard='%s'"%oncard)
        if self.modify_database_check("update_device_database_collections") is False:
            return

        # Only process categories in this list
        supportedcategories = {
            "Im_Reading":   1,
            "Read":         2,
            "Closed":       3,
            "Shortlist":    4,
            "Archived":     5,
            }

        # Define lists for the ReadStatus
        readstatuslist = {
            "Im_Reading":1,
            "Read":2,
            "Closed":3,
            }

        accessibilitylist = {
            "Deleted":1,
            "OverDrive":9,
            "Preview":6,
            "Recommendation":4,
            }
#        debug_print('KoboTouch:update_device_database_collections - collections_attributes=', collections_attributes)

        create_collections       = self.create_collections
        delete_empty_collections = self.delete_empty_collections
        update_series_details   = self.update_series_details
        debugging_title         = self.get_debugging_title()
        debug_print("KoboTouch:update_device_database_collections - set_debugging_title to '%s'" % debugging_title)
        booklists.set_debugging_title(debugging_title)
        booklists.set_device_managed_collections(self.ignore_collections_names)

        bookshelf_attribute = len(collections_attributes) > 0

        collections = booklists.get_collections(collections_attributes) if bookshelf_attribute else None
#        debug_print('KoboTouch:update_device_database_collections - Collections:', collections)

        # Create a connection to the sqlite database
        # Needs to be outside books collection as in the case of removing
        # the last book from the collection the list of books is empty
        # and the removal of the last book would not occur

        with closing(self.device_database_connection()) as connection:

            if self.manage_collections:
                if collections:
                    # debug_print("KoboTouch:update_device_database_collections - length collections=" + unicode(len(collections)))

                    # Need to reset the collections outside the particular loops
                    # otherwise the last item will not be removed
                    if self.dbversion < 53:
                        debug_print("KoboTouch:update_device_database_collections - calling reset_readstatus")
                        self.reset_readstatus(connection, oncard)
                    if self.dbversion >= 14 and self.fwversion < self.min_fwversion_shelves:
                        debug_print("KoboTouch:update_device_database_collections - calling reset_favouritesindex")
                        self.reset_favouritesindex(connection, oncard)

#                     debug_print("KoboTouch:update_device_database_collections - length collections=", len(collections))
#                     debug_print("KoboTouch:update_device_database_collections - self.bookshelvelist=", self.bookshelvelist)
                    # Process any collections that exist
                    for category, books in collections.items():
                        debug_print("KoboTouch:update_device_database_collections - category='%s' books=%d"%(category, len(books)))
                        if create_collections and not (category in supportedcategories or category in readstatuslist or category in accessibilitylist):
                            self.check_for_bookshelf(connection, category)
#                         if category in self.bookshelvelist:
#                             debug_print("Category: ", category, " id = ", readstatuslist.get(category))
                        for book in books:
                            # debug_print('    Title:', book.title, 'category: ', category)
                            show_debug = self.is_debugging_title(book.title)
                            if show_debug:
                                debug_print('    Title="%s"'%book.title, 'category="%s"'%category)
#                                 debug_print(book)
                                debug_print('    class=%s'%book.__class__)
                                debug_print('    book.contentID="%s"'%book.contentID)
                                debug_print('    book.application_id="%s"'%book.application_id)

                            if book.application_id is None:
                                continue

                            category_added = False

                            if book.contentID is None:
                                debug_print('    Do not know ContentID - Title="%s"'%book.title)
                                extension =  os.path.splitext(book.path)[1]
                                ContentType = self.get_content_type_from_extension(extension) if extension != '' else self.get_content_type_from_path(book.path)
                                book.contentID = self.contentid_from_path(book.path, ContentType)

                            if category in self.ignore_collections_names:
                                debug_print('        Ignoring collection=%s' % category)
                                category_added = True
                            elif category in self.bookshelvelist and self.supports_bookshelves:
                                if show_debug:
                                    debug_print('        length book.device_collections=%d'%len(book.device_collections))
                                if category not in book.device_collections:
                                    if show_debug:
                                        debug_print('        Setting bookshelf on device')
                                    self.set_bookshelf(connection, book, category)
                                    category_added = True
                            elif category in readstatuslist.keys():
                                debug_print("KoboTouch:update_device_database_collections - about to set_readstatus - category='%s'"%(category, ))
                                # Manage ReadStatus
                                self.set_readstatus(connection, book.contentID, readstatuslist.get(category))
                                category_added = True

                            elif category == 'Shortlist' and self.dbversion >= 14:
                                if show_debug:
                                    debug_print('        Have an older version shortlist - %s'%book.title)
                                # Manage FavouritesIndex/Shortlist
                                if not self.supports_bookshelves:
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

                elif bookshelf_attribute:  # No collections but have set the shelf option
                    # Since no collections exist the ReadStatus needs to be reset to 0 (Unread)
                    debug_print("No Collections - reseting ReadStatus")
                    if self.dbversion < 53:
                        self.reset_readstatus(connection, oncard)
                    if self.dbversion >= 14 and self.fwversion < self.min_fwversion_shelves:
                        debug_print("No Collections - resetting FavouritesIndex")
                        self.reset_favouritesindex(connection, oncard)

            # Set the series info and cleanup the bookshelves only if the firmware supports them and the user has set the options.
            if (self.supports_bookshelves and self.manage_collections or self.supports_series()) and (bookshelf_attribute or update_series_details):
                debug_print("KoboTouch:update_device_database_collections - managing bookshelves and series.")

                self.series_set  = 0
                books_in_library = 0
                for book in booklists:
                    if book.application_id is not None:
                        books_in_library += 1
                        show_debug = self.is_debugging_title(book.title)
                        if show_debug:
                            debug_print("KoboTouch:update_device_database_collections - book.title=%s" % book.title)
                        if update_series_details:
                            self.set_series(connection, book)
                        if self.manage_collections and bookshelf_attribute:
                            if show_debug:
                                debug_print("KoboTouch:update_device_database_collections - about to remove a book from shelves book.title=%s" % book.title)
                            self.remove_book_from_device_bookshelves(connection, book)
                            book.device_collections.extend(book.kobo_collections)
                if not prefs['manage_device_metadata'] == 'manual' and delete_empty_collections:
                    debug_print("KoboTouch:update_device_database_collections - about to clear empty bookshelves")
                    self.delete_empty_bookshelves(connection)
                debug_print("KoboTouch:update_device_database_collections - Number of series set=%d Number of books=%d" % (self.series_set, books_in_library))

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
        debug_print("KoboTouch:upload_cover - path='%s' filename='%s' "%(path, filename))
        debug_print("        filepath='%s' "%(filepath))

        if not self.upload_covers:
            # Building thumbnails disabled
            # debug_print('KoboTouch: not uploading cover')
            return

        # Only upload covers to SD card if that is supported
        if self._card_a_prefix and os.path.abspath(path).startswith(os.path.abspath(self._card_a_prefix)) and not self.supports_covers_on_sdcard():
            return

#        debug_print('KoboTouch: uploading cover')
        try:
            self._upload_cover(path, filename, metadata, filepath, self.upload_grayscale, self.keep_cover_aspect)
        except Exception as e:
            debug_print('KoboTouch: FAILED to upload cover=%s Exception=%s'%(filepath, str(e)))

    def imageid_from_contentid(self, ContentID):
        ImageID = ContentID.replace('/', '_')
        ImageID = ImageID.replace(' ', '_')
        ImageID = ImageID.replace(':', '_')
        ImageID = ImageID.replace('.', '_')
        return ImageID

    def images_path(self, path, imageId=None):
        if self._card_a_prefix and os.path.abspath(path).startswith(os.path.abspath(self._card_a_prefix)) and self.supports_covers_on_sdcard():
            path_prefix = 'koboExtStorage/images-cache/' if self.supports_images_tree() else 'koboExtStorage/images/'
            path = os.path.join(self._card_a_prefix, path_prefix)
        else:
            path_prefix = '.kobo-images/' if self.supports_images_tree() else '.kobo/images/'
            path = os.path.join(self._main_prefix, path_prefix)

        if self.supports_images_tree() and imageId:
            hash1 = qhash(imageId)
            dir1  = hash1 & (0xff * 1)
            dir2  = (hash1 & (0xff00 * 1)) >> 8
            path = os.path.join(path, "%s" % dir1, "%s" % dir2)

        if imageId:
            path = os.path.join(path, imageId)
        return path

    def _calculate_kobo_cover_size(self, library_size, kobo_size, keep_cover_aspect, is_full_size):
        if keep_cover_aspect:
            library_aspect = library_size[0] / library_size[1]
            kobo_aspect = kobo_size[0] / kobo_size[1]
            if library_aspect > kobo_aspect:
                kobo_size = (kobo_size[0], int(kobo_size[0] / library_aspect))
            else:
                kobo_size = (int(library_aspect * kobo_size[1]), kobo_size[1])
        return kobo_size

    def _create_cover_data(self, cover_data, resize_to, kobo_size, upload_grayscale=False, keep_cover_aspect=False, is_full_size=False):
        '''
        This will generate the new cover image from the cover in the library. It is a wrapper
        for save_cover_data_to to allow it to be overriden in a subclass. For this reason,
        options are passed in that are not used by this implementation.

        :param cover_data:    original cover data
        :param resize_to:     Size to resize the cover to (width, height). None means do not resize.
        :param kobo_size:     Size of the cover image on the device.
        :param upload_grayscale: boolean True if driver configured to send grayscale thumbnails
                        Passed to allow ability to decide to quantize to 16-col grayscale
                        at calibre end
        :param keep_cover_aspect: bookean - True if the aspect ratio of the cover in the library is to be kept.
        :param is_full_size:  True if this is the kobo_size is for the full size cover image
                        Passed to allow ability to process screensaver differently
                        to smaller thumbnails
        '''

        from calibre.utils.img import save_cover_data_to
        data = save_cover_data_to(cover_data, grayscale=upload_grayscale, resize_to=resize_to)
        return data

    def _upload_cover(self, path, filename, metadata, filepath, upload_grayscale, keep_cover_aspect=False):
        from calibre.utils.imghdr import identify
        debug_print("KoboTouch:_upload_cover - filename='%s' upload_grayscale='%s' "%(filename, upload_grayscale))

        if not metadata.cover:
            return

        show_debug = self.is_debugging_title(filename)
        if show_debug:
            debug_print("KoboTouch:_upload_cover - path='%s'"%path, "filename='%s'"%filename)
            debug_print("        filepath='%s'"%filepath)
        cover = self.normalize_path(metadata.cover.replace('/', os.sep))

        if not os.path.exists(cover):
            debug_print("KoboTouch:_upload_cover - Cover file does not exist in library")
            return

        # Get ContentID for Selected Book
        extension =  os.path.splitext(filepath)[1]
        ContentType = self.get_content_type_from_extension(extension) if extension != '' else self.get_content_type_from_path(filepath)
        ContentID = self.contentid_from_path(filepath, ContentType)

        try:
            with closing(self.device_database_connection()) as connection:

                cursor = connection.cursor()
                t = (ContentID,)
                cursor.execute('select ImageId from Content where BookID is Null and ContentID = ?', t)
                try:
                    result = cursor.next()
                    ImageID = result[0]
                except StopIteration:
                    ImageID = self.imageid_from_contentid(ContentID)
                    debug_print("KoboTouch:_upload_cover - No rows exist in the database - generated ImageID='%s'" % ImageID)

                cursor.close()

            if ImageID is not None:
                path = self.images_path(path, ImageID)

                if show_debug:
                    debug_print("KoboTouch:_upload_cover - About to loop over cover endings")

                image_dir = os.path.dirname(os.path.abspath(path))
                if not os.path.exists(image_dir):
                    debug_print("KoboTouch:_upload_cover - Image directory does not exust. Creating path='%s'" % (image_dir))
                    os.makedirs(image_dir)

                with lopen(cover, 'rb') as f:
                    cover_data = f.read()

                fmt, width, height = identify(cover_data)
                library_cover_size = (width, height)

                for ending, cover_options in self.cover_file_endings().items():
                    kobo_size, min_dbversion, max_dbversion, is_full_size = cover_options
                    if show_debug:
                        debug_print("KoboTouch:_upload_cover - library_cover_size=%s min_dbversion=%d max_dbversion=%d" % (
                            library_cover_size, min_dbversion, max_dbversion))
                    if self.dbversion >= min_dbversion and self.dbversion <= max_dbversion:
                        if show_debug:
                            debug_print("KoboTouch:_upload_cover - creating cover for ending='%s'"%ending)  # , "library_cover_size'%s'"%library_cover_size)
                        fpath = path + ending
                        fpath = self.normalize_path(fpath.replace('/', os.sep))

                        resize_to = self._calculate_kobo_cover_size(library_cover_size, kobo_size, keep_cover_aspect, is_full_size)

                        # Return the data resized and in Grayscale if required
                        data = self._create_cover_data(cover_data, resize_to, kobo_size, upload_grayscale, keep_cover_aspect, is_full_size)

                        with lopen(fpath, 'wb') as f:
                            f.write(data)
                            fsync(f)
        except Exception as e:
            err = str(e)
            debug_print("KoboTouch:_upload_cover - Exception string: %s"%err)
            raise

    def remove_book_from_device_bookshelves(self, connection, book):
        show_debug = self.is_debugging_title(book.title)  # or True

        remove_shelf_list = set(book.current_shelves) - set(book.device_collections)
        remove_shelf_list = remove_shelf_list - set(self.ignore_collections_names)

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
        cursor.close()

    def set_filesize_in_device_database(self, connection, contentID, fpath):
        show_debug = self.is_debugging_title(fpath)
        if show_debug:
            debug_print('KoboTouch:set_filesize_in_device_database contentID="%s"'%contentID)

        test_query = 'SELECT ___FileSize '     \
                        'FROM content '        \
                        'WHERE ContentID = ? ' \
                        ' AND ContentType = 6'
        test_values = (contentID, )

        updatequery = 'UPDATE content '         \
                        'SET ___FileSize = ? '  \
                        'WHERE ContentId = ? '  \
                        'AND ContentType = 6'

        cursor = connection.cursor()
        cursor.execute(test_query, test_values)
        try:
            result = cursor.next()
        except StopIteration:
            result = None

        if result is None:
            if show_debug:
                debug_print('        Did not find a record - new book on device')
        elif os.path.exists(fpath):
            file_size = os.stat(self.normalize_path(fpath)).st_size
            if show_debug:
                debug_print('        Found a record - will update - ___FileSize=', result[0], ' file_size=', file_size)
            if file_size != int(result[0]):
                update_values = (file_size, contentID, )
                cursor.execute(updatequery, update_values)
                if show_debug:
                    debug_print('        Size updated.')

        cursor.close()

#        debug_print("KoboTouch:set_filesize_in_device_database - end")

    def delete_empty_bookshelves(self, connection):
        debug_print("KoboTouch:delete_empty_bookshelves - start")

        ignore_collections_in = ''
        if self.ignore_collections_names:
            ignore_collections_in = ','.join(["'%s'" % collections_name for collections_name in self.ignore_collections_names])
            ignore_collections_in = ', %s' % ignore_collections_in

        delete_query = ("DELETE FROM Shelf "
                        "WHERE Shelf._IsSynced = 'false' "
                        "AND Shelf.InternalName not in ('Shortlist', 'Wishlist'" + ignore_collections_in + ") "
                        "AND (Type IS NULL OR Type <> 'SystemTag') "    # Collections are created with Type of NULL and change after a sync.
                        "AND NOT EXISTS "
                        "(SELECT 1 FROM ShelfContent c "
                        "WHERE Shelf.Name = C.ShelfName "
                        "AND c._IsDeleted <> 'true')")

        update_query = ("UPDATE Shelf "
                        "SET _IsDeleted = 'true' "
                        "WHERE Shelf._IsSynced = 'true' "
                        "AND Shelf.InternalName not in ('Shortlist', 'Wishlist'" + ignore_collections_in + ") "
                        "AND (Type IS NULL OR Type <> 'SystemTag') "
                        "AND NOT EXISTS "
                        "(SELECT 1 FROM ShelfContent C "
                        "WHERE Shelf.Name = C.ShelfName "
                        "AND c._IsDeleted <> 'true')")

        delete_activity_query = ("DELETE FROM Activity "
                                 "WHERE Type = 'Shelf' "
                                 "AND NOT EXISTS "
                                    "(SELECT 1 FROM Shelf "
                                    "WHERE Shelf.Name = Activity.Id "
                                    "AND Shelf._IsDeleted = 'false')"
                                 )

        cursor = connection.cursor()
        cursor.execute(delete_query)
        cursor.execute(update_query)
        if self.has_activity_table():
            cursor.execute(delete_activity_query)
        cursor.close()

        debug_print("KoboTouch:delete_empty_bookshelves - end")

    def get_bookshelflist(self, connection):
        # Retrieve the list of booksehelves
        #        debug_print('KoboTouch:get_bookshelflist')
        bookshelves = []

        if not self.supports_bookshelves:
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

    def set_bookshelf(self, connection, book, shelfName):
        show_debug = self.is_debugging_title(book.title)
        if show_debug:
            debug_print('KoboTouch:set_bookshelf book.ContentID="%s"'%book.contentID)
            debug_print('KoboTouch:set_bookshelf book.current_shelves="%s"'%book.current_shelves)

        if shelfName in book.current_shelves:
            if show_debug:
                debug_print('        book already on shelf.')
            return

        test_query = 'SELECT _IsDeleted FROM ShelfContent WHERE ShelfName = ? and ContentId = ?'
        test_values = (shelfName, book.contentID, )
        addquery = 'INSERT INTO ShelfContent ("ShelfName","ContentId","DateModified","_IsDeleted","_IsSynced") VALUES (?, ?, ?, "false", "false")'
        add_values = (shelfName, book.contentID, time.strftime(self.TIMESTAMP_STRING, time.gmtime()), )
        updatequery = 'UPDATE ShelfContent SET _IsDeleted = "false" WHERE ShelfName = ? and ContentId = ?'
        update_values = (shelfName, book.contentID, )

        cursor = connection.cursor()
        cursor.execute(test_query, test_values)
        try:
            result = cursor.next()
        except StopIteration:
            result = None

        if result is None:
            if show_debug:
                debug_print('        Did not find a record - adding')
            cursor.execute(addquery, add_values)
        elif result[0] == 'true':
            if show_debug:
                debug_print('        Found a record - updating - result=', result)
            cursor.execute(updatequery, update_values)

        cursor.close()

#        debug_print("KoboTouch:set_bookshelf - end")

    def check_for_bookshelf(self, connection, bookshelf_name):
        show_debug = self.is_debugging_title(bookshelf_name)
        if show_debug:
            debug_print('KoboTouch:check_for_bookshelf bookshelf_name="%s"'%bookshelf_name)
        test_query = 'SELECT InternalName, Name, _IsDeleted FROM Shelf WHERE Name = ?'
        test_values = (bookshelf_name, )
        addquery = 'INSERT INTO "main"."Shelf"'
        add_values = (time.strftime(self.TIMESTAMP_STRING, time.gmtime()),
                      bookshelf_name,
                      time.strftime(self.TIMESTAMP_STRING, time.gmtime()),
                      bookshelf_name,
                      "false",
                      "true",
                      "false",
                      )
        shelf_type = "UserTag"  # if self.supports_reading_list else None
        if self.dbversion < 64:
            addquery += ' ("CreationDate","InternalName","LastModified","Name","_IsDeleted","_IsVisible","_IsSynced")'\
                        ' VALUES (?, ?, ?, ?, ?, ?, ?)'
        else:
            addquery += ' ("CreationDate", "InternalName","LastModified","Name","_IsDeleted","_IsVisible","_IsSynced", "Id", "Type")'\
                        ' VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)'
            add_values = add_values +(bookshelf_name, shelf_type)

        if show_debug:
            debug_print('KoboTouch:check_for_bookshelf addquery=', addquery)
            debug_print('KoboTouch:check_for_bookshelf add_values=', add_values)
        updatequery = 'UPDATE Shelf SET _IsDeleted = "false" WHERE Name = ?'

        cursor = connection.cursor()
        cursor.execute(test_query, test_values)
        try:
            result = cursor.next()
        except StopIteration:
            result = None

        if result is None:
            if show_debug:
                debug_print('        Did not find a record - adding shelf "%s"' % bookshelf_name)
            cursor.execute(addquery, add_values)
        elif result[2] == 'true':
            debug_print('KoboTouch:check_for_bookshelf - Shelf "%s" is deleted - undeleting. result[2]="%s"' % (bookshelf_name, unicode(result[2])))
            cursor.execute(updatequery, test_values)

        cursor.close()

        # Update the bookshelf list.
        self.bookshelvelist = self.get_bookshelflist(connection)

#        debug_print("KoboTouch:set_bookshelf - end")

    def remove_from_bookshelves(self, connection, oncard, ContentID=None, bookshelves=None):
        debug_print('KoboTouch:remove_from_bookshelf ContentID=', ContentID)
        if not self.supports_bookshelves:
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
        cursor.close()

        debug_print("KoboTouch:remove_from_bookshelf - end")

    def set_series(self, connection, book):
        show_debug = self.is_debugging_title(book.title)
        if show_debug:
            debug_print('KoboTouch:set_series book.kobo_series="%s"'%book.kobo_series)
            debug_print('KoboTouch:set_series book.series="%s"'%book.series)
            debug_print('KoboTouch:set_series book.series_index=', book.series_index)

        if book.series == book.kobo_series:
            kobo_series_number = None
            if book.kobo_series_number is not None:
                try:
                    kobo_series_number = float(book.kobo_series_number)
                except:
                    kobo_series_number = None
            if kobo_series_number == book.series_index:
                if show_debug:
                    debug_print('KoboTouch:set_series - series info the same - not changing')
                return

        update_query = 'UPDATE content SET Series=?, SeriesNumber==? where BookID is Null and ContentID = ?'
        if book.series is None:
            update_values = (None, None, book.contentID, )
        elif book.series_index is None:         # This should never happen, but...
            update_values = (book.series, None, book.contentID, )
        else:
            update_values = (book.series, "%g"%book.series_index, book.contentID, )

        cursor = connection.cursor()
        try:
            if show_debug:
                debug_print('KoboTouch:set_series - about to set - parameters:', update_values)
            cursor.execute(update_query, update_values)
            self.series_set += 1
        except:
            debug_print('    Database Exception:  Unable to set series info')
            raise
        finally:
            cursor.close()

        if show_debug:
            debug_print("KoboTouch:set_series - end")

    @classmethod
    def config_widget(cls):
        # TODO: Cleanup the following
        cls.current_friendly_name = cls.gui_name

        from calibre.devices.kobo.kobotouch_config import KOBOTOUCHConfig
        return KOBOTOUCHConfig(cls.settings(), cls.FORMATS,
                               cls.SUPPORTS_SUB_DIRS, cls.MUST_READ_METADATA,
                               cls.SUPPORTS_USE_AUTHOR_SORT, cls.EXTRA_CUSTOMIZATION_MESSAGE,
                               cls, extra_customization_choices=cls.EXTRA_CUSTOMIZATION_CHOICES
                               )

    @classmethod
    def get_pref(cls, key):
        ''' Get the setting named key. First looks for a device specific setting.
        If that is not found looks for a device default and if that is not
        found uses the global default.'''
#         debug_print("KoboTouch::get_prefs - key=", key, "cls=", cls)
        if not cls.opts:
            cls.opts = cls.settings()
        try:
            return getattr(cls.opts, key)
        except:
            debug_print("KoboTouch::get_prefs - probably an extra_customization:", key)
        return None

    @classmethod
    def save_settings(cls, config_widget):
        cls.opts = None
        config_widget.commit()

    @classmethod
    def save_template(cls):
        return cls.settings().save_template

    @classmethod
    def _config(cls):
        c = super(KOBOTOUCH, cls)._config()

        c.add_opt('manage_collections', default=True)
        c.add_opt('collections_columns', default='')
        c.add_opt('create_collections', default=False)
        c.add_opt('delete_empty_collections', default=False)
        c.add_opt('ignore_collections_names', default='')

        c.add_opt('upload_covers', default=False)
        c.add_opt('keep_cover_aspect', default=False)
        c.add_opt('upload_grayscale', default=False)

        c.add_opt('show_archived_books', default=False)
        c.add_opt('show_previews', default=False)
        c.add_opt('show_recommendations', default=False)

        c.add_opt('update_series', default=True)
        c.add_opt('update_device_metadata', default=True)

        c.add_opt('modify_css', default=False)

        c.add_opt('support_newer_firmware', default=False)
        c.add_opt('debugging_title', default='')
        c.add_opt('driver_version', default='')  # Mainly for debugging purposes, but might use if need to migrate between versions.

        return c

    @classmethod
    def settings(cls):
        opts = cls._config().parse()
        if opts.extra_customization:
            opts = cls.migrate_old_settings(opts)

        cls.opts = opts
        return opts

    def isAura(self):
        return self.detected_device.idProduct in self.AURA_PRODUCT_ID

    def isAuraEdition2(self):
        return self.detected_device.idProduct in self.AURA_EDITION2_PRODUCT_ID

    def isAuraHD(self):
        return self.detected_device.idProduct in self.AURA_HD_PRODUCT_ID

    def isAuraH2O(self):
        return self.detected_device.idProduct in self.AURA_H2O_PRODUCT_ID

    def isAuraH2OEdition2(self):
        return self.detected_device.idProduct in self.AURA_H2O_EDITION2_PRODUCT_ID

    def isAuraOne(self):
        return self.detected_device.idProduct in self.AURA_ONE_PRODUCT_ID

    def isGlo(self):
        return self.detected_device.idProduct in self.GLO_PRODUCT_ID

    def isGloHD(self):
        return self.detected_device.idProduct in self.GLO_HD_PRODUCT_ID

    def isMini(self):
        return self.detected_device.idProduct in self.MINI_PRODUCT_ID

    def isTouch(self):
        return self.detected_device.idProduct in self.TOUCH_PRODUCT_ID

    def isTouch2(self):
        return self.detected_device.idProduct in self.TOUCH2_PRODUCT_ID

    def cover_file_endings(self):
        if self.isAura():
            _cover_file_endings = self.GLO_COVER_FILE_ENDINGS
        elif self.isAuraEdition2():
            _cover_file_endings = self.GLO_COVER_FILE_ENDINGS
        elif self.isAuraHD():
            _cover_file_endings = self.AURA_HD_COVER_FILE_ENDINGS
        elif self.isAuraH2O():
            _cover_file_endings = self.AURA_HD_COVER_FILE_ENDINGS
        elif self.isAuraH2OEdition2():
            _cover_file_endings = self.AURA_HD_COVER_FILE_ENDINGS
        elif self.isAuraOne():
            _cover_file_endings = self.AURA_ONE_COVER_FILE_ENDINGS
        elif self.isGlo():
            _cover_file_endings = self.GLO_COVER_FILE_ENDINGS
        elif self.isGloHD():
            _cover_file_endings = self.GLO_HD_COVER_FILE_ENDINGS
        elif self.isMini():
            _cover_file_endings = self.COVER_FILE_ENDINGS
        elif self.isTouch():
            _cover_file_endings = self.COVER_FILE_ENDINGS
        elif self.isTouch2():
            _cover_file_endings = self.COVER_FILE_ENDINGS
        else:
            _cover_file_endings = self.COVER_FILE_ENDINGS

        return _cover_file_endings

    def set_device_name(self):
        device_name = self.gui_name
        if self.isAura():
            device_name = 'Kobo Aura'
        elif self.isAuraEdition2():
            device_name = 'Kobo Aura Edition 2'
        elif self.isAuraHD():
            device_name = 'Kobo Aura HD'
        elif self.isAuraH2O():
            device_name = 'Kobo Aura H2O'
        elif self.isAuraH2OEdition2():
            device_name = 'Kobo Aura H2O Edition 2'
        elif self.isAuraOne():
            device_name = 'Kobo Aura ONE'
        elif self.isGlo():
            device_name = 'Kobo Glo'
        elif self.isGloHD():
            device_name = 'Kobo Glo HD'
        elif self.isMini():
            device_name = 'Kobo Mini'
        elif self.isTouch():
            device_name = 'Kobo Touch'
        elif self.isTouch2():
            device_name = 'Kobo Touch 2'
        self.__class__.gui_name = device_name
        return device_name

    @property
    def manage_collections(self):
        return self.get_pref('manage_collections')

    @property
    def create_collections(self):
        return self.manage_collections and self.supports_bookshelves and self.get_pref('create_collections') and len(self.collections_columns) > 0

    @property
    def collections_columns(self):
        return self.get_pref('collections_columns')

    @property
    def delete_empty_collections(self):
        return self.manage_collections and self.get_pref('delete_empty_collections')

    @property
    def ignore_collections_names(self):
        # Cache the collection from the options string.
        if not hasattr(self.opts, '_ignore_collections_names'):
            icn = self.get_pref('ignore_collections_names')
            self.opts._ignore_collections_names = [x.lower().strip() for x in icn.split(',')] if icn else []
        return self.opts._ignore_collections_names

    @property
    def create_bookshelves(self):
        # Only for backwards compatabilty
        return self.manage_collections

    @property
    def delete_empty_shelves(self):
        # Only for backwards compatabilty
        return self.delete_empty_collections

    @property
    def upload_covers(self):
        return self.get_pref('upload_covers')

    @property
    def keep_cover_aspect(self):
        return self.upload_covers and self.get_pref('keep_cover_aspect')

    @property
    def upload_grayscale(self):
        return self.upload_covers and self.get_pref('upload_grayscale')

    def modifying_epub(self):
        return self.modifying_css()

    def modifying_css(self):
        return self.get_pref('modify_css')

    @property
    def update_device_metadata(self):
        return self.get_pref('update_device_metadata')

    @property
    def update_series_details(self):
        return self.update_device_metadata and self.get_pref('update_series') and self.supports_series()

    @classmethod
    def get_debugging_title(cls):
        debugging_title = cls.get_pref('debugging_title')
        if not debugging_title:  # Make sure the value is set to prevent rereading the settings.
            debugging_title = ''
        return debugging_title

    @property
    def supports_bookshelves(self):
        return self.dbversion >= self.min_supported_dbversion

    @property
    def show_archived_books(self):
        return self.get_pref('show_archived_books')

    @property
    def show_previews(self):
        return self.get_pref('show_previews')

    @property
    def show_recommendations(self):
        return self.get_pref('show_recommendations')

    @property
    def read_metadata(self):
        return self.get_pref('read_metadata')

    def supports_series(self):
        return self.dbversion >= self.min_dbversion_series

    def supports_kobo_archive(self):
        return self.dbversion >= self.min_dbversion_archive

    def supports_overdrive(self):
        return self.fwversion >= self.min_fwversion_overdrive

    def supports_covers_on_sdcard(self):
        return self.dbversion >= self.min_dbversion_images_on_sdcard and self.fwversion >= self.min_fwversion_images_on_sdcard

    def supports_images_tree(self):
        return self.fwversion >= self.min_fwversion_images_tree

    def has_externalid(self):
        return self.dbversion >= self.min_dbversion_externalid

    def has_activity_table(self):
        return self.dbversion >= self.min_dbversion_activity

    def modify_database_check(self, function):
        # Checks to see whether the database version is supported
        # and whether the user has chosen to support the firmware version
        if self.dbversion > self.supported_dbversion or self.is_supported_fwversion:
            # Unsupported database
            if not self.get_pref('support_newer_firmware'):
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
                    ' your Kobo.') + (
                    '\nDevice database version: %s.'
                    '\nDevice firmware version: %s'
                     ) % (self.dbversion, self.fwversion),
                     UserFeedback.WARN)

                return False
            else:
                # The user chose to edit the database anyway
                return True
        else:
            # Supported database version
            return True

    @property
    def is_supported_fwversion(self):
        # Starting with firmware version 3.19.x, the last number appears to be is a
        # build number. It can be safely ignored when testing the firmware version.
        debug_print("KoboTouch::is_supported_fwversion - self.fwversion[:2]", self.fwversion[:2])
        return self.fwversion[:2] > self.max_supported_fwversion

    @classmethod
    def migrate_old_settings(cls, settings):
        debug_print("KoboTouch::migrate_old_settings - start")
        debug_print("KoboTouch::migrate_old_settings - settings.extra_customization=", settings.extra_customization)
        debug_print("KoboTouch::migrate_old_settings - For class=", cls.name)

        count_options = 0
        OPT_COLLECTIONS                 = count_options
        count_options += 1
        OPT_CREATE_BOOKSHELVES          = count_options
        count_options += 1
        OPT_DELETE_BOOKSHELVES          = count_options
        count_options += 1
        OPT_UPLOAD_COVERS               = count_options
        count_options += 1
        OPT_UPLOAD_GRAYSCALE_COVERS     = count_options
        count_options += 1
        OPT_KEEP_COVER_ASPECT_RATIO     = count_options
        count_options += 1
        OPT_SHOW_ARCHIVED_BOOK_RECORDS  = count_options
        count_options += 1
        OPT_SHOW_PREVIEWS               = count_options
        count_options += 1
        OPT_SHOW_RECOMMENDATIONS        = count_options
        count_options += 1
        OPT_UPDATE_SERIES_DETAILS       = count_options
        count_options += 1
        OPT_MODIFY_CSS                  = count_options
        count_options += 1
        OPT_SUPPORT_NEWER_FIRMWARE      = count_options
        count_options += 1
        OPT_DEBUGGING_TITLE             = count_options

        # Always migrate options if for the KoboTouch class.
        # For a subclass, only migrate the KoboTouch options if they haven't already been migrated. This is based on
        # the total number of options.
        if cls == KOBOTOUCH or len(settings.extra_customization) >= count_options:
            config = cls._config()
            debug_print("KoboTouch::migrate_old_settings - config.preferences=", config.preferences)
            debug_print("KoboTouch::migrate_old_settings - settings need to be migrated")
            settings.manage_collections = True
            settings.collections_columns = settings.extra_customization[OPT_COLLECTIONS]
            debug_print("KoboTouch::migrate_old_settings - settings.collections_columns=", settings.collections_columns)
            settings.create_collections = settings.extra_customization[OPT_CREATE_BOOKSHELVES]
            settings.delete_empty_collections = settings.extra_customization[OPT_DELETE_BOOKSHELVES]

            settings.upload_covers = settings.extra_customization[OPT_UPLOAD_COVERS]
            settings.keep_cover_aspect = settings.extra_customization[OPT_KEEP_COVER_ASPECT_RATIO]
            settings.upload_grayscale = settings.extra_customization[OPT_UPLOAD_GRAYSCALE_COVERS]

            settings.show_archived_books = settings.extra_customization[OPT_SHOW_ARCHIVED_BOOK_RECORDS]
            settings.show_previews = settings.extra_customization[OPT_SHOW_PREVIEWS]
            settings.show_recommendations = settings.extra_customization[OPT_SHOW_RECOMMENDATIONS]

            # If the configuration hasn't been change for a long time, the last few option will be out
            # of sync. The last two options aare always the support newer firmware and the debugging
            # title. Set seties and Modify CSS were the last two new options. The debugging title is
            # a string, so looking for that.
            start_subclass_extra_options = OPT_MODIFY_CSS
            debugging_title = ''
            if isinstance(settings.extra_customization[OPT_MODIFY_CSS], basestring):
                debug_print("KoboTouch::migrate_old_settings - Don't have update_series option")
                settings.update_series = config.get_option('update_series').default
                settings.modify_css = config.get_option('modify_css').default
                settings.support_newer_firmware = settings.extra_customization[OPT_UPDATE_SERIES_DETAILS]
                debugging_title = settings.extra_customization[OPT_MODIFY_CSS]
                start_subclass_extra_options = OPT_MODIFY_CSS + 1
            elif isinstance(settings.extra_customization[OPT_SUPPORT_NEWER_FIRMWARE], basestring):
                debug_print("KoboTouch::migrate_old_settings - Don't have modify_css option")
                settings.update_series = settings.extra_customization[OPT_UPDATE_SERIES_DETAILS]
                settings.modify_css = config.get_option('modify_css').default
                settings.support_newer_firmware = settings.extra_customization[OPT_MODIFY_CSS]
                debugging_title = settings.extra_customization[OPT_SUPPORT_NEWER_FIRMWARE]
                start_subclass_extra_options = OPT_SUPPORT_NEWER_FIRMWARE + 1
            else:
                debug_print("KoboTouch::migrate_old_settings - Have all options")
                settings.update_series = settings.extra_customization[OPT_UPDATE_SERIES_DETAILS]
                settings.modify_css = settings.extra_customization[OPT_MODIFY_CSS]
                settings.support_newer_firmware = settings.extra_customization[OPT_SUPPORT_NEWER_FIRMWARE]
                debugging_title = settings.extra_customization[OPT_DEBUGGING_TITLE]
                start_subclass_extra_options = OPT_DEBUGGING_TITLE + 1

            settings.debugging_title = debugging_title if isinstance(debugging_title, basestring) else ''
            settings.update_device_metadata = settings.update_series
            settings.extra_customization = settings.extra_customization[start_subclass_extra_options:]

        return settings

    def is_debugging_title(self, title):
        if not DEBUG:
            return False
#         debug_print("KoboTouch:is_debugging - title=", title)

        if not self.debugging_title and not self.debugging_title == '':
            self.debugging_title = self.get_debugging_title()
        is_debugging = len(self.debugging_title) > 0 and title.lower().find(self.debugging_title.lower()) >= 0 or len(title) == 0

        return is_debugging

    def dump_bookshelves(self, connection):
        if not (DEBUG and self.supports_bookshelves and False):
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

    def __str__(self, *args, **kwargs):
        options = ', '.join(['%s: %s' % (x.name, self.get_pref(x.name)) for x in self._config().preferences])
        return u"Driver:%s, Options - %s" % (self.name, options)


if __name__ == '__main__':
    dev = KOBOTOUCH(None)
    dev.startup()
    try:
        dev.initialize()
        from calibre.devices.scanner import DeviceScanner
        scanner = DeviceScanner()
        scanner.scan()
        devs = scanner.devices
#         debug_print("unit test: devs.__class__=", devs.__class__)
#         debug_print("unit test: devs.__class__=", devs.__class__.__name__)
        debug_print("unit test: devs=", devs)
        debug_print("unit test: dev=", dev)
    #         cd = dev.detect_managed_devices(devs)
    #         if cd is None:
    #             raise ValueError('Failed to detect KOBOTOUCH device')
        dev.set_progress_reporter(prints)
#         dev.open(cd, None)
#         dev.filesystem_cache.dump()
        print ('Prefix for main memory:', dev.dbversion)
    finally:
        dev.shutdown()
