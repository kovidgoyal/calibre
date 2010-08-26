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
    # TODO: not sure what this is, but it is used by OPF
    'category',

])

PUBLICATION_METADATA_FIELDS = frozenset([
    # title must never be None. Should be _('Unknown')
    'title',
    # Pseudo field that can be set, but if not set is auto generated
    # from title and languages
    'title_sort',
    # Ordered list of authors. Must never be None, can be [_('Unknown')]
    'authors',
    # Map of sort strings for each author
    'author_sort_map',
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
    # A dict of dicts similar to field_metadata. Each field description dict
    # also contains a value field with the key #value#.
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
    # (It is currently set to the db_id.)
    'application_id',
    # the calibre primary key of the item. May want to remove this once Sony's no longer use it
    'db_id',
    ]
)

ALL_METADATA_FIELDS =      SOCIAL_METADATA_FIELDS.union(
                           PUBLICATION_METADATA_FIELDS).union(
                           BOOK_STRUCTURE_FIELDS).union(
                           USER_METADATA_FIELDS).union(
                           DEVICE_METADATA_FIELDS).union(
                           CALIBRE_METADATA_FIELDS)

# All fields except custom fields
STANDARD_METADATA_FIELDS = SOCIAL_METADATA_FIELDS.union(
                           PUBLICATION_METADATA_FIELDS).union(
                           BOOK_STRUCTURE_FIELDS).union(
                           DEVICE_METADATA_FIELDS).union(
                           CALIBRE_METADATA_FIELDS)

# Metadata fields that smart update should copy without special handling
COPYABLE_METADATA_FIELDS = SOCIAL_METADATA_FIELDS.union(
                           PUBLICATION_METADATA_FIELDS).union(
                           BOOK_STRUCTURE_FIELDS).union(
                           DEVICE_METADATA_FIELDS).union(
                           CALIBRE_METADATA_FIELDS) - \
                           frozenset(['title', 'authors', 'comments', 'cover_data'])

SERIALIZABLE_FIELDS =      SOCIAL_METADATA_FIELDS.union(
                           USER_METADATA_FIELDS).union(
                           PUBLICATION_METADATA_FIELDS).union(
                           CALIBRE_METADATA_FIELDS).union(
                           DEVICE_METADATA_FIELDS) - \
                           frozenset(['device_collections'])
                      # I don't think we need device_collections

# Serialization of covers/thumbnails will have to be handled carefully, maybe
# as an option to the serializer class
