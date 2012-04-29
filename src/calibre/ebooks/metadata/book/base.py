#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import copy, traceback

from calibre import prints
from calibre.constants import DEBUG
from calibre.ebooks.metadata.book import (SC_COPYABLE_FIELDS,
        SC_FIELDS_COPY_NOT_NULL, STANDARD_METADATA_FIELDS,
        TOP_LEVEL_IDENTIFIERS, ALL_METADATA_FIELDS)
from calibre.library.field_metadata import FieldMetadata
from calibre.utils.date import isoformat, format_date
from calibre.utils.icu import sort_key
from calibre.utils.formatter import TemplateFormatter

# Special sets used to optimize the performance of getting and setting
# attributes on Metadata objects
SIMPLE_GET = frozenset(STANDARD_METADATA_FIELDS - TOP_LEVEL_IDENTIFIERS)
SIMPLE_SET = frozenset(SIMPLE_GET - {'identifiers'})

def human_readable(size, precision=2):
    """ Convert a size in bytes into megabytes """
    return ('%.'+str(precision)+'f'+ 'MB') % ((size/(1024.*1024.)),)

NULL_VALUES = {
                'user_metadata': {},
                'cover_data'   : (None, None),
                'tags'         : [],
                'identifiers'  : {},
                'languages'    : [],
                'device_collections': [],
                'author_sort_map': {},
                'authors'      : [_('Unknown')],
                'author_sort'  : _('Unknown'),
                'title'        : _('Unknown'),
                'user_categories' : {},
                'author_link_map' : {},
                'language'     : 'und'
}

field_metadata = FieldMetadata()

class SafeFormat(TemplateFormatter):

    def get_value(self, orig_key, args, kwargs):
        if not orig_key:
            return ''
        key = orig_key = orig_key.lower()
        if key != 'title_sort' and key not in TOP_LEVEL_IDENTIFIERS and \
                key not in ALL_METADATA_FIELDS:
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
        if b and ((b['datatype'] == 'int' and self.book.get(key, 0) == 0) or
                  (b['datatype'] == 'float' and self.book.get(key, 0.0) == 0.0)):
            v = ''
        else:
            v = self.book.format_field(key, series_with_index=False)[1]
        if v is None:
            return ''
        if v == '':
            return ''
        return v

# DEPRECATED. This is not thread safe. Do not use.
composite_formatter = SafeFormat()

class Metadata(object):

    '''
    A class representing all the metadata for a book. The various standard metadata
    fields are available as attributes of this object. You can also stick
    arbitrary attributes onto this object.

    Metadata from custom columns should be accessed via the get() method,
    passing in the lookup name for the column, for example: "#mytags".

    Use the :meth:`is_null` method to test if a field is null.

    This object also has functions to format fields into strings.

    The list of standard metadata fields grows with time is in
    :data:`STANDARD_METADATA_FIELDS`.

    Please keep the method based API of this class to a minimum. Every method
    becomes a reserved field name.
    '''

    def __init__(self, title, authors=(_('Unknown'),), other=None, template_cache=None):
        '''
        @param title: title or ``_('Unknown')``
        @param authors: List of strings or []
        @param other: None or a metadata object
        '''
        _data = copy.deepcopy(NULL_VALUES)
        _data.pop('language')
        object.__setattr__(self, '_data', _data)
        if other is not None:
            self.smart_update(other)
        else:
            if title:
                self.title = title
            if authors:
                # List of strings or []
                self.author = list(authors) if authors else []# Needed for backward compatibility
                self.authors = list(authors) if authors else []
        self.formatter = SafeFormat()
        self.template_cache = template_cache

    def is_null(self, field):
        '''
        Return True if the value of field is null in this object.
        'null' means it is unknown or evaluates to False. So a title of
        _('Unknown') is null or a language of 'und' is null.

        Be careful with numeric fields since this will return True for zero as
        well as None.

        Also returns True if the field does not exist.
        '''
        try:
            null_val = NULL_VALUES.get(field, None)
            val = getattr(self, field, None)
            return not val or val == null_val
        except:
            return True

    def __getattribute__(self, field):
        _data = object.__getattribute__(self, '_data')
        if field in SIMPLE_GET:
            return _data.get(field, None)
        if field in TOP_LEVEL_IDENTIFIERS:
            return _data.get('identifiers').get(field, None)
        if field == 'language':
            try:
                return _data.get('languages', [])[0]
            except:
                return NULL_VALUES['language']
        try:
            return object.__getattribute__(self, field)
        except AttributeError:
            pass
        if field in _data['user_metadata'].iterkeys():
            d = _data['user_metadata'][field]
            val = d['#value#']
            if d['datatype'] != 'composite':
                return val
            if val is None:
                d['#value#'] = 'RECURSIVE_COMPOSITE FIELD (Metadata) ' + field
                val = d['#value#'] = self.formatter.safe_format(
                                            d['display']['composite_template'],
                                            self,
                                            _('TEMPLATE ERROR'),
                                            self, column_name=field,
                                            template_cache=self.template_cache).strip()
            return val
        if field.startswith('#') and field.endswith('_index'):
            try:
                return self.get_extra(field[:-6])
            except:
                pass
        raise AttributeError(
                'Metadata object has no attribute named: '+ repr(field))

    def __setattr__(self, field, val, extra=None):
        _data = object.__getattribute__(self, '_data')
        if field in SIMPLE_SET:
            if val is None:
                val = copy.copy(NULL_VALUES.get(field, None))
            _data[field] = val
        elif field in TOP_LEVEL_IDENTIFIERS:
            field, val = self._clean_identifier(field, val)
            identifiers = _data['identifiers']
            identifiers.pop(field, None)
            if val:
                identifiers[field] = val
        elif field == 'identifiers':
            if not val:
                val = copy.copy(NULL_VALUES.get('identifiers', None))
            self.set_identifiers(val)
        elif field == 'language':
            langs = []
            if val and val.lower() != 'und':
                langs = [val]
            _data['languages'] = langs
        elif field in _data['user_metadata'].iterkeys():
            _data['user_metadata'][field]['#value#'] = val
            _data['user_metadata'][field]['#extra#'] = extra
        else:
            # You are allowed to stick arbitrary attributes onto this object as
            # long as they don't conflict with global or user metadata names
            # Don't abuse this privilege
            self.__dict__[field] = val

    def __iter__(self):
        return object.__getattribute__(self, '_data').iterkeys()

    def has_key(self, key):
        return key in object.__getattribute__(self, '_data')

    def deepcopy(self):
        m = Metadata(None)
        m.__dict__ = copy.deepcopy(self.__dict__)
        object.__setattr__(m, '_data', copy.deepcopy(object.__getattribute__(self, '_data')))
        return m

    def deepcopy_metadata(self):
        m = Metadata(None)
        object.__setattr__(m, '_data', copy.deepcopy(object.__getattribute__(self, '_data')))
        return m

    def get(self, field, default=None):
        try:
            return self.__getattribute__(field)
        except AttributeError:
            return default

    def get_extra(self, field, default=None):
        _data = object.__getattribute__(self, '_data')
        if field in _data['user_metadata'].iterkeys():
            try:
                return _data['user_metadata'][field]['#extra#']
            except:
                return default
        raise AttributeError(
                'Metadata object has no attribute named: '+ repr(field))

    def set(self, field, val, extra=None):
        self.__setattr__(field, val, extra)

    def get_identifiers(self):
        '''
        Return a copy of the identifiers dictionary.
        The dict is small, and the penalty for using a reference where a copy is
        needed is large. Also, we don't want any manipulations of the returned
        dict to show up in the book.
        '''
        ans = object.__getattribute__(self,
            '_data')['identifiers']
        if not ans:
            ans = {}
        return copy.deepcopy(ans)

    def _clean_identifier(self, typ, val):
        if typ:
            typ = icu_lower(typ).strip().replace(':', '').replace(',', '')
        if val:
            val = val.strip().replace(',', '|').replace(':', '|')
        return typ, val

    def set_identifiers(self, identifiers):
        '''
        Set all identifiers. Note that if you previously set ISBN, calling
        this method will delete it.
        '''
        cleaned = {}
        for key, val in identifiers.iteritems():
            key, val = self._clean_identifier(key, val)
            if key and val:
                cleaned[key] = val
        object.__getattribute__(self, '_data')['identifiers'] = cleaned

    def set_identifier(self, typ, val):
        'If val is empty, deletes identifier of type typ'
        typ, val = self._clean_identifier(typ, val)
        if not typ:
            return
        identifiers = object.__getattribute__(self,
            '_data')['identifiers']

        identifiers.pop(typ, None)
        if val:
            identifiers[typ] = val

    def has_identifier(self, typ):
        identifiers = object.__getattribute__(self,
            '_data')['identifiers']
        return typ in identifiers

    # field-oriented interface. Intended to be the same as in LibraryDatabase

    def standard_field_keys(self):
        '''
        return a list of all possible keys, even if this book doesn't have them
        '''
        return STANDARD_METADATA_FIELDS

    def custom_field_keys(self):
        '''
        return a list of the custom fields in this book
        '''
        return object.__getattribute__(self, '_data')['user_metadata'].iterkeys()

    def all_field_keys(self):
        '''
        All field keys known by this instance, even if their value is None
        '''
        _data = object.__getattribute__(self, '_data')
        return frozenset(ALL_METADATA_FIELDS.union(_data['user_metadata'].iterkeys()))

    def metadata_for_field(self, key):
        '''
        return metadata describing a standard or custom field.
        '''
        if key not in self.custom_field_keys():
            return self.get_standard_metadata(key, make_copy=False)
        return self.get_user_metadata(key, make_copy=False)

    def all_non_none_fields(self):
        '''
        Return a dictionary containing all non-None metadata fields, including
        the custom ones.
        '''
        result = {}
        _data = object.__getattribute__(self, '_data')
        for attr in STANDARD_METADATA_FIELDS:
            v = _data.get(attr, None)
            if v is not None:
                result[attr] = v
        # separate these because it uses the self.get(), not _data.get()
        for attr in TOP_LEVEL_IDENTIFIERS:
            v = self.get(attr, None)
            if v is not None:
                result[attr] = v
        for attr in _data['user_metadata'].iterkeys():
            v = self.get(attr, None)
            if v is not None:
                result[attr] = v
                if _data['user_metadata'][attr]['datatype'] == 'series':
                    result[attr+'_index'] = _data['user_metadata'][attr]['#extra#']
        return result

    # End of field-oriented interface

    # Extended interfaces. These permit one to get copies of metadata dictionaries, and to
    # get and set custom field metadata

    def get_standard_metadata(self, field, make_copy):
        '''
        return field metadata from the field if it is there. Otherwise return
        None. field is the key name, not the label. Return a copy if requested,
        just in case the user wants to change values in the dict.
        '''
        if field in field_metadata and field_metadata[field]['kind'] == 'field':
            if make_copy:
                return copy.deepcopy(field_metadata[field])
            return field_metadata[field]
        return None

    def get_all_standard_metadata(self, make_copy):
        '''
        return a dict containing all the standard field metadata associated with
        the book.
        '''
        if not make_copy:
            return field_metadata
        res = {}
        for k in field_metadata:
            if field_metadata[k]['kind'] == 'field':
                res[k] = copy.deepcopy(field_metadata[k])
        return res

    def get_all_user_metadata(self, make_copy):
        '''
        return a dict containing all the custom field metadata associated with
        the book.
        '''
        _data = object.__getattribute__(self, '_data')
        user_metadata = _data['user_metadata']
        if not make_copy:
            return user_metadata
        res = {}
        for k in user_metadata:
            res[k] = copy.deepcopy(user_metadata[k])
        return res

    def get_user_metadata(self, field, make_copy):
        '''
        return field metadata from the object if it is there. Otherwise return
        None. field is the key name, not the label. Return a copy if requested,
        just in case the user wants to change values in the dict.
        '''
        _data = object.__getattribute__(self, '_data')
        _data = _data['user_metadata']
        if field in _data:
            if make_copy:
                return copy.deepcopy(_data[field])
            return _data[field]
        return None

    def set_all_user_metadata(self, metadata):
        '''
        store custom field metadata into the object. Field is the key name
        not the label
        '''
        if metadata is None:
            traceback.print_stack()
            return

        um = {}
        for key, meta in metadata.iteritems():
            m = meta.copy()
            if '#value#' not in m:
                if m['datatype'] == 'text' and m['is_multiple']:
                    m['#value#'] = []
                else:
                    m['#value#'] = None
            um[key] = m
        _data = object.__getattribute__(self, '_data')
        _data['user_metadata'].update(um)

    def set_user_metadata(self, field, metadata):
        '''
        store custom field metadata for one column into the object. Field is
        the key name not the label
        '''
        if field is not None:
            if not field.startswith('#'):
                raise AttributeError(
                        'Custom field name %s must begin with \'#\''%repr(field))
            if metadata is None:
                traceback.print_stack()
                return
            m = dict(metadata)
            # Copying the elements should not be necessary. The objects referenced
            # in the dict should not change. Of course, they can be replaced.
            # for k,v in metadata.iteritems():
            #     m[k] = copy.copy(v)
            if '#value#' not in m:
                if m['datatype'] == 'text' and m['is_multiple']:
                    m['#value#'] = []
                else:
                    m['#value#'] = None
            _data = object.__getattribute__(self, '_data')
            _data['user_metadata'][field] = m

    def template_to_attribute(self, other, ops):
        '''
        Takes a list [(src,dest), (src,dest)], evaluates the template in the
        context of other, then copies the result to self[dest]. This is on a
        best-efforts basis. Some assignments can make no sense.
        '''
        if not ops:
            return
        formatter = SafeFormat()
        for op in ops:
            try:
                src = op[0]
                dest = op[1]
                val = formatter.safe_format\
                    (src, other, 'PLUGBOARD TEMPLATE ERROR', other)
                if dest == 'tags':
                    self.set(dest, [f.strip() for f in val.split(',') if f.strip()])
                elif dest == 'authors':
                    self.set(dest, [f.strip() for f in val.split('&') if f.strip()])
                else:
                    self.set(dest, val)
            except:
                if DEBUG:
                    traceback.print_exc()

    # Old Metadata API {{{
    def print_all_attributes(self):
        for x in STANDARD_METADATA_FIELDS:
            prints('%s:'%x, getattr(self, x, 'None'))
        for x in self.custom_field_keys():
            meta = self.get_user_metadata(x, make_copy=False)
            if meta is not None:
                prints(x, meta)
        prints('--------------')

    def smart_update(self, other, replace_metadata=False):
        '''
        Merge the information in `other` into self. In case of conflicts, the information
        in `other` takes precedence, unless the information in `other` is NULL.
        '''
        def copy_not_none(dest, src, attr):
            v = getattr(src, attr, None)
            if v not in (None, NULL_VALUES.get(attr, None)):
                setattr(dest, attr, copy.deepcopy(v))

        if other.title and other.title != _('Unknown'):
            self.title = other.title
            if hasattr(other, 'title_sort'):
                self.title_sort = other.title_sort

        if other.authors and other.authors[0] != _('Unknown'):
            self.authors = list(other.authors)
            if hasattr(other, 'author_sort_map'):
                self.author_sort_map = dict(other.author_sort_map)
            if hasattr(other, 'author_sort'):
                self.author_sort = other.author_sort

        if replace_metadata:
            # SPECIAL_FIELDS = frozenset(['lpath', 'size', 'comments', 'thumbnail'])
            for attr in SC_COPYABLE_FIELDS:
                setattr(self, attr, getattr(other, attr, 1.0 if \
                        attr == 'series_index' else None))
            self.tags = other.tags
            self.cover_data = getattr(other, 'cover_data',
                                      NULL_VALUES['cover_data'])
            self.set_all_user_metadata(other.get_all_user_metadata(make_copy=True))
            for x in SC_FIELDS_COPY_NOT_NULL:
                copy_not_none(self, other, x)
            if callable(getattr(other, 'get_identifiers', None)):
                self.set_identifiers(other.get_identifiers())
            # language is handled below
        else:
            for attr in SC_COPYABLE_FIELDS:
                copy_not_none(self, other, attr)
            for x in SC_FIELDS_COPY_NOT_NULL:
                copy_not_none(self, other, x)

            if other.tags:
                # Case-insensitive but case preserving merging
                lotags = [t.lower() for t in other.tags]
                lstags = [t.lower() for t in self.tags]
                ot, st = map(frozenset, (lotags, lstags))
                for t in st.intersection(ot):
                    sidx = lstags.index(t)
                    oidx = lotags.index(t)
                    self.tags[sidx] = other.tags[oidx]
                self.tags += [t for t in other.tags if t.lower() in ot-st]

            if getattr(other, 'cover_data', False):
                other_cover = other.cover_data[-1]
                self_cover = self.cover_data[-1] if self.cover_data else ''
                if not self_cover: self_cover = ''
                if not other_cover: other_cover = ''
                if len(other_cover) > len(self_cover):
                    self.cover_data = other.cover_data

            if callable(getattr(other, 'custom_field_keys', None)):
                for x in other.custom_field_keys():
                    meta = other.get_user_metadata(x, make_copy=True)
                    if meta is not None:
                        self_tags = self.get(x, [])
                        self.set_user_metadata(x, meta) # get... did the deepcopy
                        other_tags = other.get(x, [])
                        if meta['datatype'] == 'text' and meta['is_multiple']:
                            # Case-insensitive but case preserving merging
                            lotags = [t.lower() for t in other_tags]
                            try:
                                lstags = [t.lower() for t in self_tags]
                            except TypeError:
                                # Happens if x is not a text, is_multiple field
                                # on self
                                lstags = []
                                self_tags = []
                            ot, st = map(frozenset, (lotags, lstags))
                            for t in st.intersection(ot):
                                sidx = lstags.index(t)
                                oidx = lotags.index(t)
                                self_tags[sidx] = other_tags[oidx]
                            self_tags += [t for t in other_tags if t.lower() in ot-st]
                            setattr(self, x, self_tags)

            my_comments = getattr(self, 'comments', '')
            other_comments = getattr(other, 'comments', '')
            if not my_comments:
                my_comments = ''
            if not other_comments:
                other_comments = ''
            if len(other_comments.strip()) > len(my_comments.strip()):
                self.comments = other_comments

            # Copy all the non-none identifiers
            if callable(getattr(other, 'get_identifiers', None)):
                d = self.get_identifiers()
                s = other.get_identifiers()
                d.update([v for v in s.iteritems() if v[1] is not None])
                self.set_identifiers(d)
            else:
                # other structure not Metadata. Copy the top-level identifiers
                for attr in TOP_LEVEL_IDENTIFIERS:
                    copy_not_none(self, other, attr)

        other_lang = getattr(other, 'languages', [])
        if other_lang and other_lang != ['und']:
            self.languages = list(other_lang)
        if not getattr(self, 'series', None):
            self.series_index = None

    def format_series_index(self, val=None):
        from calibre.ebooks.metadata import fmt_sidx
        v = self.series_index if val is None else val
        try:
            x = float(v)
        except (ValueError, TypeError):
            x = 1
        return fmt_sidx(x)

    def authors_from_string(self, raw):
        from calibre.ebooks.metadata import string_to_authors
        self.authors = string_to_authors(raw)

    def format_authors(self):
        from calibre.ebooks.metadata import authors_to_string
        return authors_to_string(self.authors)

    def format_tags(self):
        return u', '.join([unicode(t) for t in sorted(self.tags, key=sort_key)])

    def format_rating(self, v=None, divide_by=1.0):
        if v is None:
            if self.rating is not None:
                return unicode(self.rating/divide_by)
            return u'None'
        return unicode(v/divide_by)

    def format_field(self, key, series_with_index=True):
        '''
        Returns the tuple (display_name, formatted_value)
        '''
        name, val, ign, ign = self.format_field_extended(key, series_with_index)
        return (name, val)

    def format_field_extended(self, key, series_with_index=True):
        from calibre.ebooks.metadata import authors_to_string
        '''
        returns the tuple (display_name, formatted_value, original_value,
        field_metadata)
        '''

        # Handle custom series index
        if key.startswith('#') and key.endswith('_index'):
            tkey = key[:-6] # strip the _index
            cmeta = self.get_user_metadata(tkey, make_copy=False)
            if cmeta and cmeta['datatype'] == 'series':
                if self.get(tkey):
                    res = self.get_extra(tkey)
                    return (unicode(cmeta['name']+'_index'),
                            self.format_series_index(res), res, cmeta)
                else:
                    return (unicode(cmeta['name']+'_index'), '', '', cmeta)

        if key in self.custom_field_keys():
            res = self.get(key, None)       # get evaluates all necessary composites
            cmeta = self.get_user_metadata(key, make_copy=False)
            name = unicode(cmeta['name'])
            if res is None or res == '':    # can't check "not res" because of numeric fields
                return (name, res, None, None)
            orig_res = res
            datatype = cmeta['datatype']
            if datatype == 'text' and cmeta['is_multiple']:
                res = cmeta['is_multiple']['list_to_ui'].join(res)
            elif datatype == 'series' and series_with_index:
                if self.get_extra(key) is not None:
                    res = res + \
                        ' [%s]'%self.format_series_index(val=self.get_extra(key))
            elif datatype == 'datetime':
                res = format_date(res, cmeta['display'].get('date_format','dd MMM yyyy'))
            elif datatype == 'bool':
                res = _('Yes') if res else _('No')
            elif datatype == 'rating':
                res = u'%.2g'%(res/2.0)
            elif datatype in ['int', 'float']:
                try:
                    fmt = cmeta['display'].get('number_format', None)
                    res = fmt.format(res)
                except:
                    pass
            return (name, unicode(res), orig_res, cmeta)

        # convert top-level ids into their value
        if key in TOP_LEVEL_IDENTIFIERS:
            fmeta = field_metadata['identifiers']
            name = key
            res = self.get(key, None)
            return (name, res, res, fmeta)

        # Translate aliases into the standard field name
        fmkey = field_metadata.search_term_to_field_key(key)
        if fmkey in field_metadata and field_metadata[fmkey]['kind'] == 'field':
            res = self.get(key, None)
            fmeta = field_metadata[fmkey]
            name = unicode(fmeta['name'])
            if res is None or res == '':
                return (name, res, None, None)
            orig_res = res
            name = unicode(fmeta['name'])
            datatype = fmeta['datatype']
            if key == 'authors':
                res = authors_to_string(res)
            elif key == 'series_index':
                res = self.format_series_index(res)
            elif datatype == 'text' and fmeta['is_multiple']:
                if isinstance(res, dict):
                    res = [k + ':' + v for k,v in res.items()]
                res = fmeta['is_multiple']['list_to_ui'].join(sorted(res, key=sort_key))
            elif datatype == 'series' and series_with_index:
                res = res + ' [%s]'%self.format_series_index()
            elif datatype == 'datetime':
                res = format_date(res, fmeta['display'].get('date_format','dd MMM yyyy'))
            elif datatype == 'rating':
                res = u'%.2g'%(res/2.0)
            elif key == 'size':
                res = human_readable(res)
            return (name, unicode(res), orig_res, fmeta)

        return (None, None, None, None)

    def __unicode__(self):
        '''
        A string representation of this object, suitable for printing to
        console
        '''
        from calibre.ebooks.metadata import authors_to_string
        ans = []
        def fmt(x, y):
            ans.append(u'%-20s: %s'%(unicode(x), unicode(y)))

        fmt('Title', self.title)
        if self.title_sort:
            fmt('Title sort', self.title_sort)
        if self.authors:
            fmt('Author(s)',  authors_to_string(self.authors) + \
               ((' [' + self.author_sort + ']')
                if self.author_sort and self.author_sort != _('Unknown') else ''))
        if self.publisher:
            fmt('Publisher', self.publisher)
        if getattr(self, 'book_producer', False):
            fmt('Book Producer', self.book_producer)
        if self.tags:
            fmt('Tags', u', '.join([unicode(t) for t in self.tags]))
        if self.series:
            fmt('Series', self.series + ' #%s'%self.format_series_index())
        if not self.is_null('languages'):
            fmt('Languages', ', '.join(self.languages))
        if self.rating is not None:
            fmt('Rating', (u'%.2g'%(float(self.rating)/2.0)) if self.rating
                    else u'')
        if self.timestamp is not None:
            fmt('Timestamp', isoformat(self.timestamp))
        if self.pubdate is not None:
            fmt('Published', isoformat(self.pubdate))
        if self.rights is not None:
            fmt('Rights', unicode(self.rights))
        if self.identifiers:
            fmt('Identifiers', u', '.join(['%s:%s'%(k, v) for k, v in
                self.identifiers.iteritems()]))
        if self.comments:
            fmt('Comments', self.comments)

        for key in self.custom_field_keys():
            val = self.get(key, None)
            if val:
                (name, val) = self.format_field(key)
                fmt(name, unicode(val))
        return u'\n'.join(ans)

    def to_html(self):
        '''
        A HTML representation of this object.
        '''
        from calibre.ebooks.metadata import authors_to_string
        ans = [(_('Title'), unicode(self.title))]
        ans += [(_('Author(s)'), (authors_to_string(self.authors) if self.authors else _('Unknown')))]
        ans += [(_('Publisher'), unicode(self.publisher))]
        ans += [(_('Producer'), unicode(self.book_producer))]
        ans += [(_('Comments'), unicode(self.comments))]
        ans += [('ISBN', unicode(self.isbn))]
        ans += [(_('Tags'), u', '.join([unicode(t) for t in self.tags]))]
        if self.series:
            ans += [(_('Series'), unicode(self.series) + ' #%s'%self.format_series_index())]
        ans += [(_('Languages'), u', '.join(self.languages))]
        if self.timestamp is not None:
            ans += [(_('Timestamp'), unicode(self.timestamp.isoformat(' ')))]
        if self.pubdate is not None:
            ans += [(_('Published'), unicode(self.pubdate.isoformat(' ')))]
        if self.rights is not None:
            ans += [(_('Rights'), unicode(self.rights))]
        for key in self.custom_field_keys():
            val = self.get(key, None)
            if val:
                (name, val) = self.format_field(key)
                ans += [(name, val)]
        for i, x in enumerate(ans):
            ans[i] = u'<tr><td><b>%s</b></td><td>%s</td></tr>'%x
        return u'<table>%s</table>'%u'\n'.join(ans)

    def __str__(self):
        return self.__unicode__().encode('utf-8')

    def __nonzero__(self):
        return bool(self.title or self.author or self.comments or self.tags)

    # }}}

