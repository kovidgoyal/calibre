#!/usr/bin/env python2
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2015, Kovid Goyal <kovid at kovidgoyal.net>'

import re, itertools
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

# Test that the string is not empty and does not contain whitespace
is_non_whitespace = re.compile(r'^[^ \t\r\n\f]+$').match

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

def normalize_language_tag(tag):
    """Return a list of normalized combinations for a `BCP 47` language tag.

    Example:

    >>> normalize_language_tag('de_AT-1901')
    ['de-at-1901', 'de-at', 'de-1901', 'de']
    """
    # normalize:
    tag = ascii_lower(tag).replace('_','-')
    # split (except singletons, which mark the following tag as non-standard):
    tag = re.sub(r'-([a-zA-Z0-9])-', r'-\1_', tag)
    subtags = [subtag.replace('_', '-') for subtag in tag.split('-')]
    base_tag = (subtags.pop(0),)
    taglist = {base_tag[0]}
    # find all combinations of subtags
    for n in range(len(subtags), 0, -1):
        for tags in itertools.combinations(subtags, n):
            taglist.add('-'.join(base_tag + tags))
    return taglist


class Select(object):

    '''

    This class implements CSS Level 3 selectors on an lxml tree, with caching
    for performance. To use:

    >>> select = Select(root)
    >>> print(tuple(select('p.myclass')))

    Tags are returned in document order. Note that attribute and tag names are
    matched case-insensitively. Also namespaces are ignored (this is for
    performance of the common case).

    WARNING: This class uses internal caches. You *must not* make any changes
    to the lxml tree. If you do make some changes, either create a new Select
    object or call :meth:`invalidate_caches`.

    This class can be easily sub-classes to work with tree implementations
    other than lxml. Simply override the methods in the ``Tree Integration``
    block.

    '''

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
    }

    def __init__(self, root, default_lang=None, dispatch_map=None, trace=False):
        self.root = root
        self.dispatch_map = dispatch_map or default_dispatch_map
        self.invalidate_caches()
        self.default_lang = default_lang
        if trace:
            self.dispatch_map = {k:trace_wrapper(v) for k, v in self.dispatch_map.iteritems()}

    def invalidate_caches(self):
        'Invalidate all caches. You must call this before using this object if you have made changes to the HTML tree'
        self._element_map = None
        self._id_map = None
        self._class_map = None
        self._attrib_map = None
        self._attrib_space_map = None
        self._lang_map = None

    def __call__(self, selector):
        'Return an iterator over all matching tags, in document order.'
        seen = set()
        for selector in get_parsed_selector(selector):
            parsed_selector = selector.parsed_tree
            for item in self.iterparsedselector(parsed_selector):
                if item not in seen:
                    yield item
                    seen.add(item)

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

            for tag in self.itertag():
                em[map_tag_name(tag.tag)].add(tag)
        return self._element_map

    @property
    def id_map(self):
        if self._id_map is None:
            self._id_map = im = defaultdict(OrderedSet)
            lower = ascii_lower
            for elem in self.iteridtags():
                im[lower(elem.get('id'))].add(elem)
        return self._id_map

    @property
    def class_map(self):
        if self._class_map is None:
            self._class_map = cm = defaultdict(OrderedSet)
            lower = ascii_lower
            for elem in self.iterclasstags():
                for cls in elem.get('class').split():
                    cm[lower(cls)].add(elem)
        return self._class_map

    @property
    def attrib_map(self):
        if self._attrib_map is None:
            self._attrib_map = am = defaultdict(lambda : defaultdict(OrderedSet))
            map_attrib_name = ascii_lower
            if '{' in self.root.tag:
                def map_attrib_name(x):
                    return ascii_lower(x.rpartition('}')[2])
            for tag in self.itertag():
                for attr, val in tag.attrib.iteritems():
                    am[map_attrib_name(attr)][val].add(tag)
        return self._attrib_map

    @property
    def attrib_space_map(self):
        if self._attrib_space_map is None:
            self._attrib_space_map = am = defaultdict(lambda : defaultdict(OrderedSet))
            map_attrib_name = ascii_lower
            if '{' in self.root.tag:
                def map_attrib_name(x):
                    return ascii_lower(x.rpartition('}')[2])
            for tag in self.itertag():
                for attr, val in tag.attrib.iteritems():
                    for v in val.split():
                        am[map_attrib_name(attr)][v].add(tag)
        return self._attrib_space_map

    @property
    def lang_map(self):
        if self._lang_map is None:
            self._lang_map = lm = defaultdict(OrderedSet)
            dl = normalize_language_tag(self.default_lang) if self.default_lang else None
            lmap = {tag:dl for tag in self.itertag()} if dl else {}
            for tag in self.itertag():
                lang = None
                for attr in ('{http://www.w3.org/XML/1998/namespace}lang', 'lang'):
                    lang = tag.get(attr)
                if lang:
                    lang = normalize_language_tag(lang)
                    for dtag in self.itertag(tag):
                        lmap[dtag] = lang
            for tag, langs in lmap.iteritems():
                for lang in langs:
                    lm[lang].add(tag)
        return self._lang_map

    # Tree Integration {{{
    def itertag(self, tag=None):
        return (self.root if tag is None else tag).iter('*')

    def iterdescendants(self, tag=None):
        return (self.root if tag is None else tag).iterdescendants('*')

    def iterchildren(self, tag=None):
        return (self.root if tag is None else tag).iterchildren('*')

    def itersiblings(self, tag=None, preceding=False):
        return (self.root if tag is None else tag).itersiblings('*', preceding=preceding)

    def iteridtags(self):
        return get_compiled_xpath('//*[@id]')(self.root)

    def iterclasstags(self):
        return get_compiled_xpath('//*[@class]')(self.root)
    # }}}

# Combinators {{{

def select_combinedselector(cache, combined):
    """Translate a combined selector."""
    combinator = cache.combinator_mapping[combined.combinator]
    # Fast path for when the sub-selector is all elements
    right = None if isinstance(combined.subselector, Element) and (
        combined.subselector.element or '*') == '*' else cache.iterparsedselector(combined.subselector)
    for item in cache.dispatch_map[combinator](cache, cache.iterparsedselector(combined.selector), right):
        yield item

def select_descendant(cache, left, right):
    """right is a child, grand-child or further descendant of left"""
    right = always_in if right is None else frozenset(right)
    for ancestor in left:
        for descendant in cache.iterdescendants(ancestor):
            if descendant in right:
                yield descendant

def select_child(cache, left, right):
    """right is an immediate child of left"""
    right = always_in if right is None else frozenset(right)
    for parent in left:
        for child in cache.iterchildren(parent):
            if child in right:
                yield child

def select_direct_adjacent(cache, left, right):
    """right is a sibling immediately after left"""
    right = always_in if right is None else frozenset(right)
    for parent in left:
        for sibling in cache.itersiblings(parent):
            if sibling in right:
                yield sibling
            break

def select_indirect_adjacent(cache, left, right):
    """right is a sibling after left, immediately or not"""
    right = always_in if right is None else frozenset(right)
    for parent in left:
        for sibling in cache.itersiblings(parent):
            if sibling in right:
                yield sibling
# }}}

def select_element(cache, selector):
    """A type or universal selector."""
    element = selector.element
    if not element or element == '*':
        for elem in cache.itertag():
            yield elem
    else:
        for elem in cache.element_map[ascii_lower(element)]:
            yield elem

def select_hash(cache, selector):
    'An id selector'
    items = cache.id_map[ascii_lower(selector.id)]
    if len(items) > 0:
        for elem in cache.iterparsedselector(selector.selector):
            if elem in items:
                yield elem

def select_class(cache, selector):
    'A class selector'
    items = cache.class_map[ascii_lower(selector.class_name)]
    if items:
        for elem in cache.iterparsedselector(selector.selector):
            if elem in items:
                yield elem

# Attribute selectors {{{

def select_attrib(cache, selector):
    operator = cache.attribute_operator_mapping[selector.operator]
    items = frozenset(cache.dispatch_map[operator](cache, ascii_lower(selector.attrib), selector.value))
    for item in cache.iterparsedselector(selector.selector):
        if item in items:
            yield item

def select_exists(cache, attrib, value=None):
    for elem_set in cache.attrib_map[attrib].itervalues():
        for elem in elem_set:
            yield elem

def select_equals(cache, attrib, value):
    for elem in cache.attrib_map[attrib][value]:
        yield elem

def select_includes(cache, attrib, value):
    if is_non_whitespace(value):
        for elem in cache.attrib_space_map[attrib][value]:
            yield elem

def select_dashmatch(cache, attrib, value):
    if value:
        for val, elem_set in cache.attrib_map[attrib].iteritems():
            if val == value or val.startswith(value + '-'):
                for elem in elem_set:
                    yield elem

def select_prefixmatch(cache, attrib, value):
    if value:
        for val, elem_set in cache.attrib_map[attrib].iteritems():
            if val.startswith(value):
                for elem in elem_set:
                    yield elem

def select_suffixmatch(cache, attrib, value):
    if value:
        for val, elem_set in cache.attrib_map[attrib].iteritems():
            if val.endswith(value):
                for elem in elem_set:
                    yield elem

def select_substringmatch(cache, attrib, value):
    if value:
        for val, elem_set in cache.attrib_map[attrib].iteritems():
            if value in val:
                for elem in elem_set:
                    yield elem

# }}}

# Function selectors {{{

def select_function(cache, function):
    """Select with a functional pseudo-class."""
    try:
        func = cache.dispatch_map[function.name.replace('-', '_')]
    except KeyError:
        raise ExpressionError(
            "The pseudo-class :%s() is unknown" % function.name)
    items = frozenset(func(cache, function))
    for item in cache.iterparsedselector(function.selector):
        if item in items:
            yield item

def select_lang(cache, function):
    if function.argument_types() not in (['STRING'], ['IDENT']):
        raise ExpressionError("Expected a single string or ident for :lang(), got %r" % function.arguments)
    lang = function.arguments[0].value
    if lang:
        lang = ascii_lower(lang)
        lp = lang + '-'
        for tlang, elem_set in cache.lang_map.iteritems():
            if tlang == lang or (tlang is not None and tlang.startswith(lp)):
                for elem in elem_set:
                    yield elem

# }}}

default_dispatch_map = {name.partition('_')[2]:obj for name, obj in globals().items() if name.startswith('select_') and callable(obj)}

if __name__ == '__main__':
    from pprint import pprint
    root = etree.fromstring('<body xmlns="xxx" xml:lang="en"><p id="p" class="one two" lang="fr"><a id="a"/></p></body>')
    select = Select(root, trace=True)
    pprint(list(select('p a')))
