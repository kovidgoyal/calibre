#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Timothy Legge <timlegge at gmail.com> and Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

'''
Device driver for the SONY T1 devices
'''

import os, time, calendar, re

import sqlite3 as sqlite
from contextlib import closing
from itertools import cycle
from calibre.devices.usbms.driver import USBMS, debug_print
from calibre import __appname__, prints
from calibre.devices.usbms.books import CollectionsBookList
from calibre.devices.usbms.books import BookList
from calibre.devices.prst1.books import ImageWrapper

class PRST1(USBMS):
    name           = 'SONY PRST1 and newer Device Interface'
    gui_name       = 'SONY Reader'
    description    = _('Communicate with Sony PRST1 and newer eBook readers')
    author         = 'Kovid Goyal'
    supported_platforms = ['windows', 'osx', 'linux']
    path_sep = '/'
    booklist_class = CollectionsBookList

    FORMATS      = ['epub', 'pdf', 'txt']
    CAN_SET_METADATA = ['collections']
    CAN_DO_DEVICE_DB_PLUGBOARD = True

    VENDOR_ID    = [0x054c]   #: SONY Vendor Id
    PRODUCT_ID   = [0x05c2]
    BCD          = [0x226]

    VENDOR_NAME        = 'SONY'
    WINDOWS_MAIN_MEM   = re.compile(
            r'(PRS-T1&)'
            )

    THUMBNAIL_HEIGHT = 144
    SUPPORTS_SUB_DIRS = True
    MUST_READ_METADATA = True
    EBOOK_DIR_MAIN   = 'Sony_Reader/media/books'

    EXTRA_CUSTOMIZATION_MESSAGE = [
        _('Comma separated list of metadata fields '
            'to turn into collections on the device. Possibilities include: ')+\
                    'series, tags, authors',
		_('Upload separate cover thumbnails for books') +
		     ':::'+_('Normally, the SONY readers get the cover image from the'
		     ' ebook file itself. With this option, calibre will send a '
		     'separate cover image to the reader, useful if you are '
		     'sending DRMed books in which you cannot change the cover.'),
		_('Refresh separate covers when using automatic management') +
		     ':::' +
		      _('Set this option to have separate book covers uploaded '
		        'every time you connect your device. Unset this option if '
		        'you have so many books on the reader that performance is '
		        'unacceptable.'),
		_('Preserve cover aspect ratio when building thumbnails') +
		      ':::' +
		      _('Set this option if you want the cover thumbnails to have '
		        'the same aspect ratio (width to height) as the cover. '
		        'Unset it if you want the thumbnail to be the maximum size, '
		        'ignoring aspect ratio.'),
    ]
    EXTRA_CUSTOMIZATION_DEFAULT = [
                ', '.join(['series', 'tags']),
				False,
				False,
				True,
    ]

    OPT_COLLECTIONS    = 0
    OPT_UPLOAD_COVERS  = 1
    OPT_REFRESH_COVERS = 2
    OPT_PRESERVE_ASPECT_RATIO = 3

    plugboards = None
    plugboard_func = None

    def post_open_callback(self):
        # Set the thumbnail width to the theoretical max if the user has asked
        # that we do not preserve aspect ratio
        if not self.settings().extra_customization[self.OPT_PRESERVE_ASPECT_RATIO]:
            self.THUMBNAIL_WIDTH = 108

    def windows_filter_pnp_id(self, pnp_id):
        return '_LAUNCHER' in pnp_id or '_SETTING' in pnp_id

    def get_carda_ebook_dir(self, for_upload=False):
        if for_upload:
            return self.EBOOK_DIR_MAIN
        return self.EBOOK_DIR_CARD_A

    def get_main_ebook_dir(self, for_upload=False):
        if for_upload:
            return self.EBOOK_DIR_MAIN
        return ''

	def books(self, oncard=None, end_session=True):
	    from calibre.ebooks.metadata.meta import path_to_ext

	    dummy_bl = BookList(None, None, None)

	    if oncard == 'carda' and not self._card_a_prefix:
	       self.report_progress(1.0, _('Getting list of books on device...'))
	       return dummy_bl
	    elif oncard and oncard != 'carda':
	       self.report_progress(1.0, _('Getting list of books on device...'))
	       return dummy_bl
	
		prefix = self._card_a_prefix if oncard == 'carda' else self._main_prefix

		# Let parent driver get the books
	    self.booklist_class.rebuild_collections = self.rebuild_collections
		bl = USBMS.books(self, oncard=oncard, end_session=end_session)
		
		debug_print("SQLite DB Path: " + self.normalize_path(prefix + 'Sony_Reader/database/books.db'))
		
		with closing(sqlite.connect(self.normalize_path(prefix + 'Sony_Reader/database/books.db'))) as connection:
			# return bytestrings if the content cannot the decoded as unicode
            connection.text_factory = lambda x: unicode(x, "utf-8", "ignore")

            cursor = connection.cursor()
			# Query collections
			query = 'select books._id, collection.title ' \
					'from collections ' \
					'left outer join books ' \
					'left outer join collection ' \
					'where collections.content_id = books._id and collections.collection_id = collection._id'
			cursor.execute (query)
			
			bl_collections = {}
			for i, row in enumerate(cursor):
				bl_collections.setdefault(row[0], [])
				bl_collections[row[0]].append(row[1])
		 
			for idx,book in enumerate(bl):
                query = 'select _id, thumbnail from books where file_path = ?'
				t = (book.lpath,)
				cursor.execute (query, t)
				
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
		debug_print('PRST1: starting sync_booklists')
		
		opts = self.settings()
        if opts.extra_customization:
            collections = [x.strip() for x in
                    opts.extra_customization[self.OPT_COLLECTIONS].split(',')]
        else:
            collections = []
        debug_print('PRST1: collection fields:', collections)
		
		if booklists[0] is not None:
			self.update_device_database(booklists[0], collections, None)
		if booklists[1] is not None:
			self.update_device_database(booklists[1], collections, 'carda')
		
		USBMS.sync_booklists(self, booklists, end_session=end_session)
        debug_print('PRST1: finished sync_booklists')
	
	def update_device_database(self, booklist, collections_attributes, oncard):
		debug_print('PRST1: starting update_device_database')
		
		plugboard = None
		if self.plugboard_func:
            plugboard = self.plugboard_func(self.__class__.__name__, 'device_db', self.plugboards)
			debug_print("PRST1: Using Plugboard", plugboard)
		
		prefix = self._card_a_prefix if oncard == 'carda' else self._main_prefix
		source_id = 1 if oncard == 'carda' else 0
		debug_print("SQLite DB Path: " + self.normalize_path(prefix + 'Sony_Reader/database/books.db'))
		
		collections = booklist.get_collections(collections_attributes)
		
		with closing(sqlite.connect(self.normalize_path(prefix + 'Sony_Reader/database/books.db'))) as connection:
			self.update_device_books(connection, booklist, source_id, plugboard)
			self.update_device_collections(connection, booklist, collections, source_id)
		
		debug_print('PRST1: finished update_device_database')

	def update_device_books(self, connection, booklist, source_id, plugboard):
		opts = self.settings()
		upload_covers = opts.extra_customization[self.OPT_UPLOAD_COVERS]
		refresh_covers = opts.extra_customization[self.OPT_REFRESH_COVERS]
				
		cursor = connection.cursor()
		
		# Get existing books
		query = 'select file_path, _id ' \
				'from books'
		cursor.execute(query)
		
		dbBooks = {}
		for i, row in enumerate(cursor):
			lpath = row[0].replace('\\', '/')
			dbBooks[lpath] = row[1]
		
		for book in booklist:	
			# Run through plugboard if needed		
			if plugboard is not None:
                newmi = book.deepcopy_metadata()
                newmi.template_to_attribute(book, plugboard)
            else:
                newmi = book
			
			# Get Metadata We Want
			lpath = book.lpath
			author = newmi.authors[0]
			title = newmi.title			

			if lpath not in dbBooks:
				query = 'insert into books ' \
						'(title, author, source_id, added_date, modified_date, file_path, file_name, file_size, mime_type, corrupted, prevent_delete) ' \
						'values (?,?,?,?,?,?,?,?,?,0,0)'
				t = (title, author, source_id, int(time.time() * 1000), calendar.timegm(book.datetime), lpath, os.path.basename(book.lpath), book.size, book.mime )
				cursor.execute(query, t)
				book.bookId = cursor.lastrowid
				if upload_covers:
					self.upload_book_cover(connection, book, source_id)
				debug_print('Inserted New Book: ' + book.title)
			else:
				query = 'update books ' \
						'set title = ?, author = ?, modified_date = ?, file_size = ? ' \
						'where file_path = ?'
				t = (title, author, calendar.timegm(book.datetime), book.size, lpath)
				cursor.execute(query, t)
				book.bookId = dbBooks[lpath]
				if refresh_covers:
					self.upload_book_cover(connection, book, source_id)
				dbBooks[lpath] = None
			
		for book, bookId in dbBooks.items():
			if bookId is not None:
				# Remove From Collections
				query = 'delete from collections ' \
						'where content_id = ?'
				t = (bookId,)
				cursor.execute(query, t)
				# Remove from Books
				query = 'delete from books ' \
						'where _id = ?'
				t = (bookId,)
				cursor.execute(query, t)
				debug_print('Deleted Book:' + book)
		
		connection.commit()
		cursor.close()
		
	def update_device_collections(self, connection, booklist, collections, source_id):
		cursor = connection.cursor()
		
		if collections:
			# Get existing collections
			query = 'select _id, title ' \
			 		'from collection'
			cursor.execute(query)
			
			dbCollections = {}
			for i, row in enumerate(cursor):
				dbCollections[row[1]] = row[0]
			
			for collection, books in collections.items():
				if collection not in dbCollections:
					query = 'insert into collection (title, source_id) values (?,?)'
					t = (collection, source_id)
					cursor.execute(query, t)
					dbCollections[collection] = cursor.lastrowid
					debug_print('Inserted New Collection: ' + collection)
					
				# Get existing books in collection
				query = 'select books.file_path, content_id ' \
				 		'from collections ' \
						'left outer join books ' \
						'where collection_id = ? and books._id = collections.content_id'
				t = (dbCollections[collection],)
				cursor.execute(query, t)

				dbBooks = {}
				for i, row in enumerate(cursor):
					dbBooks[row[0]] = row[1]
					
				for idx, book in enumerate(books):
					if dbBooks.get(book.lpath, None) is None:
						if collection not in book.device_collections:
							book.device_collections.append(collection)
						query = 'insert into collections (collection_id, content_id, added_order) values (?,?,?)'
						t = (dbCollections[collection], book.bookId, idx)
						cursor.execute(query, t)
						debug_print('Inserted Book Into Collection: ' + book.title + ' -> ' + collection)
					else:
						query = 'update collections ' \
						        'set added_order = ? ' \
						        'where content_id = ? and collection_id = ? '
						t = (idx, book.bookId, dbCollections[collection])
						cursor.execute(query, t)
					
					dbBooks[book.lpath] = None
					
				for bookPath, bookId in dbBooks.items():	
					if bookId is not None:
						query = 'delete from collections ' \
								'where content_id = ? and collection_id = ? '
						t = (bookId,dbCollections[collection],)
						cursor.execute(query, t)
						debug_print('Deleted Book From Collection: ' + bookPath + ' -> ' + collection)
					
				dbCollections[collection] = None
				
			for collection, collectionId in dbCollections.items():
				if collectionId is not None:
					# Remove Books from Collection
					query = 'delete from collections ' \
							'where collection_id = ?'
					t = (collectionId,)
					cursor.execute(query, t)
					# Remove Collection
					query = 'delete from collection ' \
							'where _id = ?'
					t = (collectionId,)
					cursor.execute(query, t)
					debug_print('Deleted Collection: ' + collection)
				
		
		connection.commit()
		cursor.close()
	
	def rebuild_collections(self, booklist, oncard):
		debug_print('PRST1: starting rebuild_collections')
		
		opts = self.settings()
        if opts.extra_customization:
            collections = [x.strip() for x in
                    opts.extra_customization[self.OPT_COLLECTIONS].split(',')]
        else:
            collections = []
        debug_print('PRST1: collection fields:', collections)
		
		self.update_device_database(booklist, collections, oncard)
	
		debug_print('PRS-T1: finished rebuild_collections')
	
	def upload_book_cover(self, connection, book, source_id):
		debug_print('PRST1: Uploading/Refreshing Cover for ' + book.title)
		cursor = connection.cursor()
		
		if book.thumbnail and book.thumbnail[-1]:
			thumbnailPath = 'Sony_Reader/database/cache/books/' + str(book.bookId) +'/thumbnail/main_thumbnail.jpg'
			
			prefix = self._main_prefix if source_id is 0 else self._card_a_prefix
			thumbnailFilePath = os.path.join(prefix, *thumbnailPath.split('/'))
			thumbnailDirPath = os.path.dirname(thumbnailFilePath)
			if not os.path.exists(thumbnailDirPath):
                os.makedirs(thumbnailDirPath)

			with open(thumbnailFilePath, 'wb') as f:
	            f.write(book.thumbnail[-1])
			
			query = 'update books ' \
					'set thumbnail = ?' \
					'where _id = ? '
			t = (thumbnailPath,book.bookId,)
			cursor.execute(query, t)
		
		cursor.close()