"""
Created on 4 Jun 2010

@author: charles
"""

import json
import traceback
from datetime import date, datetime, time
from typing import IO, TYPE_CHECKING, cast

from calibre.constants import filesystem_encoding, preferred_encoding
from calibre.ebooks.metadata.book import SERIALIZABLE_FIELDS
from calibre.library.field_metadata import FieldMetadata
from polyglot.binary import as_base64_unicode, from_base64_bytes
from polyglot.builtins import as_bytes

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable

    from calibre.ebooks.metadata.book.base import FieldMetadataDict, Metadata

# Translate datetimes to and from strings. The string form is the datetime in
# UTC. The returned date is also UTC


def string_to_datetime(src: str | None) -> datetime | None:
    from calibre.utils.iso8601 import parse_iso8601

    if src != 'None':
        try:
            return parse_iso8601(src)
        except Exception:
            pass
    return None


def datetime_to_string(dateval: date | None) -> str:
    from calibre.utils.date import UNDEFINED_DATE, isoformat, local_tz

    if dateval is None:
        return 'None'
    if not isinstance(dateval, datetime):
        dateval = datetime.combine(dateval, time())
    if dateval.tzinfo is None:
        dateval = dateval.replace(tzinfo=local_tz)
    if dateval <= UNDEFINED_DATE:
        return 'None'
    return isoformat(dateval)


def encode_thumbnail(thumbnail: object) -> tuple[object, object, str] | None:
    """
    Encode the image part of a thumbnail, then return the 3 part tuple
    """
    from calibre.utils.imghdr import identify

    if thumbnail is None:
        return None
    if not isinstance(thumbnail, (tuple, list)):
        try:
            width, height = identify(as_bytes(thumbnail))[1:]
            if width < 0 or height < 0:
                return None
            thumbnail = (width, height, thumbnail)
        except Exception:
            return None
    return (thumbnail[0], thumbnail[1], as_base64_unicode(thumbnail[2]))


def decode_thumbnail(tup: tuple[int, int, str] | list[int | str] | None) -> tuple[int | str, int | str, bytes] | None:
    """
    Decode an encoded thumbnail into its 3 component parts
    """
    if tup is None:
        return None
    return (tup[0], tup[1], from_base64_bytes(tup[2]))


def object_to_unicode(obj: object, enc: str = preferred_encoding) -> object:

    def dec(x: bytes) -> str:
        return x.decode(enc, 'replace')

    if isinstance(obj, bytes):
        return dec(obj)
    if isinstance(obj, (list, tuple)):
        return [dec(x) if isinstance(x, bytes) else object_to_unicode(x) for x in obj]
    if isinstance(obj, dict):
        ans = {}
        for k, v in obj.items():
            k = object_to_unicode(k)
            v = object_to_unicode(v)
            ans[k] = v
        return ans
    return obj


def encode_is_multiple(fm: dict[str, object]) -> None:
    if fm.get('is_multiple'):
        # migrate is_multiple back to a character
        fm['is_multiple2'] = fm.get('is_multiple', {})
        dt = fm.get('datatype', None)
        if dt == 'composite':
            fm['is_multiple'] = ','
        else:
            fm['is_multiple'] = '|'
    else:
        fm['is_multiple'] = None
        fm['is_multiple2'] = {}


def decode_is_multiple(fm: dict[str, object]) -> None:
    im = fm.get('is_multiple2', None)
    if im:
        fm['is_multiple'] = im
        del fm['is_multiple2']
    else:
        # Must migrate the is_multiple from char to dict
        im = fm.get('is_multiple', {})
        if im:
            dt = fm.get('datatype', None)
            if dt == 'composite':
                im = {'cache_to_list': ',', 'ui_to_list': ',', 'list_to_ui': ', '}
            # display is a dict, cast as an assert would need restructuring this elif chain
            elif cast('dict[str, object]', fm.get('display', {})).get('is_names', False):
                im = {'cache_to_list': '|', 'ui_to_list': '&', 'list_to_ui': ', '}
            else:
                im = {'cache_to_list': '|', 'ui_to_list': ',', 'list_to_ui': ', '}
        elif im is None:
            im = {}
        fm['is_multiple'] = im


class JsonCodec:
    def __init__(self, field_metadata: FieldMetadata | None = None) -> None:
        self.field_metadata = field_metadata or FieldMetadata()

    def encode_to_file(self, file_: IO[bytes], booklist: Iterable[Metadata]) -> None:
        data = json.dumps(self.encode_booklist_metadata(booklist), indent=2)
        if not isinstance(data, bytes):
            data = data.encode('utf-8')
        file_.write(data)

    def encode_booklist_metadata(self, booklist: Iterable[Metadata]) -> list[dict[str, object]]:
        result = []
        for book in booklist:
            result.append(self.encode_book_metadata(book))
        return result

    def encode_book_metadata(self, book: Metadata) -> dict[str, object]:
        result = {}
        for key in SERIALIZABLE_FIELDS:
            result[key] = self.encode_metadata_attr(book, key)
        return result

    def encode_metadata_attr(self, book: Metadata, key: str) -> object:
        if key == 'user_metadata':
            meta: dict[str, dict[str, object]] = {}
            for fkey, ufm in book.get_all_user_metadata(make_copy=True).items():
                # the serialized form is not a FieldMetadataDict, see encode_is_multiple()
                meta[fkey] = fm = dict(ufm)
                if fm['datatype'] == 'datetime':
                    val = fm['#value#']
                    assert val is None or isinstance(val, date)
                    fm['#value#'] = datetime_to_string(val)
                encode_is_multiple(fm)
            return meta
        if key in self.field_metadata:
            datatype = self.field_metadata[key]['datatype']
        else:
            datatype = None
        value = book.get(key)
        if key == 'thumbnail':
            return encode_thumbnail(value)
        elif isinstance(value, bytes):  # str includes bytes
            enc = filesystem_encoding if key == 'lpath' else preferred_encoding
            return object_to_unicode(value, enc=enc)
        elif datatype == 'datetime':
            assert value is None or isinstance(value, date)
            return datetime_to_string(value)
        else:
            return object_to_unicode(value)

    def decode_from_file(self, file_: IO[bytes], booklist: list[Metadata], book_class: Callable[[str, str], Metadata], prefix: str) -> None:
        js = []
        try:
            js = json.load(file_)
            for item in js:
                entry = self.raw_to_book(item, book_class, prefix)
                if entry is not None:
                    booklist.append(entry)
        except Exception:
            print('exception during JSON decode_from_file')
            traceback.print_exc()

    def raw_to_book(self, json_book: dict[str, object], book_class: Callable[[str, str], Metadata], prefix: str) -> Metadata | None:
        try:
            book = book_class(prefix, cast('str', json_book.get('lpath', None)))  # device books always have an lpath
            for key, val in json_book.items():
                meta = self.decode_metadata(key, val)
                if key == 'user_metadata':
                    book.set_all_user_metadata(cast('dict[str, FieldMetadataDict]', meta))  # see decode_metadata()
                else:
                    if key == 'classifiers':
                        key = 'identifiers'
                    setattr(book, key, meta)
            return book
        except Exception:
            print('exception during JSON decoding')
            traceback.print_exc()

    def decode_metadata(self, key: str, value: object) -> object:
        if key == 'classifiers':
            key = 'identifiers'
        if key == 'user_metadata':
            um = cast('dict[str, dict[str, object]]', value)  # as created by encode_metadata_attr()
            for fm in um.values():
                if fm['datatype'] == 'datetime':
                    val = fm['#value#']
                    # encoded by datetime_to_string(), string_to_datetime() returns None for non-strings
                    fm['#value#'] = string_to_datetime(val) if isinstance(val, str) else None
                decode_is_multiple(fm)
            return um
        elif key in self.field_metadata:
            if self.field_metadata[key]['datatype'] == 'datetime':
                return string_to_datetime(cast('str', value))  # encoded by datetime_to_string()
        if key == 'thumbnail':
            return decode_thumbnail(cast('list[int | str] | None', value))  # encoded by encode_thumbnail()
        return value
