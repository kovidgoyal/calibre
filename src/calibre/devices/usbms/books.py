# -*- coding: utf-8 -*-

__license__ = 'GPL 3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

import os, re, time, sys

from calibre.ebooks.metadata.book.base import Metadata
from calibre.devices.mime import mime_type_ext
from calibre.devices.interface import BookList as _BookList
from calibre.constants import preferred_encoding
from calibre import isbytestring
from calibre.utils.config import prefs, tweaks

class Book(Metadata):
    def __init__(self, prefix, lpath, size=None, other=None):
        from calibre.ebooks.metadata.meta import path_to_ext

        Metadata.__init__(self, '')

        self._new_book = False
        self.device_collections = []
        self.path = os.path.join(prefix, lpath)
        if os.sep == '\\':
            self.path = self.path.replace('/', '\\')
            self.lpath = lpath.replace('\\', '/')
        else:
            self.lpath = lpath
        self.mime = mime_type_ext(path_to_ext(lpath))
        self.size = size # will be set later if None
        try:
            self.datetime = time.gmtime(os.path.getctime(self.path))
        except:
            self.datetime = time.gmtime()
        if other:
            self.smart_update(other)

    def __eq__(self, other):
        # use lpath because the prefix can change, changing path
        return self.lpath == getattr(other, 'lpath', None)

    @dynamic_property
    def db_id(self):
        doc = '''The database id in the application database that this file corresponds to'''
        def fget(self):
            match = re.search(r'_(\d+)$', self.lpath.rpartition('.')[0])
            if match:
                return int(match.group(1))
            return None
        return property(fget=fget, doc=doc)

    @dynamic_property
    def title_sorter(self):
        doc = '''String to sort the title. If absent, title is returned'''
        def fget(self):
            return re.sub('^\s*A\s+|^\s*The\s+|^\s*An\s+', '', self.title).rstrip()
        return property(doc=doc, fget=fget)

    @dynamic_property
    def thumbnail(self):
        return None

class BookList(_BookList):

    def __init__(self, oncard, prefix, settings):
        _BookList.__init__(self, oncard, prefix, settings)
        self._bookmap = {}

    def supports_collections(self):
        return False

    def add_book(self, book, replace_metadata):
        try:
            b = self.index(book)
        except (ValueError, IndexError):
            b = None
        if b is None:
            self.append(book)
            return True
        if replace_metadata:
            self[b].smart_update(book, replace_metadata=True)
            return True
        return False

    def remove_book(self, book):
        self.remove(book)

    def get_collections(self):
        return {}

class CollectionsBookList(BookList):

    def supports_collections(self):
        return True

    def compute_category_name(self, attr, category, cust_field_meta):
        renames = tweaks['sony_collection_renaming_rules']
        attr_name = renames.get(attr, None)
        if attr_name is None:
            if attr in cust_field_meta:
                attr_name = '(%s)'%cust_field_meta[attr]['name']
            else:
                attr_name = ''
        elif attr_name != '':
            attr_name = '(%s)'%attr_name
        cat_name = '%s %s'%(category, attr_name)
        return cat_name.strip()

    def get_collections(self, collection_attributes):
        from calibre.devices.usbms.driver import debug_print
        debug_print('Starting get_collections:', prefs['manage_device_metadata'])
        debug_print('Renaming rules:', tweaks['sony_collection_renaming_rules'])
        collections = {}
        # This map of sets is used to avoid linear searches when testing for
        # book equality
        collections_lpaths = {}
        for book in self:
            # Make sure we can identify this book via the lpath
            lpath = getattr(book, 'lpath', None)
            if lpath is None:
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
            meta_vals = book.get_all_non_none_attributes()
            cust_field_meta = book.get_all_user_metadata(make_copy=False)
            for attr in attrs:
                attr = attr.strip()
                ign, val = book.format_field(attr,
                                             ignore_series_index=True,
                                             return_multiples_as_list=True)
                if not val: continue
                if isbytestring(val):
                    val = val.decode(preferred_encoding, 'replace')
                if isinstance(val, (list, tuple)):
                    val = list(val)
                else:
                    val = [val]
                for category in val:
                    is_series = False
                    if attr in cust_field_meta: # is a custom field
                        fm = cust_field_meta[attr]
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
                                 meta_vals.get('series', None) == category):
                            is_series = True
                    cat_name = self.compute_category_name(attr, category,
                                                          cust_field_meta)
                    if cat_name not in collections:
                        collections[cat_name] = []
                        collections_lpaths[cat_name] = set()
                    if lpath in collections_lpaths[cat_name]:
                        continue
                    collections_lpaths[cat_name].add(lpath)
                    if is_series:
                        collections[cat_name].append(
                            (book, meta_vals.get(attr+'_index', sys.maxint)))
                    else:
                        collections[cat_name].append(
                            (book, meta_vals.get('title_sort', 'zzzz')))
        # Sort collections
        result = {}
        for category, books in collections.items():
            books.sort(cmp=lambda x,y:cmp(x[1], y[1]))
            result[category] = [x[0] for x in books]
        return result

    def rebuild_collections(self, booklist, oncard):
        '''
        For each book in the booklist for the card oncard, remove it from all
        its current collections, then add it to the collections specified in
        device_collections.

        oncard is None for the main memory, carda for card A, cardb for card B,
        etc.

        booklist is the object created by the :method:`books` call above.
        '''
        pass
