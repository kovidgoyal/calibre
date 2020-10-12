#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2017, Kovid Goyal <kovid at kovidgoyal.net>


from polyglot.builtins import iteritems
from polyglot.urllib import quote, quote_plus

AUTHOR_SEARCHES = {
    'goodreads':
    'https://www.goodreads.com/book/author/{author}',
    'wikipedia':
    'https://en.wikipedia.org/w/index.php?search={author}',
    'google':
    'https://www.google.com/search?tbm=bks&q=inauthor:%22{author}%22',
    'amzn':
    'https://www.amazon.com/gp/search/ref=sr_adv_b/?search-alias=stripbooks&unfiltered=1&field-author={author}&sort=relevanceexprank'
}

BOOK_SEARCHES = {
    'goodreads':
    'https://www.goodreads.com/search?q={author}+{title}&search%5Bsource%5D=goodreads&search_type=books&tab=books',
    'google':
    'https://www.google.com/search?tbm=bks&q=inauthor:%22{author}%22+intitle:%22{title}%22',
    'gws':
    'https://www.google.com/search?q=inauthor:%22{author}%22+intitle:%22{title}%22',
    'amzn':
    'https://www.amazon.com/s/ref=nb_sb_noss?url=search-alias%3Dstripbooks&field-keywords={author}+{title}',
    'gimg':
    'https://www.google.com/images?q=%22{author}%22+%22{title}%22',
}

NAMES = {
    'goodreads': _('Goodreads'),
    'google': _('Google books'),
    'wikipedia': _('Wikipedia'),
    'gws': _('Google web search'),
    'amzn': _('Amazon'),
    'gimg': _('Google images'),
}

DEFAULT_AUTHOR_SOURCE = 'goodreads'
assert DEFAULT_AUTHOR_SOURCE in AUTHOR_SEARCHES

name_for = NAMES.get
all_book_searches = BOOK_SEARCHES.__iter__
all_author_searches = AUTHOR_SEARCHES.__iter__


def qquote(val, use_plus=True):
    if not isinstance(val, bytes):
        val = val.encode('utf-8')
    ans = quote_plus(val) if use_plus else quote(val)
    if isinstance(ans, bytes):
        ans = ans.decode('utf-8')
    return ans


def specialised_quote(template, val):
    return qquote(val, 'goodreads.com' not in template)


def url_for(template, data):
    return template.format(**{k: specialised_quote(template, v) for k, v in iteritems(data)})


def url_for_author_search(key, **kw):
    return url_for(AUTHOR_SEARCHES[key], kw)


def url_for_book_search(key, **kw):
    return url_for(BOOK_SEARCHES[key], kw)
