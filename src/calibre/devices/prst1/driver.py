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
from calibre.devices.prst1.books import Book

class PRST1(USBMS):
    name           = 'SONY PRST1 and newer Device Interface'
    gui_name       = 'SONY Reader'
    description    = _('Communicate with Sony PRST1 and newer eBook readers')
    author         = 'Kovid Goyal'
    supported_platforms = ['windows', 'osx', 'linux']
    path_sep = '/'
    booklist_class = CollectionsBookList

    FORMATS      = ['epub', 'pdf', 'txt']
    CAN_SET_METADATA = ['title', 'authors', 'collections']

    VENDOR_ID    = [0x054c]   #: SONY Vendor Id
    PRODUCT_ID   = [0x05c2]
    BCD          = [0x226]

    VENDOR_NAME        = 'SONY'
    WINDOWS_MAIN_MEM   = re.compile(
            r'(PRS-T1&)'
            )

    THUMBNAIL_HEIGHT = 144
    SCAN_FROM_ROOT   = True
    SUPPORT_SUB_DIRS = True
	EBOOK_DIR_MAIN   = 'Sony_Reader/media/books'

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

		# get the metadata cache
	    self.booklist_class.rebuild_collections = self.rebuild_collections
		bl = self.booklist_class(oncard, prefix, self.settings)
		need_sync = self.parse_metadata_cache(bl, prefix, self.METADATA_CACHE)
		
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

			# Query books themselves
			query = 'select _id, file_path, title, author, mime_type, modified_date, thumbnail, file_size ' \
					'from books'
			cursor.execute (query)
		    
			# make a dict cache of paths so the lookup in the loop below is faster.
	        bl_cache = {}
	        for idx,b in enumerate(bl):
            	bl_cache[b.lpath] = idx
		
		    changed = False
		    for i, row in enumerate(cursor):
				#Book(prefix, bookId, lpath, title, author, mime, date, thumbnail_name, size=None, other=None)
				thumbnail = row[6]
				if thumbnail is not None:
					thumbnail = self.normalize_path(prefix + row[6])
				
				book = Book(row[0], prefix, row[1], row[2], row[3], row[4], row[5], thumbnail, row[7])
				book.device_collections = bl_collections.get(row[0], None)
				debug_print('Collections for ' + row[2] + ': ' + str(book.device_collections))
				bl_cache[row[1]] = None
				if bl.add_book(book, replace_metadata=True):
                    changed = True
						
			# Remove books that are no longer in the filesystem. Cache contains
			# indices into the booklist if book not in filesystem, None otherwise
			# Do the operation in reverse order so indices remain valid
			for idx in sorted(bl_cache.itervalues(), reverse=True):
				if idx is not None:
			    	changed = True
			        del bl[idx]			
			
			cursor.close()

			if changed:
	            if oncard == 'carda':
		   	        self.sync_booklists((None, bl, None))
				else:
				    self.sync_booklists((bl, None, None))

		return bl
		
	def sync_booklists(self, booklists, end_session=True):
		debug_print('PRST1: starting sync_booklists')
		
		if booklists[0] is not None:
			booklists[0].rebuild_collections(booklists[0], None)
		if booklists[1] is not None:
			booklists[1].rebuild_collections(booklists[1], 'carda')
		
		USBMS.sync_booklists(self, booklists, end_session=end_session)
        debug_print('PRST1: finished sync_booklists')
	
	def rebuild_collections(self, booklist, oncard):
	    collections_attributes = ['tags']
		debug_print('PRS-T1: starting rebuild_collections')
	
	    prefix = self._card_a_prefix if oncard == 'carda' else self._main_prefix
		source_id = 1 if oncard == 'carda' else 0
		debug_print("SQLite DB Path: " + self.normalize_path(prefix + 'Sony_Reader/database/books.db'))

		collections = booklist.get_collections(collections_attributes)
        #debug_print('Collections', collections)

		with closing(sqlite.connect(self.normalize_path(prefix + 'Sony_Reader/database/books.db'))) as connection:
			cursor = connection.cursor()
						
			if collections:
				# Get existing collections
				query = 'select _id, title ' \
				 		'from collection'
				cursor.execute(query)
				debug_print('Got Existing Collections')
				
				categories = {}
				for i, row in enumerate(cursor):
					categories[row[1]] = row[0]
					
				# Get existing books
				query = 'select file_path, _id ' \
						'from books'
				cursor.execute(query)
				debug_print('Got Existing Books')
				
				dbBooks = {}
				for i, row in enumerate(cursor):
					dbBooks[self.normalize_path(row[0])] = row[1]
				
                # Process any collections that exist
                for category, books in collections.items():
					if categories.get(category, None) is not None:
						query = 'delete from collections where collection_id = ?'
						t = (categories[category],)
						debug_print('Query: ' + query + ' ... ' + str(t))
						cursor.execute(query, t)
	
					for book in books:
                        # debug_print('    Title:', book.title, 'category: ', category)
                        if category not in book.device_collections:
                            book.device_collections.append(category)
							
						if self.normalize_path(book.lpath) not in dbBooks:
							query = 'insert into books ' \
									'(title, author, source_id, added_date, modified_date, file_path, file_name, file_size, mime_type, corrupted, prevent_delete) ' \
									'values (?,?,?,?,?,?,?,?,?,0,0)'
							t = (book.title, book.authors[0], source_id, time.time() * 1000, calendar.timegm(book.datetime), book.lpath, os.path.basename(book.lpath), book.size, book.mime )
							cursor.execute(query, t)
							dbBooks[book.lpath] = cursor.lastrowid
							debug_print('Inserted Unknown Book: ' + book.title)
							
						if category not in categories:
							query = 'insert into collection (title, source_id) values (?,?)'
							t = (category, source_id)
							cursor.execute(query, t)
							categories[category] = cursor.lastrowid
							debug_print('Inserted Unknown Collection: ' + category)
								
						query = 'insert into collections (collection_id, content_id) values (?,?)'
						t = (categories[category], dbBooks[book.lpath])
						cursor.execute(query, t)
						debug_print('Inserted Book Into Collection: ' + book.title + ' -> ' + category)
			
			connection.commit()
			cursor.close()
		
		debug_print('PRS-T1: finished rebuild_collections')
		