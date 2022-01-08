#!/usr/bin/env python


__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

from calibre.ebooks.metadata.book import TOP_LEVEL_IDENTIFIERS, ALL_METADATA_FIELDS

from calibre.utils.formatter import TemplateFormatter
from numbers import Number


class SafeFormat(TemplateFormatter):

    def __init__(self):
        TemplateFormatter.__init__(self)

    def get_value(self, orig_key, args, kwargs):
        if not orig_key or isinstance(orig_key, Number):
            return ''
        key = orig_key = orig_key.lower()
        if (key != 'title_sort' and key not in TOP_LEVEL_IDENTIFIERS and
                key not in ALL_METADATA_FIELDS):
            from calibre.ebooks.metadata.book.base import field_metadata
            key = field_metadata.search_term_to_field_key(key)
            if key is None or (self.book and
                                key not in self.book.all_field_keys()):
                if hasattr(self.book, orig_key):
                    key = orig_key
                else:
                    raise ValueError(_('Value: unknown field ') + orig_key)
        try:
            b = self.book.get_user_metadata(key, False)
        except:
            b = None
        if b and b['datatype'] in {'int', 'float'} and self.book.get(key, None) is None:
            v = ''
        else:
            v = self.book.format_field(key, series_with_index=False)[1]
        if v is None:
            return ''
        if v == '':
            return ''
        return v
