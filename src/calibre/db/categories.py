#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import copy
from functools import partial
from operator import attrgetter
from future_builtins import map

from calibre.ebooks.metadata import author_to_author_sort
from calibre.library.field_metadata import TagsIcons
from calibre.utils.config_base import tweaks
from calibre.utils.icu import sort_key
from calibre.utils.search_query_parser import saved_searches

CATEGORY_SORTS = ('name', 'popularity', 'rating')  # This has to be a tuple not a set

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
        if tooltip is None:
            tooltip = '(%s:%s)'%(category, name)
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
    dt = cat['datatype']
    icon = None
    label = fm.key_to_label(category)
    if icon_map:
        if not fm.is_custom_field(category):
            if category in icon_map:
                icon = icon_map[label]
        else:
            icon = icon_map['custom:']
            icon_map[category] = icon
    is_editable = category not in {'news', 'rating', 'languages', 'formats',
                                   'identifiers'} and dt != 'composite'

    if (tweaks['categories_use_field_for_author_name'] == 'author_sort' and
            (category == 'authors' or
                (cat['display'].get('is_names', False) and
                cat['is_custom'] and cat['is_multiple'] and
                dt == 'text'))):
        use_sort_as_name = True
    else:
        use_sort_as_name = False

    return partial(Tag, use_sort_as_name=use_sort_as_name, icon=icon,
                        is_editable=is_editable, category=category)

def clean_user_categories(dbcache):
    user_cats = dbcache.pref('user_categories', {})
    new_cats = {}
    for k in user_cats:
        comps = [c.strip() for c in k.split('.') if c.strip()]
        if len(comps) == 0:
            i = 1
            while True:
                if unicode(i) not in user_cats:
                    new_cats[unicode(i)] = user_cats[k]
                    break
                i += 1
        else:
            new_cats['.'.join(comps)] = user_cats[k]
    try:
        if new_cats != user_cats:
            dbcache.set_pref('user_categories', new_cats)
    except:
        pass
    return new_cats

def sort_categories(items, sort):
    reverse = True
    if sort == 'popularity':
        key=attrgetter('count')
    elif sort == 'rating':
        key=attrgetter('avg_rating')
    else:
        key=lambda x:sort_key(x.sort or x.name)
        reverse=False
    items.sort(key=key, reverse=reverse)
    return items

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
    get_metadata = partial(dbcache._get_metadata, get_user_categories=False)
    bids = None

    for category, is_multiple, is_composite in find_categories(fm):
        tag_class = create_tag_class(category, fm, icon_map)
        if is_composite:
            if bids is None:
                bids = dbcache._all_book_ids() if book_ids is None else book_ids
            cats = dbcache.fields[category].get_composite_categories(
                tag_class, book_rating_map, bids, is_multiple, get_metadata)
        elif category == 'news':
            cats = dbcache.fields['tags'].get_news_category(tag_class, book_ids)
        else:
            cat = fm[category]
            brm = book_rating_map
            if cat['datatype'] == 'rating' and category != 'rating':
                brm = dbcache.fields[category].book_value_map
            cats = dbcache.fields[category].get_categories(
                tag_class, brm, lang_map, book_ids)
            if (category != 'authors' and cat['datatype'] == 'text' and
                cat['is_multiple'] and cat['display'].get('is_names', False)):
                for item in cats:
                    item.sort = author_to_author_sort(item.sort)
        sort_categories(cats, sort)
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

    # User categories
    user_categories = clean_user_categories(dbcache).copy()
    if user_categories:
        # We want to use same node in the user category as in the source
        # category. To do that, we need to find the original Tag node. There is
        # a time/space tradeoff here. By converting the tags into a map, we can
        # do the verification in the category loop much faster, at the cost of
        # temporarily duplicating the categories lists.
        taglist = {}
        for c, items in categories.iteritems():
            taglist[c] = dict(map(lambda t:(icu_lower(t.name), t), items))

        muc = dbcache.pref('grouped_search_make_user_categories', [])
        gst = dbcache.pref('grouped_search_terms', {})
        for c in gst:
            if c not in muc:
                continue
            user_categories[c] = []
            for sc in gst[c]:
                if sc in categories.keys():
                    for t in categories[sc]:
                        user_categories[c].append([t.name, sc, 0])

        gst_icon = icon_map['gst'] if icon_map else None
        for user_cat in sorted(user_categories.iterkeys(), key=sort_key):
            items = []
            names_seen = {}
            for name, label, ign in user_categories[user_cat]:
                n = icu_lower(name)
                if label in taglist and n in taglist[label]:
                    if user_cat in gst:
                        # for gst items, make copy and consolidate the tags by name.
                        if n in names_seen:
                            t = names_seen[n]
                            t.id_set |= taglist[label][n].id_set
                            t.count += taglist[label][n].count
                            t.tooltip = t.tooltip.replace(')', ', ' + label + ')')
                        else:
                            t = copy.copy(taglist[label][n])
                            t.icon = gst_icon
                            names_seen[t.name] = t
                            items.append(t)
                    else:
                        items.append(taglist[label][n])
                # else: do nothing, to not include nodes w zero counts
            cat_name = '@' + user_cat  # add the '@' to avoid name collision
            # Not a problem if we accumulate entries in the icon map
            if icon_map is not None:
                icon_map[cat_name] = icon_map['user:']
            categories[cat_name] = sort_categories(items, sort)

    #### Finally, the saved searches category ####
    items = []
    icon = None
    if icon_map and 'search' in icon_map:
        icon = icon_map['search']
    ss = saved_searches()
    for srch in ss.names():
        items.append(Tag(srch, tooltip=ss.lookup(srch),
                            sort=srch, icon=icon, category='search',
                            is_editable=False))
    if len(items):
        categories['search'] = items

    return categories


