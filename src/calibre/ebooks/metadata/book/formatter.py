#!/usr/bin/env python


__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

from numbers import Number

from calibre.ebooks.metadata.book import ALL_METADATA_FIELDS, TOP_LEVEL_IDENTIFIERS
from calibre.utils.formatter import TemplateFormatter
from calibre.utils.localization import _


class SafeFormat(TemplateFormatter):

    def __init__(self):
        TemplateFormatter.__init__(self)

    def get_value(self, key, args, kwargs):
        if not key or isinstance(key, Number):
            return ''
        orig_key = key = key.lower()
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
        if self.book is None:
            return ''
        try:
            b = self.book.get_user_metadata(key, False)
        except Exception:
            b = None
        if b and b['datatype'] in {'int', 'float'} and self.book.get(key, None) is None:
            v = ''
        else:
            v = self.book.format_field(key, series_with_index=False)[1]
        if v is None:
            return ''
        return v
