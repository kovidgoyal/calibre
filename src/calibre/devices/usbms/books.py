# -*- coding: utf-8 -*-

__license__ = 'GPL 3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

import os, re, time, sys

from calibre.ebooks.metadata import title_sort
from calibre.ebooks.metadata.book.base import Metadata
from calibre.devices.mime import mime_type_ext
from calibre.devices.interface import BookList as _BookList
from calibre.constants import preferred_encoding
from calibre import isbytestring, force_unicode
from calibre.utils.config import device_prefs, tweaks
from calibre.utils.icu import strcmp
from calibre.utils.formatter import EvalFormatter

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
            return title_sort(self.title)
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
        '''
        Add the book to the booklist, if needed. Return None if the book is
        already there and not updated, otherwise return the book.
        '''
        try:
            b = self.index(book)
        except (ValueError, IndexError):
            b = None
        if b is None:
            self.append(book)
            return book
        if replace_metadata:
            self[b].smart_update(book, replace_metadata=True)
            return self[b]
        return None

    def remove_book(self, book):
        self.remove(book)

    def get_collections(self):
        return {}

class CollectionsBookList(BookList):

    def supports_collections(self):
        return True

    def in_category_sort_rules(self, attr):
        sorts = tweaks['sony_collection_sorting_rules']
        for attrs,sortattr in sorts:
            if attr in attrs or '*' in attrs:
                return sortattr
        return None

    def compute_category_name(self, field_key, field_value, field_meta):
        renames = tweaks['sony_collection_renaming_rules']
        field_name = renames.get(field_key, None)
        if field_name is None:
            if field_meta['is_custom']:
                field_name = field_meta['name']
            else:
                field_name = ''
        cat_name = EvalFormatter().safe_format(
                        fmt=tweaks['sony_collection_name_template'],
                        kwargs={'category':field_name, 'value':field_value},
                        error_value='GET_CATEGORY', book=None)
        return cat_name.strip()

    def get_collections(self, collection_attributes):
        from calibre.devices.usbms.driver import debug_print
        debug_print('Starting get_collections:', device_prefs['manage_device_metadata'])
        debug_print('Renaming rules:', tweaks['sony_collection_renaming_rules'])
        debug_print('Formatting template:', tweaks['sony_collection_name_template'])
        debug_print('Sorting rules:', tweaks['sony_collection_sorting_rules'])

        # Complexity: we can use renaming rules only when using automatic
        # management. Otherwise we don't always have the metadata to make the
        # right decisions
        use_renaming_rules = device_prefs['manage_device_metadata'] == 'on_connect'

        collections = {}

        # get the special collection names
        all_by_author = ''
        all_by_title = ''
        ca = []
        all_by_something = []
        for c in collection_attributes:
            if c.startswith('aba:') and c[4:].strip():
                all_by_author = c[4:].strip()
            elif c.startswith('abt:') and c[4:].strip():
                all_by_title = c[4:].strip()
            elif c.startswith('abs:') and c[4:].strip():
                name = c[4:].strip()
                sby = self.in_category_sort_rules(name)
                if sby is None:
                    sby = name
                if name and sby:
                    all_by_something.append((name, sby))
            else:
                ca.append(c.lower())
        collection_attributes = ca

        for book in self:
            tsval = book.get('_pb_title_sort',
                             book.get('title_sort', book.get('title', 'zzzz')))
            asval = book.get('_pb_author_sort', book.get('author_sort', ''))
            # Make sure we can identify this book via the lpath
            lpath = getattr(book, 'lpath', None)
            if lpath is None:
                continue
            # Decide how we will build the collections. The default: leave the
            # book in all existing collections. Do not add any new ones.
            attrs = ['device_collections']
            if getattr(book, '_new_book', False):
                if device_prefs['manage_device_metadata'] == 'manual':
                    # Ensure that the book is in all the book's existing
                    # collections plus all metadata collections
                    attrs += collection_attributes
                else:
                    # For new books, both 'on_send' and 'on_connect' do the same
                    # thing. The book's existing collections are ignored. Put
                    # the book in collections defined by its metadata.
                    attrs = collection_attributes
            elif device_prefs['manage_device_metadata'] == 'on_connect':
                # For existing books, modify the collections only if the user
                # specified 'on_connect'
                attrs = collection_attributes
            for attr in attrs:
                attr = attr.strip()
                # If attr is device_collections, then we cannot use
                # format_field, because we don't know the fields where the
                # values came from.
                if attr == 'device_collections':
                    doing_dc = True
                    val = book.device_collections # is a list
                else:
                    doing_dc = False
                    ign, val, orig_val, fm = book.format_field_extended(attr)

                if not val: continue
                if isbytestring(val):
                    val = val.decode(preferred_encoding, 'replace')
                if isinstance(val, (list, tuple)):
                    val = list(val)
                elif fm['datatype'] == 'series':
                    val = [orig_val]
                elif fm['datatype'] == 'text' and fm['is_multiple']:
                    val = orig_val
                elif fm['datatype'] == 'composite' and fm['is_multiple']:
                    val = [v.strip() for v in
                           val.split(fm['is_multiple']['ui_to_list'])]
                else:
                    val = [val]

                sort_attr = self.in_category_sort_rules(attr)
                for category in val:
                    is_series = False
                    if doing_dc:
                        # Attempt to determine if this value is a series by
                        # comparing it to the series name.
                        if category == book.series:
                            is_series = True
                    elif fm['is_custom']: # is a custom field
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
                    if use_renaming_rules:
                        cat_name = self.compute_category_name(attr, category, fm)
                    else:
                        cat_name = category

                    if cat_name not in collections:
                        collections[cat_name] = {}
                    if use_renaming_rules and sort_attr:
                        sort_val = book.get(sort_attr, None)
                        collections[cat_name][lpath] = (book, sort_val, tsval)
                    elif is_series:
                        if doing_dc:
                            collections[cat_name][lpath] = \
                                (book, book.get('series_index', sys.maxint), tsval)
                        else:
                            collections[cat_name][lpath] = \
                                (book, book.get(attr+'_index', sys.maxint), tsval)
                    else:
                        if lpath not in collections[cat_name]:
                            collections[cat_name][lpath] = (book, tsval, tsval)

            # All books by author
            if all_by_author:
                if all_by_author not in collections:
                    collections[all_by_author] = {}
                collections[all_by_author][lpath] = (book, asval, tsval)
            # All books by title
            if all_by_title:
                if all_by_title not in collections:
                    collections[all_by_title] = {}
                collections[all_by_title][lpath] = (book, tsval, asval)
            for (n, sb) in all_by_something:
                if n not in collections:
                    collections[n] = {}
                collections[n][lpath] = (book, book.get(sb, ''), tsval)

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
