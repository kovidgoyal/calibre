'''
Created on 4 Jun 2010

@author: charles
'''

from base64 import b64encode, b64decode
import json, traceback
from datetime import datetime, time

from calibre.ebooks.metadata.book import SERIALIZABLE_FIELDS
from calibre.constants import filesystem_encoding, preferred_encoding
from calibre.library.field_metadata import FieldMetadata
from calibre.utils.date import parse_date, isoformat, UNDEFINED_DATE, local_tz
from calibre import isbytestring

# Translate datetimes to and from strings. The string form is the datetime in
# UTC. The returned date is also UTC
def string_to_datetime(src):
    if src == "None":
        return None
    return parse_date(src)

def datetime_to_string(dateval):
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
    from calibre.utils.magick import Image

    if thumbnail is None:
        return None
    if not isinstance(thumbnail, (tuple, list)):
        try:
            img = Image()
            img.load(thumbnail)
            width, height = img.size
            thumbnail = (width, height, thumbnail)
        except:
            return None
    return (thumbnail[0], thumbnail[1], b64encode(str(thumbnail[2])))

def decode_thumbnail(tup):
    '''
    Decode an encoded thumbnail into its 3 component parts
    '''
    if tup is None:
        return None
    return (tup[0], tup[1], b64decode(tup[2]))

def object_to_unicode(obj, enc=preferred_encoding):

    def dec(x):
        return x.decode(enc, 'replace')

    if isbytestring(obj):
        return dec(obj)
    if isinstance(obj, (list, tuple)):
        return [dec(x) if isbytestring(x) else x for x in obj]
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

class JsonCodec(object):

    def __init__(self):
        self.field_metadata = FieldMetadata()

    def encode_to_file(self, file_, booklist):
        file_.write(json.dumps(self.encode_booklist_metadata(booklist),
                              indent=2, encoding='utf-8'))

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
            for fm in meta.itervalues():
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
        elif isbytestring(value): # str includes bytes
            enc = filesystem_encoding if key == 'lpath' else preferred_encoding
            return object_to_unicode(value, enc=enc)
        elif datatype == 'datetime':
            return datetime_to_string(value)
        else:
            return object_to_unicode(value)

    def decode_from_file(self, file_, booklist, book_class, prefix):
        js = []
        try:
            js = json.load(file_, encoding='utf-8')
            self.raw_to_booklist(js, booklist, book_class, prefix)
            for item in js:
                booklist.append(self.raw_to_book(item, book_class, prefix))
        except:
            print 'exception during JSON decode_from_file'
            traceback.print_exc()

    def raw_to_book(self, json_book, book_class, prefix):
        try:
            book = book_class(prefix, json_book.get('lpath', None))
            for key,val in json_book.iteritems():
                meta = self.decode_metadata(key, val)
                if key == 'user_metadata':
                    book.set_all_user_metadata(meta)
                else:
                    if key == 'classifiers':
                        key = 'identifiers'
                    setattr(book, key, meta)
            return book
        except:
            print 'exception during JSON decoding'
            traceback.print_exc()

    def decode_metadata(self, key, value):
        if key == 'classifiers':
            key = 'identifiers'
        if key == 'user_metadata':
            for fm in value.itervalues():
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
