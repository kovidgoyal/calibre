#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2017, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import absolute_import, division, print_function, unicode_literals

from urllib import quote_plus

AUTHOR_SEARCHES = {
    'goodreads':
    'https://www.goodreads.com/search?q={author}&search%5Bfield%5D=author&search%5Bsource%5D=goodreads&search_type=people&tab=people',
    'wikipedia':
    'https://en.wikipedia.org/w/index.php?search={author}',
    'google':
    'https://www.google.com/search?tbm=bks&q=inauthor:%22{author}%22',
}

BOOK_SEARCHES = {
    'goodreads':
    'https://www.goodreads.com/search?q={author}+{title}&search%5Bsource%5D=goodreads&search_type=books&tab=books',
    'google':
    'https://www.google.com/search?tbm=bks&q=inauthor:%22{author}%22+intitle:%22{title}%22',
    'gws':
    'https://www.google.com/search?q=inauthor:%22{author}%22+intitle:%22{title}%22',
    'amzn':
    'http://www.amazon.com/s/ref=nb_sb_noss?url=search-alias%3Dstripbooks&field-keywords={author}+{title}',
    'gimg':
    'http://www.google.com/images?q=%22{author}%22+%22{title}%22',
}

NAMES = {
    'goodreads': _('Goodreads'),
    'google': _('Google books'),
    'wikipedia': _('Wikipedia'),
    'gws': _('Google web search'),
    'amzn': _('Amazon'),
    'gimg': _('Google images'),
}

name_for = NAMES.get


def qquote(val):
    if not isinstance(val, bytes):
        val = val.encode('utf-8')
    return quote_plus(val).decode('utf-8')


def url_for(template, data):
    return template.format(**{k: qquote(v) for k, v in data.iteritems()})


def url_for_author_search(key, **kw):
    return url_for(AUTHOR_SEARCHES[key], kw)


def url_for_book_search(key, **kw):
    return url_for(BOOK_SEARCHES[key], kw)
