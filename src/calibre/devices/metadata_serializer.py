'''
Created on 21 May 2010

@author: charles
'''

from calibre.constants import filesystem_encoding, preferred_encoding
from calibre import isbytestring
import json

class MetadataSerializer(object):

    SERIALIZED_ATTRS = [
        'lpath', 'title', 'authors', 'mime', 'size', 'tags', 'author_sort',
        'title_sort', 'comments', 'category', 'publisher', 'series',
        'series_index', 'rating', 'isbn', 'language', 'application_id',
        'book_producer', 'lccn', 'lcc', 'ddc', 'rights', 'publication_type',
        'uuid',
    ]

    def to_json(self):
        json = {}
        for attr in self.SERIALIZED_ATTRS:
            val = getattr(self, attr)
            if isbytestring(val):
                enc = filesystem_encoding if attr == 'lpath' else preferred_encoding
                val = val.decode(enc, 'replace')
            elif isinstance(val, (list, tuple)):
                val = [x.decode(preferred_encoding, 'replace') if
                        isbytestring(x) else x for x in val]
            json[attr] = val
        return json

    def read_json(self, cache_file):
        with open(cache_file, 'rb') as f:
            js = json.load(f, encoding='utf-8')
        return js

    def write_json(self, js, cache_file):
        with open(cache_file, 'wb') as f:
            json.dump(js, f, indent=2, encoding='utf-8')

    def string_to_value(self, string, col_metadata, column_label=None):
        '''
        if column_label is none, col_metadata must be a dict containing custom
        column metadata for one column. If column_label is not none, then
        col_metadata must be a dict of custom column metadata, with column
        labels as keys. Metadata for standard columns is always assumed to be in
        the col_metadata dict. If column_label is not standard and is not in
        col_metadata, check if it matches a custom column. If so, use that
        column metadata. See get_column_metadata below.
        '''
        pass

    def value_to_display(self, value, col_metadata, column_label=None):
        pass

    def value_to_string (self, value, col_metadata, column_label=None):
        pass

    def get_column_metadata(self, column_label = None, from_book=None):
        '''
        if column_label is None, then from_book must not be None. Returns the
        complete set of custom column metadata for that book.

        If column_label is not None, return the column metadata for the given
        column. This works even if the label is for a built-in column. If
        from_book is None, then column_label must be a current custom column
        label or a standard label. If from_book is not None, then the column
        metadata from that metadata set is returned if it exists, otherwise the
        standard metadata for that column is returned. If neither is found,
        return {}
        '''
        pass

    def get_custom_column_labels(self, book):
        '''
        returns a list of custom column attributes in the book metadata.
        '''
        pass

    def get_standard_column_labels(self):
        '''
        returns a list of standard attributes that should be in any book's
        metadata
        '''
        pass

metadata_serializer = MetadataSerializer()

