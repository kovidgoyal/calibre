#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from functools import partial
from operator import attrgetter

from calibre.library.field_metadata import TagsIcons
from calibre.utils.config_base import tweaks
from calibre.utils.icu import sort_key

CATEGORY_SORTS = ('name', 'popularity', 'rating') # This has to be a tuple not a set

class Tag(object):

    def __init__(self, name, id=None, count=0, state=0, avg=0, sort=None,
                 tooltip=None, icon=None, category=None, id_set=None,
                 is_editable=True, is_searchable=True, use_sort_as_name=False):
        self.name = self.original_name = name
        self.id = id
        self.count = count
        self.state = state
        self.is_hierarchical = ''
        self.is_editable = is_editable
        self.is_searchable = is_searchable
        self.id_set = id_set if id_set is not None else set([])
        self.avg_rating = avg/2.0 if avg is not None else 0
        self.sort = sort
        self.use_sort_as_name = use_sort_as_name
        if self.avg_rating > 0:
            if tooltip:
                tooltip = tooltip + ': '
            tooltip = _('%(tt)sAverage rating is %(rating)3.1f')%dict(
                    tt=tooltip, rating=self.avg_rating)
        self.tooltip = tooltip
        self.icon = icon
        self.category = category

    def __unicode__(self):
        return u'%s:%s:%s:%s:%s:%s'%(self.name, self.count, self.id, self.state,
                                  self.category, self.tooltip)

    def __str__(self):
        return unicode(self).encode('utf-8')

    def __repr__(self):
        return str(self)

def find_categories(field_metadata):
    for category, cat in field_metadata.iteritems():
        if (cat['is_category'] and cat['kind'] not in {'user', 'search'}):
            yield (category, cat['is_multiple'].get('cache_to_list', None), False)
        elif (cat['datatype'] == 'composite' and
              cat['display'].get('make_category', False)):
            yield (category, cat['is_multiple'].get('cache_to_list', None), True)

def create_tag_class(category, fm, icon_map):
    cat = fm[category]
    icon = None
    tooltip = None if category in {'formats', 'identifiers'} else ('(' + category + ')')
    label = fm.key_to_label(category)
    if icon_map:
        if not fm.is_custom_field(category):
            if category in icon_map:
                icon = icon_map[label]
        else:
            icon = icon_map['custom:']
            icon_map[category] = icon
    is_editable = category not in {'news', 'rating', 'languages', 'formats',
                                   'identifiers'}

    if (tweaks['categories_use_field_for_author_name'] == 'author_sort' and
            (category == 'authors' or
                (cat['display'].get('is_names', False) and
                cat['is_custom'] and cat['is_multiple'] and
                cat['datatype'] == 'text'))):
        use_sort_as_name = True
    else:
        use_sort_as_name = False

    return partial(Tag, use_sort_as_name=use_sort_as_name, icon=icon,
                        tooltip=tooltip, is_editable=is_editable,
                        category=category)

def get_categories(dbcache, sort='name', book_ids=None, icon_map=None):
    if icon_map is not None and type(icon_map) != TagsIcons:
        raise TypeError('icon_map passed to get_categories must be of type TagIcons')
    if sort not in CATEGORY_SORTS:
        raise ValueError('sort ' + sort + ' not a valid value')

    fm = dbcache.field_metadata
    book_rating_map = dbcache.fields['rating'].book_value_map
    lang_map = dbcache.fields['languages'].book_value_map

    categories = {}
    book_ids = frozenset(book_ids) if book_ids else book_ids
    for category, is_multiple, is_composite in find_categories(fm):
        tag_class = create_tag_class(category, fm, icon_map)
        # TODO: Handle composite column based categories (both is_multiple and
        # not is_multiple)
        if category == 'news':
            cats = dbcache.fields['tags'].get_news_category(tag_class, book_ids)
        else:
            cats = dbcache.fields[category].get_categories(
                tag_class, book_rating_map, lang_map, book_ids)
        if sort == 'popularity':
            key=attrgetter('count')
        elif sort == 'rating':
            key=attrgetter('avg_rating')
        else:
            key=lambda x:sort_key(x.sort or x.name)
        cats.sort(key=key)
        categories[category] = cats

    # Needed for legacy databases that have multiple ratings that
    # map to n stars
    for r in categories['rating']:
        for x in tuple(categories['rating']):
            if r.name == x.name and r.id != x.id:
                r.id_set |= x.id_set
                r.count = r.count + x.count
                categories['rating'].remove(x)
                break

    # TODO: User categories and saved searches

    return categories


