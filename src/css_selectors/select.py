#!/usr/bin/env python2
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2015, Kovid Goyal <kovid at kovidgoyal.net>'

from collections import OrderedDict, defaultdict
from functools import wraps

from lxml import etree

from css_selectors.errors import ExpressionError
from css_selectors.parse import parse, ascii_lower, Element
from css_selectors.ordered_set import OrderedSet

PARSE_CACHE_SIZE = 200
parse_cache = OrderedDict()
XPATH_CACHE_SIZE = 30
xpath_cache = OrderedDict()

def get_parsed_selector(raw):
    try:
        return parse_cache[raw]
    except KeyError:
        parse_cache[raw] = ans = parse(raw)
        if len(parse_cache) > PARSE_CACHE_SIZE:
            parse_cache.pop(next(iter(parse_cache)))
        return ans

def get_compiled_xpath(expr):
    try:
        return xpath_cache[expr]
    except KeyError:
        xpath_cache[expr] = ans = etree.XPath(expr)
        if len(xpath_cache) > XPATH_CACHE_SIZE:
            xpath_cache.pop(next(iter(xpath_cache)))
        return ans

class AlwaysIn(object):

    def __contains__(self, x):
        return True
always_in = AlwaysIn()

def trace_wrapper(func):
    @wraps(func)
    def trace(*args, **kwargs):
        targs = args[1:] if args and isinstance(args[0], Select) else args
        print ('Called:', func.__name__, 'with args:', targs, kwargs or '')
        return func(*args, **kwargs)
    return trace

class Select(object):

    combinator_mapping = {
        ' ': 'descendant',
        '>': 'child',
        '+': 'direct_adjacent',
        '~': 'indirect_adjacent',
    }

    attribute_operator_mapping = {
        'exists': 'exists',
        '=': 'equals',
        '~=': 'includes',
        '|=': 'dashmatch',
        '^=': 'prefixmatch',
        '$=': 'suffixmatch',
        '*=': 'substringmatch',
        '!=': 'different',  # Not in Level 3 but I like it ;)
    }

    def __init__(self, root, dispatch_map=None, trace=False):
        self.root = root
        self.dispatch_map = dispatch_map or default_dispatch_map
        self.invalidate_caches()
        if trace:
            self.dispatch_map = {k:trace_wrapper(v) for k, v in self.dispatch_map.iteritems()}

    def invalidate_caches(self):
        self._element_map = None
        self._id_map = None
        self._class_map = None

    def __call__(self, selector):
        for selector in get_parsed_selector(selector):
            parsed_selector = selector.parsed_tree
            for item in self.iterparsedselector(parsed_selector):
                yield item

    def iterparsedselector(self, parsed_selector):
        type_name = type(parsed_selector).__name__
        try:
            func = self.dispatch_map[ascii_lower(type_name)]
        except KeyError:
            raise ExpressionError('%s is not supported' % type_name)
        for item in func(self, parsed_selector):
            yield item

    @property
    def element_map(self):
        if self._element_map is None:
            self._element_map = em = defaultdict(OrderedSet)
            map_tag_name = ascii_lower
            if '{' in self.root.tag:
                def map_tag_name(x):
                    return ascii_lower(x.rpartition('}')[2])

            for tag in root.iter('*'):
                em[map_tag_name(tag.tag)].add(tag)
        return self._element_map

    @property
    def id_map(self):
        if self._id_map is None:
            self._id_map = im = defaultdict(OrderedSet)
            lower = ascii_lower
            for elem in get_compiled_xpath('//*[@id]')(self.root):
                im[lower(elem.get('id'))].add(elem)
        return self._id_map

    @property
    def class_map(self):
        if self._class_map is None:
            self._class_map = cm = defaultdict(OrderedSet)
            lower = ascii_lower
            for elem in get_compiled_xpath('//*[@class]')(self.root):
                for cls in elem.get('class').split():
                    cm[lower(cls)].add(elem)
        return self._class_map

# Combinators {{{

def select_combinedselector(cache, combined):
    """Translate a combined selector."""
    combinator = cache.combinator_mapping[combined.combinator]
    # Fast path for when the sub-selector is all elements
    right = None if isinstance(combined.subselector, Element) and (
        combined.subselector.element or '*') == '*' else cache.iterparsedselector(combined.subselector)
    for item in cache.dispatch_map[combinator](cache.iterparsedselector(combined.selector), right):
        yield item

def select_descendant(left, right):
    """right is a child, grand-child or further descendant of left"""
    right = always_in if right is None else frozenset(right)
    for ancestor in left:
        for descendant in ancestor.iterdescendants('*'):
            if descendant in right:
                yield descendant

def select_child(left, right):
    """right is an immediate child of left"""
    right = always_in if right is None else frozenset(right)
    for parent in left:
        for child in parent.iterchildren('*'):
            if child in right:
                yield child

def select_direct_adjacent(left, right):
    """right is a sibling immediately after left"""
    right = always_in if right is None else frozenset(right)
    for parent in left:
        for sibling in parent.itersiblings('*'):
            if sibling in right:
                yield sibling
            break

def select_indirect_adjacent(left, right):
    """right is a sibling after left, immediately or not"""
    right = always_in if right is None else frozenset(right)
    for parent in left:
        for sibling in parent.itersiblings('*'):
            if sibling in right:
                yield sibling
# }}}

def select_element(cache, selector):
    """A type or universal selector."""
    element = selector.element
    if not element or element == '*':
        for elem in cache.root.iter('*'):
            yield elem
    else:
        for elem in cache.element_map[ascii_lower(element)]:
            yield elem

def select_hash(cache, selector):
    'An id selector'
    items = cache.id_map[ascii_lower(selector.id)]
    if len(items) > 1:
        for elem in cache.iterparsedselector(selector.selector):
            if elem in items:
                yield elem
    elif items:
        yield items[0]

def select_class(cache, selector):
    'A class selector'
    items = cache.class_map[ascii_lower(selector.class_name)]
    if items:
        for elem in cache.iterparsedselector(selector.selector):
            if elem in items:
                yield elem

default_dispatch_map = {name.partition('_')[2]:obj for name, obj in globals().items() if name.startswith('select_') and callable(obj)}

if __name__ == '__main__':
    from pprint import pprint
    root = etree.fromstring('<body xmlns="xxx"><p id="p" class="one two"><a id="a"/></p></body>')
    select = Select(root, trace=True)
    pprint(list(select('p#p.one.two')))
