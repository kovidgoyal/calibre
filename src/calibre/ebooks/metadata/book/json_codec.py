'''
Created on 4 Jun 2010

@author: charles
'''

import json, traceback
from datetime import datetime, time

from calibre.ebooks.metadata.book import SERIALIZABLE_FIELDS
from calibre.constants import filesystem_encoding, preferred_encoding
from calibre.library.field_metadata import FieldMetadata
from calibre import isbytestring
from polyglot.builtins import iteritems, itervalues, as_bytes
from polyglot.binary import as_base64_unicode, from_base64_bytes

# Translate datetimes to and from strings. The string form is the datetime in
# UTC. The returned date is also UTC


def string_to_datetime(src):
    from calibre.utils.iso8601 import parse_iso8601
    if src != "None":
        try:
            return parse_iso8601(src)
        except Exception:
            pass
    return None


def datetime_to_string(dateval):
    from calibre.utils.date import isoformat, UNDEFINED_DATE, local_tz
    if dateval is None:
        return "None"
    if not isinstance(dateval, datetime):
        dateval = datetime.combine(dateval, time())
    if hasattr(dateval, 'tzinfo') and dateval.tzinfo is None:
        dateval = dateval.replace(tzinfo=local_tz)
    if dateval <= UNDEFINED_DATE:
        return "None"
    return isoformat(dateval)


def encode_thumbnail(thumbnail):
    '''
    Encode the image part of a thumbnail, then return the 3 part tuple
    '''
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


def decode_thumbnail(tup):
    '''
    Decode an encoded thumbnail into its 3 component parts
    '''
    if tup is None:
        return None
    return (tup[0], tup[1], from_base64_bytes(tup[2]))


def object_to_unicode(obj, enc=preferred_encoding):

    def dec(x):
        return x.decode(enc, 'replace')

    if isbytestring(obj):
        return dec(obj)
    if isinstance(obj, (list, tuple)):
        return [dec(x) if isbytestring(x) else object_to_unicode(x) for x in obj]
    if isinstance(obj, dict):
        ans = {}
        for k, v in obj.items():
            k = object_to_unicode(k)
            v = object_to_unicode(v)
            ans[k] = v
        return ans
    return obj


def encode_is_multiple(fm):
    if fm.get('is_multiple', None):
        # migrate is_multiple back to a character
        fm['is_multiple2'] = fm.get('is_multiple', {})
        dt = fm.get('datatype', None)
        if dt == 'composite':
            fm['is_multiple'] = ','
        else:
            fm['is_multiple'] =  '|'
    else:
        fm['is_multiple'] = None
        fm['is_multiple2'] = {}


def decode_is_multiple(fm):
    im = fm.get('is_multiple2',  None)
    if im:
        fm['is_multiple'] = im
        del fm['is_multiple2']
    else:
        # Must migrate the is_multiple from char to dict
        im = fm.get('is_multiple',  {})
        if im:
            dt = fm.get('datatype', None)
            if dt == 'composite':
                im = {'cache_to_list': ',', 'ui_to_list': ',',
                      'list_to_ui': ', '}
            elif fm.get('display', {}).get('is_names', False):
                im = {'cache_to_list': '|', 'ui_to_list': '&',
                      'list_to_ui': ', '}
            else:
                im = {'cache_to_list': '|', 'ui_to_list': ',',
                      'list_to_ui': ', '}
        elif im is None:
            im = {}
        fm['is_multiple'] = im


class JsonCodec:

    def __init__(self, field_metadata=None):
        self.field_metadata = field_metadata or FieldMetadata()

    def encode_to_file(self, file_, booklist):
        data = json.dumps(self.encode_booklist_metadata(booklist), indent=2)
        if not isinstance(data, bytes):
            data = data.encode('utf-8')
        file_.write(data)

    def encode_booklist_metadata(self, booklist):
        result = []
        for book in booklist:
            result.append(self.encode_book_metadata(book))
        return result

    def encode_book_metadata(self, book):
        result = {}
        for key in SERIALIZABLE_FIELDS:
            result[key] = self.encode_metadata_attr(book, key)
        return result

    def encode_metadata_attr(self, book, key):
        if key == 'user_metadata':
            meta = book.get_all_user_metadata(make_copy=True)
            for fm in itervalues(meta):
                if fm['datatype'] == 'datetime':
                    fm['#value#'] = datetime_to_string(fm['#value#'])
                encode_is_multiple(fm)
            return meta
        if key in self.field_metadata:
            datatype = self.field_metadata[key]['datatype']
        else:
            datatype = None
        value = book.get(key)
        if key == 'thumbnail':
            return encode_thumbnail(value)
        elif isbytestring(value):  # str includes bytes
            enc = filesystem_encoding if key == 'lpath' else preferred_encoding
            return object_to_unicode(value, enc=enc)
        elif datatype == 'datetime':
            return datetime_to_string(value)
        else:
            return object_to_unicode(value)

    def decode_from_file(self, file_, booklist, book_class, prefix):
        js = []
        try:
            js = json.load(file_)
            for item in js:
                entry = self.raw_to_book(item, book_class, prefix)
                if entry is not None:
                    booklist.append(entry)
        except:
            print('exception during JSON decode_from_file')
            traceback.print_exc()

    def raw_to_book(self, json_book, book_class, prefix):
        try:
            book = book_class(prefix, json_book.get('lpath', None))
            for key,val in iteritems(json_book):
                meta = self.decode_metadata(key, val)
                if key == 'user_metadata':
                    book.set_all_user_metadata(meta)
                else:
                    if key == 'classifiers':
                        key = 'identifiers'
                    setattr(book, key, meta)
            return book
        except:
            print('exception during JSON decoding')
            traceback.print_exc()

    def decode_metadata(self, key, value):
        if key == 'classifiers':
            key = 'identifiers'
        if key == 'user_metadata':
            for fm in itervalues(value):
                if fm['datatype'] == 'datetime':
                    fm['#value#'] = string_to_datetime(fm['#value#'])
                decode_is_multiple(fm)
            return value
        elif key in self.field_metadata:
            if self.field_metadata[key]['datatype'] == 'datetime':
                return string_to_datetime(value)
        if key == 'thumbnail':
            return decode_thumbnail(value)
        return value
