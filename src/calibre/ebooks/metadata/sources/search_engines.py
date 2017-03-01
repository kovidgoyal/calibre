#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2017, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import absolute_import, division, print_function, unicode_literals

import time
from collections import defaultdict, namedtuple
from future_builtins import map
from urllib import quote_plus, urlencode
from urlparse import parse_qs

from lxml import etree

import html5lib
from calibre import browser, prints
from calibre.utils.monotonic import monotonic

current_version = (1, 0, 0)
minimum_calibre_version = (2, 80, 0)


last_visited = defaultdict(lambda: 0)
Result = namedtuple('Result', 'url text cached_url')


def encode_query(**query):
    q = {k.encode('utf-8'): v.encode('utf-8') for k, v in query.iteritems()}
    return urlencode(q).decode('utf-8')


def parse(raw):
    return html5lib.parse(raw, treebuilder='lxml', namespaceHTMLElements=False)


def query(br, url, key, dump_raw=None):
    delta = monotonic() - last_visited[key]
    if delta < 1 and delta > 0:
        time.sleep(delta)
    try:
        raw = br.open_novisit(url).read()
    finally:
        last_visited[key] = monotonic()
    if dump_raw is not None:
        with open(dump_raw, 'wb') as f:
            f.write(raw)
    return parse(raw)


def quote_term(x):
    return quote_plus(x.encode('utf-8')).decode('utf-8')


def ddg_term(t):
    t = t.replace('"', '')
    if t.lower() in {'map', 'news'}:
        t = '"' + t + '"'
    if t in {'OR', 'AND'}:
        t = t.lower()
    return t


def ddg_href(url):
    if url.startswith('/'):
        q = url.partition('?')[2]
        url = parse_qs(q.encode('utf-8'))['uddg'][0].decode('utf-8')
    return url


def ddg_search(terms, site=None, br=None, log=prints, safe_search=False, dump_raw=None):
    # https://duck.co/help/results/syntax
    terms = map(ddg_term, terms)
    terms = [quote_term(t) for t in terms]
    if site is not None:
        terms.append(quote_term(('site:' + site)))
    q = '+'.join(terms)
    url = 'https://duckduckgo.com/html/?q={q}&kp={kp}'.format(q=q, kp=1 if safe_search else -1)
    log('Making ddg query: ' + url)
    br = br or browser()
    root = query(br, url, 'ddg', dump_raw)
    ans = []
    for a in root.xpath('//*[@class="results"]//*[@class="result__title"]/a[@href and @class="result__a"]'):
        ans.append(Result(ddg_href(a.get('href')), etree.tostring(a, encoding=unicode, method='text', with_tail=False), None))
    return ans


def ddg_develop():
    from pprint import pprint
    pprint(ddg_search('heroes abercrombie'.split(), 'amazon.com', dump_raw='/t/raw.html'))
