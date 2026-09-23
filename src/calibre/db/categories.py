#!/usr/bin/env python
# License: GPLv3 Copyright: 2013, Kovid Goyal <kovid at kovidgoyal.net>

import copy
from collections import OrderedDict
from functools import partial

from calibre.db.locking import RWLockWrapper
from calibre.ebooks.metadata import author_to_author_sort
from calibre.utils.config_base import prefs, tweaks
from calibre.utils.icu import collation_order, sort_key
from calibre.utils.icu import lower as icu_lower
from calibre.utils.icu import upper as icu_upper

CATEGORY_SORTS = ('name', 'popularity', 'rating')  # This has to be a tuple not a set


class Tag:
    __slots__ = (
        'avg_rating',
        'category',
        'count',
        'id',
        'id_set',
        'is_editable',
        'is_hierarchical',
        'is_searchable',
        'name',
        'original_categories',
        'original_name',
        'search_expression',
        'sort',
        'state',
        'use_sort_as_name',
    )

    def __init__(
        self,
        name,
        id=None,
        count=0,
        state=0,
        avg=0,
        sort=None,
        category=None,
        id_set=None,
        search_expression=None,
        is_editable=True,
        is_searchable=True,
        use_sort_as_name=False,
        original_categories=None,
    ):
        self.name = self.original_name = name
        self.id = id
        self.count = count
        self.state = state
        self.is_hierarchical = ''
        self.is_editable = is_editable
        self.is_searchable = is_searchable
        self.id_set = id_set if id_set is not None else set()
        self.avg_rating = avg / 2.0 if avg is not None else 0
        self.sort = sort
        self.use_sort_as_name = use_sort_as_name
        self.category = category
        self.search_expression = search_expression
        self.original_categories = None

    @property
    def string_representation(self):
        return f'{self.name}:{self.count}:{self.id}:{self.state}:{self.category}:{self.original_categories}'

    def __str__(self):
        return self.string_representation

    def __repr__(self):
        return str(self)

    __calibre_serializable__ = True

    def as_dict(self):
        return {k: getattr(self, k) for k in self.__slots__}

    @classmethod
    def from_dict(cls, d):
        ans = cls('')
        for k in cls.__slots__:
            setattr(ans, k, d[k])
        return ans


def find_categories(field_metadata):
    for category, cat in field_metadata.iter_items():
        if cat['is_category'] and cat['kind'] not in {'user', 'search'}:
            yield (category, cat['is_multiple'].get('cache_to_list', None), False)
        elif cat['datatype'] == 'composite' and cat['display'].get('make_category', False):
            yield (category, cat['is_multiple'].get('cache_to_list', None), True)


def create_tag_class(category, fm):
    cat = fm[category]
    dt = cat['datatype']
    is_editable = category not in {'news', 'rating', 'languages', 'formats', 'identifiers'} and dt != 'composite'

    if (
        (category == 'authors' or (cat['display'].get('is_names', False) and cat['is_custom'] and cat['is_multiple'] and dt == 'text'))
        and tweaks['categories_use_field_for_author_name'] == 'author_sort'
    ) or (dt == 'series' and tweaks['categories_use_field_for_series_name'] == 'series_sort'):
        use_sort_as_name = True
    else:
        use_sort_as_name = False

    return partial(Tag, use_sort_as_name=use_sort_as_name, is_editable=is_editable, category=category)


def clean_user_categories(dbcache):
    user_cats = dbcache.pref('user_categories', {})
    new_cats = {}
    for k in user_cats:
        comps = [c.strip() for c in k.split('.') if c.strip()]
        if len(comps) == 0:
            i = 1
            while True:
                if str(i) not in user_cats:
                    new_cats[str(i)] = user_cats[k]
                    break
                i += 1
        else:
            new_cats['.'.join(comps)] = user_cats[k]
    try:
        if new_cats != user_cats:
            dbcache.set_pref('user_categories', new_cats)
    except Exception:
        pass
    return new_cats


def is_standard_category(key):
    return not (key.startswith('@') or key == 'search')


def category_display_order(ordered_cats, all_cats):
    # ordered_cats is the desired order. all_cats is the list of keys returned
    # by get_categories, which is in the default order
    cat_ord = []
    all_cat_set = frozenset(all_cats)
    # Do the standard categories first
    # Verify all the columns in ordered_cats are actually in all_cats
    for key in ordered_cats:
        if is_standard_category(key) and key in all_cat_set:
            cat_ord.append(key)
    # Add any new standard cats at the end of the list
    for key in all_cats:
        if key not in cat_ord and is_standard_category(key):
            cat_ord.append(key)
    # Now add the non-standard cats (user cats and search). As these are always
    # hierarchical, only keep the prefix.
    user_cat_prefixes = set()
    for key in all_cats:
        if not is_standard_category(key):
            prefix = key.partition('.')[0]
            if prefix not in user_cat_prefixes:
                cat_ord.append(prefix)
                user_cat_prefixes.add(prefix)
    return cat_ord


numeric_collation = prefs['numeric_collation']


def sort_key_for_popularity(x, hierarchical_categories=None):
    return (-getattr(x, 'count', 0), sort_key(x.sort or x.name))


def sort_key_for_rating(x, hierarchical_categories=None):
    return (-getattr(x, 'avg_rating', 0.0), sort_key(x.sort or x.name))


# When sorting by name, treat the period in hierarchical categories as a tab so
# that the value sorts above similarly-named items. Example: "foo.bar" should
# sort above "foo a.bar". Without this substitution "foo.bar" sorts below "foo
# a.bar" because '.' sorts higher than space.


def sort_key_for_name_and_first_letter(x, hierarchical_categories=()):
    v1 = icu_upper(x.sort or x.name)
    if x.category in hierarchical_categories:
        v1 = v1.replace('.', '\t')
    v2 = v1 or ' '
    # The idea is that '9999999999' is larger than any digit so all digits
    # will sort in front. Non-digits will sort according to their ICU first letter
    c = v2[0]
    return (c if numeric_collation and c.isdigit() else '9999999999', collation_order(v2), sort_key(v1))


def sort_key_for_name(x, hierarchical_categories=()):
    v = x.sort or x.name
    if x.category not in hierarchical_categories:
        return sort_key(v)
    return sort_key(v.replace('.', '\t'))


category_sort_keys = {True: {}, False: {}}
category_sort_keys[True]['popularity'] = category_sort_keys[False]['popularity'] = sort_key_for_popularity
category_sort_keys[True]['rating'] = category_sort_keys[False]['rating'] = sort_key_for_rating
category_sort_keys[True]['name'] = sort_key_for_name_and_first_letter
category_sort_keys[False]['name'] = sort_key_for_name


# Caching of computed categories {{{

# Cache API methods that take the write lock but cannot change any of the data
# the categories are computed from. set_field and set_metadata are here
# because set_field() reports the changed field itself, which allows only the
# affected categories to be recomputed.
CATEGORY_NEUTRAL_WRITES = frozenset((
    'set_field',
    'set_metadata',
    'mark_as_dirty',
    'commit_dirty_cache',
    'check_dirtied_annotations',
    'clear_dirtied',
    'write_backup',
    'dump_metadata',
    'set_cover',
    'add_cover_cache',
    'remove_cover_cache',
    'compress_covers',
    'update_last_modified',
    'update_path',
    'fts_start_measuring_rate',
    'fts_unindex',
    'queue_next_fts_job',
    'commit_fts_result',
    'reindex_fts_book',
    'set_fts_num_of_workers',
    'set_fts_speed',
    'fts_search',
    'mark_for_pages_recount',
    'queue_pages_scan',
    'set_pages',
    'add_listener',
    'remove_listener',
    'set_conversion_options',
    'delete_conversion_options',
    'set_last_read_position',
    'add_custom_book_data',
    'delete_custom_book_data',
    'delete_annotations',
    'update_annotations',
    'restore_annotations',
    'set_annotations_for_book',
    'merge_annotations_for_book',
    'save_annotations_list',
    'reindex_annotations',
    'set_notes_for',
    'add_notes_resource',
    'unretire_note_for',
    'import_note',
    'search_notes',
    'add_extra_files',
    'rename_extra_files',
    'merge_extra_files',
    'remove_extra_files',
    'clear_extra_files_cache',
    'clear_caches',
    'clear_composite_caches',
    'clear_search_caches',
    'clear_link_map_cache',
    'initialize_template_cache',
    'embed_metadata',
    'refresh_ondevice',
))


class CategoriesCache:
    """
    Caches the sorted list of Tag objects for each category when categories are
    computed for all books. An entry is valid as long as neither the global
    version nor the versions of the fields it depends on have changed.
    """

    def __init__(self):
        self.global_version = 0
        self.field_versions = {}
        self.entries = {}

    def invalidate_all(self):
        self.global_version += 1
        self.entries.clear()

    def field_changed(self, name):
        self.field_versions[name] = self.field_versions.get(name, 0) + 1

    def fingerprint(self, field_metadata):
        "Changes whenever any data the categories are computed from may have changed"
        fv = self.field_versions
        relevant = {c for c, _, _ in find_categories(field_metadata)} | {'rating', 'languages', 'tags'}
        return self.global_version, tuple(sorted((f, fv[f]) for f in relevant if f in fv))

    def version_for(self, *field_names):
        fv = self.field_versions
        return (self.global_version,) + tuple(fv.get(n, 0) for n in field_names)

    def get(self, key, version):
        entry = self.entries.get(key)
        if entry is None or entry[0] != version:
            return None
        tags, avg_ratings = entry[1], entry[2]
        # Undo any changes made to the Tag objects by previous users
        for tag, avg in zip(tags, avg_ratings):
            tag.avg_rating = avg
            tag.state = 0
            tag.is_hierarchical = ''
        return list(tags)

    def set(self, key, version, tags):
        self.entries[key] = version, tuple(tags), tuple(t.avg_rating for t in tags)


class CategoriesInvalidatingLock(RWLockWrapper):
    """Wrapper for the exclusive lock that invalidates all cached categories when the lock is acquired"""

    def __init__(self, lock, categories_cache):
        super().__init__(lock._shlock, lock._is_shared)
        self._categories_cache = categories_cache

    def acquire(self):
        super().acquire()
        self._categories_cache.invalidate_all()

    __enter__ = acquire


# }}}


# Various parts of calibre depend on the order of fields in the returned
# dict being in the default display order: standard fields, custom in alpha order,
# user categories, then saved searches. This works because the backend adds
# custom columns to field metadata in the right order.
def get_categories(dbcache, sort='name', book_ids=None, first_letter_sort=False, uncollapsed_categories=None):
    if sort not in CATEGORY_SORTS:
        raise ValueError('sort ' + sort + ' not a valid value')

    hierarchical_categories = frozenset(dbcache.pref('categories_using_hierarchy', ()))
    fm = dbcache.field_metadata
    book_rating_map = dbcache.fields['rating'].book_value_map
    lang_map = dbcache.fields['languages'].book_value_map

    categories = OrderedDict()
    book_ids = frozenset(book_ids) if book_ids else book_ids
    pm_cache = {}

    def get_metadata(book_id):
        ans = pm_cache.get(book_id)
        if ans is None:
            ans = pm_cache[book_id] = dbcache._get_proxy_metadata(book_id)
        return ans

    bids = None
    uncollapsed_categories = () if uncollapsed_categories is None else uncollapsed_categories
    cache = getattr(dbcache, 'categories_cache', None)

    for category, is_multiple, is_composite in find_categories(fm):
        fl_sort = False if category in uncollapsed_categories else bool(first_letter_sort)
        tag_class = create_tag_class(category, fm)
        sort_on, reverse = sort, False
        use_cache = False
        if is_composite:
            if bids is None:
                bids = dbcache._all_book_ids() if book_ids is None else book_ids
            cats = dbcache.fields[category].get_composite_categories(tag_class, book_rating_map, bids, is_multiple, get_metadata)
        elif category == 'news':
            cats = dbcache.fields['tags'].get_news_category(tag_class, book_ids)
        else:
            cat = fm[category]
            brm = book_rating_map
            dt = cat['datatype']
            if dt == 'rating':
                if category != 'rating':
                    brm = dbcache.fields[category].book_value_map
                if sort_on == 'name':
                    sort_on, reverse = 'rating', True
            # The rating category is tiny and is modified below, so is not cached
            use_cache = cache is not None and book_ids is None and category != 'rating'
            if use_cache:
                rating_field = category if dt == 'rating' else 'rating'
                cache_key = category, sort_on, reverse, fl_sort, category in hierarchical_categories
                cache_version = cache.version_for(category, rating_field, 'languages')
                cats = cache.get(cache_key, cache_version)
                if cats is not None:
                    categories[category] = cats
                    continue
            cats = dbcache.fields[category].get_categories(tag_class, brm, lang_map, book_ids)
            if category != 'authors' and dt == 'text' and cat['is_multiple'] and cat['display'].get('is_names', False):
                for item in cats:
                    item.sort = author_to_author_sort(item.sort)
        cats.sort(
            key=partial(category_sort_keys[fl_sort][sort_on], hierarchical_categories=hierarchical_categories),
            reverse=reverse,
        )
        if use_cache:
            cache.set(cache_key, cache_version, cats)
        categories[category] = cats

    # Needed for legacy databases that have multiple ratings that
    # map to n stars
    for r in categories['rating']:
        for x in tuple(categories['rating']):
            if r.name == x.name and r.id != x.id:
                r.id_set |= x.id_set
                r.count = len(r.id_set)
                categories['rating'].remove(x)
                break

    # User categories
    user_categories = clean_user_categories(dbcache).copy()

    # First add any grouped search terms to the user categories
    muc = dbcache.pref('grouped_search_make_user_categories', [])
    gst = dbcache.pref('grouped_search_terms', {})
    for c in gst:
        if c not in muc:
            continue
        uc = []
        for sc in gst[c]:
            for t in categories.get(sc, ()):
                uc.append([t.name, sc, 0])
        user_categories[c] = uc

    if user_categories:
        # We want to use same node in the user category as in the source
        # category. To do that, we need to find the original Tag node. There is
        # a time/space tradeoff here. By converting the tags into a map, we can
        # do the verification in the category loop much faster, at the cost of
        # temporarily duplicating the categories lists.
        taglist = {}
        for c, items in categories.items():
            taglist[c] = {icu_lower(t.name): t for t in items}

        # Add the category values to the user categories
        for user_cat in sorted(user_categories, key=sort_key):
            items = []
            names_seen = {}
            user_cat_is_gst = user_cat in gst
            for name, label, ign in user_categories[user_cat]:
                n = icu_lower(name)
                if label in taglist and n in taglist[label]:
                    if user_cat_is_gst:
                        # for gst items, make copy and consolidate the tags by name.
                        if n in names_seen:
                            # We must combine this node into a previous one with
                            # the same name ignoring case. As part of the process,
                            # remember the source categories and correct the
                            # average rating
                            t = names_seen[n]
                            other_tag = taglist[label][n]
                            t.id_set |= other_tag.id_set
                            t.count = len(t.id_set)
                            t.original_categories.add(other_tag.category)

                            total_rating = 0
                            count = 0
                            for id_ in t.id_set:
                                rating = book_rating_map.get(id_, 0)
                                if rating:
                                    total_rating += rating / 2
                                    count += 1
                            if total_rating and count:
                                t.avg_rating = total_rating / count
                        else:
                            # Must deepcopy so we don't share the id_set between nodes
                            t = copy.deepcopy(taglist[label][n])
                            t.original_categories = {t.category}
                            names_seen[n] = t
                            items.append(t)
                    else:
                        items.append(taglist[label][n])
                # else: do nothing, to not include nodes w zero counts
            cat_name = '@' + user_cat  # add the '@' to avoid name collision
            items.sort(key=partial(category_sort_keys[False][sort], hierarchical_categories=hierarchical_categories))
            categories[cat_name] = items

    # ### Finally, the saved searches category ####
    items = []
    queries = dbcache._search_api.saved_searches.queries
    for srch in sorted(queries, key=sort_key):
        items.append(Tag(srch, sort=srch, search_expression=queries[srch], category='search', is_editable=False))
    if items:
        categories['search'] = items

    return categories
