__license__   = 'GPL v3'
__copyright__ = '2010-2012, , Timothy Legge <timlegge at gmail.com> and David Forrester <davidfor@internode.on.net>'
__docformat__ = 'restructuredtext en'

import os, time, sys

from calibre.constants import preferred_encoding, DEBUG
from calibre import isbytestring, force_unicode
from calibre.utils.icu import strcmp

from calibre.devices.usbms.books import Book as Book_
from calibre.devices.usbms.books import CollectionsBookList
from calibre.utils.config import prefs
from calibre.utils.date import parse_date
from calibre.devices.usbms.driver import debug_print
from calibre.ebooks.metadata import author_to_author_sort

class Book(Book_):

    def __init__(self, prefix, lpath, title=None, authors=None, mime=None, date=None, ContentType=None,
                 thumbnail_name=None, size=0, other=None):
#        debug_print('Book::__init__ - title=', title)
        show_debug = title is not None and title.lower().find("xxxxx") >= 0
        if show_debug:
            debug_print("Book::__init__ - title=", title, 'authors=', authors)
            debug_print("Book::__init__ - other=", other)
        Book_.__init__(self, prefix, lpath, size, other)

        if title is not None and len(title) > 0:
            self.title = title

        if authors is not None and len(authors) > 0:
            self.authors_from_string(authors)
            if self.author_sort is None or self.author_sort == "Unknown":
                self.author_sort = author_to_author_sort(authors)

        self.mime = mime

        self.size = size # will be set later if None

        if ContentType == '6' and date is not None:
            try:
                self.datetime = time.strptime(date, "%Y-%m-%dT%H:%M:%S.%f")
            except:
                try:
                    self.datetime = time.strptime(date.split('+')[0], "%Y-%m-%dT%H:%M:%S")
                except:
                    try:
                        self.datetime = time.strptime(date.split('+')[0], "%Y-%m-%d")
                    except:
                        try:
                            self.datetime = parse_date(date,
                                    assume_utc=True).timetuple()
                        except:
                            try:
                                self.datetime = time.gmtime(os.path.getctime(self.path))
                            except:
                                self.datetime = time.gmtime()

        self.contentID = None
        self.current_shelves    = []
        self.kobo_collections   = []

        if thumbnail_name is not None:
            self.thumbnail = ImageWrapper(thumbnail_name)

        if show_debug:
            debug_print("Book::__init__ - self=", self)


class ImageWrapper(object):
    def __init__(self, image_path):
        self.image_path = image_path


class KTCollectionsBookList(CollectionsBookList):

    def get_collections(self, collection_attributes):
        debug_print("KTCollectionsBookList:get_collections - start - collection_attributes=", collection_attributes)

        collections = {}

        ca = []
        for c in collection_attributes:
            ca.append(c.lower())
        collection_attributes = ca
        debug_print("KTCollectionsBookList:get_collections - collection_attributes=", collection_attributes)

        for book in self:
            tsval = book.get('title_sort', book.title)
            if tsval is None:
                tsval = book.title

            show_debug = self.is_debugging_title(tsval) or tsval is None
            if show_debug: # or len(book.device_collections) > 0:
                debug_print('KTCollectionsBookList:get_collections - tsval=', tsval, "book.title=", book.title, "book.title_sort=", book.title_sort)
                debug_print('KTCollectionsBookList:get_collections - book.device_collections=', book.device_collections)
#                debug_print(book)
            # Make sure we can identify this book via the lpath
            lpath = getattr(book, 'lpath', None)
            if lpath is None:
                continue
            # If the book is not in the current library, we don't want to use the metadtaa for the collections
            if book.application_id is None:
#                debug_print("KTCollectionsBookList:get_collections - Book not in current library")
                continue
            # Decide how we will build the collections. The default: leave the
            # book in all existing collections. Do not add any new ones.
            attrs = ['device_collections']
            if getattr(book, '_new_book', False):
                if prefs['manage_device_metadata'] == 'manual':
                    # Ensure that the book is in all the book's existing
                    # collections plus all metadata collections
                    attrs += collection_attributes
                else:
                    # For new books, both 'on_send' and 'on_connect' do the same
                    # thing. The book's existing collections are ignored. Put
                    # the book in collections defined by its metadata.
                    attrs = collection_attributes
            elif prefs['manage_device_metadata'] == 'on_connect':
                # For existing books, modify the collections only if the user
                # specified 'on_connect'
                attrs = collection_attributes
                book.device_collections = []
            if show_debug:
                debug_print("KTCollectionsBookList:get_collections - attrs=", attrs)

            for attr in attrs:
                attr = attr.strip()
                if show_debug:
                    debug_print("KTCollectionsBookList:get_collections - attr='%s'"%attr)
                # If attr is device_collections, then we cannot use
                # format_field, because we don't know the fields where the
                # values came from.
                if attr == 'device_collections':
                    doing_dc = True
                    val = book.device_collections # is a list
                    if show_debug:
                        debug_print("KTCollectionsBookList:get_collections - adding book.device_collections", book.device_collections)
                # If the book is not in the current library, we don't want to use the metadtaa for the collections
                elif book.application_id is None:
#                    debug_print("KTCollectionsBookList:get_collections - Book not in current library")
                    continue
                else:
                    doing_dc = False
                    ign, val, orig_val, fm = book.format_field_extended(attr)
                    val = book.get(attr, None)
                    if show_debug:
                        debug_print("KTCollectionsBookList:get_collections - not device_collections")
                        debug_print('          ign=', ign, ', val=', val, ' orig_val=', orig_val, 'fm=', fm)
                        debug_print('          val=', val)
                if not val: continue
                if isbytestring(val):
                    val = val.decode(preferred_encoding, 'replace')
                if isinstance(val, (list, tuple)):
                    val = list(val)
#                    debug_print("KTCollectionsBookList:get_collections - val is list=", val)
                elif fm is not None and fm['datatype'] == 'series':
                    val = [orig_val]
                elif fm is not None and fm['datatype'] == 'text' and fm['is_multiple']:
                    if isinstance(orig_val, (list, tuple)):
                        val = orig_val
                    else:
                        val = [orig_val]
                    if show_debug:
                        debug_print("KTCollectionsBookList:get_collections - val is text and multiple", val)
                elif fm is not None and fm['datatype'] == 'composite' and fm['is_multiple']:
                    if show_debug:
                        debug_print("KTCollectionsBookList:get_collections - val is compositeand multiple", val)
                    val = [v.strip() for v in
                           val.split(fm['is_multiple']['ui_to_list'])]
                else:
                    val = [val]
                if show_debug:
                    debug_print("KTCollectionsBookList:get_collections - val=", val)

                for category in val:
#                    debug_print("KTCollectionsBookList:get_collections - category=", category)
                    is_series = False
                    if doing_dc:
                        # Attempt to determine if this value is a series by
                        # comparing it to the series name.
                        if category == book.series:
                            is_series = True
                    elif fm is not None and fm['is_custom']: # is a custom field
                        if fm['datatype'] == 'text' and len(category) > 1 and \
                                category[0] == '[' and category[-1] == ']':
                            continue
                        if fm['datatype'] == 'series':
                            is_series = True
                    else:                       # is a standard field
                        if attr == 'tags' and len(category) > 1 and \
                                category[0] == '[' and category[-1] == ']':
                            continue
                        if attr == 'series' or \
                                ('series' in collection_attributes and
                                 book.get('series', None) == category):
                            is_series = True
                    cat_name = category.strip(' ,')

                    if cat_name not in collections:
                        collections[cat_name] = {}
                        if show_debug:
                            debug_print("KTCollectionsBookList:get_collections - created collection for cat_name", cat_name)
                    if lpath not in collections[cat_name]:
                        if is_series:
                            if doing_dc:
                                collections[cat_name][lpath] = \
                                    (book, book.get('series_index', sys.maxint), tsval)
                            else:
                                collections[cat_name][lpath] = \
                                    (book, book.get(attr+'_index', sys.maxint), tsval)
                        else:
                            collections[cat_name][lpath] = (book, tsval, tsval)
                        if show_debug:
                            debug_print("KTCollectionsBookList:get_collections - added book to collection for cat_name", cat_name)
                    if show_debug:
                        debug_print("KTCollectionsBookList:get_collections - cat_name", cat_name)

        # Sort collections
        result = {}

        def none_cmp(xx, yy):
            x = xx[1]
            y = yy[1]
            if x is None and y is None:
                # No sort_key needed here, because defaults are ascii
                return cmp(xx[2], yy[2])
            if x is None:
                return 1
            if y is None:
                return -1
            if isinstance(x, basestring) and isinstance(y, basestring):
                c = strcmp(force_unicode(x), force_unicode(y))
            else:
                c = cmp(x, y)
            if c != 0:
                return c
            # same as above -- no sort_key needed here
            return cmp(xx[2], yy[2])

        for category, lpaths in collections.items():
            books = lpaths.values()
            books.sort(cmp=none_cmp)
            result[category] = [x[0] for x in books]
        debug_print("KTCollectionsBookList:get_collections - end")
        return result

    def set_debugging_title(self, title):
        self.debugging_title = title

    def is_debugging_title(self, title):
        if not DEBUG:
            return False
#        debug_print("KTCollectionsBookList:is_debugging - title=", title, "self.debugging_title=", self.debugging_title)
        is_debugging = self.debugging_title is not None and len(self.debugging_title) > 0 and title is not None and (title.lower().find(self.debugging_title.lower()) >= 0 or len(title) == 0)
#        debug_print("KTCollectionsBookList:is_debugging - is_debugging=", is_debugging)

        return is_debugging
