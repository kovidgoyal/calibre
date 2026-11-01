#!/usr/bin/env python
# License: GPLv3 Copyright: 2013, Kovid Goyal <kovid at kovidgoyal.net>

from numbers import Number
from typing import TYPE_CHECKING, cast

from calibre.ebooks.metadata.book import ALL_METADATA_FIELDS, TOP_LEVEL_IDENTIFIERS
from calibre.utils.formatter import TemplateFormatter
from calibre.utils.localization import _

if TYPE_CHECKING:
    from collections.abc import Sequence

    from calibre.utils.formatter import Kwargs


class SafeFormat(TemplateFormatter):
    def __init__(self) -> None:
        TemplateFormatter.__init__(self)

    def get_value(self, key: int | str, args: Sequence[object], kwargs: Kwargs) -> str:
        if not key or isinstance(key, (int, Number)):  # int is a virtual subclass of Number, spelled out for the type checker
            return ''
        orig_key = key = key.lower()
        if key != 'title_sort' and key not in TOP_LEVEL_IDENTIFIERS and key not in ALL_METADATA_FIELDS:
            from calibre.ebooks.metadata.book.base import field_metadata

            # grouped search terms (which map to lists) are not valid here
            key = cast('str', field_metadata.search_term_to_field_key(key))
            if key is None or (self.book and key not in self.book.all_field_keys()):
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
