#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

'''
All fields must have a NULL value represented as None for simple types,
an empty list/dictionary for complex types and (None, None) for cover_data
'''

SOCIAL_METADATA_FIELDS = frozenset([
    'tags', # Ordered list
    # A floating point number between 0 and 10
    'rating',
    # A simple HTML enabled string
    'comments',
    # A simple string
    'series',
    # A floating point number
    'series_index',
    # Of the form { scheme1:value1, scheme2:value2}
    # For example: {'isbn':'123456789', 'doi':'xxxx', ... }
    'classifiers',
    'isbn', # Pseudo field for convenience, should get/set isbn classifier

])

PUBLICATION_METADATA_FIELDS = frozenset([
    # title must never be None. Should be _('Unknown')
    'title',
    # Pseudo field that can be set, but if not set is auto generated
    # from title and languages
    'title_sort',
    # Ordered list of authors. Must never be None, can be [_('Unknown')]
    'authors',
    # Pseudo field that can be set, but if not set is auto generated
    # from authors and languages
    'author_sort',
    'book_producer',
    # Dates and times must be timezone aware
    'timestamp',
    'pubdate',
    'rights',
    # So far only known publication type is periodical:calibre
    # If None, means book
    'publication_type',
    # A UUID usually of type 4
    'uuid',
    'languages', # ordered list
    # Simple string, no special semantics
    'publisher',
    # Absolute path to image file encoded in filesystem_encoding
    'cover',
    # Of the form (format, data) where format is, for e.g. 'jpeg', 'png', 'gif'...
    'cover_data',
    # Either thumbnail data, or an object with the attribute
    # image_path which is the path to an image file, encoded
    # in filesystem_encoding
    'thumbnail',
    ])

BOOK_STRUCTURE_FIELDS = frozenset([
    # These are used by code, Null values are None.
    'toc', 'spine', 'guide', 'manifest',
    ])

USER_METADATA_FIELDS = frozenset([
    # A dict of a form to be specified
    'user_metadata',
])

DEVICE_METADATA_FIELDS = frozenset([
    # Ordered list of strings
    'device_collections',
    'lpath', # Unicode, / separated
    # In bytes
    'size',
    # Mimetype of the book file being represented
    'mime',
])

CALIBRE_METADATA_FIELDS = frozenset([
    # An application id
    # Semantics to be defined. Is it a db key? a db name + key? A uuid?
    'application_id',
    ]
)

CALIBRE_RESERVED_LABELS = frozenset([
    # reserved for saved searches
    'search',
    ]
)

RESERVED_METADATA_FIELDS = SOCIAL_METADATA_FIELDS.union(
                           PUBLICATION_METADATA_FIELDS).union(
                           BOOK_STRUCTURE_FIELDS).union(
                           USER_METADATA_FIELDS).union(
                           DEVICE_METADATA_FIELDS).union(
                           CALIBRE_METADATA_FIELDS).union(
                           CALIBRE_RESERVED_LABELS)

assert len(RESERVED_METADATA_FIELDS) == sum(map(len, (
    SOCIAL_METADATA_FIELDS, PUBLICATION_METADATA_FIELDS,
    BOOK_STRUCTURE_FIELDS, USER_METADATA_FIELDS,
    DEVICE_METADATA_FIELDS, CALIBRE_METADATA_FIELDS,
    CALIBRE_RESERVED_LABELS
    )))

SERIALIZABLE_FIELDS = SOCIAL_METADATA_FIELDS.union(
                      USER_METADATA_FIELDS).union(
                      PUBLICATION_METADATA_FIELDS).union(
                      CALIBRE_METADATA_FIELDS).union(
        frozenset(['lpath'])) # I don't think we need device_collections

# Serialization of covers/thumbnails will have to be handled carefully, maybe
# as an option to the serializer class
