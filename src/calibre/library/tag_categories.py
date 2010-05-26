'''
Created on 25 May 2010

@author: charles
'''

from UserDict import DictMixin
from calibre.utils.ordered_dict import OrderedDict

class TagsIcons(dict):
    '''
    If the client wants icons to be in the tag structure, this class must be
    instantiated and filled in with real icons. If this class is instantiated
    and passed to get_categories, All items must be given a value not None
    '''

    category_icons = ['authors', 'series', 'formats', 'publisher', 'rating',
                      'news',    'tags',   ':custom', ':user',     'search',]
    def __init__(self, icon_dict):
        for a in self.category_icons:
            if a not in icon_dict:
                raise ValueError('Missing category icon [%s]'%a)
            self[a] = icon_dict[a]

class TagsMetadata(dict, DictMixin):

    # kind == standard: is tag category. May be a search label. Is db col
    #                   or is specially handled (e.g., news)
    # kind == not_cat: Is not a tag category. Should be a search label. Is db col
    # kind == user: user-defined tag category
    # kind == search: saved-searches category
    # Order as has been customary in the tags pane.
    category_items_ = [
            ('authors',   {'table':'authors', 'column':'name',
                           'datatype':'text', 'is_multiple':False,
                           'kind':'standard', 'name':_('Authors'),
                           'search_labels':['authors', 'author']}),
            ('series',    {'table':'series', 'column':'name',
                           'datatype':None, 'is_multiple':False,
                           'kind':'standard', 'name':_('Series'),
                           'search_labels':['series']}),
            ('formats',   {'table':None, 'column':None,
                           'datatype':None, 'is_multiple':False,
                           'kind':'standard', 'name':_('Formats'),
                           'search_labels':['formats', 'format']}),
            ('publisher', {'table':'publishers', 'column':'name',
                           'datatype':'text', 'is_multiple':False,
                           'kind':'standard', 'name':_('Publishers'),
                           'search_labels':['publisher']}),
            ('rating',    {'table':'ratings', 'column':'rating',
                           'datatype':'rating', 'is_multiple':False,
                           'kind':'standard', 'name':_('Ratings'),
                           'search_labels':['rating']}),
            ('news',      {'table':'news', 'column':'name',
                           'datatype':None, 'is_multiple':False,
                           'kind':'standard', 'name':_('News'),
                           'search_labels':[]}),
            ('tags',      {'table':'tags', 'column':'name',
                           'datatype':'text', 'is_multiple':True,
                           'kind':'standard', 'name':_('Tags'),
                           'search_labels':['tags', 'tag']}),
            ('comments',  {'table':None, 'column':None,
                           'datatype':None, 'is_multiple':False,
                           'kind':'not_cat', 'name':None,
                           'search_labels':['comments', 'comment']}),
            ('cover',     {'table':None, 'column':None,
                           'datatype':None, 'is_multiple':False,
                           'kind':'not_cat', 'name':None,
                           'search_labels':['cover']}),
            ('isbn',      {'table':None, 'column':None,
                           'datatype':None, 'is_multiple':False,
                           'kind':'not_cat', 'name':None,
                           'search_labels':['isbn']}),
            ('pubdate',   {'table':None, 'column':None,
                           'datatype':None, 'is_multiple':False,
                           'kind':'not_cat', 'name':None,
                           'search_labels':['pubdate']}),
            ('title',     {'table':None, 'column':None,
                           'datatype':None, 'is_multiple':False,
                           'kind':'not_cat', 'name':None,
                           'search_labels':['title']}),
            ]

    # search labels that are not db columns
    search_items = [    'all',
                        'date',
                        'search',
                    ]

    def __init__(self):
        self.tb_cats_ = OrderedDict()
        for k,v in self.category_items_:
            self.tb_cats_[k] = v

    def __getattr__(self, name):
        if name in self.tb_cats_:
            return self.tb_cats_[name]
        return None

#    def __setattr__(self, name, val):
#        dict.__setattr__(self, name, val)

    def __getitem__(self, key):
        return self.tb_cats_[key]

#    def __setitem__(self, key, val):
#        print 'setitem', key, val
#        self.tb_cats_[key] = val

    def __delitem__(self, key):
        del self.tb_cats_[key]

    def __iter__(self):
        for key in self.tb_cats_:
            yield key

    def keys(self):
        return self.tb_cats_.keys()

    def iterkeys(self):
        for key in self.tb_cats_:
            yield key

    def iteritems(self):
        for key in self.tb_cats_:
            yield (key, self.tb_cats_[key])

    def get_label(self, key):
        if 'label' not in self.tb_cats_[key]:
            return key
        return self.tb_cats_[key]['label']

    def get_custom_fields(self):
        return [l for l in self.tb_cats_ if self.tb_cats_[l]['kind'] == 'custom']

    def add_custom_field(self, field_name, table, column, datatype, is_multiple, number, name):
        fn = '#' + field_name
        if fn in self.tb_cats_:
            raise ValueError('Duplicate custom field [%s]'%(field_name))
        self.tb_cats_[fn] = {'table':table,       'column':column,
                             'datatype':datatype, 'is_multiple':is_multiple,
                             'kind':'custom',     'name':name,
                             'search_labels':[fn],'label':field_name,
                             'colnum':number}

    def add_user_category(self, field_name, name):
        if field_name in self.tb_cats_:
            raise ValueError('Duplicate user field [%s]'%(field_name))
        self.tb_cats_[field_name] = {'table':None,        'column':None,
                                     'datatype':None,     'is_multiple':False,
                                     'kind':'user',       'name':name,
                                     'search_labels':[]}

    def add_search_category(self, field_name, name):
        if field_name in self.tb_cats_:
            raise ValueError('Duplicate user field [%s]'%(field_name))
        self.tb_cats_[field_name] = {'table':None,        'column':None,
                                     'datatype':None,     'is_multiple':False,
                                     'kind':'search',     'name':name,
                                     'search_labels':[]}

#    DEFAULT_LOCATIONS = frozenset([
#        'all',
#        'author',       # compatibility
#        'authors',
#        'comment',      # compatibility
#        'comments',
#        'cover',
#        'date',
#        'format',       # compatibility
#        'formats',
#        'isbn',
#        'ondevice',
#        'pubdate',
#        'publisher',
#        'search',
#        'series',
#        'rating',
#        'tag',          # compatibility
#        'tags',
#        'title',
#                 ])


    def get_search_labels(self):
        s_labels = []
        for v in self.tb_cats_.itervalues():
            map((lambda x:s_labels.append(x)), v['search_labels'])
        for v in self.search_items:
            s_labels.append(v)
#        if set(s_labels) != self.DEFAULT_LOCATIONS:
#            print 'search labels and default_locations do not match:'
#            print set(s_labels) ^ self.DEFAULT_LOCATIONS
        return s_labels
