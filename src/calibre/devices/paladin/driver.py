#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2016, Kovid Goyal <kovid at kovidgoyal.net>


'''
Device driver for the Paladin devices
'''

import os, time, sys
from contextlib import closing

from calibre.devices.mime import mime_type_ext
from calibre.devices.errors import DeviceError
from calibre.devices.usbms.driver import USBMS, debug_print
from calibre.devices.usbms.books import CollectionsBookList, BookList

DBPATH = 'paladin/database/books.db'


class ImageWrapper(object):

    def __init__(self, image_path):
        self.image_path = image_path


class PALADIN(USBMS):
    name           = 'Paladin Device Interface'
    gui_name       = 'Paladin eLibrary'
    description    = _('Communicate with the Paladin readers')
    author         = 'David Hobley'
    supported_platforms = ['windows', 'osx', 'linux']
    path_sep = '/'
    booklist_class = CollectionsBookList

    FORMATS      = ['epub', 'pdf']
    CAN_SET_METADATA = ['collections']
    CAN_DO_DEVICE_DB_PLUGBOARD = True

    VENDOR_ID    = [0x2207]   #: Onyx Vendor Id (currently)
    PRODUCT_ID   = [0x0010]
    BCD          = None

    SUPPORTS_SUB_DIRS = True
    SUPPORTS_USE_AUTHOR_SORT = True
    MUST_READ_METADATA = True
    EBOOK_DIR_MAIN   = 'paladin/books'

    EXTRA_CUSTOMIZATION_MESSAGE = [
        _(
            'Comma separated list of metadata fields '
            'to turn into collections on the device. Possibilities include: '
        ) + 'series, tags, authors',
    ]
    EXTRA_CUSTOMIZATION_DEFAULT = [
        ', '.join(['series', 'tags']),
    ]
    OPT_COLLECTIONS    = 0

    plugboards = None
    plugboard_func = None

    device_offset = None

    def books(self, oncard=None, end_session=True):
        import apsw
        dummy_bl = BookList(None, None, None)

        if (
                (oncard == 'carda' and not self._card_a_prefix) or
                (oncard and oncard != 'carda')
            ):
            self.report_progress(1.0, _('Getting list of books on device...'))
            return dummy_bl

        prefix = self._card_a_prefix if oncard == 'carda' else self._main_prefix

        # Let parent driver get the books
        self.booklist_class.rebuild_collections = self.rebuild_collections
        bl = USBMS.books(self, oncard=oncard, end_session=end_session)

        dbpath = self.normalize_path(prefix + DBPATH)
        debug_print("SQLite DB Path: " + dbpath)

        with closing(apsw.Connection(dbpath)) as connection:
            cursor = connection.cursor()
            # Query collections
            query = '''
                SELECT books._id, tags.tagname
                    FROM booktags
                    LEFT OUTER JOIN books
                    LEFT OUTER JOIN tags
                    WHERE booktags.book_id = books._id AND
                    booktags.tag_id = tags._id
                '''
            cursor.execute(query)

            bl_collections = {}
            for i, row in enumerate(cursor):
                bl_collections.setdefault(row[0], [])
                bl_collections[row[0]].append(row[1])

            # collect information on offsets, but assume any
            # offset we already calculated is correct
            if self.device_offset is None:
                query = 'SELECT filename, addeddate FROM books'
                cursor.execute(query)

                time_offsets = {}
                for i, row in enumerate(cursor):
                    try:
                        comp_date = int(os.path.getmtime(self.normalize_path(prefix + row[0])) * 1000)
                    except (OSError, IOError, TypeError):
                        # In case the db has incorrect path info
                        continue
                    device_date = int(row[1])
                    offset = device_date - comp_date
                    time_offsets.setdefault(offset, 0)
                    time_offsets[offset] = time_offsets[offset] + 1

                try:
                    device_offset = max(time_offsets, key=lambda a: time_offsets.get(a))
                    debug_print("Device Offset: %d ms"%device_offset)
                    self.device_offset = device_offset
                except ValueError:
                    debug_print("No Books To Detect Device Offset.")

            for idx, book in enumerate(bl):
                query = 'SELECT _id, thumbnail FROM books WHERE filename = ?'
                t = (book.lpath,)
                cursor.execute(query, t)

                for i, row in enumerate(cursor):
                    book.device_collections = bl_collections.get(row[0], None)
                    thumbnail = row[1]
                    if thumbnail is not None:
                        thumbnail = self.normalize_path(prefix + thumbnail)
                        book.thumbnail = ImageWrapper(thumbnail)

            cursor.close()

        return bl

    def set_plugboards(self, plugboards, pb_func):
        self.plugboards = plugboards
        self.plugboard_func = pb_func

    def sync_booklists(self, booklists, end_session=True):
        debug_print('PALADIN: starting sync_booklists')

        opts = self.settings()
        if opts.extra_customization:
            collections = [x.strip() for x in
                    opts.extra_customization[self.OPT_COLLECTIONS].split(',')]
        else:
            collections = []
        debug_print('PALADIN: collection fields:', collections)

        if booklists[0] is not None:
            self.update_device_database(booklists[0], collections, None)
        if len(booklists) > 1 and booklists[1] is not None:
            self.update_device_database(booklists[1], collections, 'carda')

        USBMS.sync_booklists(self, booklists, end_session=end_session)
        debug_print('PALADIN: finished sync_booklists')

    def update_device_database(self, booklist, collections_attributes, oncard):
        import apsw
        debug_print('PALADIN: starting update_device_database')

        plugboard = None
        if self.plugboard_func:
            plugboard = self.plugboard_func(self.__class__.__name__,
                    'device_db', self.plugboards)
            debug_print("PALADIN: Using Plugboard", plugboard)

        prefix = self._card_a_prefix if oncard == 'carda' else self._main_prefix
        if prefix is None:
            # Reader has no sd card inserted
            return
        source_id = 1 if oncard == 'carda' else 0

        dbpath = self.normalize_path(prefix + DBPATH)
        debug_print("SQLite DB Path: " + dbpath)

        collections = booklist.get_collections(collections_attributes)

        with closing(apsw.Connection(dbpath)) as connection:
            self.remove_orphaned_records(connection, dbpath)
            self.update_device_books(connection, booklist, source_id,
                    plugboard, dbpath)
            self.update_device_collections(connection, booklist, collections, source_id, dbpath)

        debug_print('PALADIN: finished update_device_database')

    def remove_orphaned_records(self, connection, dbpath):
        try:
            cursor = connection.cursor()

            debug_print("Removing Orphaned Collection Records")

            # Purge any collections references that point into the abyss
            query = 'DELETE FROM booktags WHERE book_id NOT IN (SELECT _id FROM books)'
            cursor.execute(query)
            query = 'DELETE FROM booktags WHERE tag_id NOT IN (SELECT _id FROM tags)'
            cursor.execute(query)

            debug_print("Removing Orphaned Book Records")

            cursor.close()
        except Exception:
            import traceback
            tb = traceback.format_exc()
            raise DeviceError((('The Paladin database is corrupted. '
                    ' Delete the file %s on your reader and then disconnect '
                    ' reconnect it. If you are using an SD card, you '
                    ' should delete the file on the card as well. Note that '
                    ' deleting this file will cause your reader to forget '
                    ' any notes/highlights, etc.')%dbpath)+' Underlying error:'
                    '\n'+tb)

    def get_database_min_id(self, source_id):
        sequence_min = 0
        if source_id == 1:
            sequence_min = 4294967296

        return sequence_min

    def set_database_sequence_id(self, connection, table, sequence_id):
        cursor = connection.cursor()

        # Update the sequence Id if it exists
        query = 'UPDATE sqlite_sequence SET seq = ? WHERE name = ?'
        t = (sequence_id, table,)
        cursor.execute(query, t)

        # Insert the sequence Id if it doesn't
        query = ('INSERT INTO sqlite_sequence (name, seq) '
                'SELECT ?, ? '
                'WHERE NOT EXISTS (SELECT 1 FROM sqlite_sequence WHERE name = ?)')
        cursor.execute(query, (table, sequence_id, table,))

        cursor.close()

    def read_device_books(self, connection, source_id, dbpath):
        sequence_min = self.get_database_min_id(source_id)
        sequence_max = sequence_min
        sequence_dirty = 0

        debug_print("Book Sequence Min: %d, Source Id: %d"%(sequence_min,source_id))

        try:
            cursor = connection.cursor()

            # Get existing books
            query = 'SELECT filename, _id FROM books'
            cursor.execute(query)
        except Exception:
            import traceback
            tb = traceback.format_exc()
            raise DeviceError((('The Paladin database is corrupted. '
                    ' Delete the file %s on your reader and then disconnect '
                    ' reconnect it. If you are using an SD card, you '
                    ' should delete the file on the card as well. Note that '
                    ' deleting this file will cause your reader to forget '
                    ' any notes/highlights, etc.')%dbpath)+' Underlying error:'
                    '\n'+tb)

        # Get the books themselves, but keep track of any that are less than the minimum.
        # Record what the max id being used is as well.
        db_books = {}
        for i, row in enumerate(cursor):
            if not hasattr(row[0], 'replace'):
                continue
            lpath = row[0].replace('\\', '/')
            db_books[lpath] = row[1]
            if row[1] < sequence_min:
                sequence_dirty = 1
            else:
                sequence_max = max(sequence_max, row[1])

        # If the database is 'dirty', then we should fix up the Ids and the sequence number
        if sequence_dirty == 1:
            debug_print("Book Sequence Dirty for Source Id: %d"%source_id)
            sequence_max = sequence_max + 1
            for book, bookId in db_books.items():
                if bookId < sequence_min:
                    # Record the new Id and write it to the DB
                    db_books[book] = sequence_max
                    sequence_max = sequence_max + 1

                    # Fix the Books DB
                    query = 'UPDATE books SET _id = ? WHERE filename = ?'
                    t = (db_books[book], book,)
                    cursor.execute(query, t)

                    # Fix any references so that they point back to the right book
                    t = (db_books[book], bookId,)
                    query = 'UPDATE booktags SET tag_id = ? WHERE tag_id = ?'
                    cursor.execute(query, t)

            self.set_database_sequence_id(connection, 'books', sequence_max)
            debug_print("Book Sequence Max: %d, Source Id: %d"%(sequence_max,source_id))

        cursor.close()
        return db_books

    def update_device_books(self, connection, booklist, source_id, plugboard,
            dbpath):
        from calibre.ebooks.metadata.meta import path_to_ext
        from calibre.ebooks.metadata import authors_to_sort_string, authors_to_string
        opts = self.settings()

        db_books = self.read_device_books(connection, source_id, dbpath)
        cursor = connection.cursor()

        for book in booklist:
            # Run through plugboard if needed
            if plugboard is not None:
                newmi = book.deepcopy_metadata()
                newmi.template_to_attribute(book, plugboard)
            else:
                newmi = book

            # Get Metadata We Want
            lpath = book.lpath
            try:
                if opts.use_author_sort:
                    if newmi.author_sort:
                        author = newmi.author_sort
                    else:
                        author = authors_to_sort_string(newmi.authors)
                else:
                    author = authors_to_string(newmi.authors)
            except Exception:
                author = _('Unknown')
            title = newmi.title or _('Unknown')

            # Get modified date
            # If there was a detected offset, use that. Otherwise use UTC (same as Sony software)
            modified_date = os.path.getmtime(book.path) * 1000
            if self.device_offset is not None:
                modified_date = modified_date + self.device_offset

            if lpath not in db_books:
                query = '''
                INSERT INTO books
                (bookname, authorname, description, addeddate, seriesname, seriesorder, filename, mimetype)
                values (?,?,?,?,?,?,?,?)
                '''
                t = (title, author, book.get('comments', None), int(time.time() * 1000),
                        book.get('series', None), book.get('series_index', sys.maxsize), lpath,
                        book.mime or mime_type_ext(path_to_ext(lpath)))
                cursor.execute(query, t)
                book.bookId = connection.last_insert_rowid()
                debug_print('Inserted New Book: (%u) '%book.bookId + book.title)
            else:
                query = '''
                UPDATE books
                SET bookname = ?, authorname = ?, addeddate = ?
                WHERE filename = ?
                '''
                t = (title, author, modified_date, lpath)
                cursor.execute(query, t)
                book.bookId = db_books[lpath]
                db_books[lpath] = None

        for book, bookId in db_books.items():
            if bookId is not None:
                # Remove From Collections
                query = 'DELETE FROM tags WHERE _id in (select tag_id from booktags where book_id = ?)'
                t = (bookId,)
                cursor.execute(query, t)
                # Remove from Books
                query = 'DELETE FROM books where _id = ?'
                t = (bookId,)
                cursor.execute(query, t)
                debug_print('Deleted Book:' + book)

        cursor.close()

    def read_device_collections(self, connection, source_id, dbpath):
        sequence_min = self.get_database_min_id(source_id)
        sequence_max = sequence_min
        sequence_dirty = 0

        debug_print("Collection Sequence Min: %d, Source Id: %d"%(sequence_min,source_id))

        try:
            cursor = connection.cursor()

            # Get existing collections
            query = 'SELECT _id, tagname FROM tags'
            cursor.execute(query)
        except Exception:
            import traceback
            tb = traceback.format_exc()
            raise DeviceError((('The Paladin database is corrupted. '
                    ' Delete the file %s on your reader and then disconnect '
                    ' reconnect it. If you are using an SD card, you '
                    ' should delete the file on the card as well. Note that '
                    ' deleting this file will cause your reader to forget '
                    ' any notes/highlights, etc.')%dbpath)+' Underlying error:'
                    '\n'+tb)

        db_collections = {}
        for i, row in enumerate(cursor):
            db_collections[row[1]] = row[0]
            if row[0] < sequence_min:
                sequence_dirty = 1
            else:
                sequence_max = max(sequence_max, row[0])

        # If the database is 'dirty', then we should fix up the Ids and the sequence number
        if sequence_dirty == 1:
            debug_print("Collection Sequence Dirty for Source Id: %d"%source_id)
            sequence_max = sequence_max + 1
            for collection, collectionId in db_collections.items():
                if collectionId < sequence_min:
                    # Record the new Id and write it to the DB
                    db_collections[collection] = sequence_max
                    sequence_max = sequence_max + 1

                    # Fix the collection DB
                    query = 'UPDATE tags SET _id = ? WHERE tagname = ?'
                    t = (db_collections[collection], collection, )
                    cursor.execute(query, t)

                    # Fix any references in existing collections
                    query = 'UPDATE booktags SET tag_id = ? WHERE tag_id = ?'
                    t = (db_collections[collection], collectionId,)
                    cursor.execute(query, t)

            self.set_database_sequence_id(connection, 'tags', sequence_max)
            debug_print("Collection Sequence Max: %d, Source Id: %d"%(sequence_max,source_id))

        # Fix up the collections table now...
        sequence_dirty = 0
        sequence_max = sequence_min

        debug_print("Collections Sequence Min: %d, Source Id: %d"%(sequence_min,source_id))

        query = 'SELECT _id FROM booktags'
        cursor.execute(query)

        db_collection_pairs = []
        for i, row in enumerate(cursor):
            db_collection_pairs.append(row[0])
            if row[0] < sequence_min:
                sequence_dirty = 1
            else:
                sequence_max = max(sequence_max, row[0])

        if sequence_dirty == 1:
            debug_print("Collections Sequence Dirty for Source Id: %d"%source_id)
            sequence_max = sequence_max + 1
            for pairId in db_collection_pairs:
                if pairId < sequence_min:
                    # Record the new Id and write it to the DB
                    query = 'UPDATE booktags SET _id = ? WHERE _id = ?'
                    t = (sequence_max, pairId,)
                    cursor.execute(query, t)
                    sequence_max = sequence_max + 1

            self.set_database_sequence_id(connection, 'booktags', sequence_max)
            debug_print("Collections Sequence Max: %d, Source Id: %d"%(sequence_max,source_id))

        cursor.close()
        return db_collections

    def update_device_collections(self, connection, booklist, collections,
            source_id, dbpath):

        if collections:
            db_collections = self.read_device_collections(connection, source_id, dbpath)
            cursor = connection.cursor()

            for collection, books in collections.items():
                if collection not in db_collections:
                    query = 'INSERT INTO tags (tagname) VALUES (?)'
                    t = (collection,)
                    cursor.execute(query, t)
                    db_collections[collection] = connection.last_insert_rowid()
                    debug_print('Inserted New Collection: (%u) '%db_collections[collection] + collection)

                # Get existing books in collection
                query = '''
                SELECT books.filename, book_id
                FROM booktags
                LEFT OUTER JOIN books
                WHERE tag_id = ? AND books._id = booktags.book_id
                '''
                t = (db_collections[collection],)
                cursor.execute(query, t)

                db_books = {}
                for i, row in enumerate(cursor):
                    db_books[row[0]] = row[1]

                for idx, book in enumerate(books):
                    if collection not in book.device_collections:
                        book.device_collections.append(collection)
                    if db_books.get(book.lpath, None) is None:
                        query = '''
                        INSERT INTO booktags (tag_id, book_id) values (?,?)
                        '''
                        t = (db_collections[collection], book.bookId)
                        cursor.execute(query, t)
                        debug_print('Inserted Book Into Collection: ' +
                                book.title + ' -> ' + collection)

                    db_books[book.lpath] = None

                for bookPath, bookId in db_books.items():
                    if bookId is not None:
                        query = ('DELETE FROM booktags '
                                'WHERE book_id = ? AND tag_id = ? ')
                        t = (bookId, db_collections[collection],)
                        cursor.execute(query, t)
                        debug_print('Deleted Book From Collection: ' + bookPath + ' -> ' + collection)

                db_collections[collection] = None

            for collection, collectionId in db_collections.items():
                if collectionId is not None:
                    # Remove Books from Collection
                    query = ('DELETE FROM booktags '
                            'WHERE tag_id = ?')
                    t = (collectionId,)
                    cursor.execute(query, t)
                    # Remove Collection
                    query = ('DELETE FROM tags '
                            'WHERE _id = ?')
                    t = (collectionId,)
                    cursor.execute(query, t)
                    debug_print('Deleted Collection: ' + repr(collection))

            cursor.close()

    def rebuild_collections(self, booklist, oncard):
        debug_print('PALADIN: starting rebuild_collections')

        opts = self.settings()
        if opts.extra_customization:
            collections = [x.strip() for x in
                    opts.extra_customization[self.OPT_COLLECTIONS].split(',')]
        else:
            collections = []
        debug_print('PALADIN: collection fields:', collections)

        self.update_device_database(booklist, collections, oncard)

        debug_print('PALADIN: finished rebuild_collections')
