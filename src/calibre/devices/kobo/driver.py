#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Timothy Legge <timlegge at gmail.com> and Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os

import cStringIO
import sqlite3 as sqlite
from calibre.devices.usbms.books import BookList
from calibre.devices.kobo.books import Book
from calibre.devices.kobo.books import ImageWrapper
from calibre.devices.mime import mime_type_ext
from calibre.devices.usbms.driver import USBMS


class KOBO(USBMS):

    name = 'Kobo Reader Device Interface'
    gui_name = 'Kobo Reader'
    description = _('Communicate with the Kobo Reader')
    author = 'Timothy Legge and Kovid Goyal'
    version = (1, 0, 2)

    supported_platforms = ['windows', 'osx', 'linux']

    # Ordered list of supported formats
    FORMATS     = ['epub', 'pdf']

    VENDOR_ID   = [0x2237]
    PRODUCT_ID  = [0x4161]
    BCD         = [0x0110]

    VENDOR_NAME = 'KOBO_INC'
    WINDOWS_MAIN_MEM = WINDOWS_CARD_A_MEM = '.KOBOEREADER'

    EBOOK_DIR_MAIN = ''
    SUPPORTS_SUB_DIRS = True

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

        ebook_dirs = self.EBOOK_DIR_CARD_A if oncard == 'carda' else \
            self.EBOOK_DIR_CARD_B if oncard == 'cardb' else \
            self.get_main_ebook_dir()

        # get the metadata cache
        bl = self.booklist_class(oncard, prefix, self.settings)
        need_sync = self.parse_metadata_cache(bl, prefix, self.METADATA_CACHE)

        # make a dict cache of paths so the lookup in the loop below is faster.
        bl_cache = {}
        for idx,b in enumerate(bl):
            bl_cache[b.lpath] = idx

        def update_booklist(prefix, path, title, authors, mime, date, ContentType, ImageID):
            changed = False
            # if path_to_ext(path) in self.FORMATS:
            try:
                lpath = path.partition(self.normalize_path(prefix))[2]
                if lpath.startswith(os.sep):
                    lpath = lpath[len(os.sep):]
                    lpath = lpath.replace('\\', '/')
#                print "LPATH: " + lpath

                path = self.normalize_path(path)
                # print "Normalized FileName: " + path

                idx = bl_cache.get(lpath, None)
                if idx is not None:
                    imagename = self.normalize_path(prefix + '.kobo/images/' + ImageID + ' - NickelBookCover.parsed')
                    #print "Image name Normalized: " + imagename
                    bl[idx].thumbnail = ImageWrapper(imagename)
                    bl_cache[lpath] = None
                    if ContentType != '6':
                        if self.update_metadata_item(bl[idx]):
                            # print 'update_metadata_item returned true'
                            changed = True
                else:
                    book = Book(prefix, lpath, title, authors, mime, date, ContentType, ImageID)
                    # print 'Update booklist'
                    if bl.add_book(book, replace_metadata=False):
                        changed = True
            except: # Probably a path encoding error
                import traceback
                traceback.print_exc()
            return changed

        connection = sqlite.connect(self._main_prefix + '.kobo/KoboReader.sqlite')
        cursor = connection.cursor()
        
        #query = 'select count(distinct volumeId) from volume_shortcovers'
        #cursor.execute(query)
        #for row in (cursor):
        #    numrows = row[0]
        #cursor.close()

        query= 'select Title, Attribution, DateCreated, ContentID, MimeType, ContentType, ' \
                'ImageID from content where ContentID in (select distinct volumeId from volume_shortcovers)'

        cursor.execute (query) 

        changed = False
        for i, row in enumerate(cursor):
         #  self.report_progress((i+1) / float(numrows), _('Getting list of books on device...'))

            path = self.path_from_contentid(row[3], row[5], oncard)
            mime = mime_type_ext(path_to_ext(row[3]))

            if oncard != 'carda' and oncard != 'cardb':
                # print "shortbook: " + path
                changed = update_booklist(self._main_prefix, path, row[0], row[1], mime, row[2], row[5], row[6])
            elif oncard == 'carda':
                changed = update_booklist(self._card_a_prefix, path, row[0], row[1], mime, row[2], row[5], row[6])
            else:
                print "Add card b support"

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

        print "count found in cache: %d, count of files in metadata: %d, need_sync: %s" % \
              (len(bl_cache), len(bl), need_sync)
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

        connection = sqlite.connect(self._main_prefix + '.kobo/KoboReader.sqlite')
        cursor = connection.cursor()
        t = (ContentID,)
        cursor.execute('select ImageID from content where ContentID = ?', t)

        ImageID = None
        for row in cursor:
            # First get the ImageID to delete the images
            ImageID = row[0]
        cursor.close()
       
        if ImageID != None:
            cursor = connection.cursor()
            if ContentType == 6:
                # Delete the shortcover_pages first
                cursor.execute('delete from shortcover_page where shortcoverid in (select ContentID from content where BookID = ?)', t)

            #Delete the volume_shortcovers second
            cursor.execute('delete from volume_shortcovers where volumeid = ?', t)

            # Delete the chapters associated with the book next
            t = (ContentID,ContentID,)
            cursor.execute('delete from content where BookID  = ? or ContentID = ?', t) 

            connection.commit()

            cursor.close()
        else:
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

            if extension == '.kobo':
                # Kobo books do not have book files.  They do have some images though
                #print "kobo book"
                ContentType = 6
                ContentID = self.contentid_from_path(path, ContentType)
            if extension == '.pdf' or extension == '.epub':
                # print "ePub or pdf"
                ContentType = 16
                #print "Path: " + path
                ContentID = self.contentid_from_path(path, ContentType)
                # print "ContentID: " + ContentID
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
            print "Add book to metatdata: "
            print "prefix: " + prefix
            lpath = path.partition(prefix)[2]
            if lpath.startswith('/') or lpath.startswith('\\'):
                lpath = lpath[1:]
            print "path: " + lpath
            #book = self.book_class(prefix, lpath, other=info)
            lpath = self.normalize_path(prefix + lpath)
            book = Book(prefix, lpath, '', '', '', '', '', '', other=info)
            if book.size is None:
                book.size = os.stat(self.normalize_path(path)).st_size
            booklists[blist].add_book(book, replace_metadata=True)
        self.report_progress(1.0, _('Adding books to device metadata listing...'))

    def contentid_from_path(self, path, ContentType):
        if ContentType == 6:
            ContentID = os.path.splitext(path)[0]
            # Remove the prefix on the file.  it could be either
            ContentID = ContentID.replace(self._main_prefix, '')
            if self._card_a_prefix is not None:
                ContentID = ContentID.replace(self._card_a_prefix, '')
        else: # ContentType = 16
            ContentID = path
            ContentID = ContentID.replace(self._main_prefix, "file:///mnt/onboard/")
            if self._card_a_prefix is not None:
                ContentID = ContentID.replace(self._card_a_prefix, "file:///mnt/sd/")
        ContentID = ContentID.replace("\\", '/')
        return ContentID


    def path_from_contentid(self, ContentID, ContentType, oncard):
        path = ContentID

        if oncard != 'carda' and oncard != 'cardb':
            if ContentType == "6":
                # This is a hack as the kobo files do not exist
                # but the path is required to make a unique id 
                # for calibre's reference
                path = self._main_prefix + os.sep + path + '.kobo'
            else:
                if path.startswith("file:///mnt/onboard/"):
                    path = path.replace("file:///mnt/onboard/", self._main_prefix)
                    # print "Internal: " + filename
        elif oncard == 'carda':
            if path.startswith("file:///mnt/sd/"):
                path = path.replace("file:///mnt/sd/", self._card_a_prefix)
                # print "SD Card: " + filename

        return path
