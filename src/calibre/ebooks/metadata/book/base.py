#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import copy
import traceback

from calibre import prints
from calibre.ebooks.metadata.book import COPYABLE_METADATA_FIELDS
from calibre.ebooks.metadata.book import STANDARD_METADATA_FIELDS
from calibre.utils.date import isoformat


NULL_VALUES = {
                'user_metadata': {},
                'cover_data'   : (None, None),
                'tags'         : [],
                'classifiers'  : {},
                'languages'    : [],
                'device_collections': [],
                'author_sort_map': {},
                'authors'      : [_('Unknown')],
                'title'        : _('Unknown'),
}

class Metadata(object):

    '''
    A class representing all the metadata for a book.

    Please keep the method based API of this class to a minimum. Every method
    becomes a reserved field name.
    '''

    def __init__(self, title, authors=(_('Unknown'),), other=None):
        '''
        @param title: title or ``_('Unknown')``
        @param authors: List of strings or []
        @param other: None or a metadata object
        '''
        object.__setattr__(self, '_data', copy.deepcopy(NULL_VALUES))
        if other is not None:
            self.smart_update(other)
        else:
            if title:
                self.title = title
            if authors:
                #: List of strings or []
                self.author = list(authors) if authors else []# Needed for backward compatibility
                self.authors = list(authors) if authors else []

    def __getattribute__(self, field):
        _data = object.__getattribute__(self, '_data')
        if field in STANDARD_METADATA_FIELDS:
            return _data.get(field, None)
        try:
            return object.__getattribute__(self, field)
        except AttributeError:
            pass
        if field in _data['user_metadata'].iterkeys():
            return _data['user_metadata'][field]['#value#']
        raise AttributeError(
                'Metadata object has no attribute named: '+ repr(field))

    def __setattr__(self, field, val):
        _data = object.__getattribute__(self, '_data')
        if field in STANDARD_METADATA_FIELDS:
            if not val:
                val = NULL_VALUES.get(field, None)
            _data[field] = val
        elif field in _data['user_metadata'].iterkeys():
            _data['user_metadata'][field]['#value#'] = val
        else:
            # You are allowed to stick arbitrary attributes onto this object as
            # long as they dont conflict with global or user metadata names
            # Don't abuse this privilege
            self.__dict__[field] = val

    def get(self, field):
        return self.__getattribute__(field)

    def set(self, field, val):
        self.__setattr__(field, val)

    @property
    def user_metadata_keys(self):
        'The set of user metadata names this object knows about'
        _data = object.__getattribute__(self, '_data')
        return frozenset(_data['user_metadata'].iterkeys())

    @property
    def all_user_metadata(self):
        '''
        return a dict containing all the custom field metadata associated with
        the book. Return a deep copy, just in case the user wants to change
        values in the dict (json does).
        '''
        _data = object.__getattribute__(self, '_data')
        _data = _data['user_metadata']
        res = {}
        for k in _data:
            res[k] = copy.deepcopy(_data[k])
        return res

    def get_user_metadata(self, field):
        '''
        return field metadata from the object if it is there. Otherwise return
        None. field is the key name, not the label. Return a shallow copy,
        just in case the user wants to change values in the dict (json does).
        '''
        _data = object.__getattribute__(self, '_data')
        _data = _data['user_metadata']
        if field in _data:
            return copy.deepcopy(_data[field])
        return None

    def set_all_user_metadata(self, metadata):
        '''
        store custom field metadata into the object. Field is the key name
        not the label
        '''
        if metadata is None:
            traceback.print_stack()
        else:
            for key in metadata:
                self.set_user_metadata(key, metadata[key])

    def set_user_metadata(self, field, metadata):
        '''
        store custom field metadata for one column into the object. Field is
        the key name not the label
        '''
        if field is not None:
            if metadata is None:
                traceback.print_stack()
            metadata = copy.deepcopy(metadata)
            if '#value#' not in metadata:
                metadata['#value#'] = None
            _data = object.__getattribute__(self, '_data')
            _data['user_metadata'][field] = metadata

    @property
    def all_attributes(self):
        result = {}
        _data = object.__getattribute__(self, '_data')
        for attr in STANDARD_METADATA_FIELDS:
            v = _data.get(attr, None)
            if v is not None:
                result[attr] = v
        for attr in self.user_metadata_keys:
            if self.get(attr) is not None:
                result[attr] = self.get(attr)
        return result

    # Old Metadata API {{{
    @staticmethod
    def copy(mi):
        ans = Metadata(mi.title, mi.authors)
        for attr in STANDARD_METADATA_FIELDS:
            if hasattr(mi, attr):
                setattr(ans, attr, copy.deepcopy(getattr(mi, attr)))
        for x in mi.user_metadata_keys:
            meta = mi.get_user_metadata(x)
            if meta is not None:
                ans.set_user_metadata(x, meta) # get... did the deep copy

    def print_all_attributes(self):
        for x in STANDARD_METADATA_FIELDS:
            prints('%s:'%x, getattr(self, x, 'None'))
        for x in self.user_metadata_keys:
            meta = self.get_user_metadata(x)
            if meta is not None:
                prints(x, meta)
        prints('--------------')

    def smart_update(self, other, replace_metadata=False):
        '''
        Merge the information in C{other} into self. In case of conflicts, the information
        in C{other} takes precedence, unless the information in other is NULL.
        '''
        if other.title and other.title != _('Unknown'):
            self.title = other.title

        if other.authors and other.authors[0] != _('Unknown'):
            self.authors = other.authors

        for attr in COPYABLE_METADATA_FIELDS:
            if replace_metadata:
                setattr(self, attr, getattr(other, attr, 1.0 if \
                        attr == 'series_index' else None))
            elif hasattr(other, attr):
                val = getattr(other, attr)
                if val is not None:
                    setattr(self, attr, copy.deepcopy(val))

        if replace_metadata:
            self.tags = other.tags
        elif other.tags:
            self.tags += other.tags
        self.tags = list(set(self.tags))

        if getattr(other, 'author_sort_map', None):
            self.author_sort_map.update(other.author_sort_map)

        if getattr(other, 'cover_data', False):
            other_cover = other.cover_data[-1]
            self_cover = self.cover_data[-1] if self.cover_data else ''
            if not self_cover: self_cover = ''
            if not other_cover: other_cover = ''
            if len(other_cover) > len(self_cover):
                self.cover_data = other.cover_data

        if getattr(other, 'user_metadata_keys', None):
            for x in other.user_metadata_keys:
                meta = other.get_user_metadata(x)
                if meta is not None or replace_metadata:
                    self.set_user_metadata(x, meta) # get... did the deepcopy

        if replace_metadata:
            self.comments = getattr(other, 'comments', '')
        else:
            my_comments = getattr(self, 'comments', '')
            other_comments = getattr(other, 'comments', '')
            if not my_comments:
                my_comments = ''
            if not other_comments:
                other_comments = ''
            if len(other_comments.strip()) > len(my_comments.strip()):
                self.comments = other_comments

        other_lang = getattr(other, 'language', None)
        if other_lang and other_lang.lower() != 'und':
            self.language = other_lang


    def format_series_index(self):
        from calibre.ebooks.metadata import fmt_sidx
        try:
            x = float(self.series_index)
        except ValueError:
            x = 1
        return fmt_sidx(x)

    def authors_from_string(self, raw):
        from calibre.ebooks.metadata import string_to_authors
        self.authors = string_to_authors(raw)

    def format_authors(self):
        from calibre.ebooks.metadata import authors_to_string
        return authors_to_string(self.authors)

    def format_tags(self):
        return u', '.join([unicode(t) for t in self.tags])

    def format_rating(self):
        return unicode(self.rating)

    def __unicode__(self):
        from calibre.ebooks.metadata import authors_to_string
        ans = []
        def fmt(x, y):
            ans.append(u'%-20s: %s'%(unicode(x), unicode(y)))

        fmt('Title', self.title)
        if self.title_sort:
            fmt('Title sort', self.title_sort)
        if self.authors:
            fmt('Author(s)',  authors_to_string(self.authors) + \
               ((' [' + self.author_sort + ']') if self.author_sort else ''))
        if self.publisher:
            fmt('Publisher', self.publisher)
        if getattr(self, 'book_producer', False):
            fmt('Book Producer', self.book_producer)
        if self.category:
            fmt('Category', self.category)
        if self.comments:
            fmt('Comments', self.comments)
        if self.isbn:
            fmt('ISBN', self.isbn)
        if self.tags:
            fmt('Tags', u', '.join([unicode(t) for t in self.tags]))
        if self.series:
            fmt('Series', self.series + ' #%s'%self.format_series_index())
        if self.language:
            fmt('Language', self.language)
        if self.rating is not None:
            fmt('Rating', self.rating)
        if self.timestamp is not None:
            fmt('Timestamp', isoformat(self.timestamp))
        if self.pubdate is not None:
            fmt('Published', isoformat(self.pubdate))
        if self.rights is not None:
            fmt('Rights', unicode(self.rights))
        if self.lccn:
            fmt('LCCN', unicode(self.lccn))
        if self.lcc:
            fmt('LCC', unicode(self.lcc))
        if self.ddc:
            fmt('DDC', unicode(self.ddc))
        # CUSTFIELD: What to do about custom fields?
        return u'\n'.join(ans)

    def to_html(self):
        from calibre.ebooks.metadata import authors_to_string
        ans = [(_('Title'), unicode(self.title))]
        ans += [(_('Author(s)'), (authors_to_string(self.authors) if self.authors else _('Unknown')))]
        ans += [(_('Publisher'), unicode(self.publisher))]
        ans += [(_('Producer'), unicode(self.book_producer))]
        ans += [(_('Comments'), unicode(self.comments))]
        ans += [('ISBN', unicode(self.isbn))]
        if self.lccn:
            ans += [('LCCN', unicode(self.lccn))]
        if self.lcc:
            ans += [('LCC', unicode(self.lcc))]
        if self.ddc:
            ans += [('DDC', unicode(self.ddc))]
        ans += [(_('Tags'), u', '.join([unicode(t) for t in self.tags]))]
        if self.series:
            ans += [(_('Series'), unicode(self.series)+ ' #%s'%self.format_series_index())]
        ans += [(_('Language'), unicode(self.language))]
        if self.timestamp is not None:
            ans += [(_('Timestamp'), unicode(self.timestamp.isoformat(' ')))]
        if self.pubdate is not None:
            ans += [(_('Published'), unicode(self.pubdate.isoformat(' ')))]
        if self.rights is not None:
            ans += [(_('Rights'), unicode(self.rights))]
        for i, x in enumerate(ans):
            ans[i] = u'<tr><td><b>%s</b></td><td>%s</td></tr>'%x
        # CUSTFIELD: What to do about custom fields
        return u'<table>%s</table>'%u'\n'.join(ans)

    def __str__(self):
        return self.__unicode__().encode('utf-8')

    def __nonzero__(self):
        return bool(self.title or self.author or self.comments or self.tags)

    # }}}
