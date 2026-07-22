#!/usr/bin/env python
# License: GPLv3 Copyright: 2012, Kovid Goyal <kovid@kovidgoyal.net>

FIELDS = [
    'all',
    'title',
    'title_sort',
    'author_sort',
    'authors',
    'comments',
    'cover',
    'formats',
    'id',
    'isbn',
    'library_name',
    'ondevice',
    'pubdate',
    'publisher',
    'rating',
    'series_index',
    'series',
    'size',
    'tags',
    'timestamp',
    'uuid',
    'languages',
    'identifiers',
]

# Allowed fields for template
TEMPLATE_ALLOWED_FIELDS = [
    'author_sort',
    'authors',
    'id',
    'isbn',
    'pubdate',
    'title_sort',
    'publisher',
    'series_index',
    'series',
    'tags',
    'timestamp',
    'title',
    'uuid',
]


class AuthorSortMismatchException(Exception):
    pass


class EmptyCatalogException(Exception):
    pass


class InvalidGenresSourceFieldException(Exception):
    pass
