'''
Created on 25 May 2010

@author: charles
'''
import traceback
from collections import OrderedDict

from calibre.utils.config_base import tweaks

category_icon_map = {
                    'authors'    : 'user_profile.png',
                    'series'     : 'series.png',
                    'formats'    : 'book.png',
                    'publisher'  : 'publisher.png',
                    'rating'     : 'rating.png',
                    'news'       : 'news.png',
                    'tags'       : 'tags.png',
                    'custom:'    : 'column.png',
                    'user:'      : 'tb_folder.png',
                    'search'     : 'search.png',
                    'identifiers': 'identifiers.png',
                    'gst'        : 'catalog.png',
                    'languages'  : 'languages.png',
            }

# Builtin metadata {{{


def _builtin_field_metadata():
    # This is a function so that changing the UI language allows newly created
    # field metadata objects to have correctly translated labels for builtin
    # fields.
    return [
            ('authors',   {'table':'authors',
                           'column':'name',
                           'link_column':'author',
                           'category_sort':'sort',
                           'datatype':'text',
                           'is_multiple':{'cache_to_list': ',',
                                          'ui_to_list': '&',
                                          'list_to_ui': ' & '},
                           'kind':'field',
                           'name':_('Authors'),
                           'search_terms':['authors', 'author'],
                           'is_custom':False,
                           'is_category':True,
                           'is_csp': False}),
            ('languages', {'table':'languages',
                           'column':'lang_code',
                           'link_column':'lang_code',
                           'category_sort':'lang_code',
                           'datatype':'text',
                           'is_multiple':{'cache_to_list': ',',
                                          'ui_to_list': ',',
                                          'list_to_ui': ', '},
                           'kind':'field',
                           'name':_('Languages'),
                           'search_terms':['languages', 'language'],
                           'is_custom':False,
                           'is_category':True,
                           'is_csp': False}),

            ('series',    {'table':'series',
                           'column':'name',
                           'link_column':'series',
                           'category_sort':'(title_sort(name))',
                           'datatype':'series',
                           'is_multiple':{},
                           'kind':'field',
                           'name':ngettext('Series', 'Series', 1),
                           'search_terms':['series'],
                           'is_custom':False,
                           'is_category':True,
                           'is_csp': False}),
            ('formats',   {'table':None,
                           'column':None,
                           'datatype':'text',
                           'is_multiple':{'cache_to_list': ',',
                                          'ui_to_list': ',',
                                          'list_to_ui': ', '},
                           'kind':'field',
                           'name':_('Formats'),
                           'search_terms':['formats', 'format'],
                           'is_custom':False,
                           'is_category':True,
                           'is_csp': False}),
            ('publisher', {'table':'publishers',
                           'column':'name',
                           'link_column':'publisher',
                           'category_sort':'name',
                           'datatype':'text',
                           'is_multiple':{},
                           'kind':'field',
                           'name':_('Publisher'),
                           'search_terms':['publisher'],
                           'is_custom':False,
                           'is_category':True,
                           'is_csp': False}),
            ('rating',    {'table':'ratings',
                           'column':'rating',
                           'link_column':'rating',
                           'category_sort':'rating',
                           'datatype':'rating',
                           'is_multiple':{},
                           'kind':'field',
                           'name':_('Rating'),
                           'search_terms':['rating'],
                           'is_custom':False,
                           'is_category':True,
                           'is_csp': False}),
            ('news',      {'table':'news',
                           'column':'name',
                           'category_sort':'name',
                           'datatype':None,
                           'is_multiple':{},
                           'kind':'category',
                           'name':_('News'),
                           'search_terms':[],
                           'is_custom':False,
                           'is_category':True,
                           'is_csp': False}),
            ('tags',      {'table':'tags',
                           'column':'name',
                           'link_column': 'tag',
                           'category_sort':'name',
                           'datatype':'text',
                           'is_multiple':{'cache_to_list': ',',
                                          'ui_to_list': ',',
                                          'list_to_ui': ', '},
                           'kind':'field',
                           'name':_('Tags'),
                           'search_terms':['tags', 'tag'],
                           'is_custom':False,
                           'is_category':True,
                           'is_csp': False}),
            ('identifiers',   {'table':None,
                           'column':None,
                           'datatype':'text',
                           'is_multiple':{'cache_to_list': ',',
                                          'ui_to_list': ',',
                                          'list_to_ui': ', '},
                           'kind':'field',
                           'name':_('Identifiers'),
                           'search_terms':['identifiers', 'identifier', 'isbn'],
                           'is_custom':False,
                           'is_category':True,
                           'is_csp': True}),
            ('author_sort',{'table':None,
                            'column':None,
                            'datatype':'text',
                           'is_multiple':{},
                           'kind':'field',
                           'name':_('Author sort'),
                           'search_terms':['author_sort'],
                           'is_custom':False,
                           'is_category':False,
                           'is_csp': False}),
            ('au_map',    {'table':None,
                           'column':None,
                           'datatype':'text',
                           'is_multiple':{'cache_to_list': ',',
                                          'ui_to_list': None,
                                          'list_to_ui': None},
                           'kind':'field',
                           'name':None,
                           'search_terms':[],
                           'is_custom':False,
                           'is_category':False,
                           'is_csp': False}),
            ('comments',  {'table':None,
                           'column':None,
                           'datatype':'text',
                           'is_multiple':{},
                           'kind':'field',
                           'name':_('Comments'),
                           'search_terms':['comments', 'comment'],
                           'is_custom':False,
                           'is_category':False,
                           'is_csp': False}),
            ('cover',     {'table':None,
                           'column':None,
                           'datatype':'int',
                           'is_multiple':{},
                           'kind':'field',
                           'name':_('Cover'),
                           'search_terms':['cover'],
                           'is_custom':False,
                           'is_category':False,
                           'is_csp': False}),
            ('id',        {'table':None,
                           'column':None,
                           'datatype':'int',
                           'is_multiple':{},
                           'kind':'field',
                           'name':None,
                           'search_terms':['id'],
                           'is_custom':False,
                           'is_category':False,
                           'is_csp': False}),
            ('last_modified', {'table':None,
                           'column':None,
                           'datatype':'datetime',
                           'is_multiple':{},
                           'kind':'field',
                           'name':_('Modified'),
                           'search_terms':['last_modified'],
                           'is_custom':False,
                           'is_category':False,
                           'is_csp': False}),
            ('ondevice',  {'table':None,
                           'column':None,
                           'datatype':'text',
                           'is_multiple':{},
                           'kind':'field',
                           'name':_('On device'),
                           'search_terms':['ondevice'],
                           'is_custom':False,
                           'is_category':False,
                           'is_csp': False}),
            ('path',      {'table':None,
                           'column':None,
                           'datatype':'text',
                           'is_multiple':{},
                           'kind':'field',
                           'name':_('Path'),
                           'search_terms':[],
                           'is_custom':False,
                           'is_category':False,
                           'is_csp': False}),
            ('pubdate',   {'table':None,
                           'column':None,
                           'datatype':'datetime',
                           'is_multiple':{},
                           'kind':'field',
                           'name':_('Published'),
                           'search_terms':['pubdate'],
                           'is_custom':False,
                           'is_category':False,
                           'is_csp': False}),
            ('marked',    {'table':None,
                           'column':None,
                           'datatype':'text',
                           'is_multiple':{},
                           'kind':'field',
                           'name': None,
                           'search_terms':['marked'],
                           'is_custom':False,
                           'is_category':False,
                           'is_csp': False}),
            ('series_index',{'table':None,
                             'column':None,
                             'datatype':'float',
                             'is_multiple':{},
                             'kind':'field',
                             'name':None,
                             'search_terms':['series_index'],
                             'is_custom':False,
                             'is_category':False,
                           'is_csp': False}),
            ('series_sort',  {'table':None,
                           'column':None,
                           'datatype':'text',
                           'is_multiple':{},
                           'kind':'field',
                           'name':_('Series sort'),
                           'search_terms':['series_sort'],
                           'is_custom':False,
                           'is_category':False,
                           'is_csp': False}),
            ('sort',      {'table':None,
                           'column':None,
                           'datatype':'text',
                           'is_multiple':{},
                           'kind':'field',
                           'name':_('Title sort'),
                           'search_terms':['title_sort'],
                           'is_custom':False,
                           'is_category':False,
                           'is_csp': False}),
            ('size',      {'table':None,
                           'column':None,
                           'datatype':'float',
                           'is_multiple':{},
                           'kind':'field',
                           'name':_('Size'),
                           'search_terms':['size'],
                           'is_custom':False,
                           'is_category':False,
                           'is_csp': False}),
            ('timestamp', {'table':None,
                           'column':None,
                           'datatype':'datetime',
                           'is_multiple':{},
                           'kind':'field',
                           'name':_('Date'),
                           'search_terms':['date'],
                           'is_custom':False,
                           'is_category':False,
                           'is_csp': False}),
            ('title',     {'table':None,
                           'column':None,
                           'datatype':'text',
                           'is_multiple':{},
                           'kind':'field',
                           'name':_('Title'),
                           'search_terms':['title'],
                           'is_custom':False,
                           'is_category':False,
                           'is_csp': False}),
            ('uuid',      {'table':None,
                           'column':None,
                           'datatype':'text',
                           'is_multiple':{},
                           'kind':'field',
                           'name':None,
                           'search_terms':['uuid'],
                           'is_custom':False,
                           'is_category':False,
                           'is_csp': False}),
        ]
# }}}


class FieldMetadata(object):
    '''
    key: the key to the dictionary is:
    - for standard fields, the metadata field name.
    - for custom fields, the metadata field name prefixed by '#'
    This is done to create two 'namespaces' so the names don't clash

    label: the actual column label. No prefixing.

    datatype: the type of information in the field. Valid values are listed in
    VALID_DATA_TYPES below.
    is_multiple: valid for the text datatype. If {}, the field is to be
    treated as a single term. If not None, it contains a dict of the form
            {'cache_to_list': ',',
             'ui_to_list': ',',
             'list_to_ui': ', '}
    where the cache_to_list contains the character used to split the value in
    the meta2 table, ui_to_list contains the character used to create a list
    from a value shown in the ui (each resulting value must be strip()ed and
    empty values removed), and list_to_ui contains the string used in join()
    to create a displayable string from the list.

    kind == field: is a db field.
    kind == category: standard tag category that isn't a field. see news.
    kind == user: user-defined tag category.
    kind == search: saved-searches category.

    is_category: is a tag browser category. If true, then:
       table: name of the db table used to construct item list
       column: name of the column in the normalized table to join on
       link_column: name of the column in the connection table to join on. This
                    key should not be present if there is no link table
       category_sort: the field in the normalized table to sort on. This
                      key must be present if is_category is True
       If these are None, then the category constructor must know how
       to build the item list (e.g., formats, news).
       The order below is the order that the categories will
       appear in the tags pane.

    name: the text that is to be used when displaying the field. Column headings
    in the GUI, etc.

    search_terms: the terms that can be used to identify the field when
    searching. They can be thought of as aliases for metadata keys, but are only
    valid when passed to search().

    is_custom: the field has been added by the user.

    rec_index: the index of the field in the db metadata record.

    is_csp: field contains colon-separated pairs. Must also be text, is_multiple

    '''

    VALID_DATA_TYPES = frozenset([None, 'rating', 'text', 'comments', 'datetime',
                'int', 'float', 'bool', 'series', 'composite', 'enumeration'])

    # search labels that are not db columns
    search_items = ['all', 'search']
    __calibre_serializable__ = True

    def __init__(self):
        self._field_metadata = _builtin_field_metadata()
        self._tb_cats = OrderedDict()
        self._tb_custom_fields = {}
        self._search_term_map = {}
        self.custom_label_to_key_map = {}
        for k,v in self._field_metadata:
            if v['kind'] == 'field' and v['datatype'] not in self.VALID_DATA_TYPES:
                raise ValueError('Unknown datatype %s for field %s'%(v['datatype'], k))
            self._tb_cats[k] = v
            self._tb_cats[k]['label'] = k
            self._tb_cats[k]['display'] = {}
            self._tb_cats[k]['is_editable'] = True
            self._add_search_terms_to_map(k, v['search_terms'])
        self._tb_cats['timestamp']['display'] = {
                        'date_format': tweaks['gui_timestamp_display_format']}
        self._tb_cats['pubdate']['display'] = {
                        'date_format': tweaks['gui_pubdate_display_format']}
        self._tb_cats['last_modified']['display'] = {
                        'date_format': tweaks['gui_last_modified_display_format']}
        self.custom_field_prefix = '#'
        self.get = self._tb_cats.get

    def __getitem__(self, key):
        if key == 'title_sort':
            return self._tb_cats['sort']
        return self._tb_cats[key]

    def __setitem__(self, key, val):
        raise AttributeError('Assigning to this object is forbidden')

    def __delitem__(self, key):
        del self._tb_cats[key]

    def __iter__(self):
        for key in self._tb_cats:
            yield key

    def __contains__(self, key):
        return key in self._tb_cats or key == 'title_sort'

    def has_key(self, key):
        return key in self

    def keys(self):
        return self._tb_cats.keys()

    def __eq__(self, other):
        if not isinstance(other, FieldMetadata):
            return False
        for attr in ('_tb_cats', '_tb_custom_fields', '_search_term_map', 'custom_label_to_key_map', 'custom_field_prefix'):
            if getattr(self, attr) != getattr(other, attr):
                return False
        return True

    def __ne__(self, other):
        return not self.__eq__(other)

    def sortable_field_keys(self):
        return [k for k in self._tb_cats.keys()
                if self._tb_cats[k]['kind']=='field' and
                   self._tb_cats[k]['datatype'] is not None]

    def ui_sortable_field_keys(self):
        ans = {k:self._tb_cats[k]['name'] for k in set(self.sortable_field_keys()) - {
            'sort', 'author_sort', 'au_map', 'series_sort', 'marked',
            'series_index', 'path', 'formats', 'identifiers', 'uuid',
            'comments',
        } if self._tb_cats[k]['name']}
        ans['cover'] = _('Has cover')
        return ans

    def displayable_field_keys(self):
        return [k for k in self._tb_cats.keys()
                if self._tb_cats[k]['kind']=='field' and
                   self._tb_cats[k]['datatype'] is not None and
                   k not in ('au_map', 'marked', 'ondevice', 'cover', 'series_sort') and
                   not self.is_series_index(k)]

    def standard_field_keys(self):
        return [k for k in self._tb_cats.keys()
                if self._tb_cats[k]['kind']=='field' and
                   not self._tb_cats[k]['is_custom']]

    def custom_field_keys(self, include_composites=True):
        res = []
        for k in self._tb_cats.keys():
            fm = self._tb_cats[k]
            if fm['kind']=='field' and fm['is_custom'] and \
                   (fm['datatype'] != 'composite' or include_composites):
                res.append(k)
        return res

    def all_field_keys(self):
        return [k for k in self._tb_cats.keys() if self._tb_cats[k]['kind']=='field']

    def iterkeys(self):
        for key in self._tb_cats:
            yield key

    def itervalues(self):
        return self._tb_cats.itervalues()

    def values(self):
        return self._tb_cats.values()

    def iteritems(self):
        for key in self._tb_cats:
            yield (key, self._tb_cats[key])

    def custom_iteritems(self):
        for key, meta in self._tb_custom_fields.iteritems():
            yield (key, meta)

    def items(self):
        return list(self.iteritems())

    def is_custom_field(self, key):
        return key.startswith(self.custom_field_prefix)

    def is_ignorable_field(self, key):
        'Custom fields and user categories are ignorable'
        return self.is_custom_field(key) or key.startswith('@')

    def ignorable_field_keys(self):
        return [k for k in self._tb_cats.iterkeys() if self.is_ignorable_field(k)]

    def is_series_index(self, key):
        try:
            m = self._tb_cats[key]
            return (m['datatype'] == 'float' and key.endswith('_index') and
                    key[:-6] in self._tb_cats)
        except (KeyError, ValueError, TypeError, AttributeError):
            return False

    def key_to_label(self, key):
        if 'label' not in self._tb_cats[key]:
            return key
        return self._tb_cats[key]['label']

    def label_to_key(self, label, prefer_custom=False):
        if prefer_custom:
            if label in self.custom_label_to_key_map:
                return self.custom_label_to_key_map[label]
        if 'label' in self._tb_cats:
            return label
        if not prefer_custom:
            if label in self.custom_label_to_key_map:
                return self.custom_label_to_key_map[label]
        raise ValueError('Unknown key [%s]'%(label))

    def all_metadata(self):
        l = {}
        for k in self._tb_cats:
            l[k] = self._tb_cats[k]
        return l

    def custom_field_metadata(self, include_composites=True):
        if include_composites:
            return self._tb_custom_fields
        l = {}
        for k in self.custom_field_keys(include_composites):
            l[k] = self._tb_cats[k]
        return l

    def add_custom_field(self, label, table, column, datatype, colnum, name,
                         display, is_editable, is_multiple, is_category,
                         is_csp=False):
        key = self.custom_field_prefix + label
        if key in self._tb_cats:
            raise ValueError('Duplicate custom field [%s]'%(label))
        if datatype not in self.VALID_DATA_TYPES:
            raise ValueError('Unknown datatype %s for field %s'%(datatype, key))
        self._tb_cats[key] = {'table':table,       'column':column,
                             'datatype':datatype,  'is_multiple':is_multiple,
                             'kind':'field',       'name':name,
                             'search_terms':[key], 'label':label,
                             'colnum':colnum,      'display':display,
                             'is_custom':True,     'is_category':is_category,
                             'link_column':'value','category_sort':'value',
                             'is_csp' : is_csp,     'is_editable': is_editable,}
        self._tb_custom_fields[key] = self._tb_cats[key]
        self._add_search_terms_to_map(key, [key])
        self.custom_label_to_key_map[label] = key
        if datatype == 'series':
            key += '_index'
            self._tb_cats[key] = {'table':None,        'column':None,
                                 'datatype':'float',   'is_multiple':{},
                                 'kind':'field',       'name':'',
                                 'search_terms':[key], 'label':label+'_index',
                                 'colnum':None,        'display':{},
                                 'is_custom':False,    'is_category':False,
                                 'link_column':None,   'category_sort':None,
                                 'is_editable': False, 'is_csp': False}
            self._add_search_terms_to_map(key, [key])
            self.custom_label_to_key_map[label+'_index'] = key

    def remove_dynamic_categories(self):
        for key in list(self._tb_cats.keys()):
            val = self._tb_cats[key]
            if val['is_category'] and val['kind'] in ('user', 'search'):
                for k in self._tb_cats[key]['search_terms']:
                    if k in self._search_term_map:
                        del self._search_term_map[k]
                del self._tb_cats[key]

    def remove_user_categories(self):
        for key in list(self._tb_cats.keys()):
            val = self._tb_cats[key]
            if val['is_category'] and val['kind']  == 'user':
                for k in self._tb_cats[key]['search_terms']:
                    if k in self._search_term_map:
                        del self._search_term_map[k]
                del self._tb_cats[key]

    def _remove_grouped_search_terms(self):
        to_remove = [v for v in self._search_term_map
                        if isinstance(self._search_term_map[v], list)]
        for v in to_remove:
            del self._search_term_map[v]

    def add_grouped_search_terms(self, gst):
        self._remove_grouped_search_terms()
        for t in gst:
            try:
                self._add_search_terms_to_map(gst[t], [t])
            except ValueError:
                traceback.print_exc()

    def cc_series_index_column_for(self, key):
        return self._tb_cats[key]['rec_index'] + 1

    def add_user_category(self, label, name):
        if label in self._tb_cats:
            raise ValueError('Duplicate user field [%s]'%(label))
        st = [label]
        if icu_lower(label) != label:
            st.append(icu_lower(label))
        self._tb_cats[label] = {'table':None,          'column':None,
                                'datatype':None,       'is_multiple':{},
                                'kind':'user',         'name':name,
                                'search_terms':st,     'is_custom':False,
                                'is_category':True,    'is_csp': False}
        self._add_search_terms_to_map(label, st)

    def add_search_category(self, label, name):
        if label in self._tb_cats:
            raise ValueError('Duplicate user field [%s]'%(label))
        self._tb_cats[label] = {'table':None,        'column':None,
                                'datatype':None,     'is_multiple':{},
                                'kind':'search',     'name':name,
                                'search_terms':[],   'is_custom':False,
                                'is_category':True,  'is_csp': False}

    def set_field_record_index(self, label, index, prefer_custom=False):
        if prefer_custom:
            key = self.custom_field_prefix+label
            if key not in self._tb_cats:
                key = label
        else:
            if label in self._tb_cats:
                key = label
            else:
                key = self.custom_field_prefix+label
        self._tb_cats[key]['rec_index'] = index  # let the exception fly ...

    def get_search_terms(self):
        s_keys = sorted(self._search_term_map.keys())
        for v in self.search_items:
            s_keys.append(v)
        return s_keys

    def _add_search_terms_to_map(self, key, terms):
        if terms is not None:
            for t in terms:
                if t in self._search_term_map:
                    raise ValueError('Attempt to add duplicate search term "%s"'%t)
                self._search_term_map[t] = key

    def search_term_to_field_key(self, term):
        return self._search_term_map.get(term, term)

    def searchable_fields(self):
        return [k for k in self._tb_cats.keys()
                if self._tb_cats[k]['kind']=='field' and
                   len(self._tb_cats[k]['search_terms']) > 0]


# The following two methods are to support serialization
# Note that they do not create copies of internal structures, for performance,
# so they are not safe to use for anything else
def fm_as_dict(self):
    return {
        'custom_fields': self._tb_custom_fields,
        'search_term_map': self._search_term_map,
        'custom_label_to_key_map': self.custom_label_to_key_map,
    }


def fm_from_dict(src):
    ans = FieldMetadata()
    ans._tb_custom_fields = src['custom_fields']
    ans._search_term_map = src['search_term_map']
    ans.custom_label_to_key_map = src['custom_label_to_key_map']
    for k, v in ans._tb_custom_fields.iteritems():
        ans._tb_cats[k] = v
    return ans
