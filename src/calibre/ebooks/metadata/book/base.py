#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import copy

from calibre.ebooks.metadata.book import RESERVED_METADATA_FIELDS

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
    This class must expose a superset of the API of MetaInformation in terms
    of attribute access and methods. Only the __init__ method is different.
    MetaInformation will simply become a function that creates and fills in
    the attributes of this class.

    Please keep the method based API of this class to a minimum. Every method
    becomes a reserved field name.
    '''

    def __init__(self):
        object.__setattr__(self, '_data', copy.deepcopy(NULL_VALUES))

    def __getattribute__(self, field):
        _data = object.__getattribute__(self, '_data')
        if field in RESERVED_METADATA_FIELDS:
            return _data.get(field, None)
        try:
            return object.__getattribute__(self, field)
        except AttributeError:
            pass
        if field in _data['user_metadata'].iterkeys():
            # TODO: getting user metadata values
            pass
        raise AttributeError(
                'Metadata object has no attribute named: '+ repr(field))


    def __setattr__(self, field, val):
        _data = object.__getattribute__(self, '_data')
        if field in RESERVED_METADATA_FIELDS:
            if field != 'user_metadata':
                if not val:
                    val = NULL_VALUES[field]
                _data[field] = val
            else:
                raise AttributeError('You cannot set user_metadata directly.')
        elif field in _data['user_metadata'].iterkeys():
            # TODO: Setting custom column values
            pass
        else:
            # You are allowed to stick arbitrary attributes onto this object as
            # long as they dont conflict with global or user metadata names
            # Don't abuse this privilege
            self.__dict__[field] = val

    @property
    def user_metadata_names(self):
        'The set of user metadata names this object knows about'
        _data = object.__getattribute__(self, '_data')
        return frozenset(_data['user_metadata'].iterkeys())

    # Old MetaInformation API {{{
    def copy(self):
        pass

    def print_all_attributes(self):
        pass

    def smart_update(self, other, replace_metadata=False):
        pass

    def format_series_index(self):
        pass

    def authors_from_string(self, raw):
        pass

    def format_authors(self):
        pass

    def format_tags(self):
        pass

    def format_rating(self):
        return unicode(self.rating)

    def __unicode__(self):
        pass

    def to_html(self):
        pass

    def __str__(self):
        return self.__unicode__().encode('utf-8')

    def __nonzero__(self):
        return True

    # }}}

# We don't need reserved field names for this object any more. Lets just use a
# protocol like the last char of a user field label should be _ when using this
# object
# So mi.tags returns the builtin tags and mi.tags_ returns the user tags

