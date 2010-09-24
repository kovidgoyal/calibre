'''
Created on 4 Jun 2010

@author: charles
'''

from base64 import b64encode, b64decode
import json
import traceback

from calibre.ebooks.metadata.book import SERIALIZABLE_FIELDS
from calibre.constants import filesystem_encoding, preferred_encoding
from calibre.library.field_metadata import FieldMetadata
from calibre.utils.date import parse_date, isoformat, UNDEFINED_DATE
from calibre.utils.magick import Image
from calibre import isbytestring

# Translate datetimes to and from strings. The string form is the datetime in
# UTC. The returned date is also UTC
def string_to_datetime(src):
    if src == "None":
        return None
    return parse_date(src)

def datetime_to_string(dateval):
    if dateval is None or dateval == UNDEFINED_DATE:
        return "None"
    return isoformat(dateval)

def encode_thumbnail(thumbnail):
    '''
    Encode the image part of a thumbnail, then return the 3 part tuple
    '''
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

class JsonCodec(object):

    def __init__(self):
        self.field_metadata = FieldMetadata()

    def encode_to_file(self, file, booklist):
        file.write(json.dumps(self.encode_booklist_metadata(booklist),
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
            for k in meta:
                if meta[k]['datatype'] == 'datetime':
                    meta[k]['#value#'] = datetime_to_string(meta[k]['#value#'])
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

    def decode_from_file(self, file, booklist, book_class, prefix):
        js = []
        try:
            js = json.load(file, encoding='utf-8')
            for item in js:
                book = book_class(prefix, item.get('lpath', None))
                for key in item.keys():
                    meta = self.decode_metadata(key, item[key])
                    if key == 'user_metadata':
                        book.set_all_user_metadata(meta)
                    else:
                        setattr(book, key, meta)
                booklist.append(book)
        except:
            print 'exception during JSON decoding'
            traceback.print_exc()

    def decode_metadata(self, key, value):
        if key == 'user_metadata':
            for k in value:
                if value[k]['datatype'] == 'datetime':
                    value[k]['#value#'] = string_to_datetime(value[k]['#value#'])
            return value
        elif key in self.field_metadata:
            if self.field_metadata[key]['datatype'] == 'datetime':
                return string_to_datetime(value)
        if key == 'thumbnail':
            return decode_thumbnail(value)
        return value
